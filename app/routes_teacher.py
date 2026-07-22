from datetime import date

from flask import Blueprint, render_template, request, abort, make_response
from flask_login import login_required, current_user

from app.models import db, ClassSession, Attendance, Enrollment, Student
from app.utils import roles_required
from app.reports import build_attendance_query, export_csv, export_excel, export_pdf, daily_trend

teacher_bp = Blueprint("teacher", __name__)


@teacher_bp.before_request
@login_required
@roles_required("teacher")
def guard():
    pass


def _my_teacher():
    return current_user.teacher


@teacher_bp.route("/dashboard")
def dashboard():
    teacher = _my_teacher()
    classes = ClassSession.query.filter_by(teacher_id=teacher.id).all()
    today = date.today()
    today_count = Attendance.query.filter(
        Attendance.class_id.in_([c.id for c in classes]), Attendance.date == today
    ).count() if classes else 0
    trend = daily_trend(days=14, class_id=classes[0].id) if classes else []
    return render_template("teacher/dashboard.html", classes=classes, today_count=today_count, trend=trend)


@teacher_bp.route("/classes/<int:class_id>/students")
def class_students(class_id):
    teacher = _my_teacher()
    cls = db.session.get(ClassSession, class_id)
    if not cls or cls.teacher_id != teacher.id:
        abort(403)
    enrollments = Enrollment.query.filter_by(class_id=class_id).all()
    return render_template("teacher/class_students.html", cls=cls, enrollments=enrollments)


@teacher_bp.route("/attendance/live/<int:class_id>")
def attendance_live(class_id):
    teacher = _my_teacher()
    cls = db.session.get(ClassSession, class_id)
    if not cls or cls.teacher_id != teacher.id:
        abort(403)
    return render_template("teacher/attendance_live.html", cls=cls)


@teacher_bp.route("/attendance")
def attendance_records():
    teacher = _my_teacher()
    my_class_ids = [c.id for c in ClassSession.query.filter_by(teacher_id=teacher.id).all()]
    class_id = request.args.get("class_id", type=int)
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    if class_id and class_id not in my_class_ids:
        abort(403)

    q = build_attendance_query(start_date, end_date, class_id)
    q = q.filter(Attendance.class_id.in_(my_class_ids)) if not class_id else q
    rows = q.limit(500).all()
    classes = ClassSession.query.filter_by(teacher_id=teacher.id).all()
    return render_template("teacher/attendance_records.html", rows=rows, classes=classes,
                            filters=dict(start_date=start_date, end_date=end_date, class_id=class_id))


@teacher_bp.route("/attendance/export/<fmt>")
def attendance_export(fmt):
    teacher = _my_teacher()
    my_class_ids = [c.id for c in ClassSession.query.filter_by(teacher_id=teacher.id).all()]
    class_id = request.args.get("class_id", type=int)
    if class_id and class_id not in my_class_ids:
        abort(403)

    q = build_attendance_query(request.args.get("start_date"), request.args.get("end_date"), class_id)
    q = q.filter(Attendance.class_id.in_(my_class_ids)) if not class_id else q
    rows = q.all()

    if fmt == "csv":
        data, mimetype, ext = export_csv(rows), "text/csv", "csv"
    elif fmt == "excel":
        data, mimetype, ext = export_excel(rows), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx"
    else:
        data, mimetype, ext = export_pdf(rows), "application/pdf", "pdf"

    resp = make_response(data)
    resp.headers["Content-Type"] = mimetype
    resp.headers["Content-Disposition"] = f"attachment; filename=attendance_report.{ext}"
    return resp
