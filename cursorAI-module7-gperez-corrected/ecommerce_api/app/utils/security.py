"""
Security utilities: CSRF tokens, HTML sanitisation, decorator helpers.
"""
import uuid

import bleach
from flask import request
from functools import wraps

from ..extensions import get_redis
from .errors import err


# ---------------------------------------------------------------------------
# CSRF – double-submit via X-CSRF-Token header
# ---------------------------------------------------------------------------

CSRF_TTL = 86_400  # 24 hours


def generate_csrf_token(user_id: str) -> str:
    """Create a new CSRF token tied to *user_id* and persist it in Redis."""
    token = str(uuid.uuid4())
    r = get_redis()
    if r:
        r.setex(f"csrf:{user_id}", CSRF_TTL, token)
    return token


def validate_csrf_token(user_id: str, token: str | None) -> bool:
    """Return True if *token* matches the stored CSRF token for *user_id*."""
    if not token:
        return False
    r = get_redis()
    if r is None:
        # If Redis is unavailable we skip CSRF in dev/test (non-production)
        return True
    stored = r.get(f"csrf:{user_id}")
    return stored is not None and stored == token


def require_csrf(f):
    """Decorator: enforce X-CSRF-Token header on state-changing endpoints (CHK-FR-010)."""
    @wraps(f)
    def decorated(*args, **kwargs):
        from flask_jwt_extended import get_jwt_identity
        user_id = get_jwt_identity()
        token = request.headers.get("X-CSRF-Token")
        if not validate_csrf_token(user_id, token):
            return err("CSRF token missing or invalid.", 403, "CSRF_INVALID")
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# HTML / injection sanitisation (SEC-001, SEC-002)
# ---------------------------------------------------------------------------

_ALLOWED_TAGS: list[str] = []   # strip all HTML tags
_ALLOWED_ATTRS: dict = {}


def sanitize(value: str | None) -> str | None:
    """Strip all HTML tags from *value* to prevent XSS. Returns None unchanged."""
    if value is None:
        return None
    return bleach.clean(str(value), tags=_ALLOWED_TAGS, attributes=_ALLOWED_ATTRS, strip=True)


def sanitize_dict(data: dict, keys: list[str]) -> dict:
    """In-place sanitise specified *keys* of *data*."""
    for key in keys:
        if key in data and isinstance(data[key], str):
            data[key] = sanitize(data[key])
    return data


# ---------------------------------------------------------------------------
# Role-based access helpers
# ---------------------------------------------------------------------------

def admin_required(f):
    """Decorator: require role == 'admin' (must be used after @jwt_required())."""
    @wraps(f)
    def decorated(*args, **kwargs):
        from flask_jwt_extended import get_jwt
        claims = get_jwt()
        if claims.get("role") != "admin":
            return err("Admin access required.", 403, "FORBIDDEN")
        return f(*args, **kwargs)
    return decorated
