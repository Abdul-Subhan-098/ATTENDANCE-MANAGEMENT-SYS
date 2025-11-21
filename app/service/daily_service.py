from datetime import datetime, timedelta, time, date
from typing import Dict, List, Tuple, Optional, Any
from sqlalchemy import inspect, text
from app import db
from app.models import DailyReport, Employee
import pandas as pd
import logging

# Configure logging
logger = logging.getLogger(__name__)

# ===========================================================
#              CONSTANTS AND CONFIGURATION
# ===========================================================
class AttendanceStatus:
    """Constants for attendance status values."""
    ABSENT = "Absent"
    PRESENT = "Present"
    LATE = "Late"
    HALF_DAY = "Half Day"
    SUNDAY = "Sunday"
    COMPENSATED = "Compensated"
    FULL_DAY_SAT = "Full Day (Sat)"
    HALF_DAY_SAT = "Half Day (Sat)"
    SATURDAY = "Saturday" 

class ShiftDefaults:
    """Default shift configuration."""
    DEFAULT_SHIFT_START = "10:00"
    DEFAULT_SHIFT_END = "19:00"
    DEFAULT_SHIFT_STR = "10:00 - 19:00"

class OvertimeConfig:
    """Overtime calculation configuration."""
    MAX_OT_HOURS = 2.0
    OT_THRESHOLD_1_HOUR = 1.0   
    OT_THRESHOLD_2_HOURS = 2.0

class AttendanceThresholds:
    """Attendance calculation thresholds."""
    FULL_TIMER_MIN_HOURS = 9.0
    SAT_HALF_DAY_MIN_HOURS = 4.5  
    GRACE_PERIOD_SECONDS = 59  
    LATE_THRESHOLD_HOURS = 1
    EARLY_CHECKOUT_MINUTES = 15


# ===========================================================
#              ATTENDANCE DATA PROCESSOR
# ===========================================================
class AttendanceProcessor:
    """Clean and prepare raw attendance data."""

    @staticmethod
    def get_clean_attendance() -> pd.DataFrame:
        """Fetch and clean attendance_raw data."""
        try:
            inspector = inspect(db.engine)
            if "attendance_raw" not in inspector.get_table_names():
                logger.warning("attendance_raw table not found")
                return pd.DataFrame()

            df = pd.read_sql(text("SELECT * FROM attendance_raw"), db.engine)
            return AttendanceProcessor._process_attendance_data(df)

        except Exception as e:
            logger.error(f"Error cleaning attendance data: {e}")
            return pd.DataFrame()

    @staticmethod
    def _process_attendance_data(df: pd.DataFrame) -> pd.DataFrame:
        """Process and clean raw attendance data."""
        if df.empty:
            return pd.DataFrame()

        # Normalize Name
        df["Name"] = (
            df["Name"].astype(str)
            .str.replace(".", " ", regex=False)
            .str.replace(r"\s+", " ", regex=True)
            .str.strip()
        )
        
        # Convert and clean time data
        df["Time"] = pd.to_datetime(df["Time"], errors="coerce")
        df = df.dropna(subset=["Time"])
        df["Date"] = df["Time"].dt.date

        # Normalize Attendance State
        df["Attendance State"] = pd.to_numeric(df.get("Attendance State", 0), errors="coerce")
        df["Attendance State"] = df["Attendance State"].apply(
            lambda x: int(x) if not pd.isna(x) else -1
        )

        return AttendanceProcessor._group_attendance_records(df)

    @staticmethod
    def _group_attendance_records(df: pd.DataFrame) -> pd.DataFrame:
        """Group attendance records per employee/day."""
        rows = []
        
        for (emp_id, name, date), group in df.groupby(["Emp ID", "Name", "Date"], dropna=False):
            checkins = group[group["Attendance State"] == 0]
            checkouts = group[group["Attendance State"] == 1]

            first_in = checkins["Time"].min() if not checkins.empty else None
            last_out = checkouts["Time"].max() if not checkouts.empty else None

            if first_in or last_out:
                rows.append({
                    "Emp ID": emp_id,
                    "Name": name,
                    "Date": date,
                    "CheckIn": first_in,
                    "CheckOut": last_out
                })
                
        return pd.DataFrame(rows)


