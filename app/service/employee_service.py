# app/services/employee_service.py
import re
from datetime import datetime
from flask import flash
from app import db
from app.models import Employee, DailyReport, MonthlyReport
from app.service.daily_service import AttendanceCalculator
from app.service.daily_service import DailyReportGenerator

class EmployeeService:
    def __init__(self):
        self.generator = DailyReportGenerator()

    def get_max_effective_date(self):
        """Return latest DailyReport date"""
        latest_date = db.session.query(db.func.max(DailyReport.date)).scalar()
        return latest_date or datetime.today().date()

    def validate_employee_data(self, name, joining_date_str, department, effective_date_str, shift_full):
        """Validate all inputs, raise ValueError on error"""
        if not all([name, joining_date_str, department, effective_date_str, shift_full]):
            raise ValueError("Please provide all required fields.")

        max_effective_date = self.get_max_effective_date()
        effective_date = datetime.strptime(effective_date_str, "%Y-%m-%d").date()

        if effective_date > max_effective_date:
            raise ValueError(f"Effective date cannot be after latest record ({max_effective_date})")

        # ✅ Removed restriction on older effective dates
        # Now you can apply updates retroactively

        if not re.match(r"(\d{2}:\d{2}\s*-\s*\d{2}:\d{2})", shift_full):
            raise ValueError("Invalid shift format.")

    def add_or_update_employee(self, name, joining_date_str, department, effective_date_str, shift_full):
        """Add/update employee & update daily & monthly reports"""
        try:
            # Validate inputs
            self.validate_employee_data(name, joining_date_str, department, effective_date_str, shift_full)

            # Parse values
            joining_date = datetime.strptime(joining_date_str, "%Y-%m-%d").date()
            effective_date = datetime.strptime(effective_date_str, "%Y-%m-%d").date()
            shift_main = re.match(r"(\d{2}:\d{2}\s*-\s*\d{2}:\d{2})", shift_full).group(1)

            # --- Add/update Employee ---
            emp = Employee.query.filter_by(name=name).first()
            if emp:
                emp.joining_date = joining_date
                emp.department = department
                emp.last_updated_date = effective_date
                emp.shift = shift_main
                flash(f"✅ Updated '{name}' effective from {effective_date}", "success")
            else:
                emp = Employee(
                    name=name,
                    joining_date=joining_date,
                    department=department,
                    last_updated_date=effective_date,
                    shift=shift_main
                )
                db.session.add(emp)
                flash(f"✅ Added new employee '{name}' effective from {effective_date}", "success")
            db.session.commit()

            # --- Update Daily & Monthly Reports ---
            self._update_daily_reports(emp, effective_date)
            flash(f"✅ Employee, Daily & Monthly reports updated for '{name}' from {effective_date}.", "success")
            return True

        except Exception as e:
            db.session.rollback()
            flash(f"❌ Error: {e}", "error")
            return False

    def _update_daily_reports(self, emp, effective_date):
        """Internal: update daily and monthly reports"""
        daily_rows = DailyReport.query.filter(
            DailyReport.employee_name == emp.name,
            DailyReport.date >= effective_date
        ).all()

        affected_months = set()
        shift_start_str, shift_end_str = [s.strip() for s in emp.shift.split("-", 1)]
        shift_start = datetime.strptime(shift_start_str, "%H:%M").time()
        shift_end = datetime.strptime(shift_end_str, "%H:%M").time()

        for row in daily_rows:
            row.shift = emp.shift
            row.department = emp.department
            row.joining_date = emp.joining_date
            row.last_updated_date = emp.last_updated_date
            row.manual_override = True

            check_in_dt = datetime.combine(row.date, row.check_in) if row.check_in else None
            check_out_dt = datetime.combine(row.date, row.check_out) if row.check_out else None

            row.status, _ = AttendanceCalculator.calculate_status(
                check_in_dt, check_out_dt, row.date, shift_start, shift_end
            )
            row.overtime = self.generator.calculate_overtime(
                check_in_dt, check_out_dt,
                datetime.combine(row.date, shift_start),
                datetime.combine(row.date, shift_end)
            )
            affected_months.add(row.date.strftime("%Y-%m"))

        db.session.commit()

        # Monthly updates
        for month in affected_months:
            monthly_records = MonthlyReport.query.filter(
                MonthlyReport.name == emp.name,
                MonthlyReport.report_month == month
            ).all()
            for monthly_rec in monthly_records:
                monthly_rec.department = emp.department
                monthly_rec.joining_date = emp.joining_date
                monthly_rec.last_updated_date = emp.last_updated_date
                monthly_rec.shift = emp.shift
        db.session.commit()
