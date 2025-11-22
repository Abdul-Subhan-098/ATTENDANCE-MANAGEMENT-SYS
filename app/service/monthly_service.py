from collections import defaultdict
from datetime import datetime, timedelta, time, date
from typing import Dict, List, Optional, Tuple, Any
from app import db
from app.models import DailyReport, MonthlyReport, Employee
from app.service.daily_service import AttendanceCalculator
import logging

# Configure logging
logger = logging.getLogger(__name__)

def generate_monthly_report_from_daily(month_str: Optional[str] = None) -> List[Dict[str, Any]]:
    """Generate monthly report from daily records, using employee shift data."""
    calculator = AttendanceCalculator() 

    if not month_str:
        latest_date = db.session.query(db.func.max(DailyReport.date)).scalar()
        if not latest_date:
            return []
        month_str = latest_date.strftime("%Y-%m")

    start_date = datetime.strptime(f"{month_str}-01", "%Y-%m-%d").date()
    next_month = start_date.replace(day=28) + timedelta(days=4)
    end_date = next_month.replace(day=1)

    daily_records = DailyReport.query.filter(
        DailyReport.date >= start_date,
        DailyReport.date < end_date
    ).all()

    if not daily_records:
        return []

    # Load all employees once
    all_emps = {e.name: e for e in Employee.query.all()}

    # Delete existing monthly reports for this month
    MonthlyReport.query.filter(MonthlyReport.report_month == month_str).delete()
    db.session.commit()

    # Aggregate data by employee
    employees_data = defaultdict(lambda: {
        "EmpID": "",
        "Name": "",
        "TotalDays": 0,
        "Present": 0,
        "Absent": 0,
        "Late": 0,
        "HalfDayWeekdays": 0,
        "HalfDaySat": 0,
        "FullDaySat": 0,
        "OverTime": 0.0,
        "Compensated": 0,
    })

    for row in daily_records:
        emp_name = row.employee_name
        emp_data = employees_data[emp_name]
        emp = all_emps.get(emp_name)
        
        # Use employee data for EmpID and other fields
        if emp:
            emp_data["EmpID"] = emp.emp_id or ""
        else:
            emp_data["EmpID"] = row.emp_id or ""
            
        emp_data["Name"] = emp_name
        emp_data["TotalDays"] += 1
        emp_data["OverTime"] += float(row.overtime or 0.0)

        status = row.status or ""
        weekday = row.date.weekday()
        
        if status == "Present":
            emp_data["Present"] += 1
        elif status == "Absent":
            emp_data["Absent"] += 1
        elif status == "Late":
            emp_data["Late"] += 1
        elif status == "Half Day":
            if weekday < 5:
                emp_data["HalfDayWeekdays"] += 1
            else:
                emp_data["HalfDaySat"] += 1
        elif status == "Half Day (Sat)":
            emp_data["HalfDaySat"] += 1
        elif status == "Full Day (Sat)":
            emp_data["FullDaySat"] += 1
        elif status == "Compensated":
            emp_data["Compensated"] += 1

    # Save monthly reports with employee data
    for name, data in employees_data.items():
        emp = all_emps.get(name)
        
        monthly_rec = MonthlyReport(
            emp_id=data["EmpID"],
            name=name,
            department=emp.department if emp else "Cold Calling",
            joining_date=emp.joining_date if emp else None,
            last_updated_date=emp.last_updated_date if emp else datetime.utcnow().date(),
            shift=emp.shift if emp else "10:00 - 19:00",  # Use employee's shift
            report_month=month_str,
            total_days=data["TotalDays"],
            present=data["Present"],
            absent=data["Absent"],
            late=data["Late"],
            half_day_weekdays=data["HalfDayWeekdays"],
            half_day_sat=data["HalfDaySat"],
            full_day_sat=data["FullDaySat"],
            ot_hours=round(data["OverTime"], 2),
            compensated=data["Compensated"]
        )
        db.session.add(monthly_rec)

    db.session.commit()

    # Return display-ready data
    def safe(val, default=""):
        return val if val is not None else default

    result = []
    for name, data in employees_data.items():
        emp = all_emps.get(name)
        result.append({
            "EmpID": safe(data["EmpID"], ""),
            "Name": safe(data["Name"]),
            "Department": safe(emp.department) if emp else "Cold Calling",
            "Shift": safe(emp.shift) if emp else "10:00 - 19:00",  # Ensure shift is included
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
            "Compensated": safe(data["Compensated"], 0),
        })
    return result