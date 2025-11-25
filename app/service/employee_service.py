import re
from datetime import datetime, date, timedelta , time
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
                             effective_date_str: str, shift_full: str) -> bool:
        """Add or update employee and update related reports."""
        try:
            self.validate_employee_data(name, joining_date_str, department, effective_date_str, shift_full)
            
            joining_date = datetime.strptime(joining_date_str, "%Y-%m-%d").date()
            effective_date = datetime.strptime(effective_date_str, "%Y-%m-%d").date()
            shift_main = self._extract_shift_from_string(shift_full)

            employee = self._save_employee_data(name, joining_date, department, effective_date, shift_main)
            self._update_related_reports(employee, effective_date)
            
            flash(f"✅ Employee '{name}' processed successfully effective from {effective_date}", "success")
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
                          effective_date: date, shift_main: str) -> Employee:
        """Save or update employee record in database."""
        employee = Employee.query.filter_by(name=name).first()
        
        if employee:
            self._update_existing_employee(employee, joining_date, department, effective_date, shift_main)
            action = "Updated"
        else:
            employee = self._create_new_employee(name, joining_date, department, effective_date, shift_main)
            action = "Added new"
        
        db.session.commit()
        logger.info(f"{action} employee '{name}' effective from {effective_date}")
        return employee

    def _update_existing_employee(self, employee: Employee, joining_date: date, department: str,
                                effective_date: date, shift_main: str):
        """Update existing employee record."""
        employee.joining_date = joining_date
        employee.department = department
        employee.last_updated_date = effective_date
        employee.shift = shift_main

    def _create_new_employee(self, name: str, joining_date: date, department: str,
                           effective_date: date, shift_main: str) -> Employee:
        """Create new employee record."""
        employee = Employee(
            name=name,
            joining_date=joining_date,
            department=department,
            last_updated_date=effective_date,
            shift=shift_main
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
        """Regenerate monthly report for a specific employee and month - FIXED with new OT logic."""
        try:
            # Parse month
            start_date = datetime.strptime(f"{month_str}-01", "%Y-%m-%d").date()
            next_month = start_date.replace(day=28) + timedelta(days=4)
            end_date = next_month.replace(day=1)
            
            # Get all daily records for this employee in the month
            daily_records = DailyReport.query.filter(
                DailyReport.employee_name == employee_name,
                DailyReport.date >= start_date,
                DailyReport.date < end_date
            ).order_by(DailyReport.date).all()
            
            if not daily_records:
                return
                
            # Get employee data
            employee = Employee.query.filter_by(name=employee_name).first()
            if not employee:
                return

            # Determine if employee is full-time based on current shift
            is_full_time = True
            if employee and employee.shift:
                try:
                    shift_parts = employee.shift.split('-')
                    if len(shift_parts) == 2:
                        shift_start = datetime.strptime(shift_parts[0].strip(), "%H:%M").time()
                        shift_end = datetime.strptime(shift_parts[1].strip(), "%H:%M").time()
                        shift_start_dt = datetime.combine(date.today(), shift_start)
                        shift_end_dt = datetime.combine(date.today(), shift_end)
                        shift_duration = (shift_end_dt - shift_start_dt).total_seconds() / 3600.0
                        is_full_time = shift_duration >= 9.0
                except Exception as e:
                    logger.warning(f"Error calculating full-time status for {employee_name}: {e}")
                
            # Initialize counters - UPDATED: No separate Saturday columns
            present_count = 0
            absent_count = 0
            late_count = 0
            half_day_weekdays_count = 0
            overtime_hours = 0.0
            compensated_count = 0
            total_days = len(daily_records)
            
            # Calculate metrics from daily records - UPDATED LOGIC
            for daily_record in daily_records:
                status = daily_record.status or ""
                
                # Status counting - simplified without Saturday-specific columns
                if status == "Present":
                    present_count += 1
                elif status == "Absent":
                    absent_count += 1
                elif status == "Late":
                    late_count += 1
                elif status == "Half Day":
                    half_day_weekdays_count += 1
                elif status == "Compensated":
                    compensated_count += 1
                
                # Overtime calculation - UPDATED for Saturday logic
                daily_overtime = float(daily_record.overtime or 0.0)
                
                # For full-timers on Saturday, ensure all hours are counted as OT
                if (daily_record.date.weekday() == 5 and  # Saturday
                    is_full_time and 
                    daily_record.check_in and 
                    daily_record.check_out):
                    
                    # Calculate actual hours worked on Saturday
                    check_in_dt = datetime.combine(daily_record.date, daily_record.check_in)
                    check_out_dt = datetime.combine(daily_record.date, daily_record.check_out)
                    saturday_hours = max(0.0, (check_out_dt - check_in_dt).total_seconds() / 3600.0)
                    
                    # Use the actual hours worked as OT (override any previous calculation)
                    daily_overtime = saturday_hours
                    logger.debug(f"Saturday OT for {employee_name} on {daily_record.date}: {saturday_hours} hours")
                
                overtime_hours += daily_overtime
            
            # Create or update monthly report - UPDATED structure
            monthly_report = MonthlyReport(
                emp_id=employee.emp_id or daily_records[0].emp_id,
                name=employee_name,
                department=employee.department or "Cold Calling",
                joining_date=employee.joining_date,
                last_updated_date=employee.last_updated_date or datetime.utcnow().date(),
                shift=employee.shift,
                report_month=month_str,
                total_days=total_days,
                present=present_count,
                absent=absent_count,
                late=late_count,
                half_day_weekdays=half_day_weekdays_count,
                half_day_sat=0,  # Deprecated column - set to 0
                full_day_sat=0,  # Deprecated column - set to 0
                ot_hours=round(overtime_hours, 2),
                compensated=compensated_count
            )
            
            db.session.add(monthly_report)
            db.session.commit()
            
            logger.info(f"Regenerated monthly report for {employee_name} - {month_str}: "
                       f"Present={present_count}, OT={overtime_hours}, FullTime={is_full_time}")
            
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
                          effective_date_str: str, shift_full: str) -> bool:
    """External entry point for adding or updating employees."""
    service = EmployeeService()
    return service.add_or_update_employee(name, joining_date_str, department, effective_date_str, shift_full)

def get_max_effective_date() -> date:
    """External entry point for getting max effective date."""
    service = EmployeeService()
    return service.get_max_effective_date()