# from datetime import datetime, timedelta
# from typing import Dict, List, Tuple, Optional, Any
# from sqlalchemy import inspect, text
# from app import db
# from app.models import DailyReport, Employee
# import pandas as pd


# # ===========================================================
# #              ATTENDANCE DATA PROCESSOR
# # ===========================================================
# class AttendanceProcessor:
#     """Clean and prepare raw attendance data."""

#     DEFAULT_SHIFT = ("10:00", "19:00")
#     GRACE_MINUTES = 5
#     HALF_DAY_MINUTES = 30
#     SATURDAY_MIN_HOURS = 6

#     @staticmethod
#     def get_clean_attendance() -> pd.DataFrame:
#         """Fetch and clean attendance_raw data."""
#         try:
#             inspector = inspect(db.engine)
#             if "attendance_raw" not in inspector.get_table_names():
#                 print("⚠️ attendance_raw table not found.")
#                 return pd.DataFrame()

#             df = pd.read_sql(text("SELECT * FROM attendance_raw"), db.engine)
#             return AttendanceProcessor._process_attendance_data(df)

#         except Exception as e:
#             print(f"❌ Error cleaning attendance data: {e}")
#             return pd.DataFrame()

#     @staticmethod
#     def _process_attendance_data(df: pd.DataFrame) -> pd.DataFrame:
#         if df.empty:
#             return pd.DataFrame()

#         # Normalize Name
#         df["Name"] = (
#             df["Name"].astype(str)
#             .str.replace(".", " ", regex=False)
#             .str.replace(r"\s+", " ", regex=True)
#             .str.strip()
#         )
#         df["Time"] = pd.to_datetime(df["Time"], errors="coerce")
#         df = df.dropna(subset=["Time"])
#         df["Date"] = df["Time"].dt.date

#         # Normalize Attendance State
#         df["Attendance State"] = pd.to_numeric(df.get("Attendance State", 0), errors="coerce")
#         df["Attendance State"] = df["Attendance State"].apply(lambda x: int(x) if not pd.isna(x) else -1)

#         return AttendanceProcessor._group_attendance_records(df)

#     @staticmethod
#     def _group_attendance_records(df: pd.DataFrame) -> pd.DataFrame:
#         """Group attendance records per employee/day."""
#         rows = []
#         for (emp_id, name, date), group in df.groupby(["Emp ID", "Name", "Date"], dropna=False):
#             checkins = group[group["Attendance State"] == 0]
#             checkouts = group[group["Attendance State"] == 1]

#             first_in = checkins["Time"].min() if not checkins.empty else None
#             last_out = checkouts["Time"].max() if not checkouts.empty else None

#             if first_in or last_out:
#                 rows.append({
#                     "Emp ID": emp_id,
#                     "Name": name,
#                     "Date": date,
#                     "CheckIn": first_in,
#                     "CheckOut": last_out
#                 })
#         return pd.DataFrame(rows)


# from datetime import datetime, timedelta
# from typing import Optional, Tuple

# class AttendanceCalculator:
#     """Calculate attendance status, overtime, missed punches, with correct Saturday logic."""

#     MAX_OT_HOURS = 2
#     FULL_TIMER_MIN_HOURS = 9       # Full-time threshold for OT and full day
#     HALF_DAY_MIN_HOURS = 4.5       # Half-day threshold for Saturday / early leave

#     @staticmethod
#     def calculate_status(
#         check_in: Optional[datetime],
#         check_out: Optional[datetime],
#         day: datetime.date,
#         shift_start: datetime.time,
#         shift_end: datetime.time,
#         full_time: bool = True
#     ) -> Tuple[str, float]:
#         shift_start_dt = datetime.combine(day, shift_start)
#         shift_end_dt = datetime.combine(day, shift_end)
#         shift_seconds = (shift_end_dt - shift_start_dt).total_seconds()
#         shift_hours = shift_seconds / 3600

#         status = "Absent"
#         overtime = 0.0

#         # ----------------- Check-in missing -----------------
#         if not check_in:
#             return "Absent", 0.0

