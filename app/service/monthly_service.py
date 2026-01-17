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

# Constants for missed punches
HALF_DAY_MISSED_IN = "HD (Missed IN)"
HALF_DAY_MISSED_OUT = "HD (Missed OUT)"

def generate_monthly_report_from_daily(month_str: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Generate monthly report from DailyReport table.
    Returns a list of dictionaries for display or API.
    """
    calculator = AttendanceCalculator()

    # Determine the month to process
    if not month_str:
        latest_date = db.session.query(db.func.max(DailyReport.date)).scalar()
        if not latest_date:
            logger.warning("No daily records found to generate monthly report.")
            return []
        month_str = latest_date.strftime("%Y-%m")

    start_date = datetime.strptime(f"{month_str}-01", "%Y-%m-%d").date()
    next_month = start_date.replace(day=28) + timedelta(days=4)
    end_date = next_month.replace(day=1)

    # Fetch daily records for that month
    daily_records = DailyReport.query.filter(
        DailyReport.date >= start_date,
        DailyReport.date < end_date
    ).all()

    if not daily_records:
        logger.info(f"No daily records found for month {month_str}")
        return []

    # Fetch all employees
    all_emps = {e.name: e for e in Employee.query.all()}

    # Determine if this is latest month
    latest_daily_date = db.session.query(db.func.max(DailyReport.date)).scalar()
    latest_month_str = latest_daily_date.strftime("%Y-%m") if latest_daily_date else None
    is_latest_month = month_str == latest_month_str

    # Delete old monthly report for that month
    try:
        MonthlyReport.query.filter(MonthlyReport.report_month == month_str).delete()
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting old monthly reports: {e}")

    # Initialize employee data dictionary
    employees_data = defaultdict(lambda: {
        "EmpID": "",
        "Name": "",
        "Gender": "Male",
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
        "PunchMissedCount": 0,
        "CompanyOff": set(),
        "MedicalLeave": 0,
        "CasualLeave": 0
    })

    # ========================
    # Process daily records
    # ========================
    for row in daily_records:
        emp_name = row.employee_name
        emp_data = employees_data[emp_name]
        emp = all_emps.get(emp_name)

        emp_data["EmpID"] = emp.emp_id if emp else row.emp_id or ""
        emp_data["Name"] = emp_name
        emp_data["Gender"] = getattr(row, "gender", "Male") or "Male"
        emp_data["TotalDays"] += 1

        status = row.status or ""
        leave_type = getattr(row, "leave_type", None)

        # Count medical/casual leave
        if leave_type:
            if leave_type.lower() == "medical":
                emp_data["MedicalLeave"] += 1
            elif leave_type.lower() == "casual":
                emp_data["CasualLeave"] += 1

        # Determine full-time based on shift
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

        weekday = row.date.weekday()

        # Company day off
        if status == "Company Day Off":
            emp_data["CompanyOff"].add(row.date)
            continue

        # Count attendance
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
        elif status in [HALF_DAY_MISSED_IN, HALF_DAY_MISSED_OUT]:
            emp_data["PunchMissedCount"] += 1

        # OT for full-timers Mon–Fri
        if is_full_time and weekday < 5:
            emp_data["OverTime"] += float(row.overtime or 0.0)

        # Compensation types
        comp_type = getattr(row, 'compensation_type', None)
        if comp_type:
            if comp_type == "By Late":
                emp_data["ByLateCount"] += 1
            elif comp_type == "By Half Day":
                emp_data["ByHalfDayCount"] += 1
            elif comp_type == "By Absent":
                emp_data["ByAbsentCount"] += 1

    # ========================
    # Save monthly report
    # ========================
    year, month = map(int, month_str.split('-'))
    total_days_in_month = monthrange(year, month)[1]

    for name, data in employees_data.items():
        emp = all_emps.get(name)

        data["Late"] = max(0, data["Late"] - data["ByLateCount"])
        data["HalfDayWeekdays"] = max(0, data["HalfDayWeekdays"] - data["ByHalfDayCount"])
        data["Absent"] = max(0, data["Absent"] - data["ByAbsentCount"])

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

        working_days = 0
        for day in range(1, total_days_in_month + 1):
            current_date = datetime(year, month, day).date()
            weekday = current_date.weekday()
            if is_latest_month and emp and emp.joining_date and current_date < emp.joining_date:
                continue
            if current_date in data["CompanyOff"]:
                continue
            if is_full_time_emp and weekday < 5:
                working_days += 1
            elif not is_full_time_emp and weekday != 6:
                working_days += 1

        monthly_rec = MonthlyReport(
            emp_id=data["EmpID"],
            name=name,
            gender=data.get("Gender", "Male"),
            department=emp.department if emp else "Cold Calling",
            joining_date=emp.joining_date if emp else None,
            last_updated_date=emp.last_updated_date if emp else datetime.utcnow().date(),
            shift=emp.shift if emp else "10:00 - 19:00",
            role=getattr(emp, "role", "FullTime") if emp else "FullTime",
            report_month=month_str,
            total_days=data["TotalDays"],
            present=data["Present"],
            absent=data["Absent"],
            late=data["Late"],
            half_day_weekdays=data["HalfDayWeekdays"],
            half_day_sat=data["HalfDaySat"],
            full_day_sat=data["FullDaySat"],
            ot_hours=round(data["OverTime"], 2),
            compensated=data["Compensated"],
            sundays=data["Sundays"],
            working_days=working_days,
            punch_missed=data["PunchMissedCount"],
            by_late_count=data["ByLateCount"],
            by_half_day_count=data["ByHalfDayCount"],
            by_absent_count=data["ByAbsentCount"],
            medical_leave=data["MedicalLeave"],
            casual_leave=data["CasualLeave"]
        )
        db.session.add(monthly_rec)

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error inserting monthly reports: {e}")
        return []

    # ========================
    # Prepare results for display
    # ========================
    def safe(val, default=0):
        return val if val is not None else default

    results = []
    for name, data in employees_data.items():
        emp = all_emps.get(name)
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

        working_days = 0
        for day in range(1, total_days_in_month + 1):
            current_date = datetime(year, month, day).date()
            weekday = current_date.weekday()
            if is_latest_month and emp and emp.joining_date and current_date < emp.joining_date:
                continue
            if current_date in data["CompanyOff"]:
                continue
            if is_full_time_emp and weekday < 5:
                working_days += 1
            elif not is_full_time_emp and weekday != 6:
                working_days += 1

        results.append({
            "EmpID": safe(data["EmpID"]),
            "Name": safe(data["Name"]),
            "Gender": data.get("Gender", "Male"),
            "Department": emp.department if emp else "Cold Calling",
            "Shift": emp.shift if emp else "10:00 - 19:00",
            "Role": getattr(emp, "role", "FullTime") if emp else "FullTime",
            "EmployeeType": "Full-Time" if is_full_time_emp else "Part-Time",
            "JoiningDate": emp.joining_date.strftime("%Y-%m-%d") if emp and emp.joining_date else "",
            "LastUpdated": emp.last_updated_date.strftime("%Y-%m-%d") if emp and emp.last_updated_date else "",
            "TotalDays": safe(data["TotalDays"]),
            "Present": safe(data["Present"]),
            "Absent": safe(data["Absent"]),
            "Late": safe(data["Late"]),
            "HalfDayWeekdays": safe(data["HalfDayWeekdays"]),
            "HalfDaySat": safe(data["HalfDaySat"]),
            "FullDaySat": safe(data["FullDaySat"]),
            "OverTime": round(float(data["OverTime"]), 2),
            "Sundays": safe(data["Sundays"]),
            "Compensated": safe(data["Compensated"]),
            "ByLateCount": safe(data["ByLateCount"]),
            "ByHalfDayCount": safe(data["ByHalfDayCount"]),
            "ByAbsentCount": safe(data["ByAbsentCount"]),
            "WorkingDays": working_days,
            "PunchMissed": safe(data["PunchMissedCount"]),
            "MedicalLeave": safe(data["MedicalLeave"]),
            "CasualLeave": safe(data["CasualLeave"]),
            "Month": month_str
        })

    return results