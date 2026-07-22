from datetime import date, datetime, timedelta

from flask import (Blueprint, render_template, request, redirect, url_for,
                    flash, jsonify, make_response)
from flask_login import login_required, current_user

from app.models import (db, User, Student, Teacher, Course, ClassSession,
                         Enrollment, Attendance, AuditLog, CameraStatus, FaceEmbedding, UnknownFaceLog)
from app.utils import roles_required, log_action
from app.reports import build_attendance_query, export_csv, export_excel, export_pdf, daily_trend, attendance_percentage

admin_bp = Blueprint("admin", __name__)


@admin_bp.before_request
@login_required
@roles_required("admin")
def guard():
    pass


# ---------------------------------------------------------------------- DASHBOARD
@admin_bp.route("/dashboard")
def dashboard():
    today = date.today()
    stats = {
        "total_students": Student.query.count(),
        "total_teachers": Teacher.query.count(),
        "total_courses": Course.query.count(),
        "total_classes": ClassSession.query.count(),
        "today_present": Attendance.query.filter_by(date=today).filter(Attendance.status.in_(["present", "late"])).count(),
        "registered_faces": Student.query.filter_by(is_face_registered=True).count(),
        "unknown_today": UnknownFaceLog.query.filter(
            db.func.date(UnknownFaceLog.detected_at) == today
        ).count(),
    }
    trend = daily_trend(days=14)
    cameras = CameraStatus.query.all()
    recent_logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(10).all()
    return render_template("admin/dashboard.html", stats=stats, trend=trend, cameras=cameras, recent_logs=recent_logs)


# ---------------------------------------------------------------------- STUDENTS
@admin_bp.route("/students")
def students_list():
    search = request.args.get("q", "").strip()
    query = Student.query.join(User)
    if search:
        like = f"%{search}%"
        query = query.filter(db.or_(Student.student_code.ilike(like), User.full_name.ilike(like)))
    students = query.order_by(Student.student_code).all()
    return render_template("admin/students_list.html", students=students, search=search)


@admin_bp.route("/students/new", methods=["GET", "POST"])
def student_new():
    courses = Course.query.all()
    classes = ClassSession.query.all()
    if request.method == "POST":
        f = request.form
        if User.query.filter((User.username == f["username"]) | (User.email == f["email"])).first():
            flash("Username or email already exists.", "danger")
            return render_template("admin/student_form.html", student=None, courses=courses, classes=classes, form=f)

        user = User(username=f["username"], email=f["email"], full_name=f["full_name"], role="student")
        user.set_password(f["password"])
        db.session.add(user)
        db.session.flush()

        student = Student(
            user_id=user.id,
            student_code=f["student_code"],
            gender=f.get("gender"),
            phone=f.get("phone"),
            address=f.get("address"),
            dob=datetime.strptime(f["dob"], "%Y-%m-%d").date() if f.get("dob") else None,
        )
        db.session.add(student)
        db.session.flush()

        for class_id in request.form.getlist("class_ids"):
            db.session.add(Enrollment(student_id=student.id, class_id=int(class_id)))

        db.session.commit()
        log_action("STUDENT_CREATE", f"student_code={student.student_code}")
        flash("Student registered. Now capture face images.", "success")
        return redirect(url_for("admin.student_capture_face", student_id=student.id))

    return render_template("admin/student_form.html", student=None, courses=courses, classes=classes, form={})


@admin_bp.route("/students/<int:student_id>/edit", methods=["GET", "POST"])
def student_edit(student_id):
    student = db.session.get(Student, student_id) or abort_404()
    courses = Course.query.all()
    classes = ClassSession.query.all()
    enrolled_ids = {e.class_id for e in student.enrollments}

    if request.method == "POST":
        f = request.form
        student.user.full_name = f["full_name"]
        student.user.email = f["email"]
        student.gender = f.get("gender")
        student.phone = f.get("phone")
        student.address = f.get("address")
        if f.get("dob"):
            student.dob = datetime.strptime(f["dob"], "%Y-%m-%d").date()
        if f.get("password"):
            student.user.set_password(f["password"])

        Enrollment.query.filter_by(student_id=student.id).delete()
        for class_id in request.form.getlist("class_ids"):
            db.session.add(Enrollment(student_id=student.id, class_id=int(class_id)))

        db.session.commit()
        log_action("STUDENT_UPDATE", f"student_code={student.student_code}")
        flash("Student updated.", "success")
        return redirect(url_for("admin.students_list"))

    return render_template("admin/student_form.html", student=student, courses=courses, classes=classes,
                            enrolled_ids=enrolled_ids, form={})


@admin_bp.route("/students/<int:student_id>/delete", methods=["POST"])
def student_delete(student_id):
    student = db.session.get(Student, student_id) or abort_404()
    code = student.student_code
    db.session.delete(student.user)  # cascades to student, embeddings, enrollments, attendance
    db.session.commit()
    log_action("STUDENT_DELETE", f"student_code={code}")
    flash("Student deleted.", "info")
    return redirect(url_for("admin.students_list"))


@admin_bp.route("/students/<int:student_id>/face")
def student_capture_face(student_id):
    student = db.session.get(Student, student_id) or abort_404()
    return render_template("admin/student_face_capture.html", student=student)


# ---------------------------------------------------------------------- TEACHERS
@admin_bp.route("/teachers")
def teachers_list():
    teachers = Teacher.query.join(User).order_by(Teacher.teacher_code).all()
    return render_template("admin/teachers_list.html", teachers=teachers)


