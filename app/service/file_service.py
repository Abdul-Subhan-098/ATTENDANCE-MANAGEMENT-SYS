import pandas as pd
import numpy as np
from sqlalchemy import text, delete, func
from app import db
from app.models import AttendanceRaw, Employee
from app.service.activity_service import log_activity
from app.service.daily_service import generate_daily_report
from app.service.monthly_service import generate_monthly_report_from_daily
from app.service.new_employees_service import NewEmployeeService
from datetime import datetime
import logging
import uuid
from typing import Tuple, Dict, Any, List
import time
import sys

# Configure logging
logger = logging.getLogger(__name__)


# ===========================================================
#              PROGRESS TRACKER CLASS
# ===========================================================
class ProgressTracker:
    """Terminal mein real-time progress dikhata hai"""
    
    def __init__(self, total_steps=100):
        self.total_steps = total_steps
        self.current_step = 0
        self.start_time = time.time()
        
    def update(self, message, step_increment=1):
        self.current_step += step_increment
        elapsed = time.time() - self.start_time
        percent = (self.current_step / self.total_steps) * 100
        
        # Progress bar
        bar_length = 40
        filled_length = int(bar_length * self.current_step // self.total_steps)
        bar = '█' * filled_length + '░' * (bar_length - filled_length)
        
        # ETA calculation
        if self.current_step > 0:
            eta = (elapsed / self.current_step) * (self.total_steps - self.current_step)
            eta_str = f"ETA: {eta:.1f}s"
        else:
            eta_str = "ETA: Calculating..."
            
        print(f"\r🚀 [{bar}] {percent:.1f}% | {message} | {eta_str}", end="", flush=True)
        
    def complete(self, message):
        elapsed = time.time() - self.start_time
        print(f"\r✅ [{'█' * 40}] 100% | {message} | Completed in {elapsed:.2f}s")
        
    def log(self, message):
        print(f"📊 {message}")

# ===========================================================
#              ULTRA-OPTIMIZED FILE SERVICE (50k+ ROWS)
# ===========================================================
class FileService:
    """50k+ rows ke liye highly optimized file service"""

    def __init__(self, employee_shifts=None, compensated_dates=None):
        self.employee_shifts = employee_shifts or {}
        self.compensated_dates = compensated_dates or {}
        self.batch_size = 10000
        self.progress = ProgressTracker(total_steps=8)

    def validate_required_columns(self, df: pd.DataFrame) -> bool:
        """Ultra-fast column validation"""
        return all(col in df.columns for col in ["Name", "Time"])

    def clean_attendance_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """50k rows ke liye optimized data cleaning"""
        self.progress.update("🔄 Data cleaning started", 1)
        
        if df.empty:
            return df
            
        start_time = time.time()
        original_rows = len(df)
        
        # Fast operations for large datasets
        df["Name"] = (
            df["Name"]
            .astype(str)
            .str.replace(".", " ", regex=False)
            .str.replace(r"\s+", " ", regex=True)
            .str.strip()
        )

        # Fast datetime conversion
        df["Time"] = pd.to_datetime(df["Time"], errors="coerce")
        
        # Remove invalid rows
        valid_mask = df["Time"].notna()
        if not valid_mask.all():
            df = df[valid_mask].copy()
            
        if df.empty:
            return df

        df["Date"] = df["Time"].dt.date

        # Optimized attendance state
        if "Attendance State" in df.columns:
            df["Attendance State"] = (
                pd.to_numeric(df["Attendance State"], errors="coerce")
                .fillna(-1)
                .astype(np.int8)
            )
        else:
            df["Attendance State"] = -1

        elapsed = time.time() - start_time
        remaining_rows = len(df)
        self.progress.log(f"🧹 Data cleaned: {original_rows} → {remaining_rows} rows ({elapsed:.2f}s)")
        
        return df

    def save_attendance_to_db(self, df: pd.DataFrame, original_filename: str) -> str:
        """50k rows ke liye ultra-fast database insertion"""
        self.progress.update("💾 Database insertion started", 1)
        
        try:
            if df.empty:
                return "no_data"
                
            batch_id = f"batch_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
            current_time = datetime.utcnow()
            total_rows = len(df)

            # Prepare records with progress tracking
            records = []
            for i, (_, row) in enumerate(df.iterrows()):
                records.append({
                    'emp_id': str(row.get("Emp ID", "")),
                    'name': str(row.get("Name", "")),
                    'time': row.get("Time"),
                    'work_code': str(row.get("Work Code", "")),
                    'attendance_state': str(row.get("Attendance State", -1)),
                    'device_name': str(row.get("Device Name", "")),
                    'upload_batch': batch_id,
                    'original_filename': original_filename,
                    'upload_date': current_time
                })
                
                # Progress every 5000 rows
                if i > 0 and i % 5000 == 0:
                    self.progress.log(f"📦 Prepared {i}/{total_rows} records")

            # Ultra-fast bulk insert with progress
            if records:
                self._massive_bulk_insert(records, batch_id)
                
            self.progress.log(f"💾 Saved {len(records)} records in batch: {batch_id}")
            return batch_id

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error saving attendance data: {e}")
            raise

    def _massive_bulk_insert(self, records: list, batch_id: str) -> None:
        """50k+ rows ke liye massive bulk insert"""
        start_time = time.time()
        total_records = len(records)
        
        self.progress.log(f"🚀 Starting bulk insert of {total_records} records...")
        
        try:
            inserted = 0
            for i in range(0, total_records, self.batch_size):
                batch = records[i:i + self.batch_size]
                db.session.bulk_insert_mappings(AttendanceRaw, batch)
                db.session.commit()
                
                inserted += len(batch)
                elapsed = time.time() - start_time
                speed = inserted / elapsed if elapsed > 0 else 0
                
                self.progress.log(f"📈 Batch {i//self.batch_size + 1}: {inserted}/{total_records} "
                                f"records ({speed:.0f} rows/sec)")

            total_time = time.time() - start_time
            
            # ✅ ACTIVITY LOG: Bulk insert completed
            if total_records > 0:
                log_activity(
                    username="System",
                    action=f"Bulk insert completed for batch {batch_id}",
                    entity_type="data_import",
                    entity_id=batch_id,
                    details=f"Inserted {total_records:,} records in {total_time:.2f}s ({total_records/total_time:.0f} rows/sec)"
                )
            
            self.progress.log(f"✅ Bulk insert completed: {total_records} records in {total_time:.2f}s "
                            f"({total_records/total_time:.0f} rows/sec)")

        except Exception as e:
            db.session.rollback()
            
            # ✅ ACTIVITY LOG: Bulk insert failed
            log_activity(
                username="System",
                action=f"Bulk insert failed for batch {batch_id}",
                entity_type="data_import_error",
                entity_id=batch_id,
                details=f"Error: {str(e)[:200]}"
            )
            
            logger.error(f"Bulk insert error: {e}")
            raise

    def sync_employee_info(self, df: pd.DataFrame) -> Tuple[int, int]:
        """Fast employee synchronization"""
        self.progress.update("👥 Employee sync started", 1)
        
        try:
            if df.empty:
                return 0, 0

            start_time = time.time()
            
            # Fast unique employee extraction
            unique_emps = df[["Emp ID", "Name"]].drop_duplicates(subset=["Emp ID", "Name"])
            unique_emps = unique_emps[unique_emps["Emp ID"].notna() & unique_emps["Name"].notna()]
            
            if unique_emps.empty:
                return 0, 0

            # Convert to list of tuples
            valid_emps = [
                (str(row["Emp ID"]).strip(), str(row["Name"]).strip())
                for _, row in unique_emps.iterrows()
            ]

            # Get existing employees
            emp_ids = [emp_id for emp_id, _ in valid_emps]
            existing_employees = {
                emp.emp_id: emp for emp in 
                Employee.query.filter(Employee.emp_id.in_(emp_ids)).all()
            }

            # Bulk operations
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
                        name=name
                    ))

            # Execute
            if to_insert:
                db.session.bulk_save_objects(to_insert)
            
            if to_update:
                db.session.bulk_save_objects(to_update)
            
            db.session.commit()
            
            elapsed = time.time() - start_time
            
            # ✅ ACTIVITY LOG: Employee sync completed
            if to_insert or to_update:
                log_activity(
                    username="System",
                    action="Synchronized employee information",
                    entity_type="employee_sync",
                    details=f"New: {len(to_insert)}, Updated: {len(to_update)} employees in {elapsed:.2f}s"
                )
            
            self.progress.log(f"✅ Employee sync: {len(to_insert)} new, {len(to_update)} "
                            f"updated ({elapsed:.2f}s)")
            
            return len(to_insert), len(to_update)

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error syncing employee info: {e}")
            return 0, 0

    def process_file(self, file) -> str:
        """50k+ rows ke liye ultra-fast file processing"""
        total_start_time = time.time()
        self.progress = ProgressTracker(total_steps=8)
        
        try:
            # Step 1: File Reading
            self.progress.update("📖 Reading Excel file...", 1)
            file_read_start = time.time()
            
            df = pd.read_excel(
                file, 
                engine='openpyxl',
                dtype={'Emp ID': str, 'Name': str},
                na_values=['', 'NULL', 'null'],
                keep_default_na=False
            )
            
            file_read_time = time.time() - file_read_start
            self.progress.log(f"📊 File read: {len(df)} rows in {file_read_time:.2f}s")
            
            # Fast column cleaning
            df.columns = df.columns.str.strip()

            # Validation
            if not self.validate_required_columns(df):
                return "❌ Invalid Excel file. 'Name' and 'Time' columns are required."

            # Step 2: Data Cleaning
            df = self.clean_attendance_data(df)
            
            if df.empty:
                return "❌ No valid attendance records found after cleaning."

            # Step 3: Database Save
            batch_id = self.save_attendance_to_db(df, file.filename)

            # ✅ Track new employees via service class
            new_detected = NewEmployeeService.track_from_batch(batch_id)

            # Step 4: Employee Sync
            added, updated = self.sync_employee_info(df)

            # Step 5: Report Generation
            self.progress.update("📊 Generating daily report...", 1)
            daily_start = time.time()
            
            # Extract dates from the uploaded dataframe to force update them
            force_dates = set(df["Date"].unique()) if "Date" in df.columns else set()
            
            daily_result = generate_daily_report(self.employee_shifts, self.compensated_dates, force_update_dates=force_dates)
            daily_time = time.time() - daily_start
            self.progress.log(f"📈 Daily report generated in {daily_time:.2f}s")
            
            if "error" in daily_result:
                return f"⚠️ Daily report generation failed: {daily_result['error']}"

            # Step 6: Monthly Report
            self.progress.update("📅 Generating monthly report...", 1)
            monthly_start = time.time()
            generate_monthly_report_from_daily()
            monthly_time = time.time() - monthly_start
            self.progress.log(f"📅 Monthly report generated in {monthly_time:.2f}s")

            # ✅ ACTIVITY LOG: File processed successfully
            total_time = time.time() - total_start_time
            rows_per_second = len(df) / total_time if total_time > 0 else 0
            
            log_activity(
                username="System",
                action=f"Processed attendance file: {file.filename}",
                entity_type="file_upload",
                entity_id=batch_id,
                details=f"Rows: {len(df):,}, Employees: {added} new, {updated} updated, Duration: {total_time:.2f}s, Speed: {rows_per_second:.0f} rows/sec"
            )
            
            self.progress.complete(f"File processing completed")
            self.progress.log(f"🎯 PERFORMANCE SUMMARY:")
            self.progress.log(f"   • Total Rows: {len(df):,}")
            self.progress.log(f"   • Total Time: {total_time:.2f}s")
            self.progress.log(f"   • Speed: {rows_per_second:.0f} rows/second")
            self.progress.log(f"   • Employees: {added} new, {updated} updated")
            self.progress.log(f"   • Batch ID: {batch_id}")

            return (
                f"✅ File '{file.filename}' processed successfully! "
                f"({len(df):,} rows, {added} new, {updated} updated employees) | "
                f"Speed: {rows_per_second:.0f} rows/sec"
            )

        except Exception as e:
            db.session.rollback()
            
            # ✅ ACTIVITY LOG: File processing failed
            log_activity(
                username="System",
                action=f"Failed to process file: {file.filename}",
                entity_type="file_upload_error",
                details=f"Error: {str(e)[:200]}"
            )
            
            error_msg = f"❌ Error processing file: {e}"
            logger.error(error_msg)
            return error_msg

# ===========================================================
#              OPTIMIZED FILE MANAGEMENT SERVICE
# ===========================================================
class FileManagementService:
    """Optimized file management service."""
    
    @staticmethod
    def get_uploaded_files() -> List[Dict[str, Any]]:
        """Fast file listing with optimized query."""
        try:
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
            
            return [
                {
                    'batch_id': file.upload_batch,
                    'filename': file.original_filename,
                    'upload_date': file.upload_date.strftime('%Y-%m-%d %H:%M') if file.upload_date else 'Unknown',
                    'record_count': file.record_count
                }
                for file in files
            ]
            
        except Exception as e:
            logger.error(f"Error fetching uploaded files: {e}")
            return []

    @staticmethod
    def delete_file_by_batch(batch_id: str) -> Tuple[bool, str]:
        """Optimized batch deletion."""
        try:
            if not batch_id:
                return False, "Batch ID is required"

            deleted_count = db.session.query(AttendanceRaw).filter(
                AttendanceRaw.upload_batch == batch_id
            ).delete(synchronize_session=False)
            
            db.session.commit()
            
            return True, f"✅ File deleted successfully ({deleted_count} records removed)"

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error deleting batch {batch_id}: {e}")
            return False, f"❌ Error deleting file: {e}"

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