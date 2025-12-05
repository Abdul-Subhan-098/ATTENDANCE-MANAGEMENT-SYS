from datetime import datetime, timedelta, time, date
from typing import Dict, List, Tuple, Optional, Any
from sqlalchemy import inspect, text
from app import db
from app.models import DailyReport, Employee
import pandas as pd
import logging
import numpy as np
import time as time_module
from app.models import db, DailyReport, MonthlyReport, Employee, CompanyDayOff

# Configure logging
logger = logging.getLogger(__name__)

# ===========================================================
#              CONSTANTS AND CONFIGURATION
# ===========================================================
class AttendanceStatus:
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
    DEFAULT_SHIFT_START = "10:00"
    DEFAULT_SHIFT_END = "19:00"
    DEFAULT_SHIFT_STR = "10:00 - 19:00"

class OvertimeConfig:
    MAX_OT_HOURS = 2.0
    OT_THRESHOLD_1_HOUR = 1.0   
    OT_THRESHOLD_2_HOURS = 2.0

class AttendanceThresholds:
    FULL_TIMER_MIN_HOURS = 9.0
    SAT_HALF_DAY_MIN_HOURS = 4.5  
    GRACE_PERIOD_SECONDS = 59  
    LATE_THRESHOLD_HOURS = 1
    EARLY_CHECKOUT_MINUTES = 15

# ===========================================================
#              ULTRA-FAST ATTENDANCE PROCESSOR
# ===========================================================
class AttendanceProcessor:
    @staticmethod
    def get_clean_attendance() -> pd.DataFrame:
        """Ultra-fast attendance data fetching"""
        try:
            start_time = time_module.time()
            
            query = text("SELECT * FROM attendance_raw")
            df = pd.read_sql_query(query, db.engine)
            
            read_time = time_module.time() - start_time
            logger.info(f"📊 Raw data read: {len(df)} rows in {read_time:.2f}s")
            
            if df.empty:
                return pd.DataFrame()

            return AttendanceProcessor._ultra_fast_process_attendance(df)

        except Exception as e:
            logger.error(f"Error cleaning attendance data: {e}")
            return pd.DataFrame()


    @staticmethod
    def _ultra_fast_process_attendance(df: pd.DataFrame) -> pd.DataFrame:
        """Massively optimized data processing"""
        if df.empty:
            return pd.DataFrame()

        start_time = time_module.time()
        original_rows = len(df)

        # Vectorized operations
        df["Name"] = (
            df["Name"].astype(str)
            .str.replace(".", " ", regex=False)
            .str.replace(r"\s+", " ", regex=True)
            .str.strip()
        )
        
        # Fast datetime conversion
        df["Time"] = pd.to_datetime(df["Time"], errors="coerce")
        
        # Remove invalid rows
        valid_mask = df["Time"].notna()
        if not valid_mask.all():
            df = df[valid_mask].copy()
            
        if df.empty:
            return df

        df["Date"] = df["Time"].dt.date

        # Optimized attendance state
        if "Attendance State" in df.columns:
            df["Attendance State"] = (
                pd.to_numeric(df["Attendance State"], errors="coerce")
                .fillna(-1)
                .astype(np.int8)
            )
        else:
            df["Attendance State"] = -1

        process_time = time_module.time() - start_time
        logger.info(f"🧹 Data processed: {original_rows} → {len(df)} rows ({process_time:.2f}s)")

        return AttendanceProcessor._ultra_fast_group_records(df)

    @staticmethod
    def _ultra_fast_group_records(df: pd.DataFrame) -> pd.DataFrame:
        """Highly optimized record grouping"""
        if df.empty:
            return pd.DataFrame()

        start_time = time_module.time()

        # Separate checkins and checkouts
        checkins = df[df["Attendance State"] == 0].copy()
        checkouts = df[df["Attendance State"] == 1].copy()
        
        # Group efficiently
        if not checkins.empty:
            checkins_grouped = checkins.groupby(["Emp ID", "Name", "Date"])["Time"].min().reset_index()
            checkins_grouped.rename(columns={'Time': 'CheckIn'}, inplace=True)
        else:
            checkins_grouped = pd.DataFrame(columns=["Emp ID", "Name", "Date", "CheckIn"])
            
        if not checkouts.empty:
            checkouts_grouped = checkouts.groupby(["Emp ID", "Name", "Date"])["Time"].max().reset_index()
            checkouts_grouped.rename(columns={'Time': 'CheckOut'}, inplace=True)
        else:
            checkouts_grouped = pd.DataFrame(columns=["Emp ID", "Name", "Date", "CheckOut"])

        # Merge efficiently
        if not checkins_grouped.empty and not checkouts_grouped.empty:
            result = pd.merge(checkins_grouped, checkouts_grouped, on=["Emp ID", "Name", "Date"], how='outer')
        elif not checkins_grouped.empty:
            result = checkins_grouped
            result['CheckOut'] = None
        elif not checkouts_grouped.empty:
            result = checkouts_grouped
            result['CheckIn'] = None
        else:
            return pd.DataFrame()

        group_time = time_module.time() - start_time
        logger.info(f"📦 Records grouped: {len(result)} daily records ({group_time:.2f}s)")

        return result

