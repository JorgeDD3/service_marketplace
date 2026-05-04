"""
RBAC / access-control helpers.

I keep the rules centralized so routes stay readable and consistent:
- unauthenticated users get redirected to login (with next=...)
- authenticated users without the right role get a 403 + a friendly flash
"""

from __future__ import annotations

from functools import wraps
from typing import Callable, ParamSpec, TypeVar

from flask import abort, flash, redirect, request, url_for
from flask_login import current_user

P = ParamSpec("P")
R = TypeVar("R")


def role_required(*allowed_roles: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Require the current user to have one of the allowed roles.

    Usage:
        @login_required
        @role_required("admin")

        @login_required
        @role_required("provider", "admin")

    Notes:
    - If the user is not logged in, we redirect to the login page and preserve `next`.
    - If they are logged in but not authorized, we return a 403 and flash a message.
    """
    allowed = {r for r in allowed_roles if r}

    def decorator(view_func: Callable[P, R]) -> Callable[P, R]:
        @wraps(view_func)
        def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
            if not current_user.is_authenticated:
                return redirect(url_for("auth.login", next=request.path))

            user_role = getattr(getattr(current_user, "role", None), "role_name", None)
            if user_role not in allowed:
                flash("You are not authorized to access that page.", "warning")
                abort(403)

            return view_func(*args, **kwargs)

        return wrapped

    return decorator