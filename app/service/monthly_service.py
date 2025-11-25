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
    """Generate monthly report from daily records - UPDATED to remove Saturday columns"""
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

    # Aggregate data by employee - UPDATED structure
    employees_data = defaultdict(lambda: {
        "EmpID": "",
        "Name": "",
        "TotalDays": 0,
        "Present": 0,
        "Absent": 0,
        "Late": 0,
        "HalfDayWeekdays": 0,
        "OverTime": 0.0,  # Now includes Saturday hours for full-timers
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
        
        # Determine if employee is full-time
        is_full_time = True  # Default
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
        
        # Count statuses - UPDATED: No separate Saturday columns
        if status == "Present":
            emp_data["Present"] += 1
        elif status == "Absent":
            emp_data["Absent"] += 1
        elif status == "Late":
            emp_data["Late"] += 1
        elif status == "Half Day":
            # All half days go to same counter now
            emp_data["HalfDayWeekdays"] += 1
        
        # Overtime calculation - UPDATED for Saturday logic
        overtime_to_add = float(row.overtime or 0.0)
        
        # For full-timers on Saturday, add all hours as OT
        if weekday == 5 and is_full_time and row.check_in and row.check_out:
            # Calculate actual hours worked on Saturday
            check_in_dt = datetime.combine(row.date, row.check_in)
            check_out_dt = datetime.combine(row.date, row.check_out)
            saturday_hours = (check_out_dt - check_in_dt).total_seconds() / 3600.0
            overtime_to_add = saturday_hours  # Override with actual hours
        
        emp_data["OverTime"] += overtime_to_add

        if status == "Compensated":
            emp_data["Compensated"] += 1

    # Save monthly reports with updated structure
    for name, data in employees_data.items():
        emp = all_emps.get(name)
        
        monthly_rec = MonthlyReport(
            emp_id=data["EmpID"],
            name=name,
            department=emp.department if emp else "Cold Calling",
            joining_date=emp.joining_date if emp else None,
            last_updated_date=emp.last_updated_date if emp else datetime.utcnow().date(),
            shift=emp.shift if emp else "10:00 - 19:00",
            report_month=month_str,
            total_days=data["TotalDays"],
            present=data["Present"],
            absent=data["Absent"],
            late=data["Late"],
            half_day_weekdays=data["HalfDayWeekdays"],
            half_day_sat=0,  # Set to 0 as column is deprecated
            full_day_sat=0,  # Set to 0 as column is deprecated
            ot_hours=round(data["OverTime"], 2),
            compensated=data["Compensated"]
        )
        db.session.add(monthly_rec)

    db.session.commit()

    # Return display-ready data with updated structure
    def safe(val, default=""):
        return val if val is not None else default

    result = []
    for name, data in employees_data.items():
        emp = all_emps.get(name)
        result.append({
            "EmpID": safe(data["EmpID"], ""),
            "Name": safe(data["Name"]),
            "Department": safe(emp.department) if emp else "Cold Calling",
            "Shift": safe(emp.shift) if emp else "10:00 - 19:00",
            "JoiningDate": emp.joining_date.strftime("%Y-%m-%d") if emp and emp.joining_date else "",
            "LastUpdated": emp.last_updated_date.strftime("%Y-%m-%d") if emp and emp.last_updated_date else "",
            "TotalDays": safe(data["TotalDays"], 0),
            "Present": safe(data["Present"], 0),
            "Absent": safe(data["Absent"], 0),
            "Late": safe(data["Late"], 0),
            "HalfDayWeekdays": safe(data["HalfDayWeekdays"], 0),
            # Removed: "HalfDaySat" and "FullDaySat" columns
            "OverTime": round(float(data["OverTime"] or 0.0), 2),
            "Compensated": safe(data["Compensated"], 0),
        })
    return result