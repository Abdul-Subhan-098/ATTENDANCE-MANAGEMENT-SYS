from datetime import datetime, date, time, timedelta
from typing import Dict, List, Optional, Tuple
from app import db
from app.models import DailyReport, Employee
from app.service.daily_service import AttendanceCalculator
import logging

logger = logging.getLogger(__name__)

class CompensationService:  
    def __init__(self):
        self.calculator = AttendanceCalculator()
    
    def apply_compensation(self, employee_name: str, violation_date: date, 
                         compensation_date: date, compensation_type: str) -> Dict[str, any]:
        try:
            logger.info(f"Applying compensation: {employee_name}, {violation_date}, {compensation_type}")
            
            employee, violation_record, compensation_record = self._fetch_records(
                employee_name, violation_date, compensation_date
            )
            if not employee:
                return {"success": False, "message": "Employee not found"}
            if not violation_record:
                return {"success": False, "message": "Violation record not found"}
                
            status_check, status_message = self._check_violation_status(
                violation_record, compensation_type
            )
            if not status_check:
                return {"success": False, "message": status_message}
            
            duplicate_check, duplicate_message = self._check_duplicate_compensation(
                employee_name, compensation_date
            )
            if not duplicate_check:
                return {"success": False, "message": duplicate_message}
            
            is_eligible, message = self._check_eligibility(
                employee, violation_record, compensation_type, compensation_date
            )
            if not is_eligible:
                return {"success": False, "message": message}
            
            self._apply_compensation_logic(
                violation_record, compensation_record, compensation_type, compensation_date
            )
            
            db.session.commit()
            self._recalculate_summaries(employee_name, violation_date, compensation_date)
            
            logger.info(f"Compensation applied successfully: {employee_name}")
            return {
                "success": True, 
                "message": f"Compensation applied successfully: {compensation_type}"
            }
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Compensation application failed: {e}")
            return {"success": False, "message": f"Error: {str(e)}"}
    
    def remove_compensation(self, employee_name: str, violation_date: date):
        """
        Remove previously applied compensation and restore original values.
        """
        try:
            logger.info(f"Removing compensation for {employee_name} on {violation_date}")

            violation_record = DailyReport.query.filter_by(
                employee_name=employee_name,
                date=violation_date
            ).first()

            if not violation_record:
                return {"success": False, "message": "Violation record not found"}

            if not violation_record.compensation_type:
                return {"success": False, "message": "No compensation applied on this violation date"}

            compensation_type = violation_record.compensation_type
            compensation_date = violation_record.compensated_date

            compensation_record = DailyReport.query.filter_by(
                employee_name=employee_name,
                date=compensation_date
            ).first()

            if compensation_type == "By Late":
                if violation_date == compensation_date:
                    violation_record.overtime = (violation_record.overtime or 0.0) + 1.0
                else:
                    if compensation_record:
                        compensation_record.overtime = (compensation_record.overtime or 0.0) + 1.0

            elif compensation_type in ["By Half Day", "By Absent"]:
                if compensation_record and compensation_date.weekday() == 5:
                    compensation_record.overtime = compensation_record.overtime_before_zero if hasattr(compensation_record, 'overtime_before_zero') else compensation_record.overtime

            violation_record.compensation_type = None
            violation_record.compensated_date = None

            db.session.commit()

            self._recalculate_summaries(employee_name, violation_date, compensation_date)

            return {"success": True, "message": "Compensation successfully removed"}

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error removing compensation: {e}")
            return {"success": False, "message": f"Error: {str(e)}"}
    
    def _fetch_records(self, employee_name: str, violation_date: date, 
                      compensation_date: date) -> Tuple[Optional[Employee], Optional[DailyReport], Optional[DailyReport]]:
        employee = Employee.query.filter_by(name=employee_name).first()
        violation_record = DailyReport.query.filter_by(
            employee_name=employee_name, 
            date=violation_date
        ).first()
        compensation_record = DailyReport.query.filter_by(
            employee_name=employee_name,
            date=compensation_date  
        ).first()
        
        return employee, violation_record, compensation_record
    
    def _check_violation_status(self, violation_record: DailyReport, compensation_type: str) -> Tuple[bool, str]:
        current_status = violation_record.status or ""
        
        if compensation_type == "By Late" and current_status != "Late":
            return False, f"Cannot apply 'By Late' compensation. Employee status was '{current_status}', not 'Late'"
            
        elif compensation_type == "By Half Day" and current_status != "Half Day":
            return False, f"Cannot apply 'By Half Day' compensation. Employee status was '{current_status}', not 'Half Day'"
            
        elif compensation_type == "By Absent" and current_status != "Absent":
            return False, f"Cannot apply 'By Absent' compensation. Employee status was '{current_status}', not 'Absent'"
        
        return True, "Status valid for compensation"
    
    def _check_duplicate_compensation(self, employee_name: str, compensation_date: date) -> Tuple[bool, str]:
        existing_compensation = DailyReport.query.filter(
            DailyReport.employee_name == employee_name,
            DailyReport.compensated_date == compensation_date
        ).first()
        
        if existing_compensation:
            return False, f"Compensation date {compensation_date} is already used for '{existing_compensation.compensation_type}' compensation of violation on {existing_compensation.date}. One compensation day cannot be used multiple times."
        
        return True, "Compensation date is available"
    
    def _check_eligibility(self, employee: Employee, violation_record: DailyReport, 
                        compensation_type: str, compensation_date: date) -> Tuple[bool, str]:
        is_full_time = self._is_employee_full_time(employee)
        violation_day = violation_record.date.weekday()
        compensation_day = compensation_date.weekday()
        is_saturday = compensation_day == 5
        is_sunday = compensation_day == 6
        
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        logger.info(f"Eligibility check: {employee.name}, "
                   f"Violation Date: {violation_record.date} ({day_names[violation_day]}), "
                   f"Compensation Date: {compensation_date} ({day_names[compensation_day]}), "
                   f"Compensation Saturday: {is_saturday}, Full-time: {is_full_time}, "
                   f"Compensation Type: {compensation_type}")
        
        if is_sunday:
            return False, "Cannot compensate on Sunday"
        
        compensation_record = DailyReport.query.filter_by(
            employee_name=employee.name,
            date=compensation_date
        ).first()
        
        if not compensation_record:
            return False, f"No attendance record found for compensation day {compensation_date}"
        
        if compensation_type == "By Late":
            compensation_ot = compensation_record.overtime or 0.0
            if compensation_ot < 1.0:
                return False, f"Cannot apply 'By Late' compensation. Compensation day must have at least 1 hour OT. Current OT: {compensation_ot}h"
            return True, "Eligible for By Late compensation"
        
        if is_full_time and is_saturday:
            if compensation_record.status not in ["Full Day (Sat)", "Half Day (Sat)", "Present", "Late"]:
                return False, f"Cannot compensate. Employee was '{compensation_record.status}' on compensation Saturday {compensation_date}"
        else:
            if compensation_record.status not in ["Present", "Late"]:
                return False, f"Cannot compensate. Employee was '{compensation_record.status}' on compensation day {compensation_date}"
        
        if not is_full_time and compensation_type in ["By Half Day", "By Absent"]:
            can_compensate, part_time_message = self._check_part_time_eligibility(employee, compensation_type, compensation_record)
            if not can_compensate:
                return False, part_time_message
        
        if compensation_type == "By Half Day":
            if is_full_time:
                if is_saturday:
                    return True, "Eligible for By Half Day compensation on Saturday"
                else:
                    return False, f"Full-timer can only compensate half day on Saturday. Selected compensation day: {day_names[compensation_day]}"
            else:
                return True, "Eligible for By Half Day compensation"
        
        elif compensation_type == "By Absent":
            if is_full_time:
                if is_saturday:
                    return True, "Eligible for By Absent compensation on Saturday"
                else:
                    return False, f"Full-timer can only compensate absent on Saturday. Selected compensation day: {day_names[compensation_day]}"
            else:
                return True, "Eligible for By Absent compensation"
                
        elif compensation_type == "Sandwich":
            eligible_days = self._get_sandwich_eligible_days(employee, violation_record.date)
            if len(eligible_days) >= 2:
                return True, f"Eligible for Sandwich policy with {len(eligible_days)} days"
            else:
                return False, f"Need 2 eligible days for Sandwich, found {len(eligible_days)}"
        
        return False, "Invalid compensation type"
    
    def _check_part_time_eligibility(self, employee: Employee, compensation_type: str, compensation_record: DailyReport) -> Tuple[bool, str]:
        try:
            worked_hours = self._calculate_actual_worked_hours(compensation_record)
            
            logger.info(f"Part-time employee {employee.name} worked {worked_hours:.1f} hours on compensation day")
            
            if worked_hours < 9.0:
                return False, f"Part-time employee must work 9+ hours on compensation day. Actual worked: {worked_hours:.1f}h"
            
            return True, "Part-time employee eligible"
            
        except Exception as e:
            logger.error(f"Error checking part-time eligibility for {employee.name}: {e}")
            return False, "Error checking part-time employee eligibility"
    
    def _calculate_actual_worked_hours(self, record: DailyReport) -> float:
        if not record.check_in or not record.check_out:
            return 0.0
        
        try:
            check_in_dt = datetime.combine(record.date, record.check_in)
            check_out_dt = datetime.combine(record.date, record.check_out)
            
            worked_seconds = (check_out_dt - check_in_dt).total_seconds()
            worked_hours = worked_seconds / 3600.0
            
            return max(0.0, worked_hours)
            
        except Exception as e:
            logger.error(f"Error calculating worked hours for {record.employee_name}: {e}")
            return 0.0
    
    def _is_employee_full_time(self, employee: Employee) -> bool:
        if not employee.shift:
            logger.warning(f"No shift defined for {employee.name}, defaulting to full-time")
            return True
            
        try:
            shift_parts = employee.shift.split('-')
            if len(shift_parts) == 2:
                shift_start = datetime.strptime(shift_parts[0].strip(), "%H:%M").time()
                shift_end = datetime.strptime(shift_parts[1].strip(), "%H:%M").time()
                return self.calculator.is_full_time_employee(shift_start, shift_end)
        except Exception as e:
            logger.error(f"Error checking employee type for {employee.name}: {e}")
            
        return True
    
    def _apply_compensation_logic(self, violation_record: DailyReport, 
                                compensation_record: DailyReport, 
                                compensation_type: str, compensation_date: date):
        logger.info(f"Applying compensation logic: {compensation_type}")
        
        violation_record.compensation_type = compensation_type
        violation_record.compensated_date = compensation_date
        
        if compensation_type == "By Late":
            self._adjust_late_compensation(violation_record, compensation_record)
        
        elif compensation_type in ["By Half Day", "By Absent"]:
            if compensation_date.weekday() == 5:
                is_full_time = self._is_employee_full_time_by_record(violation_record)
                if is_full_time:
                    if compensation_record:
                        previous_ot = compensation_record.overtime or 0.0
                        compensation_record.overtime = 0.0
                        
                        logger.info(f"Removed Saturday OT for {violation_record.employee_name} on compensation day. "
                                   f"OT: {previous_ot} -> 0.0")
    
    def _is_employee_full_time_by_record(self, record: DailyReport) -> bool:
        try:
            if record.shift:
                shift_parts = record.shift.split('-')
                if len(shift_parts) == 2:
                    shift_start = datetime.strptime(shift_parts[0].strip(), "%H:%M").time()
                    shift_end = datetime.strptime(shift_parts[1].strip(), "%H:%M").time()
                    return self.calculator.is_full_time_employee(shift_start, shift_end)
        except Exception as e:
            logger.error(f"Error checking employee type from record: {e}")
        
        return True
    
    def _adjust_late_compensation(self, violation_record: DailyReport, 
                                compensation_record: DailyReport):
        if violation_record.date == compensation_record.date:
            current_ot = violation_record.overtime or 0.0
            new_ot = max(0.0, current_ot - 1.0)
            violation_record.overtime = new_ot
            logger.info(f"Same day By Late compensation. OT adjusted from {current_ot} to {new_ot}")
        else:
            if compensation_record:
                current_ot = compensation_record.overtime or 0.0
                new_ot = max(0.0, current_ot - 1.0)
                compensation_record.overtime = new_ot
                logger.info(f"Different day By Late compensation. Compensation day OT adjusted from {current_ot} to {new_ot}")
    
    def _get_sandwich_eligible_days(self, employee: Employee, target_date: date) -> List[date]:
        is_full_time = self._is_employee_full_time(employee)
        
        start_date = target_date - timedelta(days=30)
        
        eligible_records = DailyReport.query.filter(
            DailyReport.employee_name == employee.name,
            DailyReport.date >= start_date,
            DailyReport.date <= target_date,
            DailyReport.status.in_(['Present', 'Late'])
        ).all()
        
        eligible_days = []
        for record in eligible_records:
            if is_full_time:
                if record.date.weekday() == 5:
                    eligible_days.append(record.date)
            else:
                if record.date.weekday() != 6:
                    eligible_days.append(record.date)
        
        logger.info(f"Sandwich eligible days for {employee.name}: {len(eligible_days)}")
        return eligible_days
    
    def _recalculate_summaries(self, employee_name: str, violation_date: date, 
                             compensation_date: date):
        try:
            from app.service.monthly_service import generate_monthly_report_from_daily
            
            months_to_update = set()
            months_to_update.add(violation_date.strftime("%Y-%m"))
            if compensation_date != violation_date:
                months_to_update.add(compensation_date.strftime("%Y-%m"))
            
            for month in months_to_update:
                generate_monthly_report_from_daily(month)
                logger.info(f"Regenerated monthly report for {month}")
                
        except Exception as e:
            logger.error(f"Error recalculating summaries: {e}")

    def get_compensation_history(self, employee_name: str = None, 
                               start_date: date = None, end_date: date = None) -> List[Dict]:
        query = DailyReport.query.filter(DailyReport.compensation_type.isnot(None))
        
        if employee_name:
            query = query.filter(DailyReport.employee_name == employee_name)
        if start_date:
            query = query.filter(DailyReport.date >= start_date)
        if end_date:
            query = query.filter(DailyReport.date <= end_date)
            
        records = query.order_by(DailyReport.date.desc()).all()
        
        history = []
        for record in records:
            history.append({
                "employee_name": record.employee_name,
                "violation_date": record.date.strftime("%Y-%m-%d"),
                "compensation_type": record.compensation_type,
                "compensated_date": record.compensated_date.strftime("%Y-%m-%d") if record.compensated_date else "",
                "original_status": record.status,
                "overtime": record.overtime or 0.0
            })
            
        return history