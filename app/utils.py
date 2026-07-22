from functools import wraps
from flask import abort, request
from flask_login import current_user

from app.models import db, AuditLog


def log_action(action, details="", user=None):
    """Write an entry to the audit log table."""
    entry = AuditLog(
        user_id=(user.id if user else (current_user.id if current_user.is_authenticated else None)),
        action=action,
        details=details,
        ip_address=request.remote_addr if request else None,
    )
    db.session.add(entry)
    db.session.commit()


def roles_required(*roles):
    """Decorator restricting a view to specific user roles."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if current_user.role not in roles:
                abort(403)
            return view_func(*args, **kwargs)
        return wrapped
    return decorator
