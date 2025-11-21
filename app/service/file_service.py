import pandas as pd
from sqlalchemy import text, delete, func
from app import db
from app.models import AttendanceRaw, Employee
from app.service.daily_service import generate_daily_report
from app.service.monthly_service import generate_monthly_report_from_daily
from datetime import datetime
import logging
import uuid
from typing import Tuple, Dict, Any, List

# Configure logging
logger = logging.getLogger(__name__)

# ===========================================================
#              FILE SERVICE (UPDATED FOR FILE TRACKING)
# ===========================================================
class FileService:
    """File service with file tracking in attendance_raw table."""

    def __init__(self, employee_shifts=None, compensated_dates=None):
        self.employee_shifts = employee_shifts or {}
        self.compensated_dates = compensated_dates or {}
        self.batch_size = 1000

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

        return df

    def save_attendance_to_db(self, df: pd.DataFrame, original_filename: str) -> str:
        """Save attendance data with file tracking."""
        try:
            # Generate unique batch ID for this upload
            batch_id = f"batch_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
            
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
                    'upload_batch': batch_id,
                    'original_filename': original_filename,
                    'upload_date': datetime.utcnow()
                })

            # Bulk insert in batches
            if records:
                self._bulk_insert_attendance(records)
                
            logger.info(f"Saved {len(records)} attendance records with batch ID: {batch_id}")
            return batch_id

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error saving attendance data: {e}")
            raise

    def _bulk_insert_attendance(self, records: list) -> None:
        """Bulk insert attendance records."""
        batch_size = self.batch_size
        
        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            db.session.bulk_insert_mappings(AttendanceRaw, batch)
            db.session.commit()
            
            if i > 0 and i % (batch_size * 10) == 0:
                logger.info(f"Processed {i} records...")

    def sync_employee_info(self, df: pd.DataFrame) -> Tuple[int, int]:
        """Optimized employee synchronization."""
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
        """Main file processing method with file tracking."""
        try:
            # Fast file reading
            df = pd.read_excel(
                file, 
                engine='openpyxl',
                dtype={'Emp ID': str, 'Name': str},
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

            # Save to database with file tracking
            logger.info("Saving to database...")
            batch_id = self.save_attendance_to_db(df, file.filename)

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

# ===========================================================
#              FILE MANAGEMENT SERVICE
# ===========================================================
class FileManagementService:
    """Service for managing uploaded files using attendance_raw table."""
    
    @staticmethod
    def get_uploaded_files() -> List[Dict[str, Any]]:
        """Get all unique uploaded files from attendance_raw."""
        try:
            # First, check if we have any data in attendance_raw
            total_records = db.session.query(func.count(AttendanceRaw.id)).scalar() or 0
            logger.info(f"Total records in attendance_raw: {total_records}")
            
            if total_records == 0:
                return []

            # Get unique uploaded files
            files = db.session.query(
                AttendanceRaw.upload_batch,
                AttendanceRaw.original_filename,
                func.max(AttendanceRaw.upload_date).label('upload_date'),
                func.count(AttendanceRaw.id).label('record_count')
            ).filter(
                AttendanceRaw.upload_batch.isnot(None),
                AttendanceRaw.original_filename.isnot(None)
            ).group_by(
                AttendanceRaw.upload_batch,
                AttendanceRaw.original_filename
            ).order_by(
                func.max(AttendanceRaw.upload_date).desc()
            ).all()
            
            logger.info(f"Found {len(files)} uploaded files")
            
            result = []
            for file in files:
                file_data = {
                    'batch_id': file.upload_batch,
                    'filename': file.original_filename,
                    'upload_date': file.upload_date.strftime('%Y-%m-%d %H:%M') if file.upload_date else 'Unknown',
                    'record_count': file.record_count
                }
                logger.info(f"File: {file_data}")
                result.append(file_data)
                
            return result
            
        except Exception as e:
            logger.error(f"Error fetching uploaded files: {e}")
            return []
    @staticmethod
    def delete_file_by_batch(batch_id: str) -> Tuple[bool, str]:
        """Delete all records for a specific batch ONLY - don't touch other data."""
        try:
            if not batch_id:
                return False, "Batch ID is required"

            # SUPER SIMPLE - Direct delete karo
            deleted_count = db.session.query(AttendanceRaw).filter(
                AttendanceRaw.upload_batch == batch_id
            ).delete()
            
            db.session.commit()
            
            if deleted_count > 0:
                return True, f"✅ File deleted successfully ({deleted_count} records removed). Other files are safe."
            else:
                return False, "No records found to delete"

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error deleting batch {batch_id}: {e}")
            return False, f"❌ Error deleting file: {e}"
    @staticmethod
    def get_file_stats() -> Dict[str, Any]:
        """Get statistics about uploaded files."""
        try:
            total_files = db.session.query(
                func.count(func.distinct(AttendanceRaw.upload_batch))
            ).scalar() or 0
            
            total_records = db.session.query(func.count(AttendanceRaw.id)).scalar() or 0
            
            latest_file = db.session.query(
                AttendanceRaw.original_filename,
                AttendanceRaw.upload_date
            ).order_by(AttendanceRaw.upload_date.desc()).first()
            
            return {
                "total_files": total_files,
                "total_records": total_records,
                "latest_upload": latest_file.upload_date if latest_file else None,
                "latest_filename": latest_file.original_filename if latest_file else None
            }
        except Exception as e:
            logger.error(f"Error getting file stats: {e}")
            return {}


# ===========================================================
#              EXTERNAL ENTRY POINTS
# ===========================================================
def process_attendance_file(file, employee_shifts=None, compensated_dates=None) -> str:
    """External entry point for file processing."""
    service = FileService(employee_shifts, compensated_dates)
    return service.process_file(file)

def get_uploaded_files() -> List[Dict[str, Any]]:
    """External entry point for getting uploaded files."""
    return FileManagementService.get_uploaded_files()

def delete_uploaded_file(batch_id: str) -> Tuple[bool, str]:
    """External entry point for deleting a specific file."""
    return FileManagementService.delete_file_by_batch(batch_id)