#         # Normalize check-in/out
#         check_in = check_in.replace(microsecond=0)
#         if check_out:
#             check_out = check_out.replace(microsecond=0)

#         # ----------------- BASE STATUS (Mon-Fri & Sat normal for part-time) -----------------
#         present_limit = shift_start_dt + timedelta(minutes=1, seconds=59)
#         late_limit = shift_start_dt + timedelta(hours=1)

#         if check_in <= present_limit:
#             status = "Present"
#         elif present_limit < check_in <= late_limit:
#             status = "Late"
#         else:
#             status = "Half Day"

#         # Early checkout reduces status
#         if check_out:
#             early_checkout_limit = shift_end_dt - timedelta(minutes=15)
#             if check_out < early_checkout_limit:
#                 status = "Half Day"

#         # ----------------- OVERTIME (FULL-TIME ONLY) -----------------
#         if full_time and check_out:
#             ot_seconds = (check_out - shift_end_dt).total_seconds()
#             if ot_seconds >= 3600 and ot_seconds < 7200:
#                 overtime = 1.0
#             elif ot_seconds >= 7200:
#                 overtime = 2.0

#         # ----------------- SATURDAY LOGIC -----------------
#         if day.weekday() == 5:  # Saturday
#             if full_time:
#                 # Full-time Saturday rules
#                 worked_hours = 0.0
#                 if check_out:
#                     worked_hours = (check_out - check_in).total_seconds() / 3600

#                 if worked_hours >= AttendanceCalculator.FULL_TIMER_MIN_HOURS:
#                     status = "Full Day (Sat)"
#                 elif worked_hours >= AttendanceCalculator.HALF_DAY_MIN_HOURS:
#                     status = "Half Day (Sat)"
#                 else:
#                     status = "Absent"
#             else:
#                 # Part-time Saturday: optional, normal weekday rules, no OT
#                 overtime = 0.0

#         return status, overtime

#     @staticmethod
#     def determine_missed_punches(
#         check_in: Optional[datetime],
#         check_out: Optional[datetime]
#     ) -> Tuple[str, str]:
#         """Check if any punch is missing."""
#         return ("Yes" if not check_in else "", "Yes" if not check_out else "")



# # ===========================================================
# #              DAILY REPORT GENERATOR
# # ===========================================================
# class DailyReportGenerator:
#     """Generate and store Daily Reports."""

#     def __init__(self):
#         self.processor = AttendanceProcessor()
#         self.calculator = AttendanceCalculator()

   

#     def update_shift_for_existing_records(self, employee_name: str, date_str: str, new_shift: str):
#         """
#         Update shift for an existing DailyReport record and recalculate status & overtime.
#         This marks the record as manual_override so it won't be overwritten by auto-generation.
#         :param employee_name: Name of the employee
#         :param date_str: Date in 'YYYY-MM-DD'
#         :param new_shift: New shift string, e.g., '11:00 - 20:00'
#         """
#         try:
#             date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
#             record = DailyReport.query.filter_by(employee_name=employee_name, date=date_obj).first()

#             if not record:
#                 print(f"⚠️ No existing record found for {employee_name} on {date_str}")
#                 return

#             # Parse new shift
#             shift_start_str, shift_end_str = [s.strip() for s in new_shift.split("-", 1)]
#             shift_start = datetime.strptime(shift_start_str, "%H:%M").time()
#             shift_end = datetime.strptime(shift_end_str, "%H:%M").time()

#             # Extract check-in/out datetimes
#             check_in_dt = datetime.combine(date_obj, record.check_in) if record.check_in else None
#             check_out_dt = datetime.combine(date_obj, record.check_out) if record.check_out else None

#             # Recalculate status and overtime based on new shift
#             status, _ = AttendanceCalculator.calculate_status(check_in_dt, check_out_dt, date_obj, shift_start, shift_end)
#             overtime = DailyReportGenerator.calculate_overtime(check_in_dt, check_out_dt,
#                                                            datetime.combine(date_obj, shift_start),
#                                                            datetime.combine(date_obj, shift_end))

