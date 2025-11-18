# app/routes.py

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from app import db
from app.models import AttendanceRaw, MonthlyReport, DailyReport, Employee, Admin
from datetime import datetime
from sqlalchemy import func
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
import re
import time

from app.service.daily_service import generate_daily_report, DailyReportGenerator, AttendanceCalculator
from app.service.monthly_service import generate_monthly_report_from_daily
from app.service.file_service import FileService
from app.service.employee_service import EmployeeService

main = Blueprint("main", __name__)

# ===========================================================
# GLOBAL VARIABLES
# ===========================================================
employee_shifts = {}  # {"Name": ("10:00", "19:00")}
compensated_dates = {}  # {"Name": {"2025-10-13"}}
_last_daily_cache = {"data": None, "timestamp": 0}  # Cache for daily reports

# ===========================================================
# AUTHENTICATION DECORATORS & HELPERS
# ===========================================================

def login_required(f):
    """Decorator to require login for protected routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session:
            flash("⚠️ Please log in first!", "warning")
            return redirect(url_for('main.login'))
        return f(*args, **kwargs)
    return decorated_function

def load_attendance_from_db():
    """Load all attendance records from database"""
    records = AttendanceRaw.query.all()
    return records if records else []

def load_employees():
    """Load unique employee names from attendance records"""
    employees = db.session.query(AttendanceRaw.name).distinct().all()
    return sorted([emp[0] for emp in employees])

def initialize_employee_shifts(employees):
    """Initialize default shifts for employees"""
    global employee_shifts
    if not employee_shifts and employees:
        employee_shifts = {name: ("10:00", "19:00") for name in employees}

def load_monthly_summary():
    """Load monthly summary dynamically from DailyReport via monthly_service"""
    return generate_monthly_report_from_daily()

def load_monthly_summary_fast():
    """Load precomputed MonthlyReport data instantly"""
    records = MonthlyReport.query.order_by(MonthlyReport.name).all()
    result = []
    for r in records:
        result.append({
            "EmpID": r.emp_id or "",
            "Name": r.name or "",
            "Shift": r.shift or "",
            "Department": r.department or "",
            "TotalDays": r.total_days or 0,
            "Present": r.present or 0,
            "Absent": r.absent or 0,
            "Late": r.late or 0,
            "HalfDayWeekdays": r.half_day_weekdays or 0,
            "HalfDaySat": r.half_day_sat or 0,
            "FullDaySat": r.full_day_sat or 0,
            "Overtime": r.ot_hours or 0,
            "JoiningDate": r.joining_date.strftime("%Y-%m-%d") if r.joining_date else "",
            "LastUpdated": r.last_updated_date.strftime("%Y-%m-%d") if r.last_updated_date else "",
        })
    return result

def get_daily_report_cached():
    """Get daily report with caching mechanism"""
    global _last_daily_cache
    now = time.time()
    if _last_daily_cache["data"] and now - _last_daily_cache["timestamp"] < 300:
        return _last_daily_cache["data"]

    try:
        result = generate_daily_report()
    except Exception as e:
        result = {"error": f"Failed to generate report: {e}", "daily_table": []}

    _last_daily_cache = {"data": result, "timestamp": now}
    return result

def clear_daily_cache():
    """Clear daily report cache"""
    global _last_daily_cache
    _last_daily_cache = {"data": None, "timestamp": 0}

# ===========================================================
# AUTHENTICATION ROUTES
# ===========================================================

@main.route('/login', methods=['GET', 'POST'])
def login():
    """
    Route: User Login
    Template: login.html
    Service: Admin model authentication
    """
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            flash("❌ All fields are required", "error")
            return redirect(url_for('main.login'))

        admin = Admin.query.filter_by(username=username).first()

        if admin and check_password_hash(admin.password_hash, password):
            session['admin_id'] = admin.id
            session['admin_username'] = admin.username
            flash("✅ Logged in successfully!", "success")
            return redirect(url_for('main.employees'))
        else:
            flash("❌ Invalid username or password", "error")
            return redirect(url_for('main.login'))

    return render_template('login.html')

@main.route("/logout")
@login_required
def logout():
    """
    Route: User Logout
    Service: Session management
    """
    session.clear()
    flash("✅ Logged out successfully!", "success")
    return redirect(url_for('main.login'))

# ===========================================================
# DASHBOARD & MAIN ROUTES
# ===========================================================

@main.route("/", methods=["GET"])
@login_required
def index():
    """
    Route: Monthly Summary Dashboard
    Template: index.html
    Service: MonthlyReport model, monthly_service
    """
    employees = load_employees()
    initialize_employee_shifts(employees)
    table = load_monthly_summary_fast()
    
    return render_template(
        "index.html", 
        message=None, 
        table=table, 
        employees=employees, 
        employee_shifts=employee_shifts
    )

@main.route("/daily", methods=["GET"])
@login_required
def daily():
    """
    Route: Daily Report View
    Template: daily.html  
    Service: DailyReport model, daily_service
    """
    try:
        query = DailyReport.query.order_by(DailyReport.date.desc())
        total_count = query.count()

        records = query.limit(100).all()

        shift_mapping = {
            "09:00 - 18:00": "(07:00 to 04:00)",
            "10:00 - 19:00": "(08:00 to 05:00)",
            "11:00 - 20:00": "(09:00 to 06:00)",
            "11:30 - 20:30": "(09:30 to 06:30)",
            "09:00 - 13:30": "(07:00 to 11:30)",
            "10:00 - 14:30": "(08:00 to 12:30)",
            "09:00 - 14:30": "(07:00 to 12:30)",
        }

        daily_table = [
            {
                "EmpID": r.emp_id,
                "Date": r.date.strftime("%Y-%m-%d"),
                "Name": r.employee_name,
                "Shift": r.shift,
                "ShiftDisplay": f"{r.shift} {shift_mapping.get(r.shift, '')}".strip(),
                "CheckIn": r.check_in.strftime("%H:%M") if r.check_in else "",
                "CheckOut": r.check_out.strftime("%H:%M") if r.check_out else "",
                "Status": r.status,
                "MissedCheckIn": "Yes" if r.missed_checkin else "No",
                "MissedCheckOut": "Yes" if r.missed_checkout else "No",
                "Overtime": r.overtime or "",
                "Department": r.department
            }
            for r in records
        ]

        message = f"Showing {len(daily_table)} of {total_count} records"
        return render_template("daily.html", daily_table=daily_table, pagination=None, message=message)

    except Exception as e:
        return render_template(
            "daily.html", 
            daily_table=[], 
            pagination=None, 
            message=f"❌ Failed to load daily report: {e}"
        )

@main.route("/employees", methods=["GET", "POST"])
@login_required
def employees():
    """
    Route: Employee Management
    Template: employees.html
    Service: EmployeeService, Employee model, DailyReport model
    """
    service = EmployeeService()

    if request.method == "POST":
        service.add_or_update_employee(
            name=request.form.get("name", "").strip(),
            joining_date_str=request.form.get("joining_date", "").strip(),
            department=request.form.get("department", "").strip(),
            effective_date_str=request.form.get("effective_date", "").strip(),
            shift_full=request.form.get("shift", "").strip()
        )
        return redirect(url_for("main.employees"))

    employees_list = Employee.query.order_by(Employee.name).all()
    daily_names_query = db.session.query(DailyReport.employee_name).distinct().all()
    daily_names = sorted([n[0] for n in daily_names_query if n[0]])

    return render_template(
        "employees.html",
        employees=employees_list,
        daily_names=daily_names,
        current_date=datetime.today().strftime("%Y-%m-%d")
    )

@main.route("/admin_panel", methods=["GET", "POST"])
@login_required
def admin_panel():
    """
    Route: Admin User Management
    Template: admin_panel.html
    Service: Admin model
    """
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()

        if not username or not password or not confirm_password:
            flash("❌ All fields are required.", "error")
            return redirect(url_for("main.admin_panel"))

        if password != confirm_password:
            flash("❌ Passwords do not match.", "error")
            return redirect(url_for("main.admin_panel"))

        existing_admin = Admin.query.filter_by(username=username).first()
        if existing_admin:
            flash(f"❌ Username '{username}' already exists.", "error")
            return redirect(url_for("main.admin_panel"))

        new_admin = Admin(username=username)
        new_admin.set_password(password)

        try:
            db.session.add(new_admin)
            db.session.commit()
            flash(f"✅ Admin '{username}' created successfully.", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"❌ Failed to create admin: {e}", "error")

        return redirect(url_for("main.admin_panel"))

    admins = Admin.query.order_by(Admin.username).all()
    return render_template("admin_panel.html", admins=admins)

# ===========================================================
# API ROUTES
# ===========================================================

@main.route("/api/daily_search", methods=["GET"])
@login_required
def daily_search():
    """
    Route: Daily Report Search API
    Service: DailyReport model
    """
    q = request.args.get("q", "").strip()
    date = request.args.get("date", "").strip()
    status = request.args.get("status", "").strip()

    query = DailyReport.query
    if q:
        query = query.filter(DailyReport.employee_name.ilike(f"%{q}%"))
    if date:
        query = query.filter(DailyReport.date == date)
    if status:
        query = query.filter(DailyReport.status.ilike(f"%{status}%"))

    total_count = query.count()
    records = query.order_by(DailyReport.date.desc()).limit(100).all()

    shift_mapping = {
        "09:00 - 18:00": "(07:00 to 04:00)",
        "10:00 - 19:00": "(08:00 to 05:00)",
        "11:00 - 20:00": "(09:00 to 06:00)",
        "11:30 - 20:30": "(09:30 to 06:30)",
        "09:00 - 13:30": "(07:00 to 11:30)",
        "10:00 - 14:30": "(08:00 to 12:30)",
        "09:00 - 14:30": "(07:00 to 12:30)",
    }

    result = [
        {
            "EmpID": r.emp_id,
            "Date": r.date.strftime("%Y-%m-%d"),
            "Name": r.employee_name,
            "Shift": r.shift,
            "ShiftDisplay": f"{r.shift} {shift_mapping.get(r.shift, '')}".strip(),
            "CheckIn": r.check_in.strftime("%H:%M") if r.check_in else "",
            "CheckOut": r.check_out.strftime("%H:%M") if r.check_out else "",
            "Status": r.status,
            "MissedCheckIn": "Yes" if r.missed_checkin else "No",
            "MissedCheckOut": "Yes" if r.missed_checkout else "No",
            "Overtime": r.overtime or "",
            "Department": r.department
        }
        for r in records
    ]

    return jsonify({"data": result, "total_count": total_count})

@main.route("/update_compensate", methods=["POST"])
@login_required
def update_compensate():
    """
    Route: Mark Attendance as Compensated
    Service: DailyReport model
    """
    try:
        data = request.get_json(force=True) or {}
        emp_name = data.get("emp_name")
        date_str = data.get("date")
        
        if not emp_name or not date_str:
            return {
                "success": False, 
                "message": "Missing employee name or date"
            }, 400
        
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return {
                "success": False, 
                "message": "Invalid date format"
            }, 400
        
        record = DailyReport.query.filter_by(
            employee_name=emp_name, 
            date=date_obj
        ).first()
        
        if not record:
            return {
                "success": False, 
                "message": "Record not found"
            }, 404
        
        record.status = "Compensated"
        db.session.commit()
        clear_daily_cache()
        
        return {
            "success": True, 
            "message": "Marked as compensated"
        }
        
    except Exception as e:
        db.session.rollback()
        print(f"Error in update_compensate: {e}")
        return {
            "success": False, 
            "message": "Internal server error"
        }, 500

@main.route("/refresh_cache", methods=["POST"])
@login_required
def refresh_cache():
    """
    Route: Clear Daily Report Cache
    Service: Cache management
    """
    clear_daily_cache()
    return jsonify({"success": True, "message": "Cache cleared successfully"})

# ===========================================================
# FILE OPERATIONS ROUTES
# ===========================================================

@main.route("/upload", methods=["POST"])
@login_required
def upload_file():
    """
    Route: Upload Attendance File
    Template: index.html
    Service: FileService
    """
    file = request.files.get("file")
    if not file or not file.filename:
        message = "❌ No file selected."
    else:
        try:
            file_service = FileService(employee_shifts=employee_shifts, compensated_dates=compensated_dates)
            message = file_service.process_file(file)
        except Exception as e:
            db.session.rollback()
            message = f"❌ File processing failed: {e}"

    employees = load_employees()
    initialize_employee_shifts(employees)
    table = load_monthly_summary()

    return render_template(
        "index.html",
        message=message,
        table=table,
        employees=employees,
        employee_shifts=employee_shifts
    )

@main.route("/delete_data", methods=["POST"])
@login_required
def delete_data():
    """
    Route: Delete All Attendance Data
    Template: index.html
    Service: MonthlyReport, DailyReport, AttendanceRaw models
    """
    try:
        db.session.query(MonthlyReport).delete()
        db.session.query(DailyReport).delete()
        db.session.query(AttendanceRaw).delete()
        db.session.commit()
        message = "✅ All attendance and report data deleted successfully."
    except Exception as e:
        db.session.rollback()
        message = f"❌ Error deleting data: {e}"

    return render_template("index.html", message=message, table=[], employees=[], employee_shifts={})

@main.route("/delete_admin", methods=["POST"])
@login_required
def delete_admin():
    """
    Route: Delete Admin User
    Template: admin_panel.html
    Service: Admin model
    """
    admin_id = request.form.get("admin_id")
    admin = Admin.query.get(admin_id)

    if not admin:
        flash("Admin not found.", "error")
        return redirect(url_for("main.admin_panel"))

    if admin.id == session.get("admin_id"):
        flash("❌ You cannot delete your own account.", "error")
        return redirect(url_for("main.admin_panel"))

    db.session.delete(admin)
    db.session.commit()

    flash("Admin deleted successfully.", "success")
    return redirect(url_for("main.admin_panel"))

# ===========================================================
# TEMPLATE FILTERS
# ===========================================================

@main.app_template_filter("convert_shift_display")
def convert_shift_display(shift_text):
    """
    Template Filter: Convert shift format for display
    Used in: daily.html, index.html templates
    """
    if not shift_text:
        return shift_text

    mapping = {
        "10:00 - 19:00": "(07:00 to 04:00)",
        "11:00 - 20:00": "(08:00 to 05:00)",
        "12:00 - 21:00": "(09:00 to 06:00)",
        "12:30 - 21:30": "(09:30 to 06:30)",
        "10:00 - 14:30": "(07:00 to 11:30)",
        "11:00 - 15:30": "(08:00 to 12:30)",
        "10:00 - 15:30": "(07:00 to 12:30)",
    }

    shift_text = shift_text.strip()
    return f"{shift_text} {mapping.get(shift_text, '')}".strip()
