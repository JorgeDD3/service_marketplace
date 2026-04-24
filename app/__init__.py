# app/__init__.py
import os
from datetime import timezone
from zoneinfo import ZoneInfo

from flask import Flask, render_template
from werkzeug.middleware.proxy_fix import ProxyFix

from config import DevelopmentConfig, ProductionConfig
from .extensions import db, login_manager
from .cli import register_cli_commands


class URLPrefixMiddleware:
    """
    Ensures Flask URL generation works when the app is mounted under a subpath
    behind Apache, e.g. /~gddelp/service_marketplace/.

    Apache ProxyPass typically strips the prefix before forwarding to gunicorn,
    so we set SCRIPT_NAME but DO NOT rewrite PATH_INFO.
    """

    def __init__(self, app, prefix: str):
        self.app = app
        self.prefix = prefix.rstrip("/")

    def __call__(self, environ, start_response):
        environ["SCRIPT_NAME"] = self.prefix
        return self.app(environ, start_response)


def create_app():
    app = Flask(__name__, instance_relative_config=True, static_folder="static")

    # ---- Reverse proxy support (Apache -> gunicorn) ----
    # Trust X-Forwarded-* headers from the local Apache proxy.
    # x_for=1: client IP, x_proto=1: https scheme, x_host=1: host header, x_port=1: port
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)

    # ---- Subpath mount support (Jeff's config) ----
    # Example: export URL_PREFIX="/~gddelp/service_marketplace"
    url_prefix = os.getenv("URL_PREFIX", "").strip()
    if url_prefix:
        app.wsgi_app = URLPrefixMiddleware(app.wsgi_app, url_prefix)
        # Make session cookie valid for the mounted path
        app.config["SESSION_COOKIE_PATH"] = url_prefix.rstrip("/") + "/"

    # Config selection via environment variable
    # Default: development
    config_name = os.getenv("APP_CONFIG", "development").lower()

    if config_name == "production":
        app.config.from_object(ProductionConfig)

        # Enforce strong SECRET_KEY only in production
        sk = app.config.get("SECRET_KEY")
        if not sk or sk == "dev-only-change-me":
            raise RuntimeError("SECRET_KEY must be set to a strong value in production.")
    else:
        app.config.from_object(DevelopmentConfig)

    # ---- Display timezone (for UI formatting) ----
    # Keep DB timestamps in UTC, but render in local timezone.
    app.config.setdefault("DISPLAY_TIMEZONE", os.getenv("DISPLAY_TIMEZONE", "America/Chicago"))

    @app.template_filter("fmt_local_dt")
    def fmt_local_dt(value, fmt="%b %d, %I:%M %p"):
        """
        Treat naive datetimes as UTC, convert to DISPLAY_TIMEZONE, then format.
        """
        if not value:
            return ""
        if getattr(value, "tzinfo", None) is None:
            value = value.replace(tzinfo=timezone.utc)

        tz_name = app.config.get("DISPLAY_TIMEZONE", "America/Chicago")
        try:
            tz = ZoneInfo(tz_name)
        except Exception:
            tz = ZoneInfo("UTC")

        return value.astimezone(tz).strftime(fmt)

    # Ensure upload directory exists (instance/uploads)
    upload_dir = app.config.get("UPLOAD_DIR")
    if upload_dir:
        os.makedirs(upload_dir, exist_ok=True)

    # init extensions
    db.init_app(app)
    login_manager.init_app(app)

    register_cli_commands(app)

    # register blueprints
    from app.routes import main
    from app.auth import auth
    from app.provider import provider
    from app.services_provider import provider_services
    from .service_requests import service_requests_bp
    from .admin import admin_bp
    from .messages import messages_bp

    app.register_blueprint(main)
    app.register_blueprint(auth)
    app.register_blueprint(provider)
    app.register_blueprint(provider_services)
    app.register_blueprint(service_requests_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(messages_bp)

    # ---- Global error handlers ----
    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template("errors/500.html"), 500

    # user loader (kept here to avoid circular imports)
    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # IMPORTANT:
    # Do NOT create tables automatically inside create_app().
    # This causes unwanted DB connections (especially with Postgres on hosted platforms).
    #
    # If you ever want an opt-in convenience for local dev only:
    #   AUTO_CREATE_DB=1 flask --app wsgi run
    if os.getenv("AUTO_CREATE_DB", "").lower() in {"1", "true", "yes"}:
        with app.app_context():
            db.create_all()

    # --- Navbar verification status for providers (available in all templates) ---
    from flask_login import current_user
    from app.models import ProviderProfile, ProviderVerification

    @app.context_processor
    def inject_nav_verification_status():
        status = None
        try:
            if current_user.is_authenticated and current_user.has_role("provider"):
                profile = ProviderProfile.query.filter_by(user_id=current_user.id).first()
                if profile:
                    v = ProviderVerification.query.filter_by(provider_profile_id=profile.id).first()
                    if v:
                        status = v.status
        except Exception:
            status = None

        return {"nav_verification_status": status}

    return app