from datetime import datetime
from app import db
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

# ===========================================================
#               ATTENDANCE RAW 
# ===========================================================
class AttendanceRaw(db.Model):
    __tablename__ = "attendance_raw"

    id = db.Column(db.Integer, primary_key=True)
    emp_id = db.Column("Emp ID", db.String(50))
    name = db.Column("Name", db.String(255))
    time = db.Column("Time", db.DateTime)
    work_code = db.Column("Work Code", db.String(50))
    attendance_state = db.Column("Attendance State", db.String(10))
    device_name = db.Column("Device Name", db.String(255))
    upload_batch = db.Column(db.String(100), nullable=False, default='default')
    original_filename = db.Column(db.String(255))
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<AttendanceRaw {self.emp_id} - {self.name} - {self.time}>"


# ===========================================================
#               EMPLOYEE MODEL
# ===========================================================
class Employee(db.Model):
    __tablename__ = "employees"

    id = db.Column(db.Integer, primary_key=True)
    emp_id = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    gender = db.Column(db.String(20), nullable=True)  # Increased from 10
    joining_date = db.Column(db.Date, nullable=True)
    department = db.Column(db.String(100), nullable=False, default="Cold Calling") # Added default
    last_updated_date = db.Column(db.Date, nullable=True)
    shift = db.Column(db.String(50), nullable=True)
    role = db.Column(db.String(20), nullable=False, default="FullTime")

    def __repr__(self):
        return f"<Employee {self.emp_id} - {self.name}>"

    @property
    def current_shift_times(self):
        """Parse shift string and return start/end times."""
        try:
            if self.shift and '-' in self.shift:
                start_str, end_str = [s.strip() for s in self.shift.split('-')]
                return start_str, end_str
        except (ValueError, AttributeError):
            pass
        return "10:00", "19:00"  # Default shift


class DailyReport(db.Model):
    __tablename__ = "daily_report"

    id = db.Column(db.Integer, primary_key=True)
    emp_id = db.Column(db.String(50), nullable=False)
    date = db.Column(db.Date, nullable=False)
    employee_name = db.Column(db.String(100), nullable=False)
    gender = db.Column(db.String(20), nullable=True) # Increased from 10
    joining_date = db.Column(db.Date, nullable=True)
    department = db.Column(db.String(100), default="Cold Calling")
    last_updated_date = db.Column(db.Date, nullable=True)
    role = db.Column(db.String(50), default="Full Timer") # Increased from 20 just in case
    compensation_type = db.Column(db.String(20), nullable=True)
    compensated_date = db.Column(db.Date, nullable=True)
    shift = db.Column(db.String(50))
    check_in = db.Column(db.Time)
    is_company_off = db.Column(db.Boolean, default=False)
    company_off_reason = db.Column(db.String(200))
    working_day = db.Column(db.Boolean, default=True)
    check_out = db.Column(db.Time)
    status = db.Column(db.String(50))
    missed_checkin = db.Column(db.Boolean, default=False)
    missed_checkout = db.Column(db.Boolean, default=False)
    overtime = db.Column(db.Float, default=0.0)
    manual_override = db.Column(db.Boolean, default=False)
    leave_type = db.Column(db.String(20), nullable=True)

    __table_args__ = (
        db.UniqueConstraint('emp_id', 'date', name='uix_emp_date'),
    )

    def __repr__(self):
        return f"<DailyReport {self.employee_name} - {self.date}>"



# ===========================================================
#               MONTHLY REPORT
# ===========================================================
class MonthlyReport(db.Model):
    __tablename__ = "monthly_report"

    id = db.Column(db.Integer, primary_key=True)
    emp_id = db.Column(db.String(50), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    gender = db.Column(db.String(20), nullable=True)  # Increased from 10
    joining_date = db.Column(db.Date, nullable=True)
    department = db.Column(db.String(100), default="Cold Calling")
    last_updated_date = db.Column(db.Date, nullable=True)
    role = db.Column(db.String(50), default="Full Timer") # Increased from 20
    shift = db.Column(db.String(50))
    total_days = db.Column(db.Integer, default=0)
    present = db.Column(db.Integer, default=0)
    absent = db.Column(db.Integer, default=0)
    late = db.Column(db.Integer, default=0)
    half_day_weekdays = db.Column(db.Integer, default=0)
    half_day_sat = db.Column(db.Integer, default=0)
    full_day_sat = db.Column(db.Integer, default=0)
    ot_hours = db.Column(db.Float, default=0.0)
    compensated = db.Column(db.Integer, default=0)
    company_off_days = db.Column(db.Integer, default=0)
    sundays = db.Column(db.Integer, default=0)
    by_late_count = db.Column(db.Integer, default=0)
    by_half_day_count = db.Column(db.Integer, default=0)
    by_absent_count = db.Column(db.Integer, default=0)
    working_days = db.Column(db.Integer, default=0)
    punch_missed = db.Column(db.Integer, default=0)  
    report_month = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    medical_leave = db.Column(db.Integer, default=0)
    casual_leave = db.Column(db.Integer, default=0)

    def __repr__(self):
        return f"<MonthlyReport {self.name} - {self.report_month}>"



# ===========================================================
#               COMPANY DAY OFF
# ===========================================================
class CompanyDayOff(db.Model):
    __tablename__ = 'company_day_off'
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, unique=True)
    reason = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ===========================================================
#               ADMIN MODEL
# ===========================================================
class Admin(db.Model):
    __tablename__ = 'admin'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<Admin {self.username}>"


# ===========================================================
#               ACTIVITY LOG MODEL
# ===========================================================
class ActivityLog(db.Model):
    __tablename__ = "activity_logs"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=False)
    action = db.Column(db.String(255), nullable=False)
    entity_type = db.Column(db.String(100), nullable=False)
    entity_id = db.Column(db.String(100), nullable=True)
    details = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(50), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<ActivityLog {self.username} - {self.action} - {self.timestamp}>"

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "action": self.action,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "details": self.details,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "timestamp": self.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        }

# ===========================================================
#               TEMPORARY SHIFT MODEL
# ===========================================================
class TemporaryShift(db.Model):
    __tablename__ = "temporary_shifts"

    id = db.Column(db.Integer, primary_key=True)
    emp_id = db.Column(db.String(50), nullable=False)
    shift = db.Column(db.String(50), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<TemporaryShift {self.emp_id}: {self.shift} ({self.start_date} to {self.end_date})>"

# ===========================================================
#               NEW EMPLOYEE TRACKING
# ===========================================================
class NewEmployee(db.Model):
    __tablename__ = "new_employee"

    id = db.Column(db.Integer, primary_key=True)
    emp_id = db.Column(db.String(50), nullable=False, unique=True)
    name = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<NewEmployee {self.emp_id} - {self.name}>"



# ===========================================================
#               NEW LeaveApplication MODEL
# ===========================================================


class LeaveApplication(db.Model):
    __tablename__ = "leave_applications"

    id = db.Column(db.Integer, primary_key=True)
    emp_id = db.Column(db.String(50), nullable=False)
    employee_name = db.Column(db.String(120), nullable=False)
    applied_date = db.Column(db.Date, nullable=False, default=datetime.utcnow().date)
    applied_day = db.Column(db.String(10), nullable=False)  # Monday, Tuesday, etc.
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    leave_type = db.Column(db.String(20), nullable=False)  # Medical / Casual etc.
    reason = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return (
            f"<LeaveApplication {self.employee_name} | "
            f"{self.start_date} → {self.end_date} | {self.leave_type}>"
        )