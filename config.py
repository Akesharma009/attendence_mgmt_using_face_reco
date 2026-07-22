import os
from datetime import timedelta

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    """
    Central configuration.

    DATABASE_URL examples:
      SQLite (default, zero-config):
        sqlite:///sms.db
      PostgreSQL:
        postgresql+psycopg2://user:password@localhost:5432/student_management
      MySQL:
        mysql+pymysql://user:password@localhost:3306/student_management
    """
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-secret-in-production-use-env-var")

    _db_url = os.environ.get(
    "DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'sms.db')}"
)
    if _db_url.startswith("postgres://"):
      _db_url = _db_url.replace("postgres://", "postgresql://", 1)
    SQLALCHEMY_DATABASE_URI = _db_url


    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    UPLOAD_FOLDER = os.path.join(BASE_DIR, "app", "static", "uploads")
    STUDENT_FACE_DIR = os.path.join(UPLOAD_FOLDER, "students")
    UNKNOWN_FACE_DIR = os.path.join(UPLOAD_FOLDER, "unknown")
    MAX_CONTENT_LENGTH = 12 * 1024 * 1024  # 12 MB uploads

    # Face recognition tuning
    FACE_MATCH_TOLERANCE = float(os.environ.get("FACE_MATCH_TOLERANCE", 0.45))
    FACE_SAMPLES_PER_STUDENT = int(os.environ.get("FACE_SAMPLES_PER_STUDENT", 5))
    FACE_DETECTION_MODEL = os.environ.get("FACE_DETECTION_MODEL", "hog")  # "hog" (CPU) or "cnn" (GPU)

    # Session / auth
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    REMEMBER_COOKIE_DURATION = timedelta(days=7)

    # Attendance rules
    ATTENDANCE_ONCE_PER_DAY = True
    LATE_AFTER_MINUTES = int(os.environ.get("LATE_AFTER_MINUTES", 15))
