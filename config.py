import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
DEFAULT_DB_PATH = INSTANCE_DIR / "site.db"
# Uploads (used for provider verification docs, messaging attachments later, etc.)
UPLOAD_DIR = INSTANCE_DIR / "uploads"
MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", 10 * 1024 * 1024))  # 10 MB default
ALLOWED_UPLOAD_EXTENSIONS = {"pdf", "png", "jpg", "jpeg"}


class BaseConfig:
    # Security (dev fallback is OK; production will enforce separately)
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me")

    # Database
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{DEFAULT_DB_PATH}",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

        # Uploads
    UPLOAD_DIR = UPLOAD_DIR
    MAX_CONTENT_LENGTH = MAX_CONTENT_LENGTH
    ALLOWED_UPLOAD_EXTENSIONS = ALLOWED_UPLOAD_EXTENSIONS


class DevelopmentConfig(BaseConfig):
    DEBUG = True


class ProductionConfig(BaseConfig):
    DEBUG = False
