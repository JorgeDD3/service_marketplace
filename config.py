# config.py
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
INSTANCE_DIR.mkdir(exist_ok=True)

DEFAULT_DB_PATH = INSTANCE_DIR / "site.db"

# Uploads (used for provider verification docs, messaging attachments later, etc.)
UPLOAD_DIR = INSTANCE_DIR / "uploads"
MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", 10 * 1024 * 1024))  # 10 MB default
ALLOWED_UPLOAD_EXTENSIONS = {"pdf", "png", "jpg", "jpeg"}


def _normalize_database_url(url: str) -> str:
    """
    Normalize DATABASE_URL for SQLAlchemy.

    Some platforms provide:
      postgres://user:pass@host:5432/dbname
    SQLAlchemy + psycopg expects:
      postgresql+psycopg://user:pass@host:5432/dbname

    Also supports:
      postgresql://...
    """
    if not url:
        return url

    url = url.strip()

    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)

    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)

    # If it already includes a driver like postgresql+psycopg://, leave it.
    return url


class BaseConfig:
    # Security (dev fallback is OK; production will enforce separately)
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me")

    # Database
    _raw_db_url = os.getenv("DATABASE_URL", "")
    if _raw_db_url:
        SQLALCHEMY_DATABASE_URI = _normalize_database_url(_raw_db_url)
    else:
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{DEFAULT_DB_PATH}"

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Uploads
    UPLOAD_DIR = UPLOAD_DIR
    MAX_CONTENT_LENGTH = MAX_CONTENT_LENGTH
    ALLOWED_UPLOAD_EXTENSIONS = ALLOWED_UPLOAD_EXTENSIONS

    # Helps URL generation when behind TLS-terminating proxies (Apache)
    PREFERRED_URL_SCHEME = "https"


class DevelopmentConfig(BaseConfig):
    DEBUG = True


class ProductionConfig(BaseConfig):
    DEBUG = False

    # ---- Cookie/session hardening ----
    SESSION_COOKIE_SECURE = True          # only send session cookie over HTTPS
    SESSION_COOKIE_HTTPONLY = True        # not readable by JS
    SESSION_COOKIE_SAMESITE = "Lax"       # mitigates CSRF; usually safe for standard logins

    # If you use Flask-Login "remember me" cookies:
    REMEMBER_COOKIE_SECURE = True
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"