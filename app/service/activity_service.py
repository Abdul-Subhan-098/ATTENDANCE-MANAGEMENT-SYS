# app/service/activity_service.py
from datetime import datetime
from flask import request
from app import db
from app.models import ActivityLog
import logging

logger = logging.getLogger(__name__)


class ActivityService:

    
    @staticmethod
    def log_activity(
        username: str,
        action: str,
        entity_type: str,
        entity_id: str = None,
        details: str = None
    ) -> None:
        """
        Log an activity to the database.
        """
        try:
            # Get request information if available
            ip_address = None
            user_agent = None
            
            if request:
                ip_address = request.remote_addr
                user_agent = request.user_agent.string if request.user_agent else None
            
            # Create activity log entry
            activity_log = ActivityLog(
                username=username,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                details=details,
                ip_address=ip_address,
                user_agent=user_agent,
                timestamp=datetime.utcnow()
            )
            
            db.session.add(activity_log)
            db.session.commit()
            
            logger.info(f"Activity logged: {username} - {action} - {entity_type}")
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to log activity: {e}")
    
    @staticmethod
    def get_activity_logs(
        username: str = None,
        entity_type: str = None,
        start_date: datetime = None,
        end_date: datetime = None,
        limit: int = 100
    ) -> list:
        """
        Retrieve ALL activity logs with optional filtering.
        """
        try:
            logger.info(f"Fetching ALL activity logs - Username: {username}, Entity: {entity_type}, Limit: {limit}")
            
            query = ActivityLog.query
            
            if username and username.strip():
                query = query.filter(ActivityLog.username.ilike(f"%{username}%"))
            
            if entity_type and entity_type.strip():
                query = query.filter(ActivityLog.entity_type == entity_type)
            
            if start_date:
                query = query.filter(ActivityLog.timestamp >= start_date)
            
            if end_date:
                query = query.filter(ActivityLog.timestamp <= end_date)
            
            # Order by most recent first
            query = query.order_by(ActivityLog.timestamp.desc())
            
            # Apply limit
            if limit:
                query = query.limit(limit)
            
            logs = query.all()
            
            logger.info(f"Found {len(logs)} activity logs")
            
            result = []
            for log in logs:
                try:
                    result.append({
                        "id": log.id,
                        "username": log.username or "",
                        "action": log.action or "",
                        "entity_type": log.entity_type or "",
                        "entity_id": log.entity_id or "",
                        "details": log.details or "",
                        "ip_address": log.ip_address or "",
                        "user_agent": log.user_agent or "",
                        "timestamp": log.timestamp.strftime("%Y-%m-%d %H:%M:%S") if log.timestamp else ""
                    })
                except Exception as e:
                    logger.error(f"Error converting log {log.id} to dict: {e}")
                    continue
            
            return result
            
        except Exception as e:
            logger.error(f"Error fetching activity logs: {e}", exc_info=True)
            return []
    
    @staticmethod
    def get_user_activity_logs(
        username: str = None,
        entity_type: str = None,
        start_date: datetime = None,
        end_date: datetime = None,
        limit: int = 100
    ) -> list:
        """
        Sirf USER ki activity logs get karo (System/Admin chhodo).
        """
        try:
            logger.info(f"Fetching USER activity logs - Username: {username}, Entity: {entity_type}, Limit: {limit}")
            
            # System aur Admin ko exclude karo
            query = ActivityLog.query.filter(
                ~ActivityLog.username.in_(['System', 'Admin'])
            )
            
            if username and username.strip():
                query = query.filter(ActivityLog.username.ilike(f"%{username}%"))
                logger.info(f"Filtering by username: {username}")
            
            if entity_type and entity_type.strip():
                query = query.filter(ActivityLog.entity_type == entity_type)
                logger.info(f"Filtering by entity type: {entity_type}")
            
            if start_date:
                query = query.filter(ActivityLog.timestamp >= start_date)
                logger.info(f"Filtering by start date: {start_date}")
            
            if end_date:
                query = query.filter(ActivityLog.timestamp <= end_date)
                logger.info(f"Filtering by end date: {end_date}")
            
            # Sabse latest pehle
            query = query.order_by(ActivityLog.timestamp.desc())
            
            # Limit lagao
            if limit:
                query = query.limit(limit)
            
            logs = query.all()
            
            # Debug: Check kitne logs mil rahe hain
            logger.info(f"Found {len(logs)} USER activity logs")
            
            # Debug: Unique users in result
            unique_users = set([log.username for log in logs])
            logger.info(f"Unique users in result: {list(unique_users)}")
            
            result = []
            for log in logs:
                try:
                    result.append({
                        "id": log.id,
                        "username": log.username or "",
                        "action": log.action or "",
                        "entity_type": log.entity_type or "",
                        "entity_id": log.entity_id or "",
                        "details": log.details or "",
                        "ip_address": log.ip_address or "",
                        "user_agent": log.user_agent or "",
                        "timestamp": log.timestamp.strftime("%Y-%m-%d %H:%M:%S") if log.timestamp else ""
                    })
                except Exception as e:
                    logger.error(f"Error converting log {log.id} to dict: {e}")
                    continue
            
            return result
            
        except Exception as e:
            logger.error(f"Error fetching USER activity logs: {e}", exc_info=True)
            return []
    
    @staticmethod
    def get_entity_types() -> list:
        """Get distinct entity types from activity logs."""
        try:
            entity_types = db.session.query(
                ActivityLog.entity_type
            ).distinct().order_by(ActivityLog.entity_type).all()
            
            return [etype[0] for etype in entity_types if etype[0]]
        except Exception as e:
            logger.error(f"Error fetching entity types: {e}")
            return []
    
    @staticmethod
    def get_usernames() -> list:
        """Get ALL distinct usernames from activity logs."""
        try:
            usernames = db.session.query(
                ActivityLog.username
            ).distinct().order_by(ActivityLog.username).all()
            
            return [username[0] for username in usernames if username[0]]
        except Exception as e:
            logger.error(f"Error fetching usernames: {e}")
            return []
    
    @staticmethod
    def get_user_usernames() -> list:
        """Get distinct usernames from USER activity logs (exclude System/Admin)."""
        try:
            # Exclude System and Admin
            usernames = db.session.query(
                ActivityLog.username
            ).filter(
                ~ActivityLog.username.in_(['System', 'Admin', 'system', 'admin'])
            ).distinct().order_by(ActivityLog.username).all()
            
            return [username[0] for username in usernames if username[0]]
        except Exception as e:
            logger.error(f"Error fetching user usernames: {e}")
            return []
    
    @staticmethod
    def get_recent_activities(limit: int = 10) -> list:
        """Get recent activities for dashboard display."""
        try:
            logs = ActivityLog.query.order_by(
                ActivityLog.timestamp.desc()
            ).limit(limit).all()
            
            result = []
            for log in logs:
                result.append({
                    "id": log.id,
                    "username": log.username or "",
                    "action": log.action or "",
                    "entity_type": log.entity_type or "",
                    "timestamp": log.timestamp.strftime("%Y-%m-%d %H:%M:%S") if log.timestamp else ""
                })
            
            return result
        except Exception as e:
            logger.error(f"Error fetching recent activities: {e}")
            return []
    
    @staticmethod
    def get_recent_user_activities(limit: int = 10) -> list:
        """Get recent USER activities for dashboard display (exclude System/Admin)."""
        try:
            logs = ActivityLog.query.filter(
                ~ActivityLog.username.in_(['System', 'Admin', 'system', 'admin'])
            ).order_by(
                ActivityLog.timestamp.desc()
            ).limit(limit).all()
            
            result = []
            for log in logs:
                result.append({
                    "id": log.id,
                    "username": log.username or "",
                    "action": log.action or "",
                    "entity_type": log.entity_type or "",
                    "timestamp": log.timestamp.strftime("%Y-%m-%d %H:%M:%S") if log.timestamp else ""
                })
            
            return result
        except Exception as e:
            logger.error(f"Error fetching recent user activities: {e}")
            return []


# Convenience function for logging activities
def log_activity(username: str, action: str, entity_type: str, entity_id: str = None, details: str = None):
    """External entry point for logging activities."""
    service = ActivityService()
    service.log_activity(username, action, entity_type, entity_id, details)


def get_activity_logs(**kwargs):
    """External entry point for getting ALL activity logs."""
    service = ActivityService()
    return service.get_activity_logs(**kwargs)


def get_user_activity_logs(**kwargs):
    """External entry point for getting ONLY USER activity logs (exclude System/Admin)."""
    service = ActivityService()
    return service.get_user_activity_logs(**kwargs)