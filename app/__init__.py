from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from app.config import Config
import os

# Initialize SQLAlchemy (but don't bind to app yet)
db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    
    # Load configuration (database, etc.)
    app.config.from_object(Config)
    app.config["UPLOAD_FOLDER"] = "app/static/uploads"

    # 🔑 Add a secret key for sessions & flash messages
    app.secret_key = os.environ.get("SECRET_KEY", "dev_secret_key_123")

    # Initialize database with app
    db.init_app(app)

    # Register blueprints
    from app.routes import main
    app.register_blueprint(main)

    return app
