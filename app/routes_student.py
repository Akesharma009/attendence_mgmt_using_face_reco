from flask import Blueprint, render_template
from flask_login import login_required, current_user

from app.models import Attendance, Enrollment
from app.utils import roles_required
from app.reports import attendance_percentage, daily_trend

student_bp = Blueprint("student", __name__)


@student_bp.before_request
@login_required
@roles_required("student")
def guard():
    pass


@student_bp.route("/dashboard")
def dashboard():
    student = current_user.student
    enrollments = Enrollment.query.filter_by(student_id=student.id).all()
    overall_pct = attendance_percentage(student.id)

    per_class = []
    for e in enrollments:
        pct = attendance_percentage(student.id, class_id=e.class_id)
        per_class.append({"class": e.class_session, "pct": pct})

    recent = (Attendance.query.filter_by(student_id=student.id)
              .order_by(Attendance.date.desc()).limit(10).all())

    return render_template("student/dashboard.html", student=student, overall_pct=overall_pct,
                            per_class=per_class, recent=recent)


@student_bp.route("/attendance")
def attendance_history():
    student = current_user.student
    records = (Attendance.query.filter_by(student_id=student.id)
               .order_by(Attendance.date.desc()).all())
    return render_template("student/attendance_history.html", records=records)


@student_bp.route("/profile")
def profile():
    student = current_user.student
    return render_template("student/profile.html", student=student)
