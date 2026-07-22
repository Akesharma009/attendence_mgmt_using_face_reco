from datetime import date, datetime, timedelta

from app.models import db, Attendance, ClassSession, Enrollment


def is_enrolled(student_id, class_id):
    return Enrollment.query.filter_by(student_id=student_id, class_id=class_id).first() is not None


def mark_attendance(student_id, class_id, confidence=None, marked_by="system", late_after_minutes=15):
    """
    Marks attendance for a student in a class for *today*.

    - The FIRST time a student's face is recognized for this class today,
      a new Attendance row is created and `time_in` is stamped.
    - Every SUBSEQUENT recognition on the same day updates `time_out` to
      "now", so time_out always reflects the last moment the student was
      seen by the camera. The difference (time_out - time_in) is how long
      the student was seated in class (see Attendance.duration_minutes /
      duration_display).

    Returns (attendance_row, created: bool, message: str)
    """
    today = date.today()
    now_time = datetime.now().time()

    existing = Attendance.query.filter_by(student_id=student_id, class_id=class_id, date=today).first()
    if existing:
        # Student seen again today -> push their "time out" forward.
        if not existing.time_out or now_time > existing.time_out:
            existing.time_out = now_time
            db.session.commit()
        return existing, False, f"Time-out updated to {now_time.strftime('%H:%M:%S')} (in class {existing.duration_display})."

    class_session = db.session.get(ClassSession, class_id)
    status = "present"

    if class_session and class_session.start_time:
        cutoff = (datetime.combine(today, class_session.start_time) + timedelta(minutes=late_after_minutes)).time()
        if now_time > cutoff:
            status = "late"

    record = Attendance(
        student_id=student_id,
        class_id=class_id,
        date=today,
        time_in=now_time,
        time_out=now_time,
        status=status,
        confidence=confidence,
        marked_by=marked_by,
    )
    db.session.add(record)
    db.session.commit()
    return record, True, f"Attendance marked as {status} at {now_time.strftime('%H:%M:%S')}."
