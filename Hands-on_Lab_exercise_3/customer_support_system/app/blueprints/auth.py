"""
Authentication blueprint.

Endpoints:
  POST /api/auth/register
  POST /api/auth/login
  POST /api/auth/logout
  GET  /api/auth/me
"""
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    jwt_required,
    get_jwt_identity,
    get_jwt,
)
from marshmallow import ValidationError

from ..extensions import db
from ..models.user import User, UserRole
from ..schemas.user import UserRegisterSchema, UserLoginSchema, UserSchema
from ..utils.decorators import error_response, success_response

auth_bp = Blueprint("auth", __name__)

register_schema = UserRegisterSchema()
login_schema = UserLoginSchema()
user_schema = UserSchema()


@auth_bp.post("/register")
def register():
    """
    Register a new user.
    ---
    tags:
      - Authentication
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required: [name, email, password]
            properties:
              name:
                type: string
                minLength: 2
                maxLength: 100
              email:
                type: string
                format: email
              password:
                type: string
                minLength: 8
              role:
                type: string
                enum: [customer, agent, admin]
                default: customer
    responses:
      201:
        description: User registered successfully
      400:
        description: Validation error
      409:
        description: Email already registered
    """
    try:
        data = register_schema.load(request.get_json() or {})
    except ValidationError as err:
        return error_response("Validation failed", "VALIDATION_ERROR", 400, err.messages)

    if User.query.filter_by(email=data["email"]).first():
        return error_response("Email already registered", "CONFLICT", 409)

    user = User(
        name=data["name"],
        email=data["email"],
        role=UserRole(data.get("role", "customer")),
    )
    user.set_password(data["password"])
    db.session.add(user)
    db.session.commit()

    access_token = create_access_token(identity=str(user.id))
    refresh_token = create_refresh_token(identity=str(user.id))

    return jsonify({
        "status": "success",
        "message": "User registered successfully",
        "data": {
            "user": user_schema.dump(user),
            "access_token": access_token,
            "refresh_token": refresh_token,
        },
    }), 201


@auth_bp.post("/login")
def login():
    """
    Authenticate a user and return JWT tokens.
    ---
    tags:
      - Authentication
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required: [email, password]
            properties:
              email:
                type: string
                format: email
              password:
                type: string
    responses:
      200:
        description: Login successful
      400:
        description: Validation error
      401:
        description: Invalid credentials
    """
    try:
        data = login_schema.load(request.get_json() or {})
    except ValidationError as err:
        return error_response("Validation failed", "VALIDATION_ERROR", 400, err.messages)

    user = User.query.filter_by(email=data["email"]).first()
    if not user or not user.check_password(data["password"]):
        return error_response("Invalid email or password", "UNAUTHORIZED", 401)

    if not user.is_active:
        return error_response("Account is disabled", "UNAUTHORIZED", 401)

    access_token = create_access_token(identity=str(user.id))
    refresh_token = create_refresh_token(identity=str(user.id))

    return jsonify({
        "status": "success",
        "message": "Login successful",
        "data": {
            "user": user_schema.dump(user),
            "access_token": access_token,
            "refresh_token": refresh_token,
        },
    }), 200


@auth_bp.post("/logout")
@jwt_required()
def logout():
    """
    Revoke the current access token (add to blocklist).
    ---
    tags:
      - Authentication
    security:
      - Bearer: []
    responses:
      200:
        description: Logged out successfully
      401:
        description: Missing or invalid token
    """
    if not current_app.config.get("TESTING"):
        try:
            import redis as redis_lib
            jti = get_jwt()["jti"]
            exp = get_jwt()["exp"]
            import time
            ttl = max(int(exp - time.time()), 0)
            r = redis_lib.from_url(current_app.config["REDIS_URL"])
            r.setex(f"blocklist:{jti}", ttl, "1")
        except Exception:
            pass

    return jsonify({"status": "success", "message": "Logged out successfully"}), 200


@auth_bp.get("/me")
@jwt_required()
def me():
    """
    Return the authenticated user's profile.
    ---
    tags:
      - Authentication
    security:
      - Bearer: []
    responses:
      200:
        description: User profile
      401:
        description: Authentication required
    """
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return error_response("User not found", "NOT_FOUND", 404)

    return success_response(user_schema.dump(user))


@auth_bp.post("/refresh")
@jwt_required(refresh=True)
def refresh():
    """
    Issue a new access token using a valid refresh token.
    ---
    tags:
      - Authentication
    security:
      - Bearer: []
    responses:
      200:
        description: New access token issued
    """
    user_id = get_jwt_identity()
    access_token = create_access_token(identity=user_id)
    return jsonify({"status": "success", "data": {"access_token": access_token}}), 200
