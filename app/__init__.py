import os
from flask import Flask
from flask_login import LoginManager

from config import Config
from app.models import db, User

login_manager = LoginManager()
login_manager.login_view = "auth.choose_login"


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    os.makedirs(os.path.dirname(app.config["SQLALCHEMY_DATABASE_URI"].replace("sqlite:///", "/")), exist_ok=True) \
        if app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite:///") else None
    os.makedirs(app.config["STUDENT_FACE_DIR"], exist_ok=True)
    os.makedirs(app.config["UNKNOWN_FACE_DIR"], exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    from app.auth import auth_bp
    from app.routes_admin import admin_bp
    from app.routes_teacher import teacher_bp
    from app.routes_student import student_bp
    from app.api import api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(teacher_bp, url_prefix="/teacher")
    app.register_blueprint(student_bp, url_prefix="/student")
    app.register_blueprint(api_bp, url_prefix="/api")

    with app.app_context():
        db.create_all()
        _ensure_schema_upgrades(app)

    return app


def _ensure_schema_upgrades(app):
    """
    db.create_all() only creates tables that don't exist yet — it will not
    add new columns to a table that was created by an older version of the
    app. This adds any columns introduced after the initial release so
    existing databases keep working without a manual migration step.
    """
    from sqlalchemy import inspect, text

    engine = db.engine
    inspector = inspect(engine)

    if "attendance" not in inspector.get_table_names():
        return

    existing_columns = {col["name"] for col in inspector.get_columns("attendance")}
    if "time_out" not in existing_columns:
        column_type = "TIME" if engine.dialect.name != "mysql" else "TIME"
        with engine.begin() as conn:
            conn.execute(text(f"ALTER TABLE attendance ADD COLUMN time_out {column_type}"))
        app.logger.info("Schema upgrade: added attendance.time_out column.")
