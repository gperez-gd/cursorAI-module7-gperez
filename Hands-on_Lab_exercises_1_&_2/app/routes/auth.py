from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token
from marshmallow import ValidationError
from sqlalchemy.exc import IntegrityError

from app import bcrypt, db
from app.models.user import User
from app.schemas.user import RegisterSchema, UserSchema, LoginSchema

auth_bp = Blueprint("auth", __name__)

_register_schema = RegisterSchema()
_login_schema = LoginSchema()
_user_schema = UserSchema()


@auth_bp.route("/register", methods=["POST"])
def register():
    """
    Register a new user.
    ---
    tags:
      - Authentication
    summary: Register a new user account
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - username
            - email
            - password
          properties:
            username:
              type: string
              minLength: 3
              maxLength: 80
              example: johndoe
            email:
              type: string
              format: email
              example: john@example.com
            password:
              type: string
              minLength: 6
              example: secret123
    responses:
      201:
        description: User registered successfully
        schema:
          type: object
          properties:
            message:
              type: string
            user:
              type: object
      400:
        description: Validation error
      409:
        description: Username or email already exists
    """
    json_data = request.get_json(silent=True)
    if not json_data:
        return jsonify({"error": "No input data provided"}), 400

    try:
        data = _register_schema.load(json_data)
    except ValidationError as err:
        return jsonify({"error": "Validation failed", "details": err.messages}), 400

    if User.query.filter_by(username=data["username"]).first():
        return jsonify({"error": "Conflict", "details": "Username already taken."}), 409
    if User.query.filter_by(email=data["email"]).first():
        return jsonify({"error": "Conflict", "details": "Email already registered."}), 409

    password_hash = bcrypt.generate_password_hash(data["password"]).decode("utf-8")
    user = User(username=data["username"], email=data["email"], password_hash=password_hash)

    try:
        db.session.add(user)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Conflict", "details": "Username or email already exists."}), 409

    return jsonify({"message": "User registered successfully.", "user": _user_schema.dump(user)}), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    """
    Authenticate a user and return a JWT.
    ---
    tags:
      - Authentication
    summary: Login with email and password
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - email
            - password
          properties:
            email:
              type: string
              format: email
              example: john@example.com
            password:
              type: string
              example: secret123
    responses:
      200:
        description: Login successful, returns JWT access token
        schema:
          type: object
          properties:
            access_token:
              type: string
      400:
        description: Validation error
      401:
        description: Invalid credentials
    """
    json_data = request.get_json(silent=True)
    if not json_data:
        return jsonify({"error": "No input data provided"}), 400

    try:
        data = _login_schema.load(json_data)
    except ValidationError as err:
        return jsonify({"error": "Validation failed", "details": err.messages}), 400

    user = User.query.filter_by(email=data["email"]).first()
    if not user or not bcrypt.check_password_hash(user.password_hash, data["password"]):
        return jsonify({"error": "Invalid email or password."}), 401

    access_token = create_access_token(identity=str(user.id))
    return jsonify({"access_token": access_token, "user": _user_schema.dump(user)}), 200
