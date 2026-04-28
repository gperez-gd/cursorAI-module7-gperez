import redis as redis_lib
from celery import Celery
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
jwt = JWTManager()
limiter = Limiter(key_func=get_remote_address, default_limits=["100 per minute"])
celery = Celery(__name__)

# Global Redis client – may be None if Redis is unavailable (graceful degradation)
redis_client = None


def init_redis(app):
    global redis_client
    url = app.config.get("REDIS_URL")
    if not url:
        return
    try:
        client = redis_lib.from_url(url, decode_responses=True)
        client.ping()
        redis_client = client
        app.logger.info("Redis connected: %s", url)
    except Exception as exc:
        app.logger.warning("Redis unavailable (%s) – caching/blacklist disabled", exc)
        redis_client = None


def get_redis():
    return redis_client