# ===========================================================
#              ATTENDANCE CALCULATOR
# ===========================================================
class AttendanceCalculator:
    """Calculate attendance status, overtime, missed punches with exact-second rules."""

    @staticmethod
    def calculate_status(
        check_in: Optional[datetime],
        check_out: Optional[datetime],
        day: date,
        shift_start: time,
        shift_end: time,
        full_time: bool = True
    ) -> Tuple[str, float]:
        """
        Returns (status_string, overtime_hours).
        Status strings:
         - Present, Late, Half Day, Absent, Saturday, Full Day (Sat), Half Day (Sat)
        """
        shift_start_dt = datetime.combine(day, shift_start)
        shift_end_dt = datetime.combine(day, shift_end)
        shift_duration_hours = (shift_end_dt - shift_start_dt).total_seconds() / 3600.0

        # Default
        status = AttendanceStatus.ABSENT
        overtime = 0.0

        # ---------- Cases: both punches missing ----------
        if (not check_in) and (not check_out):
            # Special rule: if it's Saturday and employee is full_time, mark "Saturday"
            if day.weekday() == 5 and full_time:
                return AttendanceStatus.SATURDAY, 0.0
            return AttendanceStatus.ABSENT, 0.0

        # ---------- Single missing punch => Half Day ----------
        if (not check_in) and check_out:
            return AttendanceStatus.HALF_DAY, 0.0
        if check_in and (not check_out):
            return AttendanceStatus.HALF_DAY, 0.0

        # At this point we have both check_in and check_out
        check_in = check_in.replace(microsecond=0)
        check_out = check_out.replace(microsecond=0)

        # ---------- Saturday logic ----------
        if day.weekday() == 5:  # Saturday
            if full_time:
                # full-time Saturday special rules
                worked_hours = max(0.0, (check_out - check_in).total_seconds() / 3600.0)
                if worked_hours >= AttendanceThresholds.FULL_TIMER_MIN_HOURS:
                    return AttendanceStatus.FULL_DAY_SAT, 0.0
                elif worked_hours >= AttendanceThresholds.SAT_HALF_DAY_MIN_HOURS:
                    return AttendanceStatus.HALF_DAY_SAT, 0.0
                else:
                    return AttendanceStatus.ABSENT, 0.0
            else:
                # part-timer: treat Saturday like a normal weekday (no OT)
                pass

        # ---------- Check-in time windows (exact second rules) ----------
        # Present if check-in <= shift_start + 59 seconds
        present_limit = shift_start_dt + timedelta(seconds=AttendanceThresholds.GRACE_PERIOD_SECONDS)
        # Late if check-in <= shift_start + 1 hour + 59 seconds (i.e., up to HH:00:59)
        late_limit = shift_start_dt + timedelta(hours=AttendanceThresholds.LATE_THRESHOLD_HOURS, 
                                              seconds=AttendanceThresholds.GRACE_PERIOD_SECONDS)

        if check_in <= present_limit:
            status = AttendanceStatus.PRESENT
        elif check_in <= late_limit:
            status = AttendanceStatus.LATE
        else:
            status = AttendanceStatus.HALF_DAY

        # ---------- Early checkout reduces status ----------
        early_checkout_limit = shift_end_dt - timedelta(minutes=AttendanceThresholds.EARLY_CHECKOUT_MINUTES)
        # if checkout is strictly before early_checkout_limit => Half Day
        if check_out < early_checkout_limit:
            status = AttendanceStatus.HALF_DAY

        # ---------- Overtime only for full-time ----------
        if full_time:
            overtime = AttendanceCalculator._calculate_overtime_hours(check_out, shift_end_dt)
        else:
            overtime = 0.0

        return status, overtime

    @staticmethod
    def _calculate_overtime_hours(check_out: datetime, shift_end_dt: datetime) -> float:
        """Calculate overtime hours based on check-out time."""
        ot_seconds = (check_out - shift_end_dt).total_seconds()
        if ot_seconds <= 0:
            return 0.0
            
        ot_hours = ot_seconds / 3600.0
        if ot_hours < OvertimeConfig.OT_THRESHOLD_1_HOUR:
            return 0.0
        elif ot_hours < OvertimeConfig.OT_THRESHOLD_2_HOURS:
            return 1.0
        else:
            return OvertimeConfig.MAX_OT_HOURS

    @staticmethod
    def determine_missed_punches(
        check_in: Optional[datetime],
        check_out: Optional[datetime]
    ) -> Tuple[str, str]:
        """Return ("Yes"/"") for MissedCheckIn and MissedCheckOut."""
        missed_in = "Yes" if not check_in else ""
        missed_out = "Yes" if not check_out else ""
        return missed_in, missed_out

    @staticmethod
    def calculate_overtime(
        check_in: Optional[datetime],
        check_out: Optional[datetime],
        shift_start_dt: datetime,
        shift_end_dt: datetime
    ) -> float:
        """Calculate overtime hours (public method)."""
        if not check_in or not check_out:
            return 0.0
        return AttendanceCalculator._calculate_overtime_hours(check_out, shift_end_dt)


