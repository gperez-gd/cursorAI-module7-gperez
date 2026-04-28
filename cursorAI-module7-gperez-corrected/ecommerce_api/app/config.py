import os
from datetime import timedelta


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///ecommerce.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "jwt-secret-change-in-production")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=int(os.environ.get("JWT_TTL_HOURS", "1")))
    # Required so logout blacklisting runs (token_in_blocklist_loader is registered in create_app).
    JWT_BLOCKLIST_ENABLED = True

    REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

    # Flask-Limiter reads RATELIMIT_STORAGE_URI (not *_URL).
    RATELIMIT_STORAGE_URI = os.environ.get(
        "RATELIMIT_STORAGE_URI",
        os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
    )
    RATELIMIT_DEFAULT = "100 per minute"
    RATELIMIT_HEADERS_ENABLED = True

    # Product list cache TTL in seconds
    CACHE_TTL_PRODUCTS = 300

    DEBUG = False
    TESTING = False


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=60)
    RATELIMIT_ENABLED = False
    REDIS_URL = None  # fakeredis is patched in conftest


class ProductionConfig(Config):
    DEBUG = False


config_map = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
