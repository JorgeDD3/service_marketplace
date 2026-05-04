"""
Flask extension instances.

These are created once and initialized inside create_app() (app factory pattern).
Keeping them here avoids circular imports and keeps configuration centralized.
"""

from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message_category = "info"