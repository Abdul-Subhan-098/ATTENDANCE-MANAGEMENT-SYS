from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from app import db
from app.models import AttendanceRaw, MonthlyReport, DailyReport, Employee, Admin
from datetime import datetime,timedelta
from sqlalchemy import func
from app.service.file_service import get_uploaded_files, delete_uploaded_file
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
import re
import time
import logging 
from app.service.daily_service import generate_daily_report, DailyReportGenerator, AttendanceCalculator
from app.service.monthly_service import generate_monthly_report_from_daily
from app.service.file_service import FileService
from app.service.employee_service import EmployeeService

main = Blueprint("main", __name__)
logger = logging.getLogger(__name__)

# ===========================================================
# CONFIGURATION & CONSTANTS
# ===========================================================
CACHE_TIMEOUT = 300  # 5 minutes
SHIFT_DISPLAY_MAPPING = {
    "09:00 - 18:00": "(07:00 to 04:00)",
    "10:00 - 19:00": "(08:00 to 05:00)",
    "11:00 - 20:00": "(09:00 to 06:00)",
    "11:30 - 20:30": "(09:30 to 06:30)",
    "09:00 - 13:30": "(07:00 to 11:30)",
    "10:00 - 14:30": "(08:00 to 12:30)",
    "09:00 - 14:30": "(07:00 to 12:30)",
}

# ===========================================================
# APPLICATION STATE
# ===========================================================
_employee_shifts = {}  # {"Employee Name": ("10:00", "19:00")}
_compensated_dates = {}  # {"Employee Name": {"2025-10-13"}}
_daily_report_cache = {"data": None, "timestamp": 0}

# ===========================================================
# AUTHENTICATION DECORATORS
# ===========================================================

