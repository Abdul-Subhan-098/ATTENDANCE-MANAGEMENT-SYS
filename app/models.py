from datetime import datetime
from app import db
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from app import db

# ===========================================================
#               ATTENDANCE RAW 
# ===========================================================
class AttendanceRaw(db.Model):
    __tablename__ = "attendance_raw"

    id = db.Column(db.Integer, primary_key=True)
    emp_id = db.Column("Emp ID", db.Integer)
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
    joining_date = db.Column(db.Date, nullable=False)
    department = db.Column(db.String(100), nullable=False)
    last_updated_date = db.Column(db.Date, nullable=True)
    shift = db.Column(db.String(50), nullable=True)
    role = db.Column(db.String(20), nullable=False, default="FullTime")  # Added from Code A

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


# ===========================================================
#               DAILY REPORT 
# ===========================================================
class DailyReport(db.Model):
    __tablename__ = "daily_report"

    id = db.Column(db.Integer, primary_key=True) 
    emp_id = db.Column(db.Integer, nullable=False)
    date = db.Column(db.Date, nullable=False)
    employee_name = db.Column(db.String(100), nullable=False)
    joining_date = db.Column(db.Date, nullable=True)
    department = db.Column(db.String(100), default="Cold Calling")
    last_updated_date = db.Column(db.Date, nullable=True)
    role = db.Column(db.String(20), default="Full Timer") 
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
    joining_date = db.Column(db.Date, nullable=True)
    department = db.Column(db.String(100), default="Cold Calling")
    last_updated_date = db.Column(db.Date, nullable=True)
    role = db.Column(db.String(20), default="Full Timer") 
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
    report_month = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

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
    
