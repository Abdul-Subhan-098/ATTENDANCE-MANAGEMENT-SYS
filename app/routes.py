from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from app import db
from app.models import AttendanceRaw, MonthlyReport, DailyReport, Employee, Admin, NewEmployee, LeaveApplication
from datetime import datetime, timedelta
from app.service.activity_service import log_activity, get_activity_logs, ActivityService, get_user_activity_logs
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
from app.service.new_employees_service import NewEmployeeService

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
        "Gender": getattr(record, "gender", "Male") or "Male",  # From A
        "Shift": record.shift,
        "Role": getattr(record, "role", "Full-Timer") or "Full-Timer",
        "ShiftDisplay": f"{record.shift} {SHIFT_DISPLAY_MAPPING.get(record.shift, '')}".strip(),
        "CheckIn": record.check_in.strftime("%H:%M") if record.check_in else "",
        "CheckOut": record.check_out.strftime("%H:%M") if record.check_out else "",
        "Status": record.status,
        "MissedCheckIn": "Yes" if record.missed_checkin else "No",
        "MissedCheckOut": "Yes" if record.missed_checkout else "No",
        "Overtime": record.overtime or 0.0,
        "Department": record.department or "Cold Calling",
        "CompensationType": record.compensation_type or "",
        "LeaveType": record.leave_type or "",
        "CompensatedDate": record.compensated_date.strftime("%Y-%m-%d") if record.compensated_date else ""
    }