@admin_bp.route("/teachers/new", methods=["GET", "POST"])
def teacher_new():
    if request.method == "POST":
        f = request.form
        if User.query.filter((User.username == f["username"]) | (User.email == f["email"])).first():
            flash("Username or email already exists.", "danger")
            return render_template("admin/teacher_form.html", teacher=None)

        user = User(username=f["username"], email=f["email"], full_name=f["full_name"], role="teacher")
        user.set_password(f["password"])
        db.session.add(user)
        db.session.flush()

        teacher = Teacher(user_id=user.id, teacher_code=f["teacher_code"], department=f.get("department"), phone=f.get("phone"))
        db.session.add(teacher)
        db.session.commit()
        log_action("TEACHER_CREATE", f"teacher_code={teacher.teacher_code}")
        flash("Teacher created.", "success")
        return redirect(url_for("admin.teachers_list"))

    return render_template("admin/teacher_form.html", teacher=None)


@admin_bp.route("/teachers/<int:teacher_id>/delete", methods=["POST"])
def teacher_delete(teacher_id):
    teacher = db.session.get(Teacher, teacher_id) or abort_404()
    code = teacher.teacher_code
    db.session.delete(teacher.user)
    db.session.commit()
    log_action("TEACHER_DELETE", f"teacher_code={code}")
    flash("Teacher deleted.", "info")
    return redirect(url_for("admin.teachers_list"))


# ---------------------------------------------------------------------- COURSES & CLASSES
@admin_bp.route("/courses", methods=["GET", "POST"])
def courses_list():
    if request.method == "POST":
        f = request.form
        db.session.add(Course(code=f["code"], name=f["name"], description=f.get("description"), credits=f.get("credits", 3)))
        db.session.commit()
        log_action("COURSE_CREATE", f["code"])
        flash("Course added.", "success")
        return redirect(url_for("admin.courses_list"))

    courses = Course.query.order_by(Course.code).all()
    return render_template("admin/courses_list.html", courses=courses)


@admin_bp.route("/courses/<int:course_id>/delete", methods=["POST"])
def course_delete(course_id):
    course = db.session.get(Course, course_id) or abort_404()
    db.session.delete(course)
    db.session.commit()
    flash("Course deleted.", "info")
    return redirect(url_for("admin.courses_list"))


@admin_bp.route("/classes", methods=["GET", "POST"])
def classes_list():
    courses = Course.query.all()
    teachers = Teacher.query.join(User).all()
    if request.method == "POST":
        f = request.form
        cls = ClassSession(
            course_id=f["course_id"], teacher_id=f.get("teacher_id") or None, class_name=f["class_name"],
            schedule_day=f.get("schedule_day"),
            start_time=datetime.strptime(f["start_time"], "%H:%M").time() if f.get("start_time") else None,
            end_time=datetime.strptime(f["end_time"], "%H:%M").time() if f.get("end_time") else None,
            room=f.get("room"),
        )
        db.session.add(cls)
        db.session.commit()
        log_action("CLASS_CREATE", f["class_name"])
        flash("Class created.", "success")
        return redirect(url_for("admin.classes_list"))

    classes = ClassSession.query.order_by(ClassSession.id.desc()).all()
    return render_template("admin/classes_list.html", classes=classes, courses=courses, teachers=teachers)


@admin_bp.route("/classes/<int:class_id>/delete", methods=["POST"])
def class_delete(class_id):
    cls = db.session.get(ClassSession, class_id) or abort_404()
    db.session.delete(cls)
    db.session.commit()
    flash("Class deleted.", "info")
    return redirect(url_for("admin.classes_list"))


# ---------------------------------------------------------------------- LIVE ATTENDANCE (camera)
@admin_bp.route("/attendance/live")
def attendance_live():
    classes = ClassSession.query.filter_by(is_active=True).all()
    return render_template("admin/attendance_live.html", classes=classes)


# ---------------------------------------------------------------------- ATTENDANCE RECORDS / REPORTS
@admin_bp.route("/attendance")
def attendance_records():
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    class_id = request.args.get("class_id", type=int)
    status = request.args.get("status")

    rows = build_attendance_query(start_date, end_date, class_id, None, status).limit(500).all()
    classes = ClassSession.query.all()
    return render_template("admin/attendance_records.html", rows=rows, classes=classes,
                            filters=dict(start_date=start_date, end_date=end_date, class_id=class_id, status=status))


@admin_bp.route("/attendance/export/<fmt>")
def attendance_export(fmt):
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    class_id = request.args.get("class_id", type=int)
    status = request.args.get("status")
    rows = build_attendance_query(start_date, end_date, class_id, None, status).all()

    if fmt == "csv":
        data, mimetype, ext = export_csv(rows), "text/csv", "csv"
    elif fmt == "excel":
        data, mimetype, ext = export_excel(rows), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx"
    elif fmt == "pdf":
        data, mimetype, ext = export_pdf(rows), "application/pdf", "pdf"
    else:
        return jsonify({"error": "invalid format"}), 400

    resp = make_response(data)
    resp.headers["Content-Type"] = mimetype
    resp.headers["Content-Disposition"] = f"attachment; filename=attendance_report.{ext}"
    log_action("REPORT_EXPORT", f"format={fmt}")
    return resp


# ---------------------------------------------------------------------- LOGS / SYSTEM
@admin_bp.route("/logs")
def logs():
    page = request.args.get("page", 1, type=int)
    entries = AuditLog.query.order_by(AuditLog.timestamp.desc()).paginate(page=page, per_page=40, error_out=False)
    return render_template("admin/logs.html", entries=entries)


@admin_bp.route("/cameras")
def cameras():
    cams = CameraStatus.query.all()
    unknown_faces = UnknownFaceLog.query.order_by(UnknownFaceLog.detected_at.desc()).limit(30).all()
    return render_template("admin/cameras.html", cams=cams, unknown_faces=unknown_faces)


def abort_404():
    from flask import abort
    abort(404)
