# app/__init__.py
import os
from flask import Flask, render_template

from config import DevelopmentConfig, ProductionConfig
from .extensions import db, login_manager
from .cli import register_cli_commands


def create_app():
    app = Flask(__name__, instance_relative_config=True, static_folder="static")

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

    # error handlers
    @app.errorhandler(403)
    def forbidden(e):
        return render_template("403.html"), 403

    # user loader (kept here to avoid circular imports)
    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    if app.config.get("DEBUG"):
        with app.app_context():
            db.create_all()

    return app