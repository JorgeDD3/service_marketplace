import os
from datetime import timezone
from zoneinfo import ZoneInfo

from flask import Flask, render_template
from flask_login import current_user
from werkzeug.middleware.proxy_fix import ProxyFix

from config import DevelopmentConfig, ProductionConfig
from .cli import register_cli_commands
from .extensions import db, login_manager


class URLPrefixMiddleware:
    """Make URL generation work when the app is mounted under a subpath.

    This is only needed when a reverse proxy hosts the app under a path prefix
    (ex: https://example.com/myapp/). In that setup the proxy often strips the
    prefix before forwarding to the WSGI server, so we set SCRIPT_NAME but do
    not rewrite PATH_INFO.
    """

    def __init__(self, app, prefix: str):
        self.app = app
        self.prefix = prefix.rstrip("/")

    def __call__(self, environ, start_response):
        environ["SCRIPT_NAME"] = self.prefix
        return self.app(environ, start_response)


def create_app():
    """Application factory for ServiceSphere.

    This configures:
    - proxy/subpath support (Apache -> gunicorn)
    - config selection (dev vs production)
    - extensions + CLI commands
    - blueprints
    - error handlers
    - small template helpers (timezone formatting, provider verification badge)
    """
    app = Flask(__name__, instance_relative_config=True, static_folder="static")

    # Reverse proxy support (Apache -> gunicorn)
    # Trust X-Forwarded-* headers from the local Apache proxy.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)

    # Subpath mount support (Jeff's config)
    # Optional subpath mount support (only needed if you're hosting under a prefix like /myapp).
    url_prefix = os.getenv("URL_PREFIX", "").strip()
    if url_prefix:
        app.wsgi_app = URLPrefixMiddleware(app.wsgi_app, url_prefix)
        # Keep the session cookie scoped to the mounted path.
        app.config["SESSION_COOKIE_PATH"] = url_prefix.rstrip("/") + "/"

    # Config selection via environment variable (default: development).
    config_name = os.getenv("APP_CONFIG", "development").lower()

    if config_name == "production":
        app.config.from_object(ProductionConfig)

        # In production we require a non-placeholder SECRET_KEY.
        sk = app.config.get("SECRET_KEY")
        if not sk or sk == "dev-only-change-me":
            raise RuntimeError("SECRET_KEY must be set to a strong value in production.")
    else:
        app.config.from_object(DevelopmentConfig)

    # Display timezone (for UI formatting only).
    # DB timestamps remain UTC; templates can render in a local timezone.
    app.config.setdefault("DISPLAY_TIMEZONE", os.getenv("DISPLAY_TIMEZONE", "America/Chicago"))

    @app.template_filter("fmt_local_dt")
    def fmt_local_dt(value, fmt: str = "%b %d, %I:%M %p") -> str:
        """Render a datetime in DISPLAY_TIMEZONE.

        Naive datetimes are treated as UTC, since that's how the project stores most timestamps.
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

    # Ensure upload directory exists (instance/uploads).
    upload_dir = app.config.get("UPLOAD_DIR")
    if upload_dir:
        os.makedirs(upload_dir, exist_ok=True)

    # Init extensions.
    db.init_app(app)
    login_manager.init_app(app)

    register_cli_commands(app)

    # Register blueprints.
    from app.admin import admin_bp
    from app.auth import auth
    from app.messages import messages_bp
    from app.provider import provider
    from app.routes import main
    from app.service_requests import service_requests_bp
    from app.services_provider import provider_services

    app.register_blueprint(main)
    app.register_blueprint(auth)
    app.register_blueprint(provider)
    app.register_blueprint(provider_services)
    app.register_blueprint(service_requests_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(messages_bp)

    # Global error handlers.
    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template("errors/500.html"), 500

    # User loader (kept here to avoid circular imports).
    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # IMPORTANT:
    # Do NOT create tables automatically inside create_app().
    # This can cause unwanted DB connections (especially on hosted platforms).
    #
    # For local dev convenience only:
    #   AUTO_CREATE_DB=1 flask --app wsgi run
    if os.getenv("AUTO_CREATE_DB", "").lower() in {"1", "true", "yes"}:
        with app.app_context():
            db.create_all()

    # Navbar verification status for providers (available in all templates).
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
            # This should never break rendering; it's only a convenience context value.
            status = None

        return {"nav_verification_status": status}

    return app