#             # Update record with new shift, status, overtime
#             record.shift = new_shift
#             record.status = status
#             record.overtime = overtime

#             # Mark as manual override to prevent auto-reset
#             record.manual_override = True

#             db.session.commit()
#             print(f"✅ Shift, status, and overtime updated for {employee_name} on {date_str}")

#         except Exception as e:
#             db.session.rollback()
#             print(f"❌ Error updating shift for {employee_name} on {date_str}: {e}")




#     def generate_daily_report(self, employee_shifts=None, compensated_dates=None):
#         employee_shifts = employee_shifts or {}
#         compensated_dates = compensated_dates or {}

#         inspector = inspect(db.engine)
#         if "attendance_raw" not in inspector.get_table_names():
#             return {"error": "No attendance data found. Please upload attendance file first.", "daily_table": []}

#         df = self.processor.get_clean_attendance()
#         if df.empty:
#             return {"error": "No valid attendance records found.", "daily_table": []}

#         daily_table = self._generate_report_data(df, employee_shifts, compensated_dates)
#         return self._save_and_return_results(daily_table, df)

#     def _generate_report_data(self, df, employee_shifts, compensated_dates) -> List[Dict[str, Any]]:
#         employees = sorted(df["Name"].unique())
#         business_dates = self._get_business_dates(df)
#         records = []
 
#         for emp in employees:
#             emp_data = df[df["Name"] == emp]
#             emp_id = str(emp_data["Emp ID"].iloc[0]) if not emp_data["Emp ID"].isna().all() else ""

#             # Get latest employee data from Employee table
#             employee_obj = Employee.query.filter_by(name=emp).first()
#             if employee_obj:
#                 # Use shift from employee object
#                 shift_str = employee_obj.shift or "10:00 - 19:00"
#                 if "-" in shift_str:
#                     shift_start_str, shift_end_str = [s.strip() for s in shift_str.split("-", 1)]
#                 else:
#                     shift_start_str, shift_end_str = ("10:00", "19:00")

#                 department = employee_obj.department
#                 joining_date = employee_obj.joining_date
#                 last_updated_date = employee_obj.last_updated_date
#             else:
#                 shift_start_str, shift_end_str = ("10:00", "19:00")
#                 department = "Cold Calling"
#                 joining_date = None
#                 last_updated_date = datetime.utcnow().date()


#             # Convert shift times to datetime.time objects
#             start_time = datetime.strptime(shift_start_str, "%H:%M").time()
#             end_time = datetime.strptime(shift_end_str, "%H:%M").time()

#             for day in business_dates:
#                 day_data = emp_data[emp_data["Date"] == day]
#                 check_in, check_out = self._extract_check_times(day_data)

#                 # Determine attendance status
#                 status, _ = self.calculator.calculate_status(check_in, check_out, day, start_time, end_time)

#                 # Calculate overtime
#                 overtime_hours = self.calculate_overtime(
#                     check_in, check_out,
#                     datetime.combine(day, start_time),
#                     datetime.combine(day, end_time)
#                 )

#                 # Compensated override
#                 if str(day) in compensated_dates.get(emp, set()):
#                     status = "Compensated"
#                     overtime_hours = 0.0

#                 missed_in, missed_out = self.calculator.determine_missed_punches(check_in, check_out)

#                 # ✅ Store formatted data
#                 records.append({
#                     "EmpID": emp_id,
#                     "Date": day.strftime("%Y-%m-%d"),
#                     "Name": emp,
#                     "Shift": f"{shift_start_str} - {shift_end_str}",
#                     "CheckIn": check_in.strftime("%H:%M") if check_in else "",
#                     "CheckOut": check_out.strftime("%H:%M") if check_out else "",
#                     "Status": status,
#                     "MissedCheckIn": missed_in,
#                     "MissedCheckOut": missed_out,
#                     "Overtime": overtime_hours,
#                     "Department": department,
#                     "JoiningDate": joining_date,
#                     "LastUpdatedDate": last_updated_date
#                 })

