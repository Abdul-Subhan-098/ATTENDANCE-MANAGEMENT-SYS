from datetime import datetime, timedelta, date
from typing import Tuple, Set
import logging

from app import db
from app.models import DailyReport, Employee, LeaveApplication
from app.service.activity_service import log_activity
from app.service.employee_service import EmployeeService

logger = logging.getLogger(__name__)


class LeaveService:
    """
    FINAL Leave Service
    ------------------
    ✔ DailyReport = source of truth
    ✔ MonthlyReport auto-regenerates
    ✔ Medical weekend logic handled
    """

    def __init__(self):
        self.employee_service = EmployeeService()

    # ==========================================================
    # MONTH HELPERS
    # ==========================================================
    def _get_affected_months(self, start_date: date, end_date: date) -> Set[str]:
        months = set()
        current = start_date.replace(day=1)

        while current <= end_date:
            months.add(current.strftime("%Y-%m"))
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1)
            else:
                current = current.replace(month=current.month + 1)

        return months

    # ==========================================================
    # MEDICAL WEEKEND LOGIC
    # ==========================================================
    def _apply_medical_weekend(self, employee_name: str, leave_day: date):
        weekday = leave_day.weekday()

        if weekday == 4:        # Friday
            sat_day = leave_day + timedelta(days=1)
            sun_day = leave_day + timedelta(days=2)
        elif weekday == 0:      # Monday
            sat_day = leave_day - timedelta(days=2)
            sun_day = leave_day - timedelta(days=1)
        else:
            return

        sat = DailyReport.query.filter_by(
            employee_name=employee_name, date=sat_day
        ).first()
        sun = DailyReport.query.filter_by(
            employee_name=employee_name, date=sun_day
        ).first()

        if not sat or not sun:
            return

        # SATURDAY ABSENT → Sat + Sun = Medical
        if not (sat.check_in or sat.check_out):
            for dr in (sat, sun):
                dr.status = "Medical"
                dr.leave_type = "Medical"
                dr.manual_override = True
                dr.working_day = False
                dr.overtime = 0.0
                dr.missed_checkin = False
                dr.missed_checkout = False
                db.session.add(dr)

        # SATURDAY PRESENT → Sun = Sunday
        else:
            sun.status = "Sunday"
            sun.leave_type = None
            sun.manual_override = False
            sun.working_day = False
            sun.overtime = 0.0
            sun.missed_checkin = False
            sun.missed_checkout = False
            db.session.add(sun)

    # ==========================================================
    # APPLY LEAVE
    # ==========================================================
    def apply_leave(
        self,
        employee_name: str,
        start_date_str: str,
        end_date_str: str,
        leave_type: str,
        reason: str = None
    ) -> Tuple[bool, str]:

        try:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()

            employee = Employee.query.filter_by(name=employee_name).first()
            if not employee:
                return False, "Employee not found"

            overlap = LeaveApplication.query.filter(
                LeaveApplication.employee_name == employee_name,
                LeaveApplication.start_date <= end_date,
                LeaveApplication.end_date >= start_date
            ).first()
            if overlap:
                return False, "Leave already exists in this range"

            leave = LeaveApplication(
                emp_id=employee.emp_id,
                employee_name=employee.name,
                applied_date=datetime.utcnow().date(),
                applied_day=datetime.utcnow().strftime("%A"),
                start_date=start_date,
                end_date=end_date,
                leave_type=leave_type,
                reason=reason
            )
            db.session.add(leave)

            shift_start, shift_end = self.employee_service._parse_employee_shift(employee)

            current = start_date
            while current <= end_date:
                dr = DailyReport.query.filter_by(
                    employee_name=employee_name,
                    date=current
                ).first()

                if dr:
                    dr.status = leave_type
                    dr.leave_type = leave_type
                    dr.manual_override = True
                    dr.working_day = False
                    dr.overtime = 0.0
                    dr.missed_checkin = False
                    dr.missed_checkout = False
                    db.session.add(dr)

                    if leave_type.lower() == "medical":
                        self._apply_medical_weekend(employee_name, current)

                    self.employee_service._update_single_daily_record(
                        dr, employee, shift_start, shift_end
                    )

                current += timedelta(days=1)

            db.session.commit()

            # 🔥 MONTHLY REGENERATION (FIX)
            affected_months = self._get_affected_months(start_date, end_date)
            for month in affected_months:
                self.employee_service._regenerate_monthly_report(employee_name, month)

            log_activity(
                username="Admin",
                action="Leave Applied",
                entity_type="leave",
                entity_id=f"{employee.emp_id}_{start_date}_{end_date}",
                details=f"{leave_type} leave applied"
            )

            return True, "Leave applied successfully"

        except Exception as e:
            db.session.rollback()
            logger.error(e)
            return False, str(e)

    # ==========================================================
    # REMOVE LEAVE
    # ==========================================================
    def remove_leave(
        self,
        employee_name: str,
        start_date_str: str,
        end_date_str: str
    ) -> Tuple[bool, str]:

        try:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()

            employee = Employee.query.filter_by(name=employee_name).first()
            if not employee:
                return False, "Employee not found"

            shift_start, shift_end = self.employee_service._parse_employee_shift(employee)

            def reset(dr: DailyReport):
                dr.leave_type = None
                dr.manual_override = False
                dr.working_day = True

                if dr.date.weekday() == 6:
                    dr.status = "Sunday"
                    dr.overtime = 0.0
                    dr.missed_checkin = False
                    dr.missed_checkout = False
                else:
                    ci = datetime.combine(dr.date, dr.check_in) if dr.check_in else None
                    co = datetime.combine(dr.date, dr.check_out) if dr.check_out else None

                    dr.status, dr.overtime = self.employee_service.calculator.calculate_status(
                        ci, co, dr.date, shift_start, shift_end, True
                    )

                    mi, mo = self.employee_service.calculator.determine_missed_punches(ci, co)
                    dr.missed_checkin = (mi == "Yes")
                    dr.missed_checkout = (mo == "Yes")

                db.session.add(dr)

            records = DailyReport.query.filter(
                DailyReport.employee_name == employee_name,
                DailyReport.date >= start_date,
                DailyReport.date <= end_date
            ).all()

            for dr in records:
                if dr.leave_type:
                    leave_type = dr.leave_type
                    weekday = dr.date.weekday()
                    reset(dr)

                    if leave_type.lower() == "medical":
                        offsets = []
                        if weekday == 4:
                            offsets = [1, 2]
                        elif weekday == 0:
                            offsets = [-2, -1]

                        for offset in offsets:
                            extra_day = dr.date + timedelta(days=offset)
                            extra_dr = DailyReport.query.filter_by(
                                employee_name=employee_name,
                                date=extra_day
                            ).first()
                            if extra_dr and extra_dr.leave_type == "Medical":
                                reset(extra_dr)

            LeaveApplication.query.filter(
                LeaveApplication.employee_name == employee_name,
                LeaveApplication.start_date <= end_date,
                LeaveApplication.end_date >= start_date
            ).delete()

            db.session.commit()

            # 🔥 MONTHLY REGENERATION (FIX)
            affected_months = self._get_affected_months(start_date, end_date)
            for month in affected_months:
                self.employee_service._regenerate_monthly_report(employee_name, month)

            return True, "Leave removed successfully"

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error removing leave: {e}")
            return False, str(e)

    # ==========================================================
    # GET ALL LEAVES
    # ==========================================================
    def get_all_leave_applications(self):
        try:
            return LeaveApplication.query.order_by(
                LeaveApplication.applied_date.desc()
            ).all()
        except Exception as e:
            logger.error(f"Error fetching leave history: {e}")
            return []