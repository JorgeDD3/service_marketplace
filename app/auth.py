"""
Authentication routes for ServiceSphere.

This file handles:
- registering new users (client/provider only)
- login/logout with Flask-Login
- password reset (demo-friendly: generates a reset link on screen in non-prod)

I keep these routes under /auth so the rest of the app can focus on marketplace logic.
"""

from flask import Blueprint, current_app, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db
from app.models import User, Role, PasswordResetToken, hash_token

auth = Blueprint("auth", __name__, url_prefix="/auth")


@auth.route("/register", methods=["GET", "POST"])
def register():
    """Creates a new account (clients and providers only)."""
    # If someone is already logged in, I don’t let them re-register on the same session.
    if current_user.is_authenticated:
        return redirect(url_for("main.home"))

    if request.method == "GET":
        return render_template("auth/register.html")

    first_name = (request.form.get("first_name") or "").strip()
    last_name = (request.form.get("last_name") or "").strip()
    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""
    confirm = request.form.get("confirm_password") or ""
    role_name = request.form.get("role") or ""

    if not first_name or not last_name or not email or not password or not confirm or not role_name:
        flash("All fields are required.", "danger")
        return redirect(url_for("auth.register"))

    if password != confirm:
        flash("Passwords do not match.", "danger")
        return redirect(url_for("auth.register"))

    # I block public creation of admin accounts. Admins should be seeded or created privately.
    if role_name not in {"client", "provider"}:
        flash("Invalid role selection.", "danger")
        return redirect(url_for("auth.register"))

    if User.query.filter_by(email=email).first():
        flash("An account with that email already exists.", "warning")
        return redirect(url_for("auth.register"))

    role = Role.query.filter_by(role_name=role_name).first()
    if not role:
        flash("Role configuration error. Contact admin.", "danger")
        return redirect(url_for("auth.register"))

    user = User(
        first_name=first_name,
        last_name=last_name,
        email=email,
        password_hash=generate_password_hash(password),
        role_id=role.id,
    )

    db.session.add(user)
    db.session.commit()

    login_user(user)
    flash("Registration successful. Welcome!", "success")
    return redirect(url_for("main.home"))


@auth.route("/login", methods=["GET", "POST"])
def login():
    """Logs a user in and sends them to the correct dashboard based on role."""
    if current_user.is_authenticated:
        return redirect(url_for("main.home"))

    if request.method == "GET":
        return render_template("auth/login.html")

    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""
    next_url = request.args.get("next")

    user = User.query.filter_by(email=email).first()

    # I keep this message generic so it doesn't leak which emails exist.
    if not user or not check_password_hash(user.password_hash, password):
        flash("Invalid email or password.", "danger")
        return redirect(url_for("auth.login"))

    # If an admin disabled the account, I block login and show the reason if available.
    if user.is_active is False:
        reason = (user.disabled_reason or "").strip()
        msg = "Your account has been disabled."
        if reason:
            msg += f" Reason: {reason}"
        flash(msg, "danger")
        return redirect(url_for("auth.login"))

    login_user(user)
    flash("Logged in successfully.", "success")

    # If Flask-Login sent them here from a protected page, I respect that redirect.
    if next_url and next_url.startswith("/"):
        return redirect(next_url)

    # Otherwise I send them to the right place based on role.
    if user.has_role("provider"):
        return redirect(url_for("provider.dashboard"))

    if user.has_role("admin"):
        return redirect(url_for("admin.dashboard"))

    return redirect(url_for("main.services"))


@auth.route("/logout")
@login_required
def logout():
    """Ends the session and returns the user to the home page."""
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("main.home"))


@auth.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    """Generates a password reset token and shows a reset link in non-production builds."""
    # If logged in already, a reset isn't needed.
    if current_user.is_authenticated:
        flash("You are already logged in.", "info")
        return redirect(url_for("main.services"))

    reset_link = None

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()

        # I always show the same message so users can't probe which emails are registered.
        flash("If an account exists for that email, a reset link has been generated.", "info")

        if email:
            user = User.query.filter(db.func.lower(User.email) == email).first()

            # I only generate a token for real, active accounts.
            if user and getattr(user, "is_active", True):
                raw_token, _row = PasswordResetToken.create_for_user(
                    user,
                    ttl_minutes=30,
                    request_ip=request.headers.get("X-Forwarded-For", request.remote_addr),
                    user_agent=request.headers.get("User-Agent"),
                )

                # For the class demo, I show the link on screen in non-prod instead of emailing it.
                is_prod = (
                    current_app.config.get("APP_CONFIG") == "production"
                    or current_app.config.get("ENV") == "production"
                )
                if not is_prod:
                    reset_link = url_for("auth.reset_password", token=raw_token, _external=True)

        return render_template("auth/forgot_password.html", reset_link=reset_link)

    return render_template("auth/forgot_password.html", reset_link=reset_link)


@auth.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token: str):
    """Validates a reset token and allows the user to set a new password."""
    if current_user.is_authenticated:
        flash("You are already logged in.", "info")
        return redirect(url_for("main.services"))

    token_h = hash_token(token)
    row = PasswordResetToken.query.filter_by(token_hash=token_h).first()

    # If the token isn't valid, I push the user back to request a new one.
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

        # This project stores hashes directly on User.password_hash.
        user.password_hash = generate_password_hash(password)

        row.used_at = db.func.now()
        db.session.commit()

        flash("Password reset successful. You can now log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/reset_password.html")