def _format_monthly_record(record):
    """Format a single monthly record for display, including medical & casual leaves."""
    return {
        "EmpID": record.emp_id or "",
        "Name": record.name or "",
        "Gender": getattr(record, "gender", "Male") or "Male",
        "Role": getattr(record, "role", "Full-Timer") or "Full-Timer",
        "Shift": record.shift or "",
        "Department": record.department or "Cold Calling",
        "TotalDays": record.total_days or 0,
        "Present": record.present or 0,
        "Absent": record.absent or 0,
        "Late": record.late or 0,
        "HalfDayWeekdays": record.half_day_weekdays or 0,
        "HalfDaySat": record.half_day_sat or 0,
        "FullDaySat": record.full_day_sat or 0,
        "Sundays": record.sundays or 0,
        "OverTime": record.ot_hours or 0.0,
        "JoiningDate": record.joining_date.strftime("%Y-%m-%d") if record.joining_date else "",
        "LastUpdated": record.last_updated_date.strftime("%Y-%m-%d") if record.last_updated_date else "",
        "Compensated": record.compensated or 0,
        "ByLateCount": record.by_late_count or 0,
        "ByHalfDayCount": record.by_half_day_count or 0,
        "ByAbsentCount": record.by_absent_count or 0,
        "WorkingDays": getattr(record, "working_days", 0) or 0,
        "PunchMissed": getattr(record, "punch_missed", 0) or 0,
        "MedicalLeave": getattr(record, "medical_leave", 0) or 0,  # NEW
        "CasualLeave": getattr(record, "casual_leave", 0) or 0,     # NEW
        "Month": record.report_month or ""  # NEW: Required for filtering
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
            
            # Log successful login (From B)
            log_activity(
                username=username,
                action="User logged in",
                entity_type="authentication",
                details="Successful login"
            )
            
            flash("✅ Logged in successfully!", "success")
            return redirect(url_for('main.employees'))
        else:
            # Log failed login attempt (From B)
            log_activity(
                username=username,
                action="Failed login attempt",
                entity_type="authentication",
                details="Invalid credentials"
            )
            
            flash("❌ Invalid username or password", "error")
            return redirect(url_for('main.login'))

    return render_template('login.html')

@main.route("/logout")
@login_required
def logout():
    username = session.get('admin_username', 'Unknown')
    
    # Log logout activity (From B)
    log_activity(
        username=username,
        action="User logged out",
        entity_type="authentication"
    )
    
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

# ===========================================================
# COMPANY DAY OFF ROUTES
# ===========================================================

@main.route("/company_day_off", methods=["POST"])
@login_required
def company_day_off():
    """Handle Company Day Off operations"""
    try:
        data = request.get_json()
        username = session.get('admin_username', 'Unknown')  # From B
        
        action = data.get("action")
        date_str = data.get("date")
        reason = data.get("reason", "Company Day Off")
        
        if not action or not date_str:
            return jsonify({"success": False, "message": "Missing required parameters"}), 400
        
        from app.service.employee_service import EmployeeService
        service = EmployeeService()
        
        if action == "add":
            success, message = service.apply_company_day_off(date_str, reason)
            log_action = "Added Company Day Off"  # From B
        elif action == "remove":
            success, message = service.remove_company_day_off(date_str)
            log_action = "Removed Company Day Off"  # From B
        else:
            return jsonify({"success": False, "message": "Invalid action"}), 400
        
        if success:
            # Log company day off activity (From B)
            log_activity(
                username=username,
                action=f"{log_action}: {date_str}",
                entity_type="company_day_off",
                entity_id=date_str,
                details=reason if action == "add" else None
            )
            
            # Clear cache to reflect changes
            _clear_daily_cache()
            
            # Regenerate monthly report
            from app.service.monthly_service import generate_monthly_report_from_daily
            generate_monthly_report_from_daily()
            
            logger.info(f"Company Day Off {action} successful: {date_str}")
            return jsonify({"success": True, "message": message})
        else:
            return jsonify({"success": False, "message": message}), 400
            
    except Exception as e:
        logger.error(f"Company Day Off error: {e}")
        return jsonify({"success": False, "message": "Internal server error"}), 500

@main.route("/api/company_off_days", methods=["GET"])
@login_required
def get_company_off_days():
    """Get list of Company Day Off dates"""
    try:
        from app.service.employee_service import EmployeeService
        service = EmployeeService()
        
        start_date_str = request.args.get("start_date")
        end_date_str = request.args.get("end_date")
        
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date() if start_date_str else None
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date() if end_date_str else None
        
        off_days = service.get_company_off_days(start_date, end_date)
        
        return jsonify({"success": True, "off_days": off_days})
        
    except Exception as e:
        logger.error(f"Error getting Company Day Off days: {e}")
        return jsonify({"success": False, "message": "Internal server error"}), 500
    

@main.route("/employees", methods=["GET", "POST"])
@login_required
def employees():
    """Handle employee management operations."""
    employee_service = EmployeeService()
    username = session.get('admin_username', 'Unknown')  # From B

    if request.method == "POST":
        name = request.form.get("name", "").strip()

        # Add or update employee
        result = employee_service.add_or_update_employee(
            name=name,
            joining_date_str=request.form.get("joining_date", "").strip(),
            department=request.form.get("department", "").strip(),
            effective_date_str=request.form.get("effective_date", "").strip(),
            shift_full=request.form.get("shift", "").strip(),
            role=request.form.get("role", "").strip(),
            gender=request.form.get("gender", "").strip()
        )

        if result:
            # Log employee update/add
            action = "Updated employee" if Employee.query.filter_by(name=name).first() else "Added new employee"
            log_activity(
                username=username,
                action=f"{action}: {name}",
                entity_type="employee_management",
                entity_id=name,
                details=(
                    f"Department: {request.form.get('department')}, "
                    f"Shift: {request.form.get('shift')}, "
                    f"Role: {request.form.get('role')}, "
                    f"Gender: {request.form.get('gender')}"
                )
            )

            # -----------------------------
            # Cleanup NewEmployee if profile complete
            employee_obj = Employee.query.filter_by(name=name).first()
            if employee_obj:
                NewEmployeeService.cleanup_if_employee_confirmed(employee_obj.emp_id)
            # -----------------------------

        return redirect(url_for("main.employees"))

    # GET request - display employee list
    employee_list = Employee.query.order_by(Employee.name).all()
    daily_employee_names_query = db.session.query(DailyReport.employee_name).distinct().all()
    daily_employee_names = sorted([name[0] for name in daily_employee_names_query if name[0]])

    # Role options and gender options for the form
    roles = ["Full-Timer", "Part-Timer"]
    genders = ["Male", "Female"]

    # Get potential new employees for Add Employee tab
    new_employees_list = NewEmployee.query.order_by(NewEmployee.created_at.desc()).all()

    return render_template(
        "employees.html",
        employees=employee_list,
        new_employees=new_employees_list,
        daily_names=daily_employee_names,
        current_date=datetime.today().strftime("%Y-%m-%d"),
        roles=roles,
        genders=genders
    )


@main.route("/admin_panel", methods=["GET", "POST"])
@login_required
def admin_panel():
    """Handle admin user management."""
    username = session.get('admin_username', 'Unknown')  # From B
    
    if request.method == "POST":
        new_username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()

        if not all([new_username, password, confirm_password]):
            flash("❌ All fields are required.", "error")
            return redirect(url_for("main.admin_panel"))

        if password != confirm_password:
            flash("❌ Passwords do not match.", "error")
            return redirect(url_for("main.admin_panel"))

        existing_admin = Admin.query.filter_by(username=new_username).first()
        if existing_admin:
            flash(f"❌ Username '{new_username}' already exists.", "error")
            return redirect(url_for("main.admin_panel"))

        new_admin = Admin(username=new_username)
        new_admin.set_password(password)

        try:
            db.session.add(new_admin)
            db.session.commit()
            
            # Log admin creation (From B)
            log_activity(
                username=username,
                action=f"Created new admin user: {new_username}",
                entity_type="admin_management",
                entity_id=new_username
            )
            
            flash(f"✅ Admin '{new_username}' created successfully.", "success")
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
    username = session.get('admin_username', 'Unknown')  # From B
    
    if not uploaded_file or not uploaded_file.filename:
        status_message = "❌ No file selected."
    else:
        try:
            file_processor = FileService(
                employee_shifts=_employee_shifts, 
                compensated_dates=_compensated_dates
            )
            status_message = file_processor.process_file(uploaded_file)
            
            # Log file upload activity (From B)
            log_activity(
                username=username,
                action=f"Uploaded attendance file: {uploaded_file.filename}",
                entity_type="file_upload",
                details=status_message
            )
            
        except Exception as error:
            db.session.rollback()
            status_message = f"❌ File processing failed: {error}"
            
            # Log failed upload (From B)
            log_activity(
                username=username,
                action=f"Failed to upload file: {uploaded_file.filename}",
                entity_type="file_upload",
                details=str(error)
            )

    employee_names = _get_unique_employee_names()
    _initialize_default_shifts(employee_names)
    
    # Generate report (updates DB)
    generate_monthly_report_from_daily()

    # Fetch ALL monthly data to ensure UI remains consistent with index route
    all_monthly_data = MonthlyReport.query.order_by(MonthlyReport.name).all()
    formatted_monthly_data = [_format_monthly_record(record) for record in all_monthly_data]

    return render_template(
        "index.html",
        message=status_message,
        table=formatted_monthly_data,
        employees=employee_names,
        employee_shifts=_employee_shifts
    )

@main.route("/delete_data", methods=["POST"])
@login_required
def delete_data():
    """Delete all attendance and report data."""
    try:
        username = session.get('admin_username', 'Unknown')  # From B
        
        db.session.query(MonthlyReport).delete()
        db.session.query(DailyReport).delete()
        db.session.query(AttendanceRaw).delete()
        db.session.commit()
        
        # Log data deletion (From B)
        log_activity(
            username=username,
            action="Deleted all attendance and report data",
            entity_type="data_deletion",
            details="All DailyReport, MonthlyReport, and AttendanceRaw records deleted"
        )
        
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
    username = session.get('admin_username', 'Unknown')  # From B

    if not target_admin:
        flash("Admin not found.", "error")
        return redirect(url_for("main.admin_panel"))

    if target_admin.id == session.get("admin_id"):
        flash("❌ You cannot delete your own account.", "error")
        return redirect(url_for("main.admin_panel"))

    target_username = target_admin.username
    
    db.session.delete(target_admin)
    db.session.commit()

    # Log admin deletion (From B)
    log_activity(
        username=username,
        action=f"Deleted admin user: {target_username}",
        entity_type="admin_management",
        entity_id=target_username
    )

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
# FILE SELECTED ROUTES
# ===========================================================

@main.route("/api/uploaded_files", methods=["GET"])
@login_required
def get_uploaded_files_api():
    """API endpoint to get all uploaded files."""
    try:
        files = get_uploaded_files()
        return jsonify({"files": files})
    except Exception as e:
        print(f"Error fetching uploaded files: {e}")
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
        username = session.get('admin_username', 'Unknown')  # From B
        
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
            
            # Log file deletion (From B)
            log_activity(
                username=username,
                action=f"Deleted uploaded file batch: {batch_id}",
                entity_type="file_deletion",
                entity_id=batch_id,
                details=message
            )
            
            flash(f"{message} Reports updated with remaining data.", "success")
        else:
            flash(message, "error")
            
    except Exception as e:
        print(f"Error in delete_file route: {e}")
        flash("❌ Error deleting file", "error")
    
    return redirect(url_for("main.index"))

# ===========================================================
# COMPENSATION ROUTES
# ===========================================================

@main.route("/apply_compensation", methods=["POST"])
@login_required
def apply_compensation():
    """Apply compensation to attendance record"""
    try:
        data = request.get_json()
        username = session.get('admin_username', 'Unknown')  # From B
        
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
        
        # Log compensation activity (From B)
        if result.get("success"):
            log_activity(
                username=username,
                action=f"Applied {compensation_type} compensation for {employee_name}",
                entity_type="compensation",
                entity_id=employee_name,
                details=f"Violation: {violation_date_str}, Compensation: {compensation_date_str}"
            )
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Compensation API error: {e}")
        return jsonify({"success": False, "message": "Internal server error"}), 500

@main.route("/remove_compensation", methods=["POST"])
@login_required
def remove_compensation():
    """Remove an applied compensation and restore original attendance values"""
    try:
        data = request.get_json()

        employee_name = data.get("employee_name")
        violation_date_str = data.get("violation_date")

        if not employee_name or not violation_date_str:
            return jsonify({
                "success": False,
                "message": "Employee name and violation date are required"
            }), 400

        try:
            violation_date = datetime.strptime(violation_date_str, "%Y-%m-%d").date()
        except:
            return jsonify({
                "success": False,
                "message": "Invalid violation date format"
            }), 400

        # Call service layer
        from app.service.compensation_service import CompensationService
        service = CompensationService()
        result = service.remove_compensation(employee_name, violation_date)

        # Clear daily cache after update
        _clear_daily_cache()

        # Regenerate monthly summary
        from app.service.monthly_service import generate_monthly_report_from_daily
        generate_monthly_report_from_daily()

        return jsonify(result)

    except Exception as e:
        logger.error(f"Remove Compensation API error: {e}")
        return jsonify({"success": False, "message": "Internal server error"}), 500

from flask import request, jsonify
from app.service.compensation_service import CompensationService
from datetime import datetime

comp_service = CompensationService()

@main.route("/api/temporary_shift/add", methods=["POST"])
@login_required
def add_temporary_shift():
    """API endpoint to add a temporary shift."""
    try:
        data = request.get_json()
        emp_id = data.get("emp_id")
        shift = data.get("shift")
        start_date = data.get("start_date")
        end_date = data.get("end_date")

        if not all([emp_id, shift, start_date, end_date]):
            return jsonify({"success": False, "message": "Missing required fields"}), 400

        employee_service = EmployeeService()
        
        # Resolve emp_id if it's a name
        employee = Employee.query.filter((Employee.emp_id == emp_id) | (Employee.name == emp_id)).first()
        if not employee:
            return jsonify({"success": False, "message": f"Employee '{emp_id}' not found"}), 404
        
        actual_emp_id = employee.emp_id

        success = employee_service.add_temporary_shift(actual_emp_id, shift, start_date, end_date)
        
        if success:
            log_activity(
                username=session.get('admin_username', 'Admin'),
                action=f"Added temporary shift for {employee.name}",
                entity_type="temporary_shift",
                entity_id=actual_emp_id,
                details=f"Shift: {shift}, From: {start_date}, To: {end_date}"
            )
            return jsonify({"success": True, "message": "Temporary shift added successfully"})
        else:
            return jsonify({"success": False, "message": "Failed to add temporary shift"}), 500

    except Exception as e:
        logger.error(f"Error in add_temporary_shift: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@main.route("/api/temporary_shift/list/all", methods=["GET"])
@login_required
def list_temporary_shifts():
    """API endpoint to list all temporary shifts."""
    try:
        employee_service = EmployeeService()
        shifts = employee_service.get_temporary_shifts()
        
        formatted_shifts = []
        for s in shifts:
            formatted_shifts.append({
                "id": s.id,
                "emp_id": s.emp_id,
                "shift": s.shift,
                "start_date": s.start_date.strftime("%Y-%m-%d"),
                "end_date": s.end_date.strftime("%Y-%m-%d")
            })
            
        return jsonify({"success": True, "shifts": formatted_shifts})
    except Exception as e:
        logger.error(f"Error in list_temporary_shifts: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@main.route("/api/temporary_shift/delete/<int:shift_id>", methods=["DELETE"])
@login_required
def delete_temporary_shift(shift_id):
    """API endpoint to delete a temporary shift."""
    try:
        employee_service = EmployeeService()
        success = employee_service.delete_temporary_shift(shift_id)
        
        if success:
            log_activity(
                username=session.get('admin_username', 'Admin'),
                action=f"Deleted temporary shift (ID: {shift_id})",
                entity_type="temporary_shift",
                entity_id=str(shift_id)
            )
            return jsonify({"success": True, "message": "Temporary shift deleted successfully"})
        else:
            return jsonify({"success": False, "message": "Failed to delete temporary shift"}), 500
    except Exception as e:
        logger.error(f"Error in delete_temporary_shift: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@main.route('/check_compensation_eligibility', methods=['POST'])
def check_compensation_eligibility():
    try:
        data = request.json
        employee_name = data.get('employee_name')
        violation_date_str = data.get('violation_date')
        compensation_date_str = data.get('compensation_date')
        compensation_type = data.get('compensation_type')

        if not all([employee_name, violation_date_str, compensation_date_str, compensation_type]):
            return jsonify({"eligible": False, "message": "Missing required fields"}), 400

        violation_date = datetime.strptime(violation_date_str, "%Y-%m-%d").date()
        compensation_date = datetime.strptime(compensation_date_str, "%Y-%m-%d").date()

        # Fetch employee and violation record
        employee, violation_record, _ = comp_service._fetch_records(employee_name, violation_date, compensation_date)
        if not employee:
            return jsonify({"eligible": False, "message": "Employee not found"})
        if not violation_record:
            return jsonify({"eligible": False, "message": "Violation record not found"})

        # Pass compensation_date to _check_eligibility
        eligible, message = comp_service._check_eligibility(
            employee, violation_record, compensation_type, compensation_date
        )

        return jsonify({"eligible": eligible, "message": message})
    
    except Exception as e:
        return jsonify({"eligible": False, "message": f"Error: {str(e)}"})


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

# ===========================================================
# ACTIVITY LOG ROUTES (From B)
# ===========================================================

@main.route("/activity_logs")
@login_required
def activity_logs():
    """Display activity logs page."""
    return render_template("activity_logs.html")


@main.route("/api/activity_logs", methods=["GET"])
@login_required
def get_activity_logs_api():
    """API endpoint to fetch ONLY USER activity logs (System/Admin excluded)."""
    try:
        # Get filter parameters
        username = request.args.get("username")
        entity_type = request.args.get("entity_type")
        start_date_str = request.args.get("start_date")
        end_date_str = request.args.get("end_date")
        limit = request.args.get("limit", 100, type=int)
        
        # Convert dates
        start_date = None
        end_date = None
        
        if start_date_str:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
        if end_date_str:
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
        
        # Get ONLY USER logs (System/Admin excluded)
        service = ActivityService()
        logs = service.get_user_activity_logs(
            username=username,
            entity_type=entity_type,
            start_date=start_date,
            end_date=end_date,
            limit=limit
        )
        
        return jsonify({
            "success": True,
            "logs": logs,
            "total": len(logs),
            "note": "System aur Admin ki activities hide ki gayi hain"
        })
        
    except Exception as e:
        logger.error(f"Error fetching USER activity logs: {e}")
        return jsonify({
            "success": False,
            "message": "Failed to fetch user activity logs",
            "logs": []
        }), 500


@main.route("/api/activity_logs/filters", methods=["GET"])
@login_required
def get_activity_filters():
    """API endpoint to get filter options for USER activity logs."""
    try:
        service = ActivityService()
        
        entity_types = service.get_entity_types()
        
        # Direct query to exclude System/Admin
        from app.models import ActivityLog
        user_usernames = db.session.query(
            ActivityLog.username
        ).filter(
            ActivityLog.username.notin_(['System', 'Admin', 'system', 'admin'])
        ).distinct().order_by(ActivityLog.username).all()
        
        user_usernames = [username[0] for username in user_usernames if username[0]]
        
        return jsonify({
            "success": True,
            "entity_types": entity_types,
            "usernames": user_usernames
        })
        
    except Exception as e:
        logger.error(f"Error fetching USER activity filters: {e}")
        return jsonify({
            "success": False,
            "entity_types": [],
            "usernames": []
        }), 500


@main.route("/api/recent_activities", methods=["GET"])
@login_required
def get_recent_activities():
    """API endpoint to get recent activities for dashboard."""
    try:
        from app.service.activity_service import ActivityService
        service = ActivityService()
        
        limit = request.args.get("limit", 10, type=int)
        activities = service.get_recent_activities(limit=limit)
        
        return jsonify({
            "success": True,
            "activities": activities
        })
        
    except Exception as e:
        logger.error(f"Error fetching recent activities: {e}")
        return jsonify({
            "success": False,
            "activities": []
        }), 500
    
@main.route("/api/employee/details/<string:name>")
@login_required
def get_employee_details(name):
    """Get full details of an existing employee by name for auto-fill."""
    try:
        employee = Employee.query.filter_by(name=name).first()
        if not employee:
            return jsonify({"success": False, "message": "Employee not found"}), 404
        
        return jsonify({
            "success": True,
            "employee": {
                "emp_id": employee.emp_id,
                "name": employee.name,
                "department": employee.department,
                "shift": employee.shift,
                "role": employee.role,
                "gender": employee.gender,
                "joining_date": employee.joining_date.strftime("%Y-%m-%d") if employee.joining_date else None,
                "last_updated_date": employee.last_updated_date.strftime("%Y-%m-%d") if employee.last_updated_date else None
            }
        })
    except Exception as e:
        logger.error(f"Error in get_employee_details: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@main.route("/api/potential_employee/details/<string:name>")
@login_required
def get_potential_employee_details(name):
    """Get details of a new/potential employee by name for auto-fill."""
    try:
        from app.models import NewEmployee
        new_emp = NewEmployee.query.filter_by(name=name).first()
        if not new_emp:
            return jsonify({"success": False, "message": "Potential employee not found"}), 404
        
        return jsonify({
            "success": True,
            "employee": {
                "emp_id": new_emp.emp_id,
                "name": new_emp.name,
                "joining_date": new_emp.created_at.strftime("%Y-%m-%d") if new_emp.created_at else datetime.now().strftime("%Y-%m-%d")
            }
        })
    except Exception as e:
        logger.error(f"Error in get_potential_employee_details: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@main.route("/new_employees")
@login_required
def new_employees():
    """
    Display new employees detected from attendance but not fully confirmed.
    Pass a 'status' flag for template rendering.
    """
    from app.models import NewEmployee, Employee

    # Fetch all new employees
    new_employees_list = NewEmployee.query.order_by(NewEmployee.created_at.desc()).all()

    # Prepare a list with 'status' field to indicate if profile is complete
    employees_data = []
    for emp in new_employees_list:
        employee_obj = Employee.query.filter_by(emp_id=emp.emp_id).first()
        confirmed = bool(
            employee_obj and
            employee_obj.shift and
            employee_obj.department and
            employee_obj.role and
            employee_obj.joining_date and
            employee_obj.gender
        )
        employees_data.append({
            "emp_id": emp.emp_id,
            "name": emp.name,
            "created_at": emp.created_at,
            "status": "complete" if confirmed else "incomplete"
        })

    return render_template(
        "new_employees.html",
        new_employees=employees_data
    )


from flask import request, jsonify
from datetime import datetime
from app.service.leave_service import LeaveService
from app.routes import main   

leave_service = LeaveService()


# ==========================================================
# APPLY LEAVE (DATE RANGE)
# ==========================================================
@main.route("/api/apply_leave", methods=["POST"])
def apply_leave():
    try:
        data = request.get_json()

        employee_name = data.get("employee_name")
        start_date = data.get("start_date")
        end_date = data.get("end_date")
        leave_type = data.get("leave_type")
        reason = data.get("reason")

        if not all([employee_name, start_date, end_date, leave_type]):
            return jsonify({
                "success": False,
                "message": "Missing required data"
            }), 400

        success, message = leave_service.apply_leave(
            employee_name=employee_name,
            start_date_str=start_date,
            end_date_str=end_date,
            leave_type=leave_type,
            reason=reason
        )

        return jsonify({
            "success": success,
            "message": message
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


# ==========================================================
# REMOVE LEAVE (DATE RANGE)
# ==========================================================
@main.route("/api/remove_leave", methods=["POST"])
def remove_leave():
    try:
        data = request.get_json()

        employee_name = data.get("employee_name")
        start_date = data.get("start_date")
        end_date = data.get("end_date")

        if not all([employee_name, start_date, end_date]):
            return jsonify({
                "success": False,
                "message": "Missing required data"
            }), 400

        success, message = leave_service.remove_leave(
            employee_name=employee_name,
            start_date_str=start_date,
            end_date_str=end_date
        )

        return jsonify({
            "success": success,
            "message": message
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


@main.route("/api/get_leave_history", methods=["GET"])
def get_leave_history():
    try:
        leaves = LeaveApplication.query.order_by(LeaveApplication.applied_date.desc()).all()
        data = []
        for leave in leaves:
            total_days = (leave.end_date - leave.start_date).days + 1
            data.append({
                "employee_name": leave.employee_name,
                "leave_type": leave.leave_type,
                "start_date": leave.start_date.strftime("%Y-%m-%d"),
                "end_date": leave.end_date.strftime("%Y-%m-%d"),
                "total_days": total_days,
                "reason": leave.reason or "",
                "applied_date": leave.applied_date.strftime("%Y-%m-%d") if leave.applied_date else "",
                "status": "Approved"  # or get real status if you track it
            })
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500