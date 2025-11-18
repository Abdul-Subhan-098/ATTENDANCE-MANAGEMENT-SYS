# app/service/file_service.py

import pandas as pd
from app import db
from app.models import AttendanceRaw
from datetime import datetime
from app.service.daily_service import generate_daily_report
from app.service.monthly_service import generate_monthly_report_from_daily
from app.models import Employee
from datetime import date

class FileService:
    def __init__(self, employee_shifts=None, compensated_dates=None):
        self.employee_shifts = employee_shifts or {}
        self.compensated_dates = compensated_dates or {}

    def validate_required_columns(self, df):
        return all(col in df.columns for col in ["Name", "Time"])

    def clean_attendance_data(self, df):
        df["Name"] = (
            df["Name"]
            .astype(str)
            .str.replace(".", " ", regex=False)
            .str.replace(r"\s+", " ", regex=True)
            .str.strip()
        )

        df["Time"] = pd.to_datetime(df["Time"], errors="coerce")
        df = df.dropna(subset=["Time"])
        df["Date"] = df["Time"].dt.date

        if "Attendance State" in df.columns:
            df["Attendance State"] = pd.to_numeric(df["Attendance State"], errors="coerce").fillna(-1).astype(int)
        else:
            df["Attendance State"] = -1

        result_rows = []
        for (emp_id, name, date), group in df.groupby(["Emp ID", "Name", "Date"], dropna=False):
            checkins = group[group["Attendance State"] == 0]
            checkouts = group[group["Attendance State"] == 1]

            first_in = checkins["Time"].min() if not checkins.empty else None
            last_out = checkouts["Time"].max() if not checkouts.empty else None

            if first_in:
                result_rows.append({
                    "Emp ID": emp_id,
                    "Name": name,
                    "Time": first_in,
                    "Work Code": None,
                    "Attendance State": 0,
                    "Device Name": None
                })
            if last_out:
                result_rows.append({
                    "Emp ID": emp_id,
                    "Name": name,
                    "Time": last_out,
                    "Work Code": None,
                    "Attendance State": 1,
                    "Device Name": None
                })

        cleaned_df = pd.DataFrame(result_rows)
        return cleaned_df if not cleaned_df.empty else df

    def save_attendance_to_db(self, df):
        AttendanceRaw.query.delete()
        for _, row in df.iterrows():
            record = AttendanceRaw(
                emp_id=row.get("Emp ID"),
                name=row.get("Name"),
                time=row.get("Time"),
                work_code=row.get("Work Code"),
                attendance_state=str(row.get("Attendance State")) if not pd.isna(row.get("Attendance State")) else None,
                device_name=row.get("Device Name"),
            )
            db.session.add(record)
        db.session.commit()

    def process_file(self, file):
        try:
            df = pd.read_excel(file)
            df.columns = df.columns.str.strip()

            if not self.validate_required_columns(df):
                return "❌ Invalid Excel file. 'Name' and 'Time' columns are required."

            df = self.clean_attendance_data(df)
            self.save_attendance_to_db(df)

            # 🔹 STEP 1: Sync employee info (only Emp ID + Name)
            unique_emps = df[["Emp ID", "Name"]].drop_duplicates(subset=["Emp ID", "Name"])
            added, updated = 0, 0

            for _, row in unique_emps.iterrows():
                emp_id = str(row["Emp ID"]).strip() if not pd.isna(row["Emp ID"]) else None
                name = str(row["Name"]).strip()

                if not emp_id or not name:
                    continue

                existing = Employee.query.filter_by(emp_id=emp_id).first()

                if not existing:
                    # New employee → only insert Emp ID and Name
                    emp = Employee(
                        emp_id=emp_id,
                        name=name,
                        joining_date=None,         # Keep NULL
                        department=None,           # Keep NULL
                        last_updated_date=None,    # Keep NULL
                        shift=None                 # Keep NULL
                    )
                    db.session.add(emp)
                    added += 1
                else:
                    # If name changed, update it
                    if existing.name != name:
                        existing.name = name
                        updated += 1

            db.session.commit()

            # 🔹 STEP 2: Generate reports
            daily_result = generate_daily_report(self.employee_shifts, self.compensated_dates)
            if "error" in daily_result:
                return f"⚠️ Daily report generation failed: {daily_result['error']}"

            generate_monthly_report_from_daily()

            return (
                f"✅ File '{file.filename}' processed successfully! "
                f"({added} new, {updated} updated employees) | "
                f"{daily_result.get('message', '')}"
            )

        except Exception as e:
            db.session.rollback()
            return f"❌ Error processing file: {e}"
