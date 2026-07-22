"""
Seed the database with a default admin account and a small demo dataset.

Usage:
    python seed_db.py
"""
from datetime import date, time

from app import create_app
from app.models import db, User, Teacher, Student, Course, ClassSession, Enrollment

app = create_app()

with app.app_context():
    db.create_all()

    if not User.query.filter_by(username="admin").first():
        admin = User(username="admin", email="admin@facetrack.local", full_name="System Administrator", role="admin")
        admin.set_password("Admin@123")
        db.session.add(admin)
        print("Created admin -> username: admin | password: Admin@123")

    if not User.query.filter_by(username="teacher1").first():
        t_user = User(username="teacher1", email="teacher1@facetrack.local", full_name="Sarah Johnson", role="teacher")
        t_user.set_password("Teacher@123")
        db.session.add(t_user)
        db.session.flush()
        teacher = Teacher(user_id=t_user.id, teacher_code="T-001", department="Computer Science", phone="555-0101")
        db.session.add(teacher)
        print("Created teacher -> username: teacher1 | password: Teacher@123")

    if not Course.query.filter_by(code="CS101").first():
        course = Course(code="CS101", name="Introduction to Computer Science", description="Foundational CS course", credits=3)
        db.session.add(course)
        db.session.flush()

        teacher = Teacher.query.filter_by(teacher_code="T-001").first()
        cls = ClassSession(course_id=course.id, teacher_id=teacher.id if teacher else None,
                            class_name="Section A", schedule_day="Monday",
                            start_time=time(9, 0), end_time=time(11, 0), room="Room 204")
        db.session.add(cls)
        db.session.flush()
        print("Created demo course CS101 / Section A")

    if not User.query.filter_by(username="student1").first():
        s_user = User(username="student1", email="student1@facetrack.local", full_name="Alex Carter", role="student")
        s_user.set_password("Student@123")
        db.session.add(s_user)
        db.session.flush()
        student = Student(user_id=s_user.id, student_code="S-0001", gender="Male",
                           enrollment_date=date.today())
        db.session.add(student)
        db.session.flush()

        cls = ClassSession.query.first()
        if cls:
            db.session.add(Enrollment(student_id=student.id, class_id=cls.id))
        print("Created student -> username: student1 | password: Student@123")
        print("NOTE: run the app, log in as admin, and register this student's FACE via the webcam capture page.")

    db.session.commit()
    print("\nSeeding complete.")
