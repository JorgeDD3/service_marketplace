from flask import Blueprint, render_template, request, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, login_required, current_user

from app.extensions import db
from app.models import User, Role

auth = Blueprint("auth", __name__, url_prefix="/auth")


@auth.route("/register", methods=["GET", "POST"])
def register():
    # If already logged in, don't allow re-register
    if current_user.is_authenticated:
        return redirect(url_for("main.home"))

    if request.method == "GET":
        return render_template("register.html")

    # POST
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

    # Prevent public creation of admin accounts
    if role_name not in {"client", "provider"}:
        flash("Invalid role selection.", "danger")
        return redirect(url_for("auth.register"))

    # Duplicate check
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
        # is_active defaults True; leave explicit set out
    )

    db.session.add(user)
    db.session.commit()

    login_user(user)
    flash("Registration successful. Welcome!", "success")
    return redirect(url_for("main.home"))


@auth.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.home"))

    if request.method == "GET":
        return render_template("login.html")

    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""
    next_url = request.args.get("next")

    user = User.query.filter_by(email=email).first()

    if not user or not check_password_hash(user.password_hash, password):
        flash("Invalid email or password.", "danger")
        return redirect(url_for("auth.login"))

    # Block disabled accounts (admin moderation)
    if user.is_active is False:
        reason = (user.disabled_reason or "").strip()
        msg = "Your account has been disabled."
        if reason:
            msg += f" Reason: {reason}"
        flash(msg, "danger")
        return redirect(url_for("auth.login"))

    login_user(user)
    flash("Logged in successfully.", "success")

    # Preserve redirect if user was sent here from protected page
    if next_url and next_url.startswith("/"):
        return redirect(next_url)

    # Role-based redirect
    if user.has_role("provider"):
        return redirect(url_for("provider.dashboard"))

    if user.has_role("admin"):
        return redirect(url_for("admin.dashboard"))

    # Default for clients
    return redirect(url_for("main.services"))

@auth.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("main.home"))

# --- Password Reset (Option B) ---
from flask import current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app.extensions import db
from app.models import User, PasswordResetToken, hash_token


@auth.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    # If logged in, no need to reset
    if current_user.is_authenticated:
        flash("You are already logged in.", "info")
        return redirect(url_for("main.services"))

    reset_link = None

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()

        # Always neutral message (prevents email enumeration)
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

                # Dev-mode demo: show link on-screen instead of sending email
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
    if current_user.is_authenticated:
        flash("You are already logged in.", "info")
        return redirect(url_for("main.services"))

    token_h = hash_token(token)
    row = PasswordResetToken.query.filter_by(token_hash=token_h).first()

    # Validate token
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