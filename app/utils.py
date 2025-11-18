import pandas as pd
from datetime import datetime, timedelta
import math

def floor_complete_hours(hours):
    if hours < 1:
        return 0
    return min(2, int(math.floor(hours)))

def compute_summaries(full_attendance, all_employees, employee_shifts, compensated_dates):
    emp_details = {}
    table = []
    daily_table = []

    if full_attendance is None or full_attendance.empty:
        return table, emp_details, daily_table

    # Make sure Time column is datetime
    full_attendance["Time"] = pd.to_datetime(full_attendance["Time"], errors="coerce")
    full_attendance = full_attendance.dropna(subset=["Time"])
    full_attendance["Date"] = full_attendance["Time"].dt.date

    # Date range (excluding Sundays)
    date_range = pd.date_range(full_attendance["Date"].min(), full_attendance["Date"].max())
    business_dates = [d.date() for d in date_range if d.weekday() != 6]

    for emp in all_employees:
        emp_df = full_attendance[full_attendance["Name"] == emp]
        shift_start_str, shift_end_str = employee_shifts.get(emp, ("10:00", "19:00"))
        start_time = datetime.strptime(shift_start_str, "%H:%M").time()
        end_time = datetime.strptime(shift_end_str, "%H:%M").time()

        # Group by date
        daily = emp_df.groupby("Date")["Time"].agg(["min", "max"]).reset_index()
        daily["Weekday"] = daily["Date"].apply(lambda d: datetime.combine(d, datetime.min.time()).weekday())

        # Determine status
        def mark_status(first_in):
            if pd.isna(first_in):
                return "Absent"
            scheduled = datetime.combine(datetime.today(), start_time)
            grace = scheduled + timedelta(minutes=5)
            return "Late" if first_in.time() > grace.time() else "Present"

        daily["Status"] = daily["min"].apply(mark_status)

        # OT hours
        def calc_ot(checkout):
            if shift_end_str == "14:30":
                return 0
            diff = (datetime.combine(datetime.today(), checkout.time()) - datetime.combine(datetime.today(), end_time)).total_seconds() / 3600.0
            return floor_complete_hours(diff)

        daily["OT_Hours"] = daily["max"].apply(calc_ot)

        # Saturday (half/full)
        half_day_sat = 0
        full_day_sat = 0
        half_dates = []
        full_dates = []
        if shift_end_str == "19:00":
            sat_rows = daily[daily["Weekday"] == 5]
            for _, r in sat_rows.iterrows():
                worked = (datetime.combine(datetime.today(), r["max"].time()) - datetime.combine(datetime.today(), r["min"].time())).total_seconds() / 3600.0
                if worked >= 6:
                    full_day_sat += 1
                    full_dates.append(str(r["Date"]))
                else:
                    half_day_sat += 1
                    half_dates.append(str(r["Date"]))

        # Valid days
        if shift_end_str == "19:00":
            valid_dates = [d for d in business_dates if d.weekday() < 5]
        else:
            valid_dates = [d for d in business_dates if d.weekday() < 6]

        recorded_dates = daily["Date"].tolist()
        absent_dates = [str(d) for d in valid_dates if d not in recorded_dates]

        # Compensations
        comp_set = compensated_dates.get(emp, set())
        absent_dates = [d for d in absent_dates if d not in comp_set]

        present_dates = daily[daily["Status"].isin(["Present", "Late"])]["Date"].astype(str).tolist()
        present_dates = sorted(set(present_dates) | set(comp_set))
        late_dates = daily[daily["Status"] == "Late"]["Date"].astype(str).tolist()
        ot_dates = daily[daily["OT_Hours"] > 0]["Date"].astype(str).tolist()

        emp_details[emp] = {
            "Present": sorted(present_dates),
            "Late": sorted(late_dates),
            "Absent": sorted(absent_dates),
            "Half_Day_Sat": sorted(half_dates),
            "Full_Day_Sat": sorted(full_dates),
            "OT": sorted(ot_dates)
        }

        summary_row = {
            "Name": emp,
            "Shift": f"{shift_start_str}-{shift_end_str}",
            "Present": len(present_dates),
            "Late": len(late_dates),
            "Absent": len(absent_dates),
            "Half_Day_Sat": half_day_sat,
            "Full_Day_Sat": full_day_sat,
            "OT_Hours": int(daily["OT_Hours"].sum()) if not daily["OT_Hours"].empty else 0
        }
        table.append(summary_row)

        # Daily table
        for d in business_dates:
            d_str = str(d)
            rec = daily[daily["Date"] == d]
            if not rec.empty:
                rec_row = rec.iloc[0]
                checkin = rec_row["min"]
                checkout = rec_row["max"]
                checkin_str = checkin.strftime("%H:%M") if not pd.isna(checkin) else ""
                checkout_str = checkout.strftime("%H:%M") if not pd.isna(checkout) else ""
                status = rec_row["Status"]
                if d_str in comp_set:
                    status = "Present"
                late_flag = "Late" if status == "Late" else ""
                daily_table.append({
                    "Date": d_str, "Name": emp, "Shift": summary_row["Shift"],
                    "CheckIn": checkin_str, "CheckOut": checkout_str,
                    "Status": status, "Late": late_flag
                })
            else:
                status = "Present" if d_str in comp_set else "Absent"
                daily_table.append({
                    "Date": d_str, "Name": emp, "Shift": summary_row["Shift"],
                    "CheckIn": "", "CheckOut": "",
                    "Status": status, "Late": ""
                })

    table = sorted(table, key=lambda x: x["Name"])
    daily_table = sorted(daily_table, key=lambda x: (x["Date"], x["Name"]))
    return table, emp_details, daily_table
