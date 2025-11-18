import os

class Config:
    # PostgreSQL connection
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:admin@localhost/attendance_management_system"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
