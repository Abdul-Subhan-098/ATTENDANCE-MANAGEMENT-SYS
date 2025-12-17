from app import db
from app.models import AttendanceRaw, Employee, NewEmployee
from app.service.activity_service import log_activity
import logging

logger = logging.getLogger(__name__)


class NewEmployeeService:
    """
    Service responsible for detecting and tracking
    new employees from attendance uploads.
    """

    @staticmethod
    def track_from_batch(batch_id: str) -> int:
        """
        Detect employees from attendance_raw batch
        that are NOT present in employees table
        and store them in new_employee table.

        Returns number of new employees detected.
        """
        try:
            records = (
                db.session.query(AttendanceRaw.emp_id, AttendanceRaw.name)
                .filter(AttendanceRaw.upload_batch == batch_id)
                .distinct()
                .all()
            )

            inserted = 0

            for emp_id, name in records:
                emp_id = str(emp_id).strip()
                name = str(name).strip()

                if not emp_id or not name:
                    continue

                # Already confirmed employee?
                if Employee.query.filter_by(emp_id=emp_id).first():
                    continue

                # Already detected as new employee?
                if NewEmployee.query.filter_by(emp_id=emp_id).first():
                    continue

                db.session.add(
                    NewEmployee(
                        emp_id=emp_id,
                        name=name
                    )
                )
                inserted += 1

            if inserted:
                db.session.commit()

                log_activity(
                    username="System",
                    action="New employees detected from attendance",
                    entity_type="new_employee_tracking",
                    entity_id=batch_id,
                    details=f"Detected {inserted} new employees"
                )

            logger.info(
                f"[NEW EMPLOYEE SERVICE] Batch {batch_id}: "
                f"{inserted} new employees detected"
            )

            return inserted

        except Exception as e:
            db.session.rollback()
            logger.error(
                f"[NEW EMPLOYEE SERVICE ERROR] Batch {batch_id}: {e}"
            )
            return 0
        

    # =====================================================
    #        ✅ NEW METHOD: CLEANUP CONFIRMED EMPLOYEE
    # =====================================================
    @staticmethod
    def cleanup_if_employee_confirmed(emp_id: str) -> bool:
        """
        If employee profile is fully updated,
        remove record from new_employee table.

        Returns True if deleted, False otherwise.
        """
        try:
            employee = Employee.query.filter_by(emp_id=emp_id).first()
            if not employee:
                return False

            # Required fields for confirmation
            required_fields = [
                employee.shift,
                employee.department,
                employee.role,
                employee.joining_date,
                employee.gender
            ]

            # Agar koi bhi field missing ho → abhi new employee hi hai
            if not all(required_fields):
                return False

            new_emp = NewEmployee.query.filter_by(emp_id=emp_id).first()
            if not new_emp:
                return False

            db.session.delete(new_emp)
            db.session.commit()

            log_activity(
                username="System",
                action="New employee removed after profile completion",
                entity_type="new_employee_cleanup",
                entity_id=emp_id,
                details="Employee profile completed (shift, department, role, joining date, gender)"
            )

            logger.info(
                f"[NEW EMPLOYEE CLEANUP] emp_id={emp_id} removed from new_employee"
            )

            return True

        except Exception as e:
            db.session.rollback()
            logger.error(
                f"[NEW EMPLOYEE CLEANUP ERROR] emp_id={emp_id}: {e}"
            )
            return False