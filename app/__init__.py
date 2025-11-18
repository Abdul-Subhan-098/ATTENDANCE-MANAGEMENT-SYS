from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from app.config import get_config
import os  # <-- ADD THIS IMPORT

# Initialize SQLAlchemy
db = SQLAlchemy()
migrate = Migrate()

def create_app(config_class=None):
    """
    Application factory pattern for creating Flask app instances.
    """
    app = Flask(__name__)
    
    # Load configuration - use provided class or auto-detect
    if config_class:
        app.config.from_object(config_class)
    else:
        app.config.from_object(get_config())
    
    # Ensure upload folder exists
    upload_folder = app.config.get("UPLOAD_FOLDER", "app/static/uploads")
    os.makedirs(upload_folder, exist_ok=True)
    
    # Initialize database with app
    db.init_app(app)
    migrate.init_app(app, db)

    # Register blueprints
    from app.routes import main
    app.register_blueprint(main)

    # Simple health check
    @app.route('/health')
    def health_check():
        return {"status": "healthy", "app": "Attendance Management System"}

    return app