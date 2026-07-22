import pickle
from datetime import datetime, date as date_cls

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


# ---------------------------------------------------------------------------
# USERS & AUTH
# ---------------------------------------------------------------------------
class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, index=True)  # admin | teacher | student
    full_name = db.Column(db.String(120), nullable=False)
    is_active_flag = db.Column("is_active", db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)

    teacher = db.relationship("Teacher", back_populates="user", uselist=False, cascade="all, delete-orphan")
    student = db.relationship("Student", back_populates="user", uselist=False, cascade="all, delete-orphan")

    def set_password(self, raw_password):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)

    @property
    def is_active(self):
        return self.is_active_flag

    def __repr__(self):
        return f"<User {self.username} ({self.role})>"


# ---------------------------------------------------------------------------
# PEOPLE
# ---------------------------------------------------------------------------
class Teacher(db.Model):
    __tablename__ = "teachers"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    teacher_code = db.Column(db.String(30), unique=True, nullable=False, index=True)
    department = db.Column(db.String(120))
    phone = db.Column(db.String(30))

    user = db.relationship("User", back_populates="teacher")
    classes = db.relationship("ClassSession", back_populates="teacher")


class Student(db.Model):
    __tablename__ = "students"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    student_code = db.Column(db.String(30), unique=True, nullable=False, index=True)
    dob = db.Column(db.Date, nullable=True)
    gender = db.Column(db.String(10))
    phone = db.Column(db.String(30))
    address = db.Column(db.String(255))
    enrollment_date = db.Column(db.Date, default=date_cls.today)
    photo_path = db.Column(db.String(255))  # primary/profile photo
    is_face_registered = db.Column(db.Boolean, default=False)

    user = db.relationship("User", back_populates="student")
    embeddings = db.relationship("FaceEmbedding", back_populates="student", cascade="all, delete-orphan")
    enrollments = db.relationship("Enrollment", back_populates="student", cascade="all, delete-orphan")
    attendances = db.relationship("Attendance", back_populates="student", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# ACADEMICS
# ---------------------------------------------------------------------------
class Course(db.Model):
    __tablename__ = "courses"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False, index=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)
    credits = db.Column(db.Integer, default=3)

    classes = db.relationship("ClassSession", back_populates="course", cascade="all, delete-orphan")


class ClassSession(db.Model):
    """A scheduled class/section (e.g. 'CS101 - Section A, Mon 9-11am')."""
    __tablename__ = "class_sessions"

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teachers.id", ondelete="SET NULL"), nullable=True, index=True)
    class_name = db.Column(db.String(100), nullable=False)  # e.g. "Section A"
    schedule_day = db.Column(db.String(20))  # Monday..Sunday
    start_time = db.Column(db.Time)
    end_time = db.Column(db.Time)
    room = db.Column(db.String(50))
    is_active = db.Column(db.Boolean, default=True)

    course = db.relationship("Course", back_populates="classes")
    teacher = db.relationship("Teacher", back_populates="classes")
    enrollments = db.relationship("Enrollment", back_populates="class_session", cascade="all, delete-orphan")
    attendances = db.relationship("Attendance", back_populates="class_session", cascade="all, delete-orphan")

    __table_args__ = (
        db.Index("ix_class_course_teacher", "course_id", "teacher_id"),
    )


class Enrollment(db.Model):
    __tablename__ = "enrollments"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    class_id = db.Column(db.Integer, db.ForeignKey("class_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    enrolled_at = db.Column(db.DateTime, default=datetime.utcnow)

    student = db.relationship("Student", back_populates="enrollments")
    class_session = db.relationship("ClassSession", back_populates="enrollments")

    __table_args__ = (
        db.UniqueConstraint("student_id", "class_id", name="uq_enrollment_student_class"),
    )


# ---------------------------------------------------------------------------
# FACE DATA
# ---------------------------------------------------------------------------
class FaceEmbedding(db.Model):
    __tablename__ = "face_embeddings"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    embedding_blob = db.Column(db.LargeBinary, nullable=False)  # pickled 128-d numpy vector
    image_path = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    student = db.relationship("Student", back_populates="embeddings")

    def set_vector(self, vector):
        self.embedding_blob = pickle.dumps(vector)

    def get_vector(self):
        return pickle.loads(self.embedding_blob)


class UnknownFaceLog(db.Model):
    __tablename__ = "unknown_face_logs"

    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.Integer, db.ForeignKey("class_sessions.id", ondelete="SET NULL"), nullable=True)
    image_path = db.Column(db.String(255))
    detected_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)


# ---------------------------------------------------------------------------
# ATTENDANCE
# ---------------------------------------------------------------------------
class Attendance(db.Model):
    __tablename__ = "attendance"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    class_id = db.Column(db.Integer, db.ForeignKey("class_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    date = db.Column(db.Date, default=date_cls.today, nullable=False, index=True)
    time_in = db.Column(db.Time, default=lambda: datetime.now().time())
    time_out = db.Column(db.Time, nullable=True)
    status = db.Column(db.String(20), default="present")  # present | late | absent
    confidence = db.Column(db.Float)  # recognition confidence score
    marked_by = db.Column(db.String(20), default="system")  # system | manual
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    student = db.relationship("Student", back_populates="attendances")
    class_session = db.relationship("ClassSession", back_populates="attendances")

    __table_args__ = (
        db.UniqueConstraint("student_id", "class_id", "date", name="uq_attendance_once_per_day"),
        db.Index("ix_attendance_date_class", "date", "class_id"),
    )

    # ------------------------------------------------------------------
    # Duration helpers — "time_in" is set the first time a student's face
    # is recognized for a class on a given day; every later recognition
    # that same day keeps pushing "time_out" forward. So time_out ends up
    # being the last moment the student was seen, and (time_out - time_in)
    # is how long they were physically present in class.
    # ------------------------------------------------------------------
    @property
    def duration_minutes(self):
        if not self.time_in or not self.time_out:
            return 0
        t_in = datetime.combine(self.date, self.time_in)
        t_out = datetime.combine(self.date, self.time_out)
        if t_out <= t_in:
            return 0
        return int((t_out - t_in).total_seconds() // 60)

    @property
    def duration_display(self):
        mins = self.duration_minutes
        if mins <= 0:
            return "—"
        h, m = divmod(mins, 60)
        if h and m:
            return f"{h}h {m}m"
        if h:
            return f"{h}h"
        return f"{m}m"


# ---------------------------------------------------------------------------
# SYSTEM / AUDIT
# ---------------------------------------------------------------------------
class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action = db.Column(db.String(100), nullable=False)
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(50))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    user = db.relationship("User")


class CameraStatus(db.Model):
    __tablename__ = "camera_status"

    id = db.Column(db.Integer, primary_key=True)
    camera_name = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(120))
    status = db.Column(db.String(20), default="offline")  # online | offline | error
    last_ping = db.Column(db.DateTime, default=datetime.utcnow)