def login_required(f):
    """Decorator to require login for protected routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session:
            flash("⚠️ Please log in first!", "warning")
            return redirect(url_for('main.login'))
        return f(*args, **kwargs)
    return decorated_function

# ===========================================================
# DATA MANAGEMENT HELPERS
# ===========================================================

def _get_unique_employee_names():
    """Get sorted list of unique employee names from attendance records."""
    employees = db.session.query(AttendanceRaw.name).distinct().all()
    return sorted([emp[0] for emp in employees if emp[0]])

def _initialize_default_shifts(employees):
    """Initialize default shifts for employees if not already set."""
    global _employee_shifts
    if not _employee_shifts and employees:
        _employee_shifts = {name: ("10:00", "19:00") for name in employees}

def _get_daily_report_with_cache():
    """Get daily report with caching to improve performance."""
    global _daily_report_cache
    
    current_time = time.time()
    if (_daily_report_cache["data"] is not None and 
        current_time - _daily_report_cache["timestamp"] < CACHE_TIMEOUT):
        return _daily_report_cache["data"]

    try:
        report_data = generate_daily_report()
    except Exception as e:
        report_data = {"error": f"Report generation failed: {e}", "daily_table": []}

    _daily_report_cache = {"data": report_data, "timestamp": current_time}
    return report_data

def _clear_daily_cache():
    """Clear the daily report cache."""
    global _daily_report_cache
    _daily_report_cache = {"data": None, "timestamp": 0}

def _format_daily_record(record):
    """Format a single daily record for API response"""
    return {
        "EmpID": record.emp_id,
        "Date": record.date.strftime("%Y-%m-%d"),
        "Name": record.employee_name,
        "Shift": record.shift,
        "Role": getattr(record, "role", "Full-Timer") or "Full-Timer",  # Added from Code A
        "ShiftDisplay": f"{record.shift} {SHIFT_DISPLAY_MAPPING.get(record.shift, '')}".strip(),
        "CheckIn": record.check_in.strftime("%H:%M") if record.check_in else "",
        "CheckOut": record.check_out.strftime("%H:%M") if record.check_out else "",
        "Status": record.status,
        "MissedCheckIn": "Yes" if record.missed_checkin else "No",
        "MissedCheckOut": "Yes" if record.missed_checkout else "No",
        "Overtime": record.overtime or 0.0,
        "Department": record.department or "Cold Calling",
        "CompensationType": record.compensation_type or "",  # Added from Code B
        "CompensatedDate": record.compensated_date.strftime("%Y-%m-%d") if record.compensated_date else ""  # Added from Code B
    }

def _format_monthly_record(record):
    """Format a single monthly record for display."""
    return {
        "EmpID": record.emp_id or "",
        "Name": record.name or "",
        "Role": getattr(record, "role", "Full-Timer") or "Full-Timer",  # Added from Code A
        "Shift": record.shift or "",
        "Department": record.department or "Cold Calling",
        "TotalDays": record.total_days or 0,
        "Present": record.present or 0,
        "Absent": record.absent or 0,
        "Late": record.late or 0,
        "HalfDayWeekdays": record.half_day_weekdays or 0,
        "HalfDaySat": record.half_day_sat or 0,  # Added from Code A
        "FullDaySat": record.full_day_sat or 0,  # Added from Code A
        "Sundays": record.sundays or 0,  # Added from Code A
        "Overtime": record.ot_hours or 0.0,
        "JoiningDate": record.joining_date.strftime("%Y-%m-%d") if record.joining_date else "",
        "LastUpdated": record.last_updated_date.strftime("%Y-%m-%d") if record.last_updated_date else "",
        "Compensated": record.compensated or 0,  # Added from Code A
        "ByLateCount": record.by_late_count or 0,  # Added from Code B
        "ByHalfDayCount": record.by_half_day_count or 0,  # Added from Code B
        "ByAbsentCount": record.by_absent_count or 0  # Added from Code B
    }


# ===========================================================
# AUTHENTICATION ROUTES
# ===========================================================

@main.route('/login', methods=['GET', 'POST'])
def login():
    """Handle user authentication."""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        if not username or not password:
            flash("❌ All fields are required", "error")
            return redirect(url_for('main.login'))

        admin_user = Admin.query.filter_by(username=username).first()

        if admin_user and check_password_hash(admin_user.password_hash, password):
            session['admin_id'] = admin_user.id
            session['admin_username'] = admin_user.username
            flash("✅ Logged in successfully!", "success")
            return redirect(url_for('main.employees'))
        else:
            flash("❌ Invalid username or password", "error")
            return redirect(url_for('main.login'))

    return render_template('login.html')

@main.route("/logout")
@login_required
def logout():
    """Handle user logout and session cleanup."""
    session.clear()
    flash("✅ Logged out successfully!", "success")
    return redirect(url_for('main.login'))

# ===========================================================
# MAIN APPLICATION ROUTES
# ===========================================================

@main.route("/", methods=["GET"])
@login_required
def index():
    """Display monthly summary dashboard."""
    employee_names = _get_unique_employee_names()
    _initialize_default_shifts(employee_names)
    
    monthly_data = MonthlyReport.query.order_by(MonthlyReport.name).all()
    formatted_monthly_data = [_format_monthly_record(record) for record in monthly_data]
    
    return render_template(
        "index.html", 
        message=None, 
        table=formatted_monthly_data, 
        employees=employee_names, 
        employee_shifts=_employee_shifts
    )

@main.route("/daily", methods=["GET"])
@login_required
def daily():
    """Display daily attendance report."""
    try:
        base_query = DailyReport.query.order_by(DailyReport.date.desc())
        total_records_count = base_query.count()
        recent_records = base_query.limit(100).all()

        formatted_daily_data = [_format_daily_record(record) for record in recent_records]
        status_message = f"Showing {len(formatted_daily_data)} of {total_records_count} records"
        
        return render_template(
            "daily.html", 
            daily_table=formatted_daily_data, 
            pagination=None, 
            message=status_message
        )

    except Exception as error:
        return render_template(
            "daily.html", 
            daily_table=[], 
            pagination=None, 
            message=f"❌ Failed to load daily report: {error}"
        )

@main.route("/employees", methods=["GET", "POST"])
@login_required
def employees():
    """Handle employee management operations."""
    employee_service = EmployeeService()

    if request.method == "POST":
        employee_service.add_or_update_employee(
            name=request.form.get("name", "").strip(),
            joining_date_str=request.form.get("joining_date", "").strip(),
            department=request.form.get("department", "").strip(),
            effective_date_str=request.form.get("effective_date", "").strip(),
            shift_full=request.form.get("shift", "").strip(),
            role=request.form.get("role", "").strip()  # <-- Added from Code A
        )
        return redirect(url_for("main.employees"))

    # GET request - display employee list
    employee_list = Employee.query.order_by(Employee.name).all()
    daily_employee_names_query = db.session.query(DailyReport.employee_name).distinct().all()
    daily_employee_names = sorted([name[0] for name in daily_employee_names_query if name[0]])

    # Add role options for the form (from Code A)
    roles = ["Full-Timer", "Part-Timer"]

    return render_template(
        "employees.html",
        employees=employee_list,
        daily_names=daily_employee_names,
        current_date=datetime.today().strftime("%Y-%m-%d"),
        roles=roles  # <-- Added from Code A
    )

@main.route("/admin_panel", methods=["GET", "POST"])
@login_required
def admin_panel():
    """Handle admin user management."""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()

        if not all([username, password, confirm_password]):
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
        except Exception as error:
            db.session.rollback()
            flash(f"❌ Failed to create admin: {error}", "error")

        return redirect(url_for("main.admin_panel"))

    admin_users = Admin.query.order_by(Admin.username).all()
    return render_template("admin_panel.html", admins=admin_users)

# ===========================================================
# API ENDPOINTS
# ===========================================================

@main.route("/api/daily_search", methods=["GET"])
@login_required
def daily_search():
    """API endpoint for searching daily reports."""
    search_query = request.args.get("q", "").strip()
    filter_date = request.args.get("date", "").strip()
    filter_status = request.args.get("status", "").strip()

    query = DailyReport.query
    
    if search_query:
        query = query.filter(DailyReport.employee_name.ilike(f"%{search_query}%"))
    if filter_date:
        query = query.filter(DailyReport.date == filter_date)
    if filter_status:
        query = query.filter(DailyReport.status.ilike(f"%{filter_status}%"))

    total_records_count = query.count()
    filtered_records = query.order_by(DailyReport.date.desc()).limit(100).all()

    formatted_results = [_format_daily_record(record) for record in filtered_records]

    return jsonify({
        "data": formatted_results, 
        "total_count": total_records_count
    })

# @main.route("/update_compensate", methods=["POST"])
# @login_required
# def update_compensate():
#     """API endpoint to mark attendance as compensated."""
#     try:
#         request_data = request.get_json(force=True) or {}
#         employee_name = request_data.get("emp_name")
#         date_string = request_data.get("date")
        
#         if not employee_name or not date_string:
#             return jsonify({
#                 "success": False, 
#                 "message": "Missing employee name or date"
#             }), 400
        
#         try:
#             target_date = datetime.strptime(date_string, "%Y-%m-%d").date()
#         except ValueError:
#             return jsonify({
#                 "success": False, 
#                 "message": "Invalid date format"
#             }), 400
        
#         target_record = DailyReport.query.filter_by(
#             employee_name=employee_name, 
#             date=target_date
#         ).first()
        
#         if not target_record:
#             return jsonify({
#                 "success": False, 
#                 "message": "Record not found"
#             }), 404
        
#         target_record.status = "Compensated"
#         db.session.commit()
#         _clear_daily_cache()
        
#         return jsonify({
#             "success": True, 
#             "message": "Marked as compensated"
#         })
        
#     except Exception as error:
#         db.session.rollback()
#         print(f"Error in update_compensate: {error}")
#         return jsonify({
#             "success": False, 
#             "message": "Internal server error"
#         }), 500

@main.route("/refresh_cache", methods=["POST"])
@login_required
def refresh_cache():
    """API endpoint to clear daily report cache."""
    _clear_daily_cache()
    return jsonify({
        "success": True, 
        "message": "Cache cleared successfully"
    })

# ===========================================================
# FILE OPERATIONS ROUTES
# ===========================================================

@main.route("/upload", methods=["POST"])
@login_required
def upload_file():
    """Handle attendance file upload and processing."""
    uploaded_file = request.files.get("file")
    
    if not uploaded_file or not uploaded_file.filename:
        status_message = "❌ No file selected."
    else:
        try:
            file_processor = FileService(
                employee_shifts=_employee_shifts, 
                compensated_dates=_compensated_dates
            )
            status_message = file_processor.process_file(uploaded_file)
        except Exception as error:
            db.session.rollback()
            status_message = f"❌ File processing failed: {error}"

    employee_names = _get_unique_employee_names()
    _initialize_default_shifts(employee_names)
    monthly_data = generate_monthly_report_from_daily()

    return render_template(
        "index.html",
        message=status_message,
        table=monthly_data,
        employees=employee_names,
        employee_shifts=_employee_shifts
    )

@main.route("/delete_data", methods=["POST"])
@login_required
def delete_data():
    """Delete all attendance and report data."""
    try:
        db.session.query(MonthlyReport).delete()
        db.session.query(DailyReport).delete()
        db.session.query(AttendanceRaw).delete()
        db.session.commit()
        status_message = "✅ All attendance and report data deleted successfully."
    except Exception as error:
        db.session.rollback()
        status_message = f"❌ Error deleting data: {error}"

    return render_template(
        "index.html", 
        message=status_message, 
        table=[], 
        employees=[], 
        employee_shifts={}
    )

@main.route("/delete_admin", methods=["POST"])
@login_required
def delete_admin():
    """Delete an admin user account."""
    admin_id = request.form.get("admin_id")
    target_admin = Admin.query.get(admin_id)

    if not target_admin:
        flash("Admin not found.", "error")
        return redirect(url_for("main.admin_panel"))

    if target_admin.id == session.get("admin_id"):
        flash("❌ You cannot delete your own account.", "error")
        return redirect(url_for("main.admin_panel"))

    db.session.delete(target_admin)
    db.session.commit()

    flash("Admin deleted successfully.", "success")
    return redirect(url_for("main.admin_panel"))

# ===========================================================
# TEMPLATE FILTERS
# ===========================================================

@main.app_template_filter("convert_shift_display")
def convert_shift_display(shift_text):
    """Template filter to convert shift format for display."""
    if not shift_text:
        return shift_text

    shift_text = shift_text.strip()
    return f"{shift_text} {SHIFT_DISPLAY_MAPPING.get(shift_text, '')}".strip()

# ===========================================================
# Selected file deleete routes 
# ===========================================================


@main.route("/api/uploaded_files", methods=["GET"])
@login_required
def get_uploaded_files_api():
    """API endpoint to get all uploaded files."""
    try:
        files = get_uploaded_files()
        return jsonify({"files": files})
    except Exception as e:
        print(f"Error fetching uploaded files: {e}")  # Temporary print
        return jsonify({"error": "Failed to fetch uploaded files"}), 500

@main.route("/api/session_check", methods=["GET"])
def session_check():
    """Public endpoint to check session status."""
    if 'admin_id' in session:
        return jsonify({
            "authenticated": True,
            "username": session.get('admin_username')
        })
    else:
        return jsonify({
            "authenticated": False
        }), 401
    

@main.route("/delete_file", methods=["POST"])
@login_required
def delete_file():
    """Delete a specific uploaded file and regenerate reports from remaining data."""
    try:
        batch_id = request.form.get("batch_id")
        if not batch_id:
            flash("❌ File selection is required", "error")
            return redirect(url_for("main.index"))

        success, message = delete_uploaded_file(batch_id)
        
        if success:
            # Clear existing reports
            db.session.query(DailyReport).delete()
            db.session.query(MonthlyReport).delete()
            db.session.commit()
            
            # Regenerate reports from REMAINING data only
            generate_daily_report()
            generate_monthly_report_from_daily()
            
            flash(f"{message} Reports updated with remaining data.", "success")
        else:
            flash(message, "error")
            
    except Exception as e:
        print(f"Error in delete_file route: {e}")
        flash("❌ Error deleting file", "error")
    
    return redirect(url_for("main.index"))

# ===========================================================
# COMPENSATION ROUTES (Added from Code B)
# ===========================================================

@main.route("/apply_compensation", methods=["POST"])
@login_required
def apply_compensation():
    """Apply compensation to attendance record"""
    try:
        data = request.get_json()
        
        employee_name = data.get("employee_name")
        violation_date_str = data.get("violation_date")
        compensation_date_str = data.get("compensation_date")
        compensation_type = data.get("compensation_type")
        
        if not all([employee_name, violation_date_str, compensation_date_str, compensation_type]):
            return jsonify({"success": False, "message": "All fields are required"}), 400
        
        # Convert dates
        violation_date = datetime.strptime(violation_date_str, "%Y-%m-%d").date()
        compensation_date = datetime.strptime(compensation_date_str, "%Y-%m-%d").date()
        
        # Apply compensation
        from app.service.compensation_service import CompensationService
        service = CompensationService()
        result = service.apply_compensation(
            employee_name, violation_date, compensation_date, compensation_type
        )
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Compensation API error: {e}")
        return jsonify({"success": False, "message": "Internal server error"}), 500

@main.route("/check_compensation_eligibility", methods=["POST"])
@login_required
def check_compensation_eligibility():
    """Check if employee is eligible for compensation"""
    try:
        data = request.get_json()
        
        employee_name = data.get("employee_name")
        violation_date_str = data.get("violation_date")
        compensation_type = data.get("compensation_type")
        
        if not all([employee_name, violation_date_str, compensation_type]):
            return jsonify({"eligible": False, "message": "All fields are required"})
        
        violation_date = datetime.strptime(violation_date_str, "%Y-%m-%d").date()
        
        from app.service.compensation_service import CompensationService
        service = CompensationService()
        
        # For eligibility check, we use compensation_date = violation_date (same day)
        employee, violation_record, _ = service._fetch_records(
            employee_name, violation_date, violation_date
        )
        
        if not employee:
            return jsonify({"eligible": False, "message": "Employee not found"})
        if not violation_record:
            return jsonify({"eligible": False, "message": "Violation record not found"})
        
        is_eligible, message = service._check_eligibility(
            employee, violation_record, compensation_type
        )
        
        return jsonify({"eligible": is_eligible, "message": message})
        
    except Exception as e:
        logger.error(f"Eligibility check error: {e}")
        return jsonify({"eligible": False, "message": "Error checking eligibility"})

@main.route("/api/compensation_history")
@login_required
def get_compensation_history():
    """Get compensation history for display"""
    try:
        from app.service.compensation_service import CompensationService
        service = CompensationService()
        
        # Get last 30 days of compensation history
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=30)
        
        history = service.get_compensation_history(
            start_date=start_date, 
            end_date=end_date
        )
        
        return jsonify({"history": history})
        
    except Exception as e:
        logger.error(f"Error getting compensation history: {e}")
        return jsonify({"history": []})