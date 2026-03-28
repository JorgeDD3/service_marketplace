from functools import wraps
from flask import abort, request, redirect, url_for, flash
from flask_login import current_user

def role_required(*allowed_roles: str):
    """
    Usage:
        @role_required("admin")
        @role_required("provider", "admin")
    """
    allowed = set(allowed_roles)

    def decorator(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            # Must be logged in
            if not current_user.is_authenticated:
                return redirect(url_for("auth.login", next=request.path))

            # Must have one of the allowed roles
            user_role = getattr(getattr(current_user, "role", None), "role_name", None)
            if user_role not in allowed:
                flash("You are not authorized to access that page.", "warning")
                abort(403)

            return view_func(*args, **kwargs)
        return wrapped

    return decorator