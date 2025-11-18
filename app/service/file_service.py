import pandas as pd
from sqlalchemy import text, delete
from app import db
from app.models import AttendanceRaw, Employee
from app.service.daily_service import generate_daily_report
from app.service.monthly_service import generate_monthly_report_from_daily
from datetime import datetime
import logging
from typing import Tuple, Dict, Any

# Configure logging
logger = logging.getLogger(__name__)

# ===========================================================
#              FILE SERVICE (OPTIMIZED)
# ===========================================================
class FileService:
    """Optimized service for fast file upload and processing."""

    def __init__(self, employee_shifts=None, compensated_dates=None):
        self.employee_shifts = employee_shifts or {}
        self.compensated_dates = compensated_dates or {}
        self.batch_size = 1000  # Process records in batches

    def validate_required_columns(self, df: pd.DataFrame) -> bool:
        """Quick validation for required columns."""
        return all(col in df.columns for col in ["Name", "Time"])

    def clean_attendance_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Optimized data cleaning with vectorized operations."""
        # Create a copy to avoid SettingWithCopyWarning
        df = df.copy()
        
        # Vectorized name cleaning
        df["Name"] = (
            df["Name"]
            .astype(str)
            .str.replace(".", " ", regex=False)
            .str.replace(r"\s+", " ", regex=True)
            .str.strip()
        )

        # Vectorized time processing
        df["Time"] = pd.to_datetime(df["Time"], errors="coerce")
        df = df.dropna(subset=["Time"])
        df["Date"] = df["Time"].dt.date

        # Vectorized attendance state processing
        if "Attendance State" in df.columns:
            df["Attendance State"] = (
                pd.to_numeric(df["Attendance State"], errors="coerce")
                .fillna(-1)
                .astype(int)
            )
        else:
            df["Attendance State"] = -1

        # Optimized grouping with aggregation
        result_rows = []
        
        # Use faster groupby with named aggregation
        grouped = df.groupby(["Emp ID", "Name", "Date"], dropna=False)
        
        for (emp_id, name, date), group in grouped:
            # Use boolean indexing instead of multiple group filters
            checkin_mask = group["Attendance State"] == 0
            checkout_mask = group["Attendance State"] == 1
            
            first_in = group.loc[checkin_mask, "Time"].min() if checkin_mask.any() else None
            last_out = group.loc[checkout_mask, "Time"].max() if checkout_mask.any() else None

            if first_in is not None:
                result_rows.append({
                    "Emp ID": emp_id,
                    "Name": name,
                    "Time": first_in,
                    "Work Code": None,
                    "Attendance State": 0,
                    "Device Name": None
                })
            if last_out is not None:
                result_rows.append({
                    "Emp ID": emp_id,
                    "Name": name,
                    "Time": last_out,
                    "Work Code": None,
                    "Attendance State": 1,
                    "Device Name": None
                })

        return pd.DataFrame(result_rows) if result_rows else df

    def save_attendance_to_db(self, df: pd.DataFrame) -> None:
        """Optimized database operations with bulk inserts."""
        try:
            # Fast table truncation
            db.session.execute(delete(AttendanceRaw))
            db.session.commit()

            # Prepare data for bulk insert
            records = []
            for _, row in df.iterrows():
                records.append({
                    'emp_id': row.get("Emp ID"),
                    'name': row.get("Name"),
                    'time': row.get("Time"),
                    'work_code': row.get("Work Code"),
                    'attendance_state': str(row.get("Attendance State")) if not pd.isna(row.get("Attendance State")) else None,
                    'device_name': row.get("Device Name"),
                })

            # Bulk insert in batches
            if records:
                self._bulk_insert_attendance(records)
                
            logger.info(f"Saved {len(records)} attendance records to database")

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error saving attendance data: {e}")
            raise

    def _bulk_insert_attendance(self, records: list) -> None:
        """Bulk insert attendance records for maximum performance."""
        batch_size = self.batch_size
        
        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            db.session.bulk_insert_mappings(AttendanceRaw, batch)
            db.session.commit()
            
            if i > 0 and i % (batch_size * 10) == 0:
                logger.info(f"Processed {i} records...")

    def sync_employee_info(self, df: pd.DataFrame) -> Tuple[int, int]:
        """Optimized employee synchronization with bulk operations."""
        try:
            # Get unique employees efficiently
            unique_emps = df[["Emp ID", "Name"]].drop_duplicates(subset=["Emp ID", "Name"])
            
            # Filter out invalid records
            valid_emps = []
            for _, row in unique_emps.iterrows():
                emp_id = str(row["Emp ID"]).strip() if not pd.isna(row["Emp ID"]) else None
                name = str(row["Name"]).strip()
                
                if emp_id and name:
                    valid_emps.append((emp_id, name))

            if not valid_emps:
                return 0, 0

            # Get existing employees in one query
            emp_ids = [emp_id for emp_id, _ in valid_emps]
            existing_employees = {
                emp.emp_id: emp for emp in 
                Employee.query.filter(Employee.emp_id.in_(emp_ids)).all()
            }

            # Prepare updates and inserts
            to_update = []
            to_insert = []
            
            for emp_id, name in valid_emps:
                if emp_id in existing_employees:
                    existing_emp = existing_employees[emp_id]
                    if existing_emp.name != name:
                        existing_emp.name = name
                        to_update.append(existing_emp)
                else:
                    to_insert.append(Employee(
                        emp_id=emp_id,
                        name=name,
                        joining_date=None,
                        department=None,
                        last_updated_date=None,
                        shift=None
                    ))

            # Bulk operations
            if to_insert:
                db.session.bulk_save_objects(to_insert)
            
            if to_update:
                db.session.bulk_save_objects(to_update)
            
            db.session.commit()
            
            logger.info(f"Employee sync: {len(to_insert)} added, {len(to_update)} updated")
            return len(to_insert), len(to_update)

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error syncing employee info: {e}")
            return 0, 0

    def process_file(self, file) -> str:
        """Main file processing method with performance optimizations."""
        try:
            # Fast file reading with optimized parameters
            df = pd.read_excel(
                file, 
                engine='openpyxl',  # Faster than default for xlsx
                dtype={'Emp ID': str, 'Name': str},  # Preserve data types
                na_values=['', 'NULL', 'null'],
                keep_default_na=False
            )
            
            # Clean column names
            df.columns = df.columns.str.strip()

            # Validate required columns
            if not self.validate_required_columns(df):
                return "❌ Invalid Excel file. 'Name' and 'Time' columns are required."

            # Clean data
            logger.info("Cleaning attendance data...")
            df = self.clean_attendance_data(df)
            
            if df.empty:
                return "❌ No valid attendance records found after cleaning."

            # Save to database
            logger.info("Saving to database...")
            self.save_attendance_to_db(df)

            # Sync employee info
            logger.info("Syncing employee information...")
            added, updated = self.sync_employee_info(df)

            # Generate reports
            logger.info("Generating daily report...")
            daily_result = generate_daily_report(self.employee_shifts, self.compensated_dates)
            
            if "error" in daily_result:
                return f"⚠️ Daily report generation failed: {daily_result['error']}"

            logger.info("Generating monthly report...")
            generate_monthly_report_from_daily()

            return (
                f"✅ File '{file.filename}' processed successfully! "
                f"({added} new, {updated} updated employees) | "
                f"{daily_result.get('message', '')}"
            )

        except Exception as e:
            db.session.rollback()
            error_msg = f"❌ Error processing file: {e}"
            logger.error(error_msg)
            return error_msg

    def get_processing_stats(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Get statistics about the processed data."""
        return {
            "total_records": len(df),
            "unique_employees": df["Name"].nunique(),
            "date_range": {
                "start": df["Date"].min(),
                "end": df["Date"].max()
            } if "Date" in df.columns else {}
        }


# ===========================================================
#              EXTERNAL ENTRY POINT
# ===========================================================
def process_attendance_file(file, employee_shifts=None, compensated_dates=None) -> str:
    """External entry point for fast file processing."""
    service = FileService(employee_shifts, compensated_dates)
    return service.process_file(file)