from datetime import datetime, date, time, timedelta
from typing import Optional, Tuple

class AttendanceCalculator:
    """FINAL — Fully updated with correct part-timer & Saturday OT logic."""

    @staticmethod
    def calculate_status(
        check_in: Optional[datetime],
        check_out: Optional[datetime],
        day: date,
        shift_start: time,
        shift_end: time,
        full_time: bool = True
    ) -> Tuple[str, Optional[float]]:
        """
        Returns (status, daily OT hours)
        - Daily OT is always None for Saturday.
        - Handles missing punches correctly for part-timers and full-timers.
        """

        shift_start_dt = datetime.combine(day, shift_start)
        shift_end_dt = datetime.combine(day, shift_end)

        # -------------------------------
        # NO PUNCHES
        # -------------------------------
        if not check_in and not check_out:
            if day.weekday() == 5 and full_time:
                return AttendanceStatus.SATURDAY, None
            return AttendanceStatus.ABSENT, 0.0

        # -------------------------------
        # ONE PUNCH MISSING
        # -------------------------------
        if not check_in or not check_out:
            # PART-TIMER → Always Half Day
            if not full_time:
                return AttendanceStatus.HALF_DAY, 0.0

            # FULL-TIMER Saturday → Half Day Sat
            if day.weekday() == 5:
                return AttendanceStatus.HALF_DAY_SAT, None

            # FULL-TIMER Weekday → Half Day
            return AttendanceStatus.HALF_DAY, 0.0

        # Normalize microseconds
        check_in = check_in.replace(microsecond=0)
        check_out = check_out.replace(microsecond=0)

        # -------------------------------
        # SATURDAY LOGIC
        # -------------------------------
        if day.weekday() == 5:
            # Part-timers on Saturday → Present, no OT
            if not full_time:
                return AttendanceStatus.PRESENT, None

            # Full-timers → status based on hours worked, OT always None for daily
            worked_hours = max(0.0, (check_out - check_in).total_seconds() / 3600.0)

            if worked_hours < 4.25:
                status = AttendanceStatus.SATURDAY
            elif worked_hours < 8.75:
                status = AttendanceStatus.HALF_DAY_SAT
            else:
                status = AttendanceStatus.FULL_DAY_SAT

            return status, None  # Daily OT is None

        # -------------------------------
        # WEEKDAY LOGIC
        # -------------------------------
        status, overtime_hours = AttendanceCalculator._calculate_regular_day_status(
            check_in, check_out, day, shift_start_dt, shift_end_dt, full_time
        )

        # Part-timers never get OT
        if not full_time:
            overtime_hours = 0.0

        return status, overtime_hours

    # ===========================================================
    # WEEKDAY STATUS + OT ENGINE
    # ===========================================================
    @staticmethod
    def _calculate_regular_day_status(
        check_in: datetime,
        check_out: datetime,
        day: date,
        shift_start_dt: datetime,
        shift_end_dt: datetime,
        full_time: bool = True
    ) -> Tuple[str, float]:
        """Calculate status for Monday–Friday"""
        present_limit = shift_start_dt + timedelta(seconds=AttendanceThresholds.GRACE_PERIOD_SECONDS)
        late_limit = shift_start_dt + timedelta(
            hours=AttendanceThresholds.LATE_THRESHOLD_HOURS,
            seconds=AttendanceThresholds.GRACE_PERIOD_SECONDS
        )

        # Status based on check-in
        if check_in <= present_limit:
            status = AttendanceStatus.PRESENT
        elif check_in <= late_limit:
            status = AttendanceStatus.LATE
        else:
            status = AttendanceStatus.HALF_DAY

        # Early checkout → Half Day
        early_limit = shift_end_dt - timedelta(minutes=AttendanceThresholds.EARLY_CHECKOUT_MINUTES)
        if check_out < early_limit:
            status = AttendanceStatus.HALF_DAY

        # Overtime only for full-timers
        overtime = AttendanceCalculator._calculate_overtime_hours(check_out, shift_end_dt) if full_time else 0.0

        return status, overtime

    # ===========================================================
    # WEEKDAY OT CALCULATION
    # ===========================================================
    @staticmethod
    def _calculate_overtime_hours(check_out: datetime, shift_end_dt: datetime) -> float:
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

    # ===========================================================
    # MONTHLY REPORT OT
    # ===========================================================
    @staticmethod
    def calculate_overtime(
        check_in: Optional[datetime],
        check_out: Optional[datetime],
        shift_start_dt: datetime,
        shift_end_dt: datetime,
        day: date,
        full_time: bool = True
    ) -> float:
        """Calculate OT for monthly report — Saturday OT counted"""

        if not check_in or not check_out or not full_time:
            return 0.0

        # Saturday → count all worked hours
        if day.weekday() == 5:
            return max(0.0, (check_out - check_in).total_seconds() / 3600.0)

        # Weekday → normal OT
        return AttendanceCalculator._calculate_overtime_hours(check_out, shift_end_dt)

    # ===========================================================
    # HELPERS
    # ===========================================================
    @staticmethod
    def determine_missed_punches(check_in, check_out) -> Tuple[str, str]:
        missed_in = "Yes" if not check_in else ""
        missed_out = "Yes" if not check_out else ""
        return missed_in, missed_out

    @staticmethod
    def is_full_time_employee(shift_start: time, shift_end: time) -> bool:
        """Shift ≥ 9 hours = full-time"""
        try:
            sdt = datetime.combine(date.today(), shift_start)
            edt = datetime.combine(date.today(), shift_end)
            hours = (edt - sdt).total_seconds() / 3600.0
            return hours >= AttendanceThresholds.FULL_TIMER_MIN_HOURS
        except:
            return True


