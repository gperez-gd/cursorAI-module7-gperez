from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt

from ..extensions import db
from ..models import User
from ..utils.errors import err
from ..utils.security import admin_required, sanitize
from ..utils.validators import UserUpdateSchema, AdminUserCreateSchema, load_or_400

users_bp = Blueprint("users", __name__)


def _paginate(query, page: int, limit: int):
    total = query.count()
    items = query.offset((page - 1) * limit).limit(limit).all()
    return items, total


# ---------------------------------------------------------------------------
# GET /users  – Admin: list all users
# ---------------------------------------------------------------------------
@users_bp.route("", methods=["GET"])
@jwt_required()
@admin_required
def list_users():
    """
    List all users (admin only, paginated).
    ---
    tags: [Users]
    security:
      - BearerAuth: []
    parameters:
      - {name: page, in: query, schema: {type: integer, default: 1}}
      - {name: limit, in: query, schema: {type: integer, default: 20}}
      - {name: search, in: query, schema: {type: string}}
    responses:
      200:
        description: Paginated list of users.
      403:
        description: Admin access required.
    """
    page = max(int(request.args.get("page", 1)), 1)
    limit = min(int(request.args.get("limit", 20)), 100)
    search = request.args.get("search", "").strip()

    query = User.query
    if search:
        like = f"%{search}%"
        query = query.filter(
            db.or_(User.email.ilike(like), User.first_name.ilike(like))
        )
    users, total = _paginate(query, page, limit)
    return jsonify({
        "users": [u.to_dict() for u in users],
        "total": total,
        "page": page,
        "limit": limit,
    }), 200


# ---------------------------------------------------------------------------
# POST /users  – Admin: create user
# ---------------------------------------------------------------------------
@users_bp.route("", methods=["POST"])
@jwt_required()
@admin_required
def create_user():
    """
    Create a new user (admin only).
    ---
    tags: [Users]
    security:
      - BearerAuth: []
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required: [email, password]
            properties:
              email: {type: string}
              password: {type: string}
              role: {type: string, enum: [user, admin]}
    responses:
      201:
        description: User created.
      400:
        description: Validation error.
      409:
        description: Email taken.
    """
    data, errors = load_or_400(AdminUserCreateSchema(), request.get_json(silent=True) or {})
    if errors:
        return err("; ".join(errors), 400)

    email = sanitize(data["email"].lower().strip())
    if User.query.filter_by(email=email).first():
        return err("Email already registered.", 409)

    user = User(email=email, role=data.get("role", "user"))
    user.set_password(data["password"])
    db.session.add(user)
    db.session.commit()
    return jsonify({"id": user.id, **user.to_dict()}), 201


# ---------------------------------------------------------------------------
# GET /users/me  – own profile
# ---------------------------------------------------------------------------
@users_bp.route("/me", methods=["GET"])
@jwt_required()
def get_me():
    """
    Get own profile.
    ---
    tags: [Users]
    security:
      - BearerAuth: []
    responses:
      200:
        description: User profile.
    """
    user = User.query.get_or_404(get_jwt_identity())
    return jsonify(user.to_dict(include_private=True)), 200


# ---------------------------------------------------------------------------
# PUT /users/me  – update own profile
# ---------------------------------------------------------------------------
@users_bp.route("/me", methods=["PUT"])
@jwt_required()
def update_me():
    """
    Update own profile (firstName, lastName, savedAddresses).
    ---
    tags: [Users]
    security:
      - BearerAuth: []
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            properties:
              firstName: {type: string, maxLength: 255}
              lastName: {type: string, maxLength: 255}
    responses:
      200:
        description: Updated profile.
      400:
        description: Validation error.
    """
    data, errors = load_or_400(UserUpdateSchema(), request.get_json(silent=True) or {})
    if errors:
        return err("; ".join(errors), 400)

    user = User.query.get_or_404(get_jwt_identity())
    if data.get("firstName") is not None:
        user.first_name = sanitize(data["firstName"])
    if data.get("lastName") is not None:
        user.last_name = sanitize(data["lastName"])
    if data.get("savedAddresses") is not None:
        user.saved_addresses = data["savedAddresses"]
    db.session.commit()
    return jsonify(user.to_dict(include_private=True)), 200


# ---------------------------------------------------------------------------
# GET /users/me/settings
# ---------------------------------------------------------------------------
@users_bp.route("/me/settings", methods=["GET"])
@jwt_required()
def get_settings():
    """Get own settings."""
    user = User.query.get_or_404(get_jwt_identity())
    return jsonify(user.settings or {}), 200


# ---------------------------------------------------------------------------
# PUT /users/me/settings
# ---------------------------------------------------------------------------
@users_bp.route("/me/settings", methods=["PUT"])
@jwt_required()
def update_settings():
    """Update own notification/privacy settings."""
    user = User.query.get_or_404(get_jwt_identity())
    payload = request.get_json(silent=True) or {}
    user.settings = {**(user.settings or {}), **payload}
    db.session.commit()
    return jsonify(user.settings), 200


# ---------------------------------------------------------------------------
# GET /users/:id  – Admin
# ---------------------------------------------------------------------------
@users_bp.route("/<user_id>", methods=["GET"])
@jwt_required()
@admin_required
def get_user(user_id):
    """Get any user by ID (admin only)."""
    user = User.query.get_or_404(user_id)
    return jsonify(user.to_dict(include_private=True)), 200


# ---------------------------------------------------------------------------
# PUT /users/:id  – Admin
# ---------------------------------------------------------------------------
@users_bp.route("/<user_id>", methods=["PUT"])
@jwt_required()
@admin_required
def update_user(user_id):
    """Update any user (admin only)."""
    data, errors = load_or_400(UserUpdateSchema(), request.get_json(silent=True) or {})
    if errors:
        return err("; ".join(errors), 400)
    user = User.query.get_or_404(user_id)
    if data.get("firstName") is not None:
        user.first_name = sanitize(data["firstName"])
    if data.get("lastName") is not None:
        user.last_name = sanitize(data["lastName"])
    db.session.commit()
    return jsonify(user.to_dict(include_private=True)), 200


# ---------------------------------------------------------------------------
# DELETE /users/:id  – Admin
# ---------------------------------------------------------------------------
@users_bp.route("/<user_id>", methods=["DELETE"])
@jwt_required()
@admin_required
def delete_user(user_id):
    """Soft-delete (deactivate) a user (admin only)."""
    user = User.query.get_or_404(user_id)
    user.is_active = False
    db.session.commit()
    return jsonify({"message": "User deactivated."}), 200


# ---------------------------------------------------------------------------
# GET /users/:id/orders  – Admin
# ---------------------------------------------------------------------------
@users_bp.route("/<user_id>/orders", methods=["GET"])
@jwt_required()
@admin_required
def get_user_orders(user_id):
    """List all orders for a specific user (admin only)."""
    from ..models import Order
    User.query.get_or_404(user_id)
    orders = Order.query.filter_by(user_id=user_id).all()
    return jsonify({"orders": [o.to_dict() for o in orders]}), 200
