from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    create_access_token,
    get_jwt,
    get_jwt_identity,
    jwt_required,
)

from ..extensions import db, limiter
from ..models import User
from ..services.cache import CacheService
from ..utils.errors import err
from ..utils.security import generate_csrf_token, sanitize
from ..utils.validators import LoginSchema, RegisterSchema, load_or_400

auth_bp = Blueprint("auth", __name__)


# ---------------------------------------------------------------------------
# POST /auth/register – AUTH-FR-001, AUTH-FR-002, AUTH-FR-003
# ---------------------------------------------------------------------------
@auth_bp.route("/register", methods=["POST"])
def register():
    """
    Register a new user.
    ---
    tags: [Auth]
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required: [email, password]
            properties:
              email: {type: string, format: email}
              password: {type: string, minLength: 8}
              firstName: {type: string}
              lastName: {type: string}
    responses:
      201:
        description: User created, JWT returned.
      400:
        description: Validation error.
      409:
        description: Email already registered.
    """
    data, errors = load_or_400(RegisterSchema(), request.get_json(silent=True) or {})
    if errors:
        return err("; ".join(errors), 400)

    email = sanitize(data["email"].lower().strip())
    if User.query.filter_by(email=email).first():
        return err("Email already registered.", 409)

    user = User(
        email=email,
        first_name=sanitize(data.get("firstName")),
        last_name=sanitize(data.get("lastName")),
        role="user",
    )
    user.set_password(data["password"])
    db.session.add(user)
    db.session.commit()

    token = create_access_token(
        identity=user.id, additional_claims={"role": user.role}
    )
    csrf_token = generate_csrf_token(user.id)
    return jsonify({"token": token, "csrfToken": csrf_token, "user": user.to_dict()}), 201


# ---------------------------------------------------------------------------
# POST /auth/login – AUTH-FR-005, AUTH-FR-006, AUTH-FR-009
# ---------------------------------------------------------------------------
@auth_bp.route("/login", methods=["POST"])
@limiter.limit("10 per minute", error_message="Too many login attempts.")
def login():
    """
    Authenticate and obtain a JWT.
    ---
    tags: [Auth]
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required: [email, password]
            properties:
              email: {type: string, format: email}
              password: {type: string}
    responses:
      200:
        description: JWT token returned.
      401:
        description: Invalid credentials.
      429:
        description: Rate limit exceeded.
    """
    data, errors = load_or_400(LoginSchema(), request.get_json(silent=True) or {})
    if errors:
        return err("Invalid credentials.", 401)

    user = User.query.filter_by(email=data["email"].lower().strip()).first()
    if not user or not user.check_password(data["password"]) or not user.is_active:
        return err("Invalid credentials.", 401)

    token = create_access_token(
        identity=user.id, additional_claims={"role": user.role}
    )
    csrf_token = generate_csrf_token(user.id)
    return jsonify({"token": token, "csrfToken": csrf_token}), 200


# ---------------------------------------------------------------------------
# POST /auth/logout – AUTH-FR-007
# ---------------------------------------------------------------------------
@auth_bp.route("/logout", methods=["POST"])
@jwt_required()
def logout():
    """
    Invalidate the current JWT (server-side blacklist via Redis).
    ---
    tags: [Auth]
    security:
      - BearerAuth: []
    responses:
      200:
        description: Logged out successfully.
      401:
        description: Unauthenticated.
    """
    jti = get_jwt().get("jti")
    # Use remaining lifetime; default 1 h if unavailable
    exp = get_jwt().get("exp", 0)
    import time
    remaining = max(int(exp - time.time()), 1)
    CacheService.blacklist_token(jti, ttl_seconds=remaining)
    return jsonify({"message": "Logged out successfully."}), 200


# ---------------------------------------------------------------------------
# POST /auth/refresh
# ---------------------------------------------------------------------------
@auth_bp.route("/refresh", methods=["POST"])
@jwt_required()
def refresh():
    """
    Exchange a valid token for a fresh one.
    ---
    tags: [Auth]
    security:
      - BearerAuth: []
    responses:
      200:
        description: New token returned.
    """
    user_id = get_jwt_identity()
    claims = get_jwt()
    new_token = create_access_token(
        identity=user_id, additional_claims={"role": claims.get("role")}
    )
    return jsonify({"token": new_token}), 200
