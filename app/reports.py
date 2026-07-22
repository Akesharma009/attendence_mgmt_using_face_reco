import io
from datetime import date, timedelta

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

from app.models import db, Attendance, Student, ClassSession, Course


def build_attendance_query(start_date=None, end_date=None, class_id=None, student_id=None, status=None):
    q = (
        db.session.query(Attendance, Student, ClassSession, Course)
        .join(Student, Attendance.student_id == Student.id)
        .join(ClassSession, Attendance.class_id == ClassSession.id)
        .join(Course, ClassSession.course_id == Course.id)
    )
    if start_date:
        q = q.filter(Attendance.date >= start_date)
    if end_date:
        q = q.filter(Attendance.date <= end_date)
    if class_id:
        q = q.filter(Attendance.class_id == class_id)
    if student_id:
        q = q.filter(Attendance.student_id == student_id)
    if status:
        q = q.filter(Attendance.status == status)
    return q.order_by(Attendance.date.desc(), Attendance.time_in.desc())


def rows_to_dataframe(rows):
    data = []
    for att, student, cls, course in rows:
        data.append({
            "Student ID": student.student_code,
            "Name": student.user.full_name,
            "Course": course.name,
            "Class": cls.class_name,
            "Date": att.date.isoformat(),
            "Time In": att.time_in.strftime("%H:%M:%S") if att.time_in else "",
            "Time Out": att.time_out.strftime("%H:%M:%S") if att.time_out else "",
            "Duration": att.duration_display,
            "Status": att.status,
            "Confidence %": att.confidence,
            "Marked By": att.marked_by,
        })
    return pd.DataFrame(data)


def export_csv(rows):
    df = rows_to_dataframe(rows)
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")


def export_excel(rows):
    df = rows_to_dataframe(rows)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Attendance")
    return buf.getvalue()


def export_pdf(rows, title="Attendance Report"):
    df = rows_to_dataframe(rows)
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4))
    styles = getSampleStyleSheet()
    elements = [Paragraph(title, styles["Title"]), Spacer(1, 12)]

    if df.empty:
        elements.append(Paragraph("No records found for the selected filters.", styles["Normal"]))
    else:
        table_data = [list(df.columns)] + df.astype(str).values.tolist()
        table = Table(table_data, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4f46e5")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
        ]))
        elements.append(table)

    doc.build(elements)
    return buf.getvalue()


def attendance_percentage(student_id, class_id=None, start_date=None, end_date=None):
    """Simplified % = present+late days / distinct scheduled days attendance exists for."""
    q = Attendance.query.filter_by(student_id=student_id)
    if class_id:
        q = q.filter_by(class_id=class_id)
    if start_date:
        q = q.filter(Attendance.date >= start_date)
    if end_date:
        q = q.filter(Attendance.date <= end_date)
    records = q.all()
    if not records:
        return 0.0
    present = sum(1 for r in records if r.status in ("present", "late"))
    return round(present / len(records) * 100, 1)


def daily_trend(days=14, class_id=None):
    """Returns list of {date, present, late, total} for the last N days (for charts)."""
    start = date.today() - timedelta(days=days - 1)
    q = Attendance.query.filter(Attendance.date >= start)
    if class_id:
        q = q.filter_by(class_id=class_id)
    records = q.all()

    buckets = {(start + timedelta(days=i)): {"present": 0, "late": 0} for i in range(days)}
    for r in records:
        if r.date in buckets:
            if r.status == "late":
                buckets[r.date]["late"] += 1
            elif r.status == "present":
                buckets[r.date]["present"] += 1

    return [
        {"date": d.isoformat(), "present": v["present"], "late": v["late"], "total": v["present"] + v["late"]}
        for d, v in sorted(buckets.items())
    ]
