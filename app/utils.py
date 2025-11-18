import pandas as pd
from datetime import datetime, timedelta
import math
from typing import Dict, List, Tuple, Any, Optional

# ===========================================================
# CONFIGURATION CONSTANTS
# ===========================================================
DEFAULT_SHIFT = ("10:00", "19:00")
GRACE_PERIOD_MINUTES = 5
SATURDAY_FULL_DAY_HOURS = 6
MAX_OVERTIME_HOURS = 2

# ===========================================================
# CORE UTILITY FUNCTIONS
# ===========================================================

def floor_complete_hours(hours: float) -> int:
    """
    Calculate complete overtime hours with floor rounding.
    
    Args:
        hours: Decimal hours worked beyond shift
        
    Returns:
        Integer hours (0, 1, or 2)
    """
    if hours < 1:
        return 0
    return min(MAX_OVERTIME_HOURS, int(math.floor(hours)))


def compute_summaries(
    attendance_data: pd.DataFrame,
    employee_list: List[str],
    employee_shift_mapping: Dict[str, Tuple[str, str]],
    compensated_dates_mapping: Dict[str, set]
) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, List[str]]], List[Dict[str, Any]]]:
    """
    Compute attendance summaries and daily details from raw attendance data.
    
    Args:
        attendance_data: Raw attendance DataFrame
        employee_list: List of employee names
        employee_shift_mapping: Employee shift configurations
        compensated_dates_mapping: Compensated dates per employee
        
    Returns:
        Tuple of (summary_table, employee_details, daily_table)
    """
    # Initialize output structures
    summary_table = []
    employee_details = {}
    daily_records = []

    # Validate input data
    if attendance_data is None or attendance_data.empty:
        return summary_table, employee_details, daily_records

    # Preprocess attendance data
    processed_data = _preprocess_attendance_data(attendance_data)
    if processed_data.empty:
        return summary_table, employee_details, daily_records

    # Get business date range (excluding Sundays)
    business_dates = _get_business_dates(processed_data)

    # Process each employee
    for employee_name in employee_list:
        employee_summary, employee_daily_records = _process_employee_attendance(
            employee_name, processed_data, business_dates, 
            employee_shift_mapping, compensated_dates_mapping
        )
        
        if employee_summary:
            summary_table.append(employee_summary)
            daily_records.extend(employee_daily_records)

    # Sort results
    summary_table.sort(key=lambda x: x["Name"])
    daily_records.sort(key=lambda x: (x["Date"], x["Name"]))
    
    return summary_table, employee_details, daily_records


def _preprocess_attendance_data(attendance_df: pd.DataFrame) -> pd.DataFrame:
    """
    Preprocess raw attendance data for analysis.
    
    Args:
        attendance_df: Raw attendance DataFrame
        
    Returns:
        Processed DataFrame with cleaned time data
    """
    df = attendance_df.copy()
    
    # Convert and validate time data
    df["Time"] = pd.to_datetime(df["Time"], errors="coerce")
    df = df.dropna(subset=["Time"])
    
    if df.empty:
        return df
    
    # Extract date information
    df["Date"] = df["Time"].dt.date
    df["Weekday"] = df["Time"].dt.weekday
    
    return df


def _get_business_dates(attendance_df: pd.DataFrame) -> List[datetime.date]:
    """
    Get business dates from attendance data (excluding Sundays).
    
    Args:
        attendance_df: Processed attendance DataFrame
        
    Returns:
        List of business dates
    """
    if attendance_df.empty:
        return []
    
    date_range = pd.date_range(attendance_df["Date"].min(), attendance_df["Date"].max())
    return [d.date() for d in date_range if d.weekday() != 6]


