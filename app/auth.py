from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, request, flash, session
from flask_login import login_user, logout_user, login_required, current_user

from app.models import db, User, Teacher, Student
from app.utils import log_action

auth_bp = Blueprint("auth", __name__)

ROLE_HOME = {
    "admin": "admin.dashboard",
    "teacher": "teacher.dashboard",
    "student": "student.dashboard",
}

REGISTER_TEMPLATE = {
    "admin": "auth/register_admin.html",
    "teacher": "auth/register_teacher.html",
    "student": "auth/register_student.html",
}

LOGIN_ROUTE = {
    "admin": "auth.login_admin",
    "teacher": "auth.login_teacher",
    "student": "auth.login_student",
}


@auth_bp.route("/")
def choose_login():
    """Landing page letting the user pick which portal to sign in to."""
    if current_user.is_authenticated:
        return redirect(url_for(ROLE_HOME[current_user.role]))
    return render_template("auth/choose_login.html")


def _handle_login(role, template):
    if current_user.is_authenticated:
        return redirect(url_for(ROLE_HOME[current_user.role]))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        remember = bool(request.form.get("remember"))

        user = User.query.filter(
            (User.username == username) | (User.email == username)
        ).first()

        if not user or not user.check_password(password):
            flash("Invalid credentials. Please try again.", "danger")
            log_action("LOGIN_FAILED", f"role={role} username={username}")
            return render_template(template, error="Invalid username or password")

        if user.role != role:
            flash(f"This account is not registered as a {role}.", "danger")
            return render_template(template, error=f"Please use the {user.role} login portal")

        if not user.is_active:
            flash("This account has been disabled. Contact the administrator.", "warning")
            return render_template(template, error="Account disabled")

        login_user(user, remember=remember)
        user.last_login = datetime.utcnow()
        db.session.commit()
        log_action("LOGIN_SUCCESS", f"role={role}", user=user)
        session.permanent = True

        next_url = request.args.get("next")
        return redirect(next_url or url_for(ROLE_HOME[role]))

    return render_template(template)


def _create_profile(role, user, f):
    """Create the role-specific profile row for a freshly self-registered user."""
    if role == "teacher":
        db.session.add(Teacher(
            user_id=user.id,
            teacher_code=f["teacher_code"].strip(),
            department=(f.get("department") or "").strip() or None,
            phone=(f.get("phone") or "").strip() or None,
        ))
    elif role == "student":
        dob = None
        if f.get("dob"):
            dob = datetime.strptime(f["dob"], "%Y-%m-%d").date()
        db.session.add(Student(
            user_id=user.id,
            student_code=f["student_code"].strip(),
            gender=f.get("gender") or None,
            phone=(f.get("phone") or "").strip() or None,
            address=(f.get("address") or "").strip() or None,
            dob=dob,
        ))
    # admin has no separate profile table - the User row is enough


def _handle_register(role, template):
    """Self-service account creation for a portal.

    An account can only be created if no existing account already matches
    the given username/email (and, for teachers/students, the given
    ID/code). If a matching account already exists, registration is blocked
    and the person is told to log in instead.
    """
    if current_user.is_authenticated:
        return redirect(url_for(ROLE_HOME[current_user.role]))

    if request.method == "POST":
        f = request.form
        username = f.get("username", "").strip()
        email = f.get("email", "").strip()
        full_name = f.get("full_name", "").strip()
        password = f.get("password", "")
        confirm_password = f.get("confirm_password", "")

        if not username or not email or not full_name or not password:
            flash("Please fill in all required fields.", "danger")
            return render_template(template, form=f)

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template(template, form=f)

        # Only allow creating the account if one doesn't already exist.
        existing = User.query.filter(
            (User.username == username) | (User.email == email)
        ).first()
        if existing:
            flash("An account with that username or email already exists. Please sign in instead.", "danger")
            return render_template(template, form=f)

        if role == "teacher":
            code = f.get("teacher_code", "").strip()
            if not code:
                flash("Teacher ID / Code is required.", "danger")
                return render_template(template, form=f)
            if Teacher.query.filter_by(teacher_code=code).first():
                flash("That Teacher ID is already registered. Please sign in instead.", "danger")
                return render_template(template, form=f)

        if role == "student":
            code = f.get("student_code", "").strip()
            if not code:
                flash("Student ID / Code is required.", "danger")
                return render_template(template, form=f)
            if Student.query.filter_by(student_code=code).first():
                flash("That Student ID is already registered. Please sign in instead.", "danger")
                return render_template(template, form=f)

        user = User(username=username, email=email, full_name=full_name, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.flush()

        _create_profile(role, user, f)

        db.session.commit()
        log_action(f"{role.upper()}_SELF_REGISTER", f"username={username}", user=user)
        flash("Account created successfully. Please sign in.", "success")
        return redirect(url_for(LOGIN_ROUTE[role]))

    return render_template(template, form={})


@auth_bp.route("/register/admin", methods=["GET", "POST"])
def register_admin():
    return _handle_register("admin", REGISTER_TEMPLATE["admin"])


@auth_bp.route("/register/teacher", methods=["GET", "POST"])
def register_teacher():
    return _handle_register("teacher", REGISTER_TEMPLATE["teacher"])


@auth_bp.route("/register/student", methods=["GET", "POST"])
def register_student():
    return _handle_register("student", REGISTER_TEMPLATE["student"])


@auth_bp.route("/login/admin", methods=["GET", "POST"])
def login_admin():
    return _handle_login("admin", "auth/login_admin.html")


@auth_bp.route("/login/teacher", methods=["GET", "POST"])
def login_teacher():
    return _handle_login("teacher", "auth/login_teacher.html")


@auth_bp.route("/login/student", methods=["GET", "POST"])
def login_student():
    return _handle_login("student", "auth/login_student.html")


@auth_bp.route("/logout")
@login_required
def logout():
    log_action("LOGOUT", "", user=current_user)
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.choose_login"))
