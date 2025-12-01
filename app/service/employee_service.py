import re
from datetime import datetime, date, timedelta, time
from typing import Optional, Tuple, Set
from flask import flash
from app import db
from app.models import Employee, DailyReport, MonthlyReport
from app.service.daily_service import AttendanceCalculator, DailyReportGenerator
import logging

# Configure logging
logger = logging.getLogger(__name__)

# ===========================================================
#              EMPLOYEE SERVICE
# ===========================================================
class EmployeeService:
    """Service for handling employee operations including CRUD and report updates."""

    def __init__(self):
        self.generator = DailyReportGenerator()
        self.calculator = AttendanceCalculator()

    def get_max_effective_date(self) -> date:
        """Return latest DailyReport date or current date if no records exist."""
        try:
            latest_date = db.session.query(db.func.max(DailyReport.date)).scalar()
            return latest_date or datetime.today().date()
        except Exception as e:
            logger.error(f"Error getting max effective date: {e}")
            return datetime.today().date()

    def validate_employee_data(self, name: str, joining_date_str: str, department: str,
                               effective_date_str: str, shift_full: str) -> None:
        """Validate all employee input data."""
        if not all([name, joining_date_str, department, effective_date_str, shift_full]):
            raise ValueError("Please provide all required fields.")

        max_effective_date = self.get_max_effective_date()
        effective_date = datetime.strptime(effective_date_str, "%Y-%m-%d").date()

        if effective_date > max_effective_date:
            raise ValueError(f"Effective date cannot be after latest record ({max_effective_date})")

        if not self._is_valid_shift_format(shift_full):
            raise ValueError("Invalid shift format. Use HH:MM - HH:MM")

    def _is_valid_shift_format(self, shift_str: str) -> bool:
        """Validate shift format using regex."""
        shift_pattern = r"(\d{2}:\d{2}\s*-\s*\d{2}:\d{2})"
        return bool(re.match(shift_pattern, shift_str))

    def add_or_update_employee(self, name: str, joining_date_str: str, department: str,
                               effective_date_str: str, shift_full: str, role: Optional[str] = None) -> bool:
        """Add or update employee and update related reports. Accepts optional role."""
        try:
            self.validate_employee_data(name, joining_date_str, department, effective_date_str, shift_full)

            joining_date = datetime.strptime(joining_date_str, "%Y-%m-%d").date()
            effective_date = datetime.strptime(effective_date_str, "%Y-%m-%d").date()
            shift_main = self._extract_shift_from_string(shift_full)

            employee = self._save_employee_data(name, joining_date, department, effective_date, shift_main, role)
            self._update_related_reports(employee, effective_date)

            flash(f"✅ Employee '{name}' ({employee.role}) processed successfully effective from {effective_date}", "success")
            return True

        except Exception as e:
            db.session.rollback()
            error_message = f"Error processing employee: {e}"
            logger.error(error_message)
            flash(f"❌ {error_message}", "error")
            return False

    def _extract_shift_from_string(self, shift_full: str) -> str:
        """Extract and format shift string from input."""
        match = re.match(r"(\d{2}:\d{2}\s*-\s*\d{2}:\d{2})", shift_full)
        if not match:
            raise ValueError("Invalid shift format")
        return match.group(1)

    def _save_employee_data(self, name: str, joining_date: date, department: str,
                            effective_date: date, shift_main: str, role: Optional[str]) -> Employee:
        """Save or update employee record in database. Preserves existing role if role param omitted."""
        employee = Employee.query.filter_by(name=name).first()

        if employee:
            # Preserve existing role if role not explicitly provided
            role_to_use = role if role else employee.role
            self._update_existing_employee(employee, joining_date, department, effective_date, shift_main, role_to_use)
            action = "Updated"
        else:
            # Use default role if none provided
            role_to_use = role or "FullTime"
            employee = self._create_new_employee(name, joining_date, department, effective_date, shift_main, role_to_use)
            action = "Added new"

        db.session.commit()
        logger.info(f"{action} employee '{name}' ({role_to_use}) effective from {effective_date}")
        return employee

    def _update_existing_employee(self, employee: Employee, joining_date: date, department: str,
                                  effective_date: date, shift_main: str, role: str):
        """Update existing employee record."""
        employee.joining_date = joining_date
        employee.department = department
        employee.last_updated_date = effective_date
        employee.shift = shift_main
        employee.role = role  # Preserve / update role

    def _create_new_employee(self, name: str, joining_date: date, department: str,
                             effective_date: date, shift_main: str, role: str) -> Employee:
        """Create new employee record."""
        employee = Employee(
            name=name,
            joining_date=joining_date,
            department=department,
            last_updated_date=effective_date,
            shift=shift_main,
            role=role  # Set role
        )
        db.session.add(employee)
        return employee

    def _update_related_reports(self, employee: Employee, effective_date: date):
        """Update daily and monthly reports for the employee."""
        try:
            affected_months = self._update_daily_reports(employee, effective_date)
            self._update_monthly_reports(employee, affected_months)
            logger.info(f"Updated reports for employee '{employee.name}' from {effective_date}")
        except Exception as e:
            logger.error(f"Error updating reports for employee '{employee.name}': {e}")
            raise

    def _update_daily_reports(self, employee: Employee, effective_date: date) -> Set[str]:
        """Update daily reports for the employee and return affected months."""
        daily_rows = DailyReport.query.filter(
            DailyReport.employee_name == employee.name,
            DailyReport.date >= effective_date
        ).all()

        if not daily_rows:
            return set()

        shift_start, shift_end = self._parse_employee_shift(employee)
        affected_months = set()

        for daily_record in daily_rows:
            self._update_single_daily_record(daily_record, employee, shift_start, shift_end)
            affected_months.add(daily_record.date.strftime("%Y-%m"))

        db.session.commit()
        return affected_months

    def _update_single_daily_record(self, daily_record: DailyReport, employee: Employee,
                                    shift_start: time, shift_end: time):
        """Update a single daily record with new employee data - FIXED Saturday OT logic."""
        daily_record.shift = employee.shift
        daily_record.department = employee.department
        daily_record.joining_date = employee.joining_date
        daily_record.last_updated_date = employee.last_updated_date
        daily_record.role = employee.role  # Always from Employee table (added from A)
        daily_record.manual_override = True

        # ---------- SUNDAY CHECK (FIRST PRIORITY) ----------
        if daily_record.date.weekday() == 6:  # Sunday
            daily_record.status = "Sunday"
            daily_record.overtime = 0.0
            daily_record.missed_checkin = False
            daily_record.missed_checkout = False
            return  # Sunday ke liye calculation skip karo

        # ---------- DETERMINE FULL-TIME STATUS ----------
        shift_start_dt = datetime.combine(daily_record.date, shift_start)
        shift_end_dt = datetime.combine(daily_record.date, shift_end)
        shift_duration = (shift_end_dt - shift_start_dt).total_seconds() / 3600.0
        full_time = shift_duration >= 9.0  # FULL_TIMER_MIN_HOURS

        # Recalculate status and overtime only for non-Sunday days
        check_in_dt = datetime.combine(daily_record.date, daily_record.check_in) if daily_record.check_in else None
        check_out_dt = datetime.combine(daily_record.date, daily_record.check_out) if daily_record.check_out else None

        # Use the UPDATED calculate_status method with full_time parameter
        daily_record.status, daily_record.overtime = self.calculator.calculate_status(
            check_in_dt, check_out_dt, daily_record.date, shift_start, shift_end, full_time
        )

        # Update missed punches
        missed_in, missed_out = self.calculator.determine_missed_punches(check_in_dt, check_out_dt)
        daily_record.missed_checkin = (missed_in == "Yes")
        daily_record.missed_checkout = (missed_out == "Yes")

        logger.debug(f"Updated {employee.name} - {daily_record.date}: Status={daily_record.status}, OT={daily_record.overtime}, FullTime={full_time}")

    def _update_monthly_reports(self, employee: Employee, affected_months: Set[str]):
        """Update monthly reports for affected months with recalculated metrics."""
        for month in affected_months:
            # Delete existing monthly records for this employee and month
            MonthlyReport.query.filter(
                MonthlyReport.name == employee.name,
                MonthlyReport.report_month == month
            ).delete()

        db.session.commit()

        # Regenerate monthly reports for all affected months using UPDATED logic
        for month in affected_months:
            self._regenerate_monthly_report(employee.name, month)

    def _regenerate_monthly_report(self, employee_name: str, month_str: str):
        """Regenerate monthly report with correct Sunday count, Sat types,
        and weekday-only OT (Saturday OT excluded)."""

        try:
            # -------------------------
            # Date Range Setup
            # -------------------------
            start_date = datetime.strptime(f"{month_str}-01", "%Y-%m-%d").date()
            next_month = start_date.replace(day=28) + timedelta(days=4)
            end_date = next_month.replace(day=1)

            daily_records = DailyReport.query.filter(
                DailyReport.employee_name == employee_name,
                DailyReport.date >= start_date,
                DailyReport.date < end_date
            ).order_by(DailyReport.date).all()

            if not daily_records:
                logger.info(f"No daily records for {employee_name} in {month_str}")
                return

            # -------------------------
            # Employee Fetch
            # -------------------------
            employee = Employee.query.filter_by(name=employee_name).first()
            if not employee:
                logger.warning(f"Employee {employee_name} not found for monthly report {month_str}")
                return

            # -------------------------
            # Determine full-time status via shift duration
            # -------------------------
            is_full_time = True
            if employee.shift:
                try:
                    parts = employee.shift.split('-')
                    if len(parts) == 2:
                        st = datetime.strptime(parts[0].strip(), "%H:%M").time()
                        et = datetime.strptime(parts[1].strip(), "%H:%M").time()
                        hrs = (datetime.combine(date.today(), et) - 
                            datetime.combine(date.today(), st)).total_seconds() / 3600

                        is_full_time = hrs >= 9
                except:
                    pass

            # -------------------------
            # Counters - UPDATED with all Code A + Code B fields
            # -------------------------
            present = absent = late = 0
            half_day_weekdays = 0
            half_day_sat = 0          
            full_day_sat = 0          
            compensated = 0
            sundays = 0                
            by_late_count = 0
            by_half_day_count = 0
            by_absent_count = 0
            weekday_ot_hours = 0.0     
            total_days = len(daily_records)

            # -------------------------
            # Loop Records
            # -------------------------
            for row in daily_records:
                status = row.status or ""

                # ----- Status Count -----
                if status == "Present":
                    present += 1
                elif status == "Absent":
                    absent += 1
                elif status == "Late":
                    late += 1
                elif status == "Half Day":
                    half_day_weekdays += 1
                elif status == "Compensated":
                    compensated += 1
                elif status == "Sunday":
                    sundays += 1
                elif status == "Half Day (Sat)":  
                    half_day_sat += 1
                elif status == "Full Day (Sat)":   
                    full_day_sat += 1

                # ----- Compensation Type Counts (Code B se) -----
                if hasattr(row, 'compensation_type') and row.compensation_type:
                    if row.compensation_type == "By Late":
                        by_late_count += 1
                    elif row.compensation_type == "By Half Day":
                        by_half_day_count += 1
                    elif row.compensation_type == "By Absent":
                        by_absent_count += 1

                # ----- Weekday Overtime ONLY -----
                if is_full_time:
                    wd = row.date.weekday() 

                    if wd in (0, 1, 2, 3, 4): 
                        weekday_ot_hours += float(row.overtime or 0.0)

            # -------------------------
            # Save Monthly Report
            # -------------------------
            monthly_report = MonthlyReport(
                emp_id=employee.emp_id,
                name=employee_name,
                joining_date=employee.joining_date,
                department=employee.department or "Cold Calling",
                last_updated_date=datetime.utcnow().date(),
                shift=employee.shift,
                role=employee.role,  
                report_month=month_str,
                total_days=total_days,
                present=present,
                absent=absent,
                late=late,
                half_day_weekdays=half_day_weekdays,
                half_day_sat=half_day_sat,
                full_day_sat=full_day_sat,                
                compensated=compensated,
                sundays=sundays,
                ot_hours=round(weekday_ot_hours, 2),
                by_late_count=by_late_count,
                by_half_day_count=by_half_day_count,
                by_absent_count=by_absent_count
            )

            db.session.add(monthly_report)
            db.session.commit()

            logger.info(
                f"[MONTHLY REPORT ✔] {employee_name} {month_str} | "
                f"OT(Weekdays): {weekday_ot_hours:.2f} | "
                f"Sun: {sundays}, Sat: Half {half_day_sat}, Full {full_day_sat} | "
                f"Comp Counts: Late={by_late_count}, Half={by_half_day_count}, Absent={by_absent_count}"
            )

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error regenerating monthly report for {employee_name} - {month_str}: {e}")

    def _parse_employee_shift(self, employee: Employee) -> Tuple[time, time]:
        """Parse employee shift string into time objects."""
        try:
            shift_start_str, shift_end_str = [s.strip() for s in employee.shift.split("-", 1)]
            shift_start = datetime.strptime(shift_start_str, "%H:%M").time()
            shift_end = datetime.strptime(shift_end_str, "%H:%M").time()
            return shift_start, shift_end
        except (ValueError, AttributeError) as e:
            logger.error(f"Error parsing shift for employee '{employee.name}': {e}")
            # Return default shift times
            default_start = datetime.strptime("10:00", "%H:%M").time()
            default_end = datetime.strptime("19:00", "%H:%M").time()
            return default_start, default_end

    def get_employee_by_name(self, name: str) -> Optional[Employee]:
        """Get employee by name with error handling."""
        try:
            return Employee.query.filter_by(name=name).first()
        except Exception as e:
            logger.error(f"Error fetching employee '{name}': {e}")
            return None

    def get_all_employees(self) -> list:
        """Get all employees with error handling."""
        try:
            return Employee.query.order_by(Employee.name).all()
        except Exception as e:
            logger.error(f"Error fetching all employees: {e}")
            return []


# ===========================================================
#              EXTERNAL ENTRY POINTS
# ===========================================================
def add_or_update_employee(name: str, joining_date_str: str, department: str,
                           effective_date_str: str, shift_full: str, role: Optional[str] = None) -> bool:
    """External entry point for adding or updating employees (supports optional role)."""
    service = EmployeeService()
    return service.add_or_update_employee(name, joining_date_str, department, effective_date_str, shift_full, role)

def get_max_effective_date() -> date:
    """External entry point for getting max effective date."""
    service = EmployeeService()
    return service.get_max_effective_date()
