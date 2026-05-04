# app/auth/routes.py

from flask import current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app.extensions import db
from app.models import User, PasswordResetToken, hash_token
from app.auth import auth


def _is_production() -> bool:
    """Best-effort production check.

    I keep this lightweight because the app may run under different configs
    (local dev only). In production, we should not show reset links on-screen.
    links in the UI.
    """
    return (
        current_app.config.get("APP_CONFIG") == "production"
        or current_app.config.get("ENV") == "production"
    )


@auth.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    """Start the password reset flow.

    Security note: the response stays neutral whether an email exists or not,
    which prevents email enumeration.
    """
    # If logged in, a reset doesn't make sense.
    if current_user.is_authenticated:
        flash("You are already logged in.", "info")
        return redirect(url_for("main.services"))

    reset_link = None

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()

        # Always neutral message (prevents email enumeration).
        flash("If an account exists for that email, a reset link has been generated.", "info")

        if email:
            user = User.query.filter(db.func.lower(User.email) == email).first()

            if user and getattr(user, "is_active", True):
                raw_token, _row = PasswordResetToken.create_for_user(
                    user,
                    ttl_minutes=30,
                    request_ip=request.headers.get("X-Forwarded-For", request.remote_addr),
                    user_agent=request.headers.get("User-Agent"),
                )

                # Dev/demo mode: show link on-screen instead of sending email.
                if not _is_production():
                    reset_link = url_for("auth.reset_password", token=raw_token, _external=True)

        return render_template("auth/forgot_password.html", reset_link=reset_link)

    return render_template("auth/forgot_password.html", reset_link=reset_link)


@auth.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token: str):
    """Complete a password reset using a single-use token."""
    if current_user.is_authenticated:
        flash("You are already logged in.", "info")
        return redirect(url_for("main.services"))

    token_h = hash_token(token)
    row = PasswordResetToken.query.filter_by(token_hash=token_h).first()

    # Validate token (missing, already used, or expired).
    if not row or row.is_used or row.is_expired:
        flash("That reset link is invalid or has expired. Please request a new one.", "warning")
        return redirect(url_for("auth.forgot_password"))

    if request.method == "POST":
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm_password") or ""

        if len(password) < 8:
            flash("Password must be at least 8 characters.", "danger")
            return render_template("auth/reset_password.html")

        if password != confirm:
            flash("Passwords do not match.", "danger")
            return render_template("auth/reset_password.html")

        user = User.query.get(row.user_id)
        if not user:
            flash("That reset link is invalid. Please request a new one.", "warning")
            return redirect(url_for("auth.forgot_password"))

        if hasattr(user, "set_password"):
            user.set_password(password)
        else:
            raise RuntimeError("User model missing set_password(password)")

        row.used_at = db.func.now()
        db.session.commit()

        flash("Password reset successful. You can now log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/reset_password.html")