# ===========================================================
#              DAILY REPORT GENERATOR
# ===========================================================
class DailyReportGenerator:
    """Generate and store Daily Reports with the corrected rules."""

    def __init__(self):
        self.processor = AttendanceProcessor()
        self.calculator = AttendanceCalculator()

    def update_shift_for_existing_records(self, employee_name: str, date_str: str, new_shift: str):
        """Update shift for an existing DailyReport record and recalculate status & overtime."""
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
            record = DailyReport.query.filter_by(employee_name=employee_name, date=date_obj).first()

            if not record:
                logger.warning(f"No existing record found for {employee_name} on {date_str}")
                return

            shift_start, shift_end = self._parse_shift(new_shift)

            check_in_dt = datetime.combine(date_obj, record.check_in) if record.check_in else None
            check_out_dt = datetime.combine(date_obj, record.check_out) if record.check_out else None

            # Get employee full-time status
            employee_obj = Employee.query.filter_by(name=employee_name).first()
            full_time = self._is_full_time_employee(employee_obj, shift_start, shift_end)

            status, overtime = self.calculator.calculate_status(
                check_in_dt, check_out_dt, date_obj, shift_start, shift_end, full_time
            )

            record.shift = new_shift
            record.status = status
            record.overtime = overtime
            record.manual_override = True

            db.session.commit()
            logger.info(f"Shift, status, and overtime updated for {employee_name} on {date_str}")

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error updating shift for {employee_name} on {date_str}: {e}")

    def generate_daily_report(self, employee_shifts: Optional[Dict[str, str]] = None,
                              compensated_dates: Optional[Dict[str, set]] = None) -> Dict[str, Any]:
        """Generate daily attendance report."""
        employee_shifts = employee_shifts or {}
        compensated_dates = compensated_dates or {}

        inspector = inspect(db.engine)
        if "attendance_raw" not in inspector.get_table_names():
            return {
                "error": "No attendance data found. Please upload attendance file first.",
                "daily_table": []
            }

        df = self.processor.get_clean_attendance()
        if df.empty:
            return {"error": "No valid attendance records found.", "daily_table": []}

        daily_table = self._generate_report_data(df, employee_shifts, compensated_dates)
        return self._save_and_return_results(daily_table, df)

    def _generate_report_data(self, df: pd.DataFrame, employee_shifts: Dict, compensated_dates: Dict) -> List[Dict[str, Any]]:
        """Generate report data for all employees and dates."""
        employees = sorted(df["Name"].unique())
        all_dates = self._get_all_dates(df)
        
        # Pre-fetch employee data to avoid N+1 queries
        employees_data = self._get_employees_data(employees)
        
        records = []

        for emp in employees:
            emp_records = self._generate_employee_records(
                emp, df, all_dates, employees_data, compensated_dates
            )
            records.extend(emp_records)

        records.sort(key=lambda x: (x["Name"], x["Date"]))
        return records

    def _generate_employee_records(
        self,
        employee_name: str,
        df: pd.DataFrame,
        all_dates: List[date],
        employees_data: Dict,
        compensated_dates: Dict
    ) -> List[Dict[str, Any]]:
        """Generate records for a single employee."""
        emp_data = df[df["Name"] == employee_name]
        emp_id = str(emp_data["Emp ID"].iloc[0]) if not emp_data["Emp ID"].isna().all() else ""

        # Get employee configuration
        employee_obj = employees_data.get(employee_name)
        shift_start_str, shift_end_str = self._get_employee_shift(employee_obj, employee_name)
        department = getattr(employee_obj, 'department', 'Cold Calling')
        joining_date = getattr(employee_obj, 'joining_date', None)
        last_updated_date = getattr(employee_obj, 'last_updated_date', datetime.utcnow().date())

        shift_start, shift_end = self._parse_shift(f"{shift_start_str} - {shift_end_str}")
        full_time = self._is_full_time_employee(employee_obj, shift_start, shift_end)
        
        records = []

        for day in all_dates:
            record = self._create_daily_record(
                employee_name, emp_id, emp_data, day, shift_start, shift_end,
                shift_start_str, shift_end_str, department, joining_date,
                last_updated_date, compensated_dates, full_time
            )
            records.append(record)

        return records

    def _create_daily_record(
        self,
        employee_name: str,
        emp_id: str,
        emp_data: pd.DataFrame,
        day: date,
        shift_start: time,
        shift_end: time,
        shift_start_str: str,
        shift_end_str: str,
        department: str,
        joining_date: Optional[date],
        last_updated_date: date,
        compensated_dates: Dict,
        full_time: bool
    ) -> Dict[str, Any]:
        """Create a single daily record for an employee."""
        day_data = emp_data[emp_data["Date"] == day]
        check_in, check_out = self._extract_check_times(day_data)

        # Sunday handling
        if day.weekday() == 6:
            status = AttendanceStatus.SUNDAY
            overtime_hours = 0.0
            missed_in, missed_out = "", ""
        else:
            status, overtime_hours = self.calculator.calculate_status(
                check_in, check_out, day, shift_start, shift_end, full_time
            )
            
            # Compensated date override
            if str(day) in compensated_dates.get(employee_name, set()):
                status = AttendanceStatus.COMPENSATED
                overtime_hours = 0.0
                
            missed_in, missed_out = self.calculator.determine_missed_punches(check_in, check_out)

        return {
            "EmpID": emp_id,
            "Date": day.strftime("%Y-%m-%d"),
            "Name": employee_name,
            "Shift": f"{shift_start_str} - {shift_end_str}",
            "CheckIn": check_in.strftime("%H:%M:%S") if check_in else "",
            "CheckOut": check_out.strftime("%H:%M:%S") if check_out else "",
            "Status": status,
            "MissedCheckIn": missed_in,
            "MissedCheckOut": missed_out,
            "Overtime": overtime_hours,
            "Department": department,
            "JoiningDate": joining_date,
            "LastUpdatedDate": last_updated_date
        }

    def _get_employees_data(self, employee_names: List[str]) -> Dict[str, Employee]:
        """Fetch all employee data in one query."""
        employees = Employee.query.filter(Employee.name.in_(employee_names)).all()
        return {emp.name: emp for emp in employees}

    def _get_employee_shift(self, employee_obj: Optional[Employee], employee_name: str) -> Tuple[str, str]:
        """Get employee shift times."""
        if employee_obj and employee_obj.shift and "-" in employee_obj.shift:
            shift_parts = [s.strip() for s in employee_obj.shift.split("-", 1)]
            return shift_parts[0], shift_parts[1]
        return ShiftDefaults.DEFAULT_SHIFT_START, ShiftDefaults.DEFAULT_SHIFT_END

    def _is_full_time_employee(self, employee_obj: Optional[Employee], shift_start: time, shift_end: time) -> bool:
        """Determine if employee is full-time based on shift duration."""
        shift_start_dt = datetime.combine(date.today(), shift_start)
        shift_end_dt = datetime.combine(date.today(), shift_end)
        shift_duration = (shift_end_dt - shift_start_dt).total_seconds() / 3600.0
        return shift_duration >= AttendanceThresholds.FULL_TIMER_MIN_HOURS

    @staticmethod
    def _parse_shift(shift_str: str) -> Tuple[time, time]:
        """Parse shift string into time objects."""
        try:
            if "-" in shift_str:
                shift_start_str, shift_end_str = [s.strip() for s in shift_str.split("-", 1)]
            else:
                shift_start_str, shift_end_str = ShiftDefaults.DEFAULT_SHIFT_STR.split("-", 1)
                shift_start_str, shift_end_str = shift_start_str.strip(), shift_end_str.strip()

            shift_start = datetime.strptime(shift_start_str, "%H:%M").time()
            shift_end = datetime.strptime(shift_end_str, "%H:%M").time()
            return shift_start, shift_end
        except (ValueError, AttributeError):
            # Return defaults on error
            default_start = datetime.strptime(ShiftDefaults.DEFAULT_SHIFT_START, "%H:%M").time()
            default_end = datetime.strptime(ShiftDefaults.DEFAULT_SHIFT_END, "%H:%M").time()
            return default_start, default_end

    @staticmethod
    def _get_all_dates(df: pd.DataFrame) -> List[date]:
        """Return all dates in the attendance range, including Sundays."""
        date_range = pd.date_range(df["Date"].min(), df["Date"].max())
        return [d.date() for d in date_range]

    @staticmethod
    def _extract_check_times(day_data: pd.DataFrame) -> Tuple[Optional[datetime], Optional[datetime]]:
        """Extract check-in and check-out times from daily data."""
        if day_data.empty:
            return None, None
            
        check_in = day_data["CheckIn"].iloc[0] if not pd.isna(day_data["CheckIn"].iloc[0]) else None
        check_out = day_data["CheckOut"].iloc[0] if not pd.isna(day_data["CheckOut"].iloc[0]) else None
        return check_in, check_out

    def _save_and_return_results(self, daily_table: List[Dict[str, Any]], df: pd.DataFrame) -> Dict[str, Any]:
        """Save results to database and return response."""
        try:
            self._save_daily_report_to_db(daily_table)
            db.session.commit()
            return {
                "daily_table": daily_table,
                "employees": sorted(df["Name"].unique()),
                "message": "✅ Daily report generated successfully with OT calculation."
            }
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error saving daily report: {e}")
            return {"error": f"Error saving daily report: {e}", "daily_table": []}

    def _save_daily_report_to_db(self, daily_table: List[Dict[str, Any]]):
        """Save or update each record in DB."""
        for row in daily_table:
            self._save_or_update_record(row)

    def _save_or_update_record(self, row: Dict[str, Any]):
        """Save or update a single daily record."""
        try:
            date_obj = datetime.strptime(row["Date"], "%Y-%m-%d").date()
            existing = DailyReport.query.filter_by(employee_name=row["Name"], date=date_obj).first()

            # Convert check-in/check-out strings to time objects
            check_in_time = datetime.strptime(row["CheckIn"], "%H:%M:%S").time() if row["CheckIn"] else None
            check_out_time = datetime.strptime(row["CheckOut"], "%H:%M:%S").time() if row["CheckOut"] else None

            # Get latest employee data
            emp_data = Employee.query.filter_by(name=row["Name"]).first()
            department = getattr(emp_data, 'department', 'Cold Calling')
            joining_date = getattr(emp_data, 'joining_date', None)
            last_updated_date_obj = getattr(emp_data, 'last_updated_date', datetime.utcnow().date())

            # Parse shift and determine full-time status
            shift_start, shift_end = self._parse_shift(row["Shift"])
            full_time = self._is_full_time_employee(emp_data, shift_start, shift_end)
            
            check_in_dt = datetime.combine(date_obj, check_in_time) if check_in_time else None
            check_out_dt = datetime.combine(date_obj, check_out_time) if check_out_time else None

            if date_obj.weekday() == 6:  # Sunday
                status = AttendanceStatus.SUNDAY
                overtime = 0.0
                missed_in, missed_out = "", ""
            else:
                status, overtime = self.calculator.calculate_status(
                    check_in_dt, check_out_dt, date_obj, shift_start, shift_end, full_time
                )
                missed_in, missed_out = self.calculator.determine_missed_punches(check_in_dt, check_out_dt)

            if existing:
                if getattr(existing, "manual_override", False):
                    # Keep existing shift/status/overtime but update check-in/check-out
                    existing.check_in = check_in_time
                    existing.check_out = check_out_time
                    return

                # Update existing record
                existing.emp_id = row["EmpID"]
                existing.shift = row["Shift"]
                existing.check_in = check_in_time
                existing.check_out = check_out_time
                existing.status = status
                existing.missed_checkin = (missed_in == "Yes")
                existing.missed_checkout = (missed_out == "Yes")
                existing.overtime = overtime
                existing.department = department
                existing.joining_date = joining_date
                existing.last_updated_date = last_updated_date_obj

            else:
                # Add new record
                new_record = DailyReport(
                    emp_id=row["EmpID"],
                    employee_name=row["Name"],
                    date=date_obj,
                    shift=row["Shift"],
                    check_in=check_in_time,
                    check_out=check_out_time,
                    status=status,
                    missed_checkin=(missed_in == "Yes"),
                    missed_checkout=(missed_out == "Yes"),
                    overtime=overtime,
                    department=department,
                    joining_date=joining_date,
                    last_updated_date=last_updated_date_obj
                )
                db.session.add(new_record)

        except Exception as e:
            logger.error(f"Error saving daily record {row}: {e}")


# ===========================================================
#              EXTERNAL ENTRY POINT
# ===========================================================
def generate_daily_report(employee_shifts: Optional[Dict[str, str]] = None,
                          compensated_dates: Optional[Dict[str, set]] = None) -> Dict[str, Any]:
    """External entry point for generating daily reports."""
    generator = DailyReportGenerator()
    return generator.generate_daily_report(employee_shifts, compensated_dates)