#         records.sort(key=lambda x: (x["Name"], x["Date"]))
#         return records


#     @staticmethod
#     def calculate_overtime(check_in, check_out, shift_start_dt, shift_end_dt):
#         if not check_in or not check_out:
#             return 0.0

#         effective_start = max(check_in, shift_start_dt)
#         overtime_seconds = (check_out - shift_end_dt).total_seconds()
#         if overtime_seconds <= 0:
#             return 0.0

#         overtime_hours = overtime_seconds / 3600
#         if overtime_hours < 1:
#             return 0.0
#         elif overtime_hours < 2:
#             return 1.0
#         else:
#             return 2.0

#     @staticmethod
#     def _get_business_dates(df: pd.DataFrame) -> List[datetime.date]:
#         date_range = pd.date_range(df["Date"].min(), df["Date"].max())
#         return [d.date() for d in date_range if d.weekday() != 6]

#     @staticmethod
#     def _extract_check_times(day_data: pd.DataFrame) -> Tuple[Optional[datetime], Optional[datetime]]:
#         if day_data.empty:
#             return None, None
#         check_in = day_data["CheckIn"].iloc[0] if not pd.isna(day_data["CheckIn"].iloc[0]) else None
#         check_out = day_data["CheckOut"].iloc[0] if not pd.isna(day_data["CheckOut"].iloc[0]) else None
#         return check_in, check_out

#     def _save_and_return_results(self, daily_table, df):
#         """Save to DB and return results."""
#         try:
#             self._save_daily_report_to_db(daily_table)
#             db.session.commit()
#             return {
#                 "daily_table": daily_table,
#                 "employees": sorted(df["Name"].unique()),
#                 "message": "✅ Daily report generated successfully with OT calculation."
#             }
#         except Exception as e:
#             db.session.rollback()
#             return {"error": f"Error saving daily report: {e}", "daily_table": []}

#     def _save_daily_report_to_db(self, daily_table: List[Dict[str, Any]]):
#         """Save or update each record in DB."""
#         for row in daily_table:
#             self._save_or_update_record(row)

#     def _save_or_update_record(self, row: Dict[str, Any]):
#         try:
#             date_obj = datetime.strptime(row["Date"], "%Y-%m-%d").date()
#             existing = DailyReport.query.filter_by(employee_name=row["Name"], date=date_obj).first()

#             # Convert check-in/check-out strings to time objects
#             check_in_time = datetime.strptime(row["CheckIn"], "%H:%M").time() if row["CheckIn"] else None
#             check_out_time = datetime.strptime(row["CheckOut"], "%H:%M").time() if row["CheckOut"] else None

#             # Pull latest Employee data
#             emp_data = Employee.query.filter_by(name=row["Name"]).first()
#             department = emp_data.department if emp_data else "Cold Calling"
#             joining_date = emp_data.joining_date if emp_data else None
#             last_updated_date_obj = emp_data.last_updated_date if emp_data else datetime.utcnow().date()

#             # Parse shift string
#             shift_start_str, shift_end_str = [s.strip() for s in row["Shift"].split("-", 1)]
#             shift_start = datetime.strptime(shift_start_str, "%H:%M").time()
#             shift_end = datetime.strptime(shift_end_str, "%H:%M").time()

#             check_in_dt = datetime.combine(date_obj, check_in_time) if check_in_time else None
#             check_out_dt = datetime.combine(date_obj, check_out_time) if check_out_time else None

#             if existing:
#                 # ✅ Only overwrite if manual_override is False
#                 if getattr(existing, "manual_override", False):
#                     # Keep existing shift/status/overtime
#                     existing.check_in = check_in_time
#                     existing.check_out = check_out_time
#                     return

