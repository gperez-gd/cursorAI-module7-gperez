from functools import wraps
from flask import jsonify
from flask_jwt_extended import get_jwt_identity
from ..models.user import User, UserRole


def _current_user():
    user_id = get_jwt_identity()
    return User.query.get(user_id)


def role_required(*roles):
    """Decorator that restricts access to users with specific roles (FR-032, FR-033)."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = _current_user()
            if user is None or not user.is_active:
                return jsonify({"status": "error", "message": "User not found or inactive", "code": "UNAUTHORIZED"}), 401
            if user.role not in roles:
                return jsonify({
                    "status": "error",
                    "message": "You do not have permission to perform this action.",
                    "code": "FORBIDDEN",
                }), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def agent_or_admin_required(fn):
    """Shorthand for agent + admin role check."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = _current_user()
        if user is None or not user.is_active:
            return jsonify({"status": "error", "message": "Unauthorized", "code": "UNAUTHORIZED"}), 401
        if user.role not in (UserRole.AGENT, UserRole.ADMIN):
            return jsonify({"status": "error", "message": "Agents and admins only.", "code": "FORBIDDEN"}), 403
        return fn(*args, **kwargs)
    return wrapper


def admin_required(fn):
    """Shorthand for admin-only check."""
    return role_required(UserRole.ADMIN)(fn)


def error_response(message, code, http_status, errors=None):
    """Standardised error response (Section 8 of PRD)."""
    body = {"status": "error", "message": message, "code": code}
    if errors:
        body["errors"] = errors
    return jsonify(body), http_status


def success_response(data, message="Success", http_status=200):
    return jsonify({"status": "success", "message": message, "data": data}), http_status
