import os
from datetime import timedelta
class Config:
    """Base configuration class with common settings."""
    
    # =====================
    # SECURITY CONFIGURATION
    # =====================
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
    
    # =====================
    # DATABASE CONFIGURATION
    # =====================
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:admin@localhost/attendance_management_system"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_recycle': 300,           # Recycle connections after 5 minutes
        'pool_pre_ping': True,         # Verify connections before use
        'pool_size': 10,               # Number of persistent connections
        'max_overflow': 20,            # Number of connections beyond pool_size
        'pool_timeout': 30,            # Seconds to wait for a connection
    }
    
    # =====================
    # APPLICATION CONFIGURATION
    # =====================
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file upload
    
    # Session configuration
    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)
    SESSION_COOKIE_SECURE = False  # Set to True in production with HTTPS
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # =====================
    # PERFORMANCE CONFIGURATION
    # =====================
    JSONIFY_PRETTYPRINT_REGULAR = False  # Disable pretty JSON in production
    EXPLAIN_TEMPLATE_LOADING = False


class DevelopmentConfig(Config):
    """Development environment configuration."""
    
    DEBUG = True
    TESTING = False
    
    # Development-specific database
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DEV_DATABASE_URL",
        "postgresql://postgres:admin@localhost/attendance_management_system"
    )
    
    # Development logging
    SQLALCHEMY_ECHO = False  # Set to True to see SQL queries
    
    # Relaxed security for development
    SESSION_COOKIE_SECURE = False


class TestingConfig(Config):
    """Testing environment configuration."""
    
    DEBUG = False
    TESTING = True
    
    # Test database
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "TEST_DATABASE_URL", 
        "postgresql://postgres:admin@localhost/attendance_management_system_test"
    )
    
    # Disable CSRF for testing
    WTF_CSRF_ENABLED = False


class ProductionConfig(Config):
    """Production environment configuration."""
    
    DEBUG = False
    TESTING = False
    
    # Production database - fallback to development if not set
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:admin@localhost/attendance_management_system"  # Fallback
    )
    
    # Production security - use fallback if not set
    SECRET_KEY = os.getenv("SECRET_KEY", "fallback-secret-key-change-this")
    
    SESSION_COOKIE_SECURE = False  # Set to True when you have HTTPS
    PREFERRED_URL_SCHEME = 'http'  # Change to 'https' when using SSL
    
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_recycle': 300,
        'pool_pre_ping': True,
        'pool_size': 100,  # 50k rows ke liye bada pool
        'max_overflow': 200,  # More overflow connections
        'pool_timeout': 60,
        'echo': False,
        'connect_args': {
            'application_name': 'attendance_app_50k',
            'connect_timeout': 30,
            'command_timeout': 300,  # 5 minutes for large operations
        }
    }


# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}


def get_config():
    """Get configuration based on environment with safe fallbacks."""
    env = os.getenv('FLASK_ENV', 'development').lower()
    
    # If production is requested but critical env vars are missing, fallback to development
    if env == 'production':
        if not os.getenv('DATABASE_URL'):
            print("⚠️  WARNING: DATABASE_URL not set, falling back to development configuration")
            return config['development']
        if not os.getenv('SECRET_KEY'):
            print("⚠️  WARNING: SECRET_KEY not set, using fallback (change in production)")
    
    return config.get(env, config['default'])


def ensure_upload_folder():
    """Ensure upload folder exists."""
    upload_folder = get_config().UPLOAD_FOLDER
    os.makedirs(upload_folder, exist_ok=True)
    return upload_folder


# Export the active configuration
CurrentConfig = get_config()

# Initialize upload folder on import
ensure_upload_folder()