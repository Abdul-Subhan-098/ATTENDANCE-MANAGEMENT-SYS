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
    calculator = AttendanceCalculator()  # ✅ Calculator instance banaya

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

    # Aggregate data
    employees_data = defaultdict(lambda: {
        "EmpID": 0,
        "Name": "",
        "TotalDays": 0,
        "Present": 0,
        "Absent": 0,
        "Late": 0,
        "HalfDayWeekdays": 0,
        "HalfDaySat": 0,
        "FullDaySat": 0,
        "OverTime": 0.0,
    })

    for row in daily_records:
        emp = all_emps.get(row.employee_name)
        if emp and row.check_in and row.check_out:
            shift_start_str, shift_end_str = (emp.shift or "10:00 - 19:00").split("-")
            shift_start = datetime.strptime(shift_start_str.strip(), "%H:%M").time()
            shift_end = datetime.strptime(shift_end_str.strip(), "%H:%M").time()
            check_in_dt = datetime.combine(row.date, row.check_in)
            check_out_dt = datetime.combine(row.date, row.check_out)

            row.status, _ = calculator.calculate_status(check_in_dt, check_out_dt, row.date, shift_start, shift_end)
            
            row.overtime = calculator.calculate_overtime(check_in_dt, check_out_dt,
                                                        datetime.combine(row.date, shift_start),
                                                        datetime.combine(row.date, shift_end))
    db.session.commit()

    for row in daily_records:
        emp_data = employees_data[row.employee_name]
        emp_data["EmpID"] = row.emp_id or 0
        emp_data["Name"] = row.employee_name or ""
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

    # Save monthly
    for name, data in employees_data.items():
        monthly_rec = MonthlyReport.query.filter_by(name=name, report_month=month_str).first()
        emp = all_emps.get(name)
        department = emp.department if emp else "Cold Calling"
        joining_date = emp.joining_date if emp else None
        last_updated_date = emp.last_updated_date if emp else datetime.utcnow().date()

        if monthly_rec:
            monthly_rec.department = department
            monthly_rec.joining_date = joining_date
            monthly_rec.last_updated_date = last_updated_date
            monthly_rec.total_days = data["TotalDays"]
            monthly_rec.present = data["Present"]
            monthly_rec.absent = data["Absent"]
            monthly_rec.late = data["Late"]
            monthly_rec.half_day_weekdays = data["HalfDayWeekdays"]
            monthly_rec.half_day_sat = data["HalfDaySat"]
            monthly_rec.full_day_sat = data["FullDaySat"]
            monthly_rec.ot_hours = data["OverTime"]
        else:
            monthly_rec = MonthlyReport(
                emp_id=data["EmpID"],
                name=name,
                department=department,
                joining_date=joining_date,
                last_updated_date=last_updated_date,
                report_month=month_str,
                total_days=data["TotalDays"],
                present=data["Present"],
                absent=data["Absent"],
                late=data["Late"],
                half_day_weekdays=data["HalfDayWeekdays"],
                half_day_sat=data["HalfDaySat"],
                full_day_sat=data["FullDaySat"],
                ot_hours=data["OverTime"],
                compensated=0
            )
            db.session.add(monthly_rec)

    db.session.commit()

    # Return display-ready dict (no None values)
    def safe(val, default=""):
        return val if val is not None else default

    result = []
    for name, data in employees_data.items():
        emp = all_emps.get(name)
        result.append({
            "EmpID": safe(data["EmpID"], 0),
            "Name": safe(data["Name"]),
            "Department": safe(emp.department) if emp else "Cold Calling",
            "Shift": safe(emp.shift) if emp else "",
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
        })
    return result