def _process_employee_attendance(
    employee_name: str,
    attendance_df: pd.DataFrame, 
    business_dates: List[datetime.date],
    shift_mapping: Dict[str, Tuple[str, str]],
    compensated_mapping: Dict[str, set]
) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Process attendance data for a single employee.
    
    Args:
        employee_name: Name of the employee
        attendance_df: Processed attendance DataFrame
        business_dates: List of business dates
        shift_mapping: Employee shift configurations
        compensated_mapping: Compensated dates mapping
        
    Returns:
        Tuple of (summary_data, daily_records)
    """
    # Filter employee data
    employee_data = attendance_df[attendance_df["Name"] == employee_name]
    if employee_data.empty:
        return None, []

    # Get shift configuration
    shift_start_str, shift_end_str = shift_mapping.get(employee_name, DEFAULT_SHIFT)
    shift_start = datetime.strptime(shift_start_str, "%H:%M").time()
    shift_end = datetime.strptime(shift_end_str, "%H:%M").time()

    # Group by date and calculate aggregates
    daily_aggregates = _calculate_daily_aggregates(employee_data, shift_start)
    
    # Calculate Saturday attendance
    saturday_counts, saturday_dates = _calculate_saturday_attendance(
        daily_aggregates, shift_end_str
    )

    # Calculate valid business dates
    valid_business_dates = _get_employee_business_dates(business_dates, shift_end_str)
    
    # Calculate attendance statistics
    attendance_stats = _calculate_attendance_statistics(
        daily_aggregates, valid_business_dates, compensated_mapping.get(employee_name, set())
    )

    # Build summary record
    summary_record = {
        "Name": employee_name,
        "Shift": f"{shift_start_str}-{shift_end_str}",
        "Present": attendance_stats["present_count"],
        "Late": attendance_stats["late_count"],
        "Absent": attendance_stats["absent_count"],
        "Half_Day_Sat": saturday_counts["half_day"],
        "Full_Day_Sat": saturday_counts["full_day"],
        "OT_Hours": int(daily_aggregates["OT_Hours"].sum()) if not daily_aggregates.empty else 0
    }

    # Build daily records
    daily_records = _build_daily_records(
        employee_name, summary_record["Shift"], daily_aggregates, 
        valid_business_dates, compensated_mapping.get(employee_name, set())
    )

    return summary_record, daily_records


def _calculate_daily_aggregates(
    employee_data: pd.DataFrame, 
    shift_start_time: datetime.time
) -> pd.DataFrame:
    """
    Calculate daily aggregates for an employee.
    
    Args:
        employee_data: Filtered employee attendance data
        shift_start_time: Employee's shift start time
        
    Returns:
        DataFrame with daily aggregates
    """
    # Group by date and calculate min/max times
    daily_groups = employee_data.groupby("Date")["Time"].agg(["min", "max"]).reset_index()
    daily_groups["Weekday"] = daily_groups["Date"].apply(
        lambda d: datetime.combine(d, datetime.min.time()).weekday()
    )

    # Calculate status and overtime
    daily_groups["Status"] = daily_groups["min"].apply(
        lambda first_in: _calculate_attendance_status(first_in, shift_start_time)
    )
    
    daily_groups["OT_Hours"] = daily_groups["max"].apply(
        lambda check_out: _calculate_overtime_hours(check_out, shift_start_time)
    )

    return daily_groups


def _calculate_attendance_status(
    first_checkin: Optional[datetime], 
    shift_start: datetime.time
) -> str:
    """
    Calculate attendance status based on first check-in time.
    
    Args:
        first_checkin: First check-in time of the day
        shift_start: Scheduled shift start time
        
    Returns:
        Attendance status ("Present", "Late", or "Absent")
    """
    if pd.isna(first_checkin):
        return "Absent"
    
    scheduled_time = datetime.combine(datetime.today(), shift_start)
    grace_cutoff = scheduled_time + timedelta(minutes=GRACE_PERIOD_MINUTES)
    
    return "Late" if first_checkin.time() > grace_cutoff.time() else "Present"


def _calculate_overtime_hours(
    last_checkout: Optional[datetime],
    shift_end: datetime.time
) -> float:
    """
    Calculate overtime hours based on last check-out time.
    
    Args:
        last_checkout: Last check-out time of the day
        shift_end: Scheduled shift end time
        
    Returns:
        Overtime hours (0, 1, or 2)
    """
    if pd.isna(last_checkout):
        return 0.0
    
    # No overtime for half-day shifts
    shift_end_str = shift_end.strftime("%H:%M")
    if shift_end_str == "14:30":
        return 0.0
    
    # Calculate overtime duration
    shift_end_dt = datetime.combine(datetime.today(), shift_end)
    checkout_dt = datetime.combine(datetime.today(), last_checkout.time())
    
    overtime_seconds = (checkout_dt - shift_end_dt).total_seconds()
    overtime_hours = overtime_seconds / 3600.0
    
    return floor_complete_hours(overtime_hours)


def _calculate_saturday_attendance(
    daily_aggregates: pd.DataFrame,
    shift_end: str
) -> Tuple[Dict[str, int], Dict[str, List[str]]]:
    """
    Calculate Saturday attendance statistics.
    
    Args:
        daily_aggregates: Daily aggregates DataFrame
        shift_end: Shift end time string
        
    Returns:
        Tuple of (counts, dates) for Saturday attendance
    """
    half_day_count = 0
    full_day_count = 0
    half_dates = []
    full_dates = []

    # Only calculate for full-day shifts
    if shift_end == "19:00":
        saturday_data = daily_aggregates[daily_aggregates["Weekday"] == 5]
        
        for _, record in saturday_data.iterrows():
            if pd.isna(record["min"]) or pd.isna(record["max"]):
                continue
                
            worked_hours = (
                datetime.combine(datetime.today(), record["max"].time()) - 
                datetime.combine(datetime.today(), record["min"].time())
            ).total_seconds() / 3600.0

            date_str = str(record["Date"])
            
            if worked_hours >= SATURDAY_FULL_DAY_HOURS:
                full_day_count += 1
                full_dates.append(date_str)
            else:
                half_day_count += 1
                half_dates.append(date_str)

    return (
        {"half_day": half_day_count, "full_day": full_day_count},
        {"half_dates": half_dates, "full_dates": full_dates}
    )


def _get_employee_business_dates(
    business_dates: List[datetime.date], 
    shift_end: str
) -> List[datetime.date]:
    """
    Get valid business dates for an employee based on shift type.
    
    Args:
        business_dates: All business dates
        shift_end: Shift end time string
        
    Returns:
        Filtered list of business dates
    """
    if shift_end == "19:00":
        # Full-time employees: Monday to Friday only
        return [d for d in business_dates if d.weekday() < 5]
    else:
        # Part-time employees: Monday to Saturday
        return [d for d in business_dates if d.weekday() < 6]


def _calculate_attendance_statistics(
    daily_aggregates: pd.DataFrame,
    valid_dates: List[datetime.date],
    compensated_dates: set
) -> Dict[str, Any]:
    """
    Calculate comprehensive attendance statistics.
    
    Args:
        daily_aggregates: Daily aggregates DataFrame
        valid_dates: Valid business dates for employee
        compensated_dates: Set of compensated dates
        
    Returns:
        Dictionary of attendance statistics
    """
    recorded_dates = set(daily_aggregates["Date"].tolist())
    
    # Calculate absent dates (excluding compensated dates)
    absent_dates = [
        str(date) for date in valid_dates 
        if date not in recorded_dates and str(date) not in compensated_dates
    ]
    
    # Calculate present dates (including compensated dates)
    present_records = daily_aggregates[
        daily_aggregates["Status"].isin(["Present", "Late"])
    ]
    present_dates = set(present_records["Date"].astype(str).tolist()) | compensated_dates
    
    # Calculate late dates
    late_dates = daily_aggregates[
        daily_aggregates["Status"] == "Late"
    ]["Date"].astype(str).tolist()

    return {
        "present_count": len(present_dates),
        "late_count": len(late_dates),
        "absent_count": len(absent_dates),
        "present_dates": sorted(present_dates),
        "late_dates": sorted(late_dates),
        "absent_dates": sorted(absent_dates)
    }


def _build_daily_records(
    employee_name: str,
    shift_display: str,
    daily_aggregates: pd.DataFrame,
    valid_dates: List[datetime.date],
    compensated_dates: set
) -> List[Dict[str, Any]]:
    """
    Build daily attendance records for an employee.
    
    Args:
        employee_name: Employee name
        shift_display: Shift display string
        daily_aggregates: Daily aggregates DataFrame
        valid_dates: Valid business dates
        compensated_dates: Set of compensated dates
        
    Returns:
        List of daily records
    """
    daily_records = []
    
    for date in valid_dates:
        date_str = str(date)
        daily_record = daily_aggregates[daily_aggregates["Date"] == date]
        
        if not daily_record.empty:
            record_data = daily_record.iloc[0]
            checkin_time = record_data["min"]
            checkout_time = record_data["max"]
            
            checkin_str = checkin_time.strftime("%H:%M") if not pd.isna(checkin_time) else ""
            checkout_str = checkout_time.strftime("%H:%M") if not pd.isna(checkout_time) else ""
            
            status = "Present" if date_str in compensated_dates else record_data["Status"]
            late_flag = "Late" if status == "Late" else ""
            
        else:
            checkin_str = checkout_str = ""
            status = "Present" if date_str in compensated_dates else "Absent"
            late_flag = ""
        
        daily_records.append({
            "Date": date_str,
            "Name": employee_name,
            "Shift": shift_display,
            "CheckIn": checkin_str,
            "CheckOut": checkout_str,
            "Status": status,
            "Late": late_flag
        })
    
    return daily_records