#                 # Recalculate status & overtime if not manual_override
#                 status, _ = AttendanceCalculator.calculate_status(check_in_dt, check_out_dt, date_obj, shift_start, shift_end)
#                 overtime = DailyReportGenerator.calculate_overtime(check_in_dt, check_out_dt,
#                                                                datetime.combine(date_obj, shift_start),
#                                                                datetime.combine(date_obj, shift_end))
#                 existing.emp_id = row["EmpID"]
#                 existing.shift = row["Shift"]
#                 existing.check_in = check_in_time
#                 existing.check_out = check_out_time
#                 existing.status = status
#                 existing.missed_checkin = (row["MissedCheckIn"] == "Yes")
#                 existing.missed_checkout = (row["MissedCheckOut"] == "Yes")
#                 existing.overtime = overtime
#                 existing.department = department
#                 existing.joining_date = joining_date
#                 existing.last_updated_date = last_updated_date_obj
#             else:
#                 # New record, add normally
#                 status, _ = AttendanceCalculator.calculate_status(check_in_dt, check_out_dt, date_obj, shift_start, shift_end)
#                 overtime = DailyReportGenerator.calculate_overtime(check_in_dt, check_out_dt,
#                                                                datetime.combine(date_obj, shift_start),
#                                                                datetime.combine(date_obj, shift_end))
#                 new_record = DailyReport(
#                     emp_id=row["EmpID"],
#                     employee_name=row["Name"],
#                     date=date_obj,
#                     shift=row["Shift"],
#                     check_in=check_in_time,
#                     check_out=check_out_time,
#                     status=status,
#                     missed_checkin=(row["MissedCheckIn"] == "Yes"),
#                     missed_checkout=(row["MissedCheckOut"] == "Yes"),
#                     overtime=overtime,
#                     department=department,
#                     joining_date=joining_date,
#                     last_updated_date=last_updated_date_obj
#                 )
#                 db.session.add(new_record)

#         except Exception as e:
#             print(f"❌ Error saving daily record {row}: {e}")


# # ===========================================================
# #              EXTERNAL ENTRY POINT
# # ===========================================================
# def generate_daily_report(employee_shifts=None, compensated_dates=None):
#     generator = DailyReportGenerator()
#     return generator.generate_daily_report(employee_shifts, compensated_dates)
















































from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
from sqlalchemy import inspect, text
from app import db
from app.models import DailyReport, Employee
import pandas as pd


