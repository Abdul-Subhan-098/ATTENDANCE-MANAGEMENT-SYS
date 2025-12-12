from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from calendar import monthrange
from app import db
from app.models import DailyReport, MonthlyReport, Employee
from app.service.daily_service import AttendanceCalculator
import logging

# Configure logging
logger = logging.getLogger(__name__)

def generate_monthly_report_from_daily(month_str: Optional[str] = None) -> List[Dict[str, Any]]:
    calculator = AttendanceCalculator()

    # Determine month
    if not month_str:
        latest_date = db.session.query(db.func.max(DailyReport.date)).scalar()
        if not latest_date:
            logger.warning("No daily records found to generate monthly report.")
            return []
        month_str = latest_date.strftime("%Y-%m")

    start_date = datetime.strptime(f"{month_str}-01", "%Y-%m-%d").date()
    next_month = start_date.replace(day=28) + timedelta(days=4)
    end_date = next_month.replace(day=1)

    # Fetch daily records
    daily_records = DailyReport.query.filter(
        DailyReport.date >= start_date,
        DailyReport.date < end_date
    ).all()

    logger.info(f"Found {len(daily_records)} daily records for month {month_str}")
    if not daily_records:
        return []

    # All employees
    all_emps = {e.name: e for e in Employee.query.all()}

    # Determine latest month in DB
    latest_daily_date = db.session.query(db.func.max(DailyReport.date)).scalar()
    latest_month_str = latest_daily_date.strftime("%Y-%m") if latest_daily_date else None
    is_latest_month = month_str == latest_month_str

    # Delete old monthly reports
    try:
        MonthlyReport.query.filter(MonthlyReport.report_month == month_str).delete()
        db.session.commit()
        logger.info(f"Deleted old monthly report for month {month_str}")
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting monthly report: {e}")

    # Employee data storage
    employees_data = defaultdict(lambda: {
        "EmpID": "",
        "Name": "",
        "Gender": "Male",  # Added from A
        "TotalDays": 0,
        "Present": 0,
        "Absent": 0,
        "Late": 0,
        "HalfDayWeekdays": 0,
        "HalfDaySat": 0,
        "FullDaySat": 0,
        "OverTime": 0.0,
        "Sundays": 0,
        "Compensated": 0,
        "ByLateCount": 0,
        "ByHalfDayCount": 0,
        "ByAbsentCount": 0,
        "CompanyOff": set()  # From B
    })

    # ========================
    # Process daily records
    # ========================
    for row in daily_records:
        emp_name = row.employee_name
        emp_data = employees_data[emp_name]
        emp = all_emps.get(emp_name)

        # Employee basic info
        emp_data["EmpID"] = emp.emp_id if emp else row.emp_id or ""
        emp_data["Name"] = emp_name
        emp_data["Gender"] = getattr(row, "gender", "Male") or "Male"  # Added from A
        emp_data["TotalDays"] += 1

        # Determine full-time based on shift duration
        is_full_time = True
        if emp and emp.shift:
            try:
                shift_parts = emp.shift.split('-')
                if len(shift_parts) == 2:
                    shift_start = datetime.strptime(shift_parts[0].strip(), "%H:%M").time()
                    shift_end = datetime.strptime(shift_parts[1].strip(), "%H:%M").time()
                    is_full_time = calculator.is_full_time_employee(shift_start, shift_end)
            except Exception as e:
                logger.warning(f"Error parsing shift for {emp_name}: {e}")

        status = row.status or ""
        weekday = row.date.weekday()

        # Capture company off (From B)
        if status == "Company Day Off":
            emp_data["CompanyOff"].add(row.date)
            continue  # Company Off → skip counts except working days

        # Count attendance status
        if status == "Present":
            emp_data["Present"] += 1
        elif status == "Absent":
            emp_data["Absent"] += 1
        elif status == "Late":
            emp_data["Late"] += 1
        elif status == "Half Day":
            emp_data["HalfDayWeekdays"] += 1
        elif status == "Full Day (Sat)":
            emp_data["FullDaySat"] += 1
        elif status == "Half Day (Sat)":
            emp_data["HalfDaySat"] += 1
        elif status == "Sunday":
            emp_data["Sundays"] += 1
        elif status == "Compensated":
            emp_data["Compensated"] += 1

        # OT logic for full-timers Mon–Fri
        if is_full_time and weekday < 5:
            emp_data["OverTime"] += float(row.overtime or 0.0)

        # Compensation counting
        compensation_type = getattr(row, 'compensation_type', None)
        if compensation_type:
            if compensation_type == "By Late":
                emp_data["ByLateCount"] += 1
            elif compensation_type == "By Half Day":
                emp_data["ByHalfDayCount"] += 1
            elif compensation_type == "By Absent":
                emp_data["ByAbsentCount"] += 1

    # ========================
    # Save monthly report
    # ========================
    inserted = 0
    year, month = map(int, month_str.split('-'))
    total_days_in_month = monthrange(year, month)[1]

    for name, data in employees_data.items():
        emp = all_emps.get(name)

        # APPLY FIX FROM A: Reduce Late Count by ByLateCount
        data["Late"] = max(0, data["Late"] - data["ByLateCount"])

        # Determine full-time for working days
        is_full_time_emp = True
        if emp and emp.shift:
            try:
                shift_parts = emp.shift.split('-')
                if len(shift_parts) == 2:
                    shift_start = datetime.strptime(shift_parts[0].strip(), "%H:%M").time()
                    shift_end = datetime.strptime(shift_parts[1].strip(), "%H:%M").time()
                    is_full_time_emp = calculator.is_full_time_employee(shift_start, shift_end)
            except Exception:
                pass

        # Calendar-based working days with Company Off exclusion (From B)
        working_days = 0
        for day in range(1, total_days_in_month + 1):
            current_date = datetime(year, month, day).date()
            weekday = current_date.weekday()

            # Skip days before joining (latest month only)
            if is_latest_month and emp and emp.joining_date and emp.joining_date > start_date:
                if current_date < emp.joining_date:
                    continue

            # Skip Company Day Off (From B)
            if current_date in data["CompanyOff"]:
                continue

            if is_full_time_emp:
                if weekday < 5:
                    working_days += 1
            else:
                if weekday != 6:
                    working_days += 1

        monthly_rec = MonthlyReport(
            emp_id=data["EmpID"],
            name=name,
            gender=data.get("Gender", "Male") or "Male",  # Added from A
            department=emp.department if emp else "Cold Calling",
            joining_date=emp.joining_date if emp else None,
            last_updated_date=emp.last_updated_date if emp else datetime.utcnow().date(),
            shift=emp.shift if emp else "10:00 - 19:00",
            role=getattr(emp, 'role', 'FullTime') if emp else "FullTime",
            report_month=month_str,
            total_days=data["TotalDays"],
            present=data["Present"],
            absent=data["Absent"],
            late=data["Late"],  # Already adjusted above
            half_day_weekdays=data["HalfDayWeekdays"],
            half_day_sat=data["HalfDaySat"],
            full_day_sat=data["FullDaySat"],
            ot_hours=round(data["OverTime"], 2),
            compensated=data["Compensated"],
            sundays=data["Sundays"],
            working_days=working_days
        )

        monthly_rec.by_late_count = data["ByLateCount"]
        monthly_rec.by_half_day_count = data["ByHalfDayCount"]
        monthly_rec.by_absent_count = data["ByAbsentCount"]

        db.session.add(monthly_rec)
        inserted += 1

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error inserting monthly reports: {e}")
        return []

    # ========================
    # Prepare results for display
    # ========================
    def safe(val, default=""):
        return val if val is not None else default

    results = []
    for name, data in employees_data.items():
        emp = all_emps.get(name)

        # APPLY FIX AGAIN FOR API RESPONSE (From A)
        data["Late"] = max(0, data["Late"] - data["ByLateCount"])

        # Determine full-time for API response
        is_full_time_emp = True
        if emp and emp.shift:
            try:
                shift_parts = emp.shift.split('-')
                if len(shift_parts) == 2:
                    shift_start = datetime.strptime(shift_parts[0].strip(), "%H:%M").time()
                    shift_end = datetime.strptime(shift_parts[1].strip(), "%H:%M").time()
                    is_full_time_emp = calculator.is_full_time_employee(shift_start, shift_end)
            except Exception:
                pass

        # Working days for display with Company Off exclusion (From B)
        working_days = 0
        for day in range(1, total_days_in_month + 1):
            current_date = datetime(year, month, day).date()
            weekday = current_date.weekday()
            
            if is_latest_month and emp and emp.joining_date and emp.joining_date > start_date:
                if current_date < emp.joining_date:
                    continue
            
            # Skip Company Day Off (From B)
            if current_date in data["CompanyOff"]:
                continue
                
            if is_full_time_emp and weekday < 5:
                working_days += 1
            elif not is_full_time_emp and weekday != 6:
                working_days += 1

        results.append({
            "EmpID": safe(data["EmpID"], ""),
            "Name": safe(data["Name"]),
            "Gender": data.get("Gender", "Male") or "Male",  # Added from A
            "Department": safe(emp.department) if emp else "Cold Calling",
            "Shift": safe(emp.shift) if emp else "10:00 - 19:00",
            "Role": safe(getattr(emp, 'role', 'FullTime')) if emp else "FullTime",
            "EmployeeType": "Full-Time" if is_full_time_emp else "Part-Time",
            "JoiningDate": emp.joining_date.strftime("%Y-%m-%d") if emp and emp.joining_date else "",
            "LastUpdated": emp.last_updated_date.strftime("%Y-%m-%d") if emp and emp.last_updated_date else "",
            "TotalDays": safe(data["TotalDays"], 0),
            "Present": safe(data["Present"], 0),
            "Absent": safe(data["Absent"], 0),
            "Late": safe(data["Late"], 0),
            "HalfDayWeekdays": safe(data["HalfDayWeekdays"], 0),
            "HalfDaySat": safe(data["HalfDaySat"], 0),
            "FullDaySat": safe(data["FullDaySat"], 0),
            "OverTime": round(float(data["OverTime"] or 0.0), 2),
            "Sundays": safe(data["Sundays"], 0),
            "Compensated": safe(data["Compensated"], 0),
            "ByLateCount": safe(data["ByLateCount"], 0),
            "ByHalfDayCount": safe(data["ByHalfDayCount"], 0),
            "ByAbsentCount": safe(data["ByAbsentCount"], 0),
            "WorkingDays": working_days
        })

    return results