# ===========================================================
#         DAILY REPORT GENERATOR
# ===========================================================
class DailyReportGenerator:
    """Massively optimized for 50k+ rows"""

    def __init__(self):
        self.processor = AttendanceProcessor()
        self.calculator = AttendanceCalculator()

    def generate_daily_report(self, employee_shifts: Optional[Dict[str, str]] = None,
                              compensated_dates: Optional[Dict[str, set]] = None) -> Dict[str, Any]:
        """Ultra-fast daily report generation"""
        total_start = time_module.time()
        logger.info("🚀 Starting ultra-fast daily report generation...")

        employee_shifts = employee_shifts or {}
        compensated_dates = compensated_dates or {}

        inspector = inspect(db.engine)
        if "attendance_raw" not in inspector.get_table_names():
            return {
                "error": "No attendance data found. Please upload attendance file first.",
                "daily_table": []
            }

        # Step 1: Get cleaned data
        df_start = time_module.time()
        df = self.processor.get_clean_attendance()
        df_time = time_module.time() - df_start
        
        if df.empty:
            return {"error": "No valid attendance records found.", "daily_table": []}

        logger.info(f"📊 Cleaned data: {len(df)} rows in {df_time:.2f}s")

        # Step 2: Generate report data with bulk operations
        report_start = time_module.time()
        daily_table = self._ultra_fast_generate_report_data(df, employee_shifts, compensated_dates)
        report_time = time_module.time() - report_start
        
        logger.info(f"📈 Report data generated: {len(daily_table)} records in {report_time:.2f}s")

        # Step 3: Save to database with bulk operations
        save_start = time_module.time()
        result = self._ultra_fast_save_and_return_results(daily_table, df)
        save_time = time_module.time() - save_start
        
        total_time = time_module.time() - total_start
        logger.info(f"✅ Daily report completed in {total_time:.2f}s "
                   f"(Data: {df_time:.2f}s, Report: {report_time:.2f}s, Save: {save_time:.2f}s)")

        return result

    def _ultra_fast_generate_report_data(self, df: pd.DataFrame, employee_shifts: Dict, 
                                       compensated_dates: Dict) -> List[Dict[str, Any]]:
        """Ultra-fast report data generation"""
        start_time = time_module.time()
        
        employees = sorted(df["Name"].unique())
        all_dates = self._get_all_dates(df)
        
        # Pre-fetch all employee data in one query
        employees_start = time_module.time()
        employees_data = self._get_all_employees_data(employees)
        employees_time = time_module.time() - employees_start
        
        logger.info(f"👥 Employee data fetched: {len(employees_data)} employees in {employees_time:.2f}s")

        records = []
        total_employees = len(employees)
        
        # Process employees with progress tracking
        for i, emp in enumerate(employees):
            emp_records = self._fast_generate_employee_records(
                emp, df, all_dates, employees_data, compensated_dates
            )
            records.extend(emp_records)
            
            # Progress every 10 employees
            if i > 0 and i % 10 == 0:
                elapsed = time_module.time() - start_time
                logger.info(f"📊 Processed {i}/{total_employees} employees ({elapsed:.2f}s)")

        records.sort(key=lambda x: (x["Name"], x["Date"]))
        
        total_time = time_module.time() - start_time
        logger.info(f"📋 Generated {len(records)} daily records in {total_time:.2f}s")
        
        return records

    def _get_all_employees_data(self, employee_names: List[str]) -> Dict[str, Employee]:
        """Fetch all employee data in one optimized query"""
        if not employee_names:
            return {}
            
        employees = Employee.query.filter(Employee.name.in_(employee_names)).all()
        return {emp.name: emp for emp in employees}

    def _fast_generate_employee_records(
        self,
        employee_name: str,
        df: pd.DataFrame,
        all_dates: List[date],
        employees_data: Dict,
        compensated_dates: Dict
    ) -> List[Dict[str, Any]]:
        """Fast employee record generation"""
        emp_data = df[df["Name"] == employee_name]
        if emp_data.empty:
            return []

        emp_id = str(emp_data["Emp ID"].iloc[0]) if not emp_data["Emp ID"].isna().all() else ""

        # Get employee configuration
        employee_obj = employees_data.get(employee_name)
        shift_start_str, shift_end_str = self._get_employee_shift(employee_obj, employee_name)
        department = getattr(employee_obj, 'department', 'Cold Calling')
        joining_date = getattr(employee_obj, 'joining_date', None)
        last_updated_date = getattr(employee_obj, 'last_updated_date', datetime.utcnow().date())
        role = getattr(employee_obj, 'role', 'FullTime')  # Added from Code A

        shift_start, shift_end = self._parse_shift(f"{shift_start_str} - {shift_end_str}")
        full_time = self._is_full_time_employee(employee_obj, shift_start, shift_end)
        
        records = []

        for day in all_dates:
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

            records.append({
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
                "LastUpdatedDate": last_updated_date,
                "Role": role  # Added from Code A
            })

        return records

    def _ultra_fast_save_and_return_results(self, daily_table: List[Dict[str, Any]], df: pd.DataFrame) -> Dict[str, Any]:
        """Ultra-fast database saving"""
        try:
            save_start = time_module.time()
            self._ultra_fast_save_daily_report(daily_table)
            db.session.commit()
            save_time = time_module.time() - save_start
            
            logger.info(f"💾 Database save completed: {len(daily_table)} records in {save_time:.2f}s")
            
            return {
                "daily_table": daily_table,
                "employees": sorted(df["Name"].unique()),
                "message": f"✅ Daily report generated successfully with {len(daily_table)} records in {save_time:.2f}s"
            }
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error saving daily report: {e}")
            return {"error": f"Error saving daily report: {e}", "daily_table": []}

    def _ultra_fast_save_daily_report(self, daily_table: List[Dict[str, Any]]):
        """Ultra-fast bulk save operations"""
        if not daily_table:
            return

        batch_size = 1000
        total_records = len(daily_table)
        
        logger.info(f"💾 Starting bulk save of {total_records} records...")
        
        for i in range(0, total_records, batch_size):
            batch = daily_table[i:i + batch_size]
            batch_records = []
            
            for row in batch:
                record = self._prepare_daily_record(row)
                if record:
                    batch_records.append(record)
            
            if batch_records:
                # Use bulk_insert_mappings for maximum performance
                db.session.bulk_insert_mappings(DailyReport, batch_records)
                
            # Progress every batch
            if i > 0 and i % 5000 == 0:
                logger.info(f"💾 Saved {i}/{total_records} records...")
        
        logger.info(f"💾 Bulk save completed: {total_records} records")

    def _prepare_daily_record(self, row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Prepare a single record for bulk insert"""
        try:
            date_obj = datetime.strptime(row["Date"], "%Y-%m-%d").date()
            
            # Convert check-in/check-out strings to time objects
            check_in_time = None
            check_out_time = None
            
            if row["CheckIn"]:
                # Directly create time object from string
                time_str = row["CheckIn"]
                if len(time_str) >= 5:  # At least "HH:MM"
                    try:
                        hours = int(time_str[:2])
                        minutes = int(time_str[3:5])
                        seconds = int(time_str[6:8]) if len(time_str) > 6 else 0
                        check_in_time = time(hours, minutes, seconds)
                    except (ValueError, IndexError):
                        logger.warning(f"Invalid time format: {time_str}")
            
            if row["CheckOut"]:
                # Directly create time object from string
                time_str = row["CheckOut"]
                if len(time_str) >= 5:  # At least "HH:MM"
                    try:
                        hours = int(time_str[:2])
                        minutes = int(time_str[3:5])
                        seconds = int(time_str[6:8]) if len(time_str) > 6 else 0
                        check_out_time = time(hours, minutes, seconds)
                    except (ValueError, IndexError):
                        logger.warning(f"Invalid time format: {time_str}")

            return {
                'emp_id': row["EmpID"],
                'employee_name': row["Name"],
                'date': date_obj,
                'shift': row["Shift"],
                'check_in': check_in_time,
                'check_out': check_out_time,
                'status': row["Status"],
                'missed_checkin': (row["MissedCheckIn"] == "Yes"),
                'missed_checkout': (row["MissedCheckOut"] == "Yes"),
                'overtime': row["Overtime"],
                'department': row["Department"],
                'joining_date': row["JoiningDate"],
                'last_updated_date': row["LastUpdatedDate"],
                'role': row.get("Role", "FullTime")  # Added from Code A
            }
        except Exception as e:
            logger.error(f"Error preparing record {row}: {e}")
            return None

    def _get_employee_shift(self, employee_obj: Optional[Employee], employee_name: str) -> Tuple[str, str]:
        if employee_obj and employee_obj.shift and "-" in employee_obj.shift:
            shift_parts = [s.strip() for s in employee_obj.shift.split("-", 1)]
            return shift_parts[0], shift_parts[1]
        return ShiftDefaults.DEFAULT_SHIFT_START, ShiftDefaults.DEFAULT_SHIFT_END

    def _is_full_time_employee(self, employee_obj: Optional[Employee], shift_start: time, shift_end: time) -> bool:
        try:
            shift_start_dt = datetime.combine(date.today(), shift_start)
            shift_end_dt = datetime.combine(date.today(), shift_end)
            shift_duration = (shift_end_dt - shift_start_dt).total_seconds() / 3600.0
            return shift_duration >= AttendanceThresholds.FULL_TIMER_MIN_HOURS
        except Exception as e:
            logger.error(f"Error calculating shift duration: {e}")
            return True

    @staticmethod
    def _parse_shift(shift_str: str) -> Tuple[time, time]:
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
            default_start = datetime.strptime(ShiftDefaults.DEFAULT_SHIFT_START, "%H:%M").time()
            default_end = datetime.strptime(ShiftDefaults.DEFAULT_SHIFT_END, "%H:%M").time()
            return default_start, default_end

    @staticmethod
    def _get_all_dates(df: pd.DataFrame) -> List[date]:
        date_range = pd.date_range(df["Date"].min(), df["Date"].max())
        return [d.date() for d in date_range]

    @staticmethod
    def _extract_check_times(day_data: pd.DataFrame) -> Tuple[Optional[datetime], Optional[datetime]]:
        if day_data.empty:
            return None, None
            
        check_in = day_data["CheckIn"].iloc[0] if not pd.isna(day_data["CheckIn"].iloc[0]) else None
        check_out = day_data["CheckOut"].iloc[0] if not pd.isna(day_data["CheckOut"].iloc[0]) else None
        return check_in, check_out
    
    def _fast_generate_employee_records(
        self,
        employee_name: str,
        df: pd.DataFrame,
        all_dates: List[date],
        employees_data: Dict,
        compensated_dates: Dict
    ) -> List[Dict[str, Any]]:
        """Fast employee record generation"""
        emp_data = df[df["Name"] == employee_name]
        if emp_data.empty:
            return []

        emp_id = str(emp_data["Emp ID"].iloc[0]) if not emp_data["Emp ID"].isna().all() else ""

        # Get employee configuration
        employee_obj = employees_data.get(employee_name)
        shift_start_str, shift_end_str = self._get_employee_shift(employee_obj, employee_name)
        department = getattr(employee_obj, 'department', 'Cold Calling')
        joining_date = getattr(employee_obj, 'joining_date', None)
        last_updated_date = getattr(employee_obj, 'last_updated_date', datetime.utcnow().date())
        role = getattr(employee_obj, 'role', 'FullTime')

        shift_start, shift_end = self._parse_shift(f"{shift_start_str} - {shift_end_str}")
        full_time = self._is_full_time_employee(employee_obj, shift_start, shift_end)
        
        # Check for Company Day Off dates
        company_off_dates = self._get_company_off_dates(all_dates)
        
        records = []

        for day in all_dates:
            # Check if this is a Company Day Off
            if day in company_off_dates:
                reason = company_off_dates[day]
                records.append({
                    "EmpID": emp_id,
                    "Date": day.strftime("%Y-%m-%d"),
                    "Name": employee_name,
                    "Shift": f"{shift_start_str} - {shift_end_str}",
                    "CheckIn": "",
                    "CheckOut": "",
                    "Status": "Company Day Off",
                    "MissedCheckIn": "",
                    "MissedCheckOut": "",
                    "Overtime": 0.0,
                    "Department": department,
                    "JoiningDate": joining_date,
                    "LastUpdatedDate": last_updated_date,
                    "Role": role,
                    "IsCompanyOff": True,
                    "CompanyOffReason": reason
                })
                continue
            
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

            records.append({
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
                "LastUpdatedDate": last_updated_date,
                "Role": role,
                "IsCompanyOff": False,
                "CompanyOffReason": None
            })

        return records
    
    def _get_company_off_dates(self, dates: List[date]) -> Dict[date, str]:
        """Get Company Day Off dates from database"""
        try:
            company_off_records = CompanyDayOff.query.filter(
                CompanyDayOff.date.in_(dates)
            ).all()
            
            return {record.date: record.reason for record in company_off_records}
        except Exception as e:
            logger.error(f"Error fetching Company Day Off dates: {e}")
            return {}

# ===========================================================
#              EXTERNAL ENTRY POINT
# ===========================================================
def generate_daily_report(employee_shifts: Optional[Dict[str, str]] = None,
                          compensated_dates: Optional[Dict[str, set]] = None) -> Dict[str, Any]:
    """External entry point for generating daily reports."""
    generator = DailyReportGenerator()
    return generator.generate_daily_report(employee_shifts, compensated_dates)