# ===========================================================
#              ATTENDANCE DATA PROCESSOR
# ===========================================================
class AttendanceProcessor:
    """Clean and prepare raw attendance data."""

    DEFAULT_SHIFT = ("10:00", "19:00")
    GRACE_MINUTES = 5
    HALF_DAY_MINUTES = 30
    SATURDAY_MIN_HOURS = 6

    @staticmethod
    def get_clean_attendance() -> pd.DataFrame:
        """Fetch and clean attendance_raw data."""
        try:
            inspector = inspect(db.engine)
            if "attendance_raw" not in inspector.get_table_names():
                print("⚠️ attendance_raw table not found.")
                return pd.DataFrame()

            df = pd.read_sql(text("SELECT * FROM attendance_raw"), db.engine)
            return AttendanceProcessor._process_attendance_data(df)

        except Exception as e:
            print(f"❌ Error cleaning attendance data: {e}")
            return pd.DataFrame()

    @staticmethod
    def _process_attendance_data(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return pd.DataFrame()

        # Normalize Name
        df["Name"] = (
            df["Name"].astype(str)
            .str.replace(".", " ", regex=False)
            .str.replace(r"\s+", " ", regex=True)
            .str.strip()
        )
        df["Time"] = pd.to_datetime(df["Time"], errors="coerce")
        df = df.dropna(subset=["Time"])
        df["Date"] = df["Time"].dt.date

        # Normalize Attendance State
        df["Attendance State"] = pd.to_numeric(df.get("Attendance State", 0), errors="coerce")
        df["Attendance State"] = df["Attendance State"].apply(lambda x: int(x) if not pd.isna(x) else -1)

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


from datetime import datetime, timedelta
from typing import Optional, Tuple

class AttendanceCalculator:
    """Calculate attendance status, overtime, missed punches, with correct Saturday logic."""

    MAX_OT_HOURS = 2
    FULL_TIMER_MIN_HOURS = 9       # Full-time threshold for OT and full day
    HALF_DAY_MIN_HOURS = 4.5       # Half-day threshold for Saturday / early leave

    @staticmethod
    def calculate_status(
        check_in: Optional[datetime],
        check_out: Optional[datetime],
        day: datetime.date,
        shift_start: datetime.time,
        shift_end: datetime.time,
        full_time: bool = True
    ) -> Tuple[str, float]:
        shift_start_dt = datetime.combine(day, shift_start)
        shift_end_dt = datetime.combine(day, shift_end)
        shift_seconds = (shift_end_dt - shift_start_dt).total_seconds()
        shift_hours = shift_seconds / 3600

        status = "Absent"
        overtime = 0.0

        # ----------------- Check-in missing -----------------
        if not check_in:
            return "Absent", 0.0

        # Normalize check-in/out
        check_in = check_in.replace(microsecond=0)
        if check_out:
            check_out = check_out.replace(microsecond=0)

        # ----------------- BASE STATUS (Mon-Fri & Sat normal for part-time) -----------------
        present_limit = shift_start_dt + timedelta(minutes=1, seconds=59)
        late_limit = shift_start_dt + timedelta(hours=1)

        if check_in <= present_limit:
            status = "Present"
        elif present_limit < check_in <= late_limit:
            status = "Late"
        else:
            status = "Half Day"

        # Early checkout reduces status
        if check_out:
            early_checkout_limit = shift_end_dt - timedelta(minutes=15)
            if check_out < early_checkout_limit:
                status = "Half Day"

        # ----------------- OVERTIME (FULL-TIME ONLY) -----------------
        if full_time and check_out:
            ot_seconds = (check_out - shift_end_dt).total_seconds()
            if ot_seconds >= 3600 and ot_seconds < 7200:
                overtime = 1.0
            elif ot_seconds >= 7200:
                overtime = 2.0

        # ----------------- SATURDAY LOGIC -----------------
        if day.weekday() == 5:  # Saturday
            if full_time:
                # Full-time Saturday rules
                worked_hours = 0.0
                if check_out:
                    worked_hours = (check_out - check_in).total_seconds() / 3600

                if worked_hours >= AttendanceCalculator.FULL_TIMER_MIN_HOURS:
                    status = "Full Day (Sat)"
                elif worked_hours >= AttendanceCalculator.HALF_DAY_MIN_HOURS:
                    status = "Half Day (Sat)"
                else:
                    status = "Absent"
            else:
                # Part-time Saturday: optional, normal weekday rules, no OT
                overtime = 0.0

        return status, overtime

    @staticmethod
    def determine_missed_punches(
        check_in: Optional[datetime],
        check_out: Optional[datetime]
    ) -> Tuple[str, str]:
        """Check if any punch is missing."""
        return ("Yes" if not check_in else "", "Yes" if not check_out else "")



# ===========================================================
#              DAILY REPORT GENERATOR (UPDATED)
# ===========================================================
class DailyReportGenerator:
    """Generate and store Daily Reports, including Sundays."""

    def __init__(self):
        self.processor = AttendanceProcessor()
        self.calculator = AttendanceCalculator()

    def update_shift_for_existing_records(self, employee_name: str, date_str: str, new_shift: str):
        """Update shift for an existing DailyReport record and recalculate status & overtime."""
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
            record = DailyReport.query.filter_by(employee_name=employee_name, date=date_obj).first()

            if not record:
                print(f"⚠️ No existing record found for {employee_name} on {date_str}")
                return

            shift_start_str, shift_end_str = [s.strip() for s in new_shift.split("-", 1)]
            shift_start = datetime.strptime(shift_start_str, "%H:%M").time()
            shift_end = datetime.strptime(shift_end_str, "%H:%M").time()

            check_in_dt = datetime.combine(date_obj, record.check_in) if record.check_in else None
            check_out_dt = datetime.combine(date_obj, record.check_out) if record.check_out else None

            status, _ = AttendanceCalculator.calculate_status(check_in_dt, check_out_dt, date_obj, shift_start, shift_end)
            overtime = DailyReportGenerator.calculate_overtime(check_in_dt, check_out_dt,
                                                               datetime.combine(date_obj, shift_start),
                                                               datetime.combine(date_obj, shift_end))

            record.shift = new_shift
            record.status = status
            record.overtime = overtime
            record.manual_override = True

            db.session.commit()
            print(f"✅ Shift, status, and overtime updated for {employee_name} on {date_str}")

        except Exception as e:
            db.session.rollback()
            print(f"❌ Error updating shift for {employee_name} on {date_str}: {e}")

    def generate_daily_report(self, employee_shifts=None, compensated_dates=None):
        employee_shifts = employee_shifts or {}
        compensated_dates = compensated_dates or {}

        inspector = inspect(db.engine)
        if "attendance_raw" not in inspector.get_table_names():
            return {"error": "No attendance data found. Please upload attendance file first.", "daily_table": []}

        df = self.processor.get_clean_attendance()
        if df.empty:
            return {"error": "No valid attendance records found.", "daily_table": []}

        daily_table = self._generate_report_data(df, employee_shifts, compensated_dates)
        return self._save_and_return_results(daily_table, df)

    def _generate_report_data(self, df, employee_shifts, compensated_dates) -> List[Dict[str, Any]]:
        employees = sorted(df["Name"].unique())
        all_dates = self._get_all_dates(df)  # Include Sundays
        records = []

        for emp in employees:
            emp_data = df[df["Name"] == emp]
            emp_id = str(emp_data["Emp ID"].iloc[0]) if not emp_data["Emp ID"].isna().all() else ""

            employee_obj = Employee.query.filter_by(name=emp).first()
            if employee_obj:
                shift_str = employee_obj.shift or "10:00 - 19:00"
                if "-" in shift_str:
                    shift_start_str, shift_end_str = [s.strip() for s in shift_str.split("-", 1)]
                else:
                    shift_start_str, shift_end_str = ("10:00", "19:00")
                department = employee_obj.department
                joining_date = employee_obj.joining_date
                last_updated_date = employee_obj.last_updated_date
            else:
                shift_start_str, shift_end_str = ("10:00", "19:00")
                department = "Cold Calling"
                joining_date = None
                last_updated_date = datetime.utcnow().date()

            start_time = datetime.strptime(shift_start_str, "%H:%M").time()
            end_time = datetime.strptime(shift_end_str, "%H:%M").time()

            for day in all_dates:
                day_data = emp_data[emp_data["Date"] == day]
                check_in, check_out = self._extract_check_times(day_data)

                # Sunday handling
                if day.weekday() == 6:  # Sunday
                    status = "Sunday"
                    overtime_hours = 0.0
                    missed_in = ""
                    missed_out = ""
                else:
                    status, _ = self.calculator.calculate_status(check_in, check_out, day, start_time, end_time)
                    overtime_hours = self.calculate_overtime(
                        check_in, check_out,
                        datetime.combine(day, start_time),
                        datetime.combine(day, end_time)
                    )
                    if str(day) in compensated_dates.get(emp, set()):
                        status = "Compensated"
                        overtime_hours = 0.0
                    missed_in, missed_out = self.calculator.determine_missed_punches(check_in, check_out)

                records.append({
                    "EmpID": emp_id,
                    "Date": day.strftime("%Y-%m-%d"),
                    "Name": emp,
                    "Shift": f"{shift_start_str} - {shift_end_str}",
                    "CheckIn": check_in.strftime("%H:%M") if check_in else "",
                    "CheckOut": check_out.strftime("%H:%M") if check_out else "",
                    "Status": status,
                    "MissedCheckIn": missed_in,
                    "MissedCheckOut": missed_out,
                    "Overtime": overtime_hours,
                    "Department": department,
                    "JoiningDate": joining_date,
                    "LastUpdatedDate": last_updated_date
                })

        records.sort(key=lambda x: (x["Name"], x["Date"]))
        return records

    @staticmethod
    def calculate_overtime(check_in, check_out, shift_start_dt, shift_end_dt):
        if not check_in or not check_out:
            return 0.0
        overtime_seconds = (check_out - shift_end_dt).total_seconds()
        if overtime_seconds <= 0:
            return 0.0
        overtime_hours = overtime_seconds / 3600
        if overtime_hours < 1:
            return 0.0
        elif overtime_hours < 2:
            return 1.0
        else:
            return 2.0

    @staticmethod
    def _get_all_dates(df: pd.DataFrame) -> List[datetime.date]:
        """Return all dates in the attendance range, including Sundays."""
        date_range = pd.date_range(df["Date"].min(), df["Date"].max())
        return [d.date() for d in date_range]

    @staticmethod
    def _extract_check_times(day_data: pd.DataFrame) -> Tuple[Optional[datetime], Optional[datetime]]:
        if day_data.empty:
            return None, None
        check_in = day_data["CheckIn"].iloc[0] if not pd.isna(day_data["CheckIn"].iloc[0]) else None
        check_out = day_data["CheckOut"].iloc[0] if not pd.isna(day_data["CheckOut"].iloc[0]) else None
        return check_in, check_out

    def _save_and_return_results(self, daily_table, df):
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
            return {"error": f"Error saving daily report: {e}", "daily_table": []}

    # _save_daily_report_to_db and _save_or_update_record logic remains unchanged


    def _save_daily_report_to_db(self, daily_table: List[Dict[str, Any]]):
        """Save or update each record in DB."""
        for row in daily_table:
            self._save_or_update_record(row)

    def _save_or_update_record(self, row: Dict[str, Any]):
        try:
            date_obj = datetime.strptime(row["Date"], "%Y-%m-%d").date()
            existing = DailyReport.query.filter_by(employee_name=row["Name"], date=date_obj).first()

            # Convert check-in/check-out strings to time objects
            check_in_time = datetime.strptime(row["CheckIn"], "%H:%M").time() if row["CheckIn"] else None
            check_out_time = datetime.strptime(row["CheckOut"], "%H:%M").time() if row["CheckOut"] else None

            # Pull latest Employee data
            emp_data = Employee.query.filter_by(name=row["Name"]).first()
            department = emp_data.department if emp_data else "Cold Calling"
            joining_date = emp_data.joining_date if emp_data else None
            last_updated_date_obj = emp_data.last_updated_date if emp_data else datetime.utcnow().date()

            # Parse shift string
            shift_start_str, shift_end_str = [s.strip() for s in row["Shift"].split("-", 1)]
            shift_start = datetime.strptime(shift_start_str, "%H:%M").time()
            shift_end = datetime.strptime(shift_end_str, "%H:%M").time()

            check_in_dt = datetime.combine(date_obj, check_in_time) if check_in_time else None
            check_out_dt = datetime.combine(date_obj, check_out_time) if check_out_time else None

            # Determine status and overtime
            if date_obj.weekday() == 6:  # Sunday
                status = "Sunday"
                overtime = 0.0
                missed_in = ""
                missed_out = ""
            else:
                status, _ = AttendanceCalculator.calculate_status(check_in_dt, check_out_dt, date_obj, shift_start, shift_end)
                overtime = DailyReportGenerator.calculate_overtime(check_in_dt, check_out_dt,
                                                               datetime.combine(date_obj, shift_start),
                                                               datetime.combine(date_obj, shift_end))
                missed_in, missed_out = AttendanceCalculator.determine_missed_punches(check_in_dt, check_out_dt)

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
            print(f"❌ Error saving daily record {row}: {e}")


# ===========================================================
#              EXTERNAL ENTRY POINT
# ===========================================================
def generate_daily_report(employee_shifts=None, compensated_dates=None):
    generator = DailyReportGenerator()
    return generator.generate_daily_report(employee_shifts, compensated_dates)
