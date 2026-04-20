"""
Users & Agents blueprint (FR-032, FR-033, FR-034).

GET    /api/users                  (admin)
GET    /api/users/:id
PUT    /api/users/:id
GET    /api/agents
GET    /api/agents/:id/tickets
PUT    /api/agents/:id/availability
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import ValidationError

from ..extensions import db, cache
from ..models.user import User, UserRole, AvailabilityStatus
from ..schemas.user import UserSchema, UserUpdateSchema
from ..schemas.ticket import TicketSchema
from ..utils.decorators import admin_required, error_response, success_response

users_bp = Blueprint("users", __name__)

user_schema = UserSchema()
ticket_schema = TicketSchema()


@users_bp.get("/users")
@jwt_required()
@admin_required
@cache.cached(timeout=600, key_prefix="users_list")
def list_users():
    """
    List all users (admin only).
    ---
    tags:
      - Users
    security:
      - Bearer: []
    responses:
      200:
        description: List of users
    """
    users = User.query.filter_by(is_active=True).order_by(User.created_at.desc()).all()
    return success_response(user_schema.dump(users, many=True))


@users_bp.get("/users/<int:user_id>")
@jwt_required()
def get_user(user_id):
    """
    Get user profile.
    ---
    tags:
      - Users
    security:
      - Bearer: []
    responses:
      200:
        description: User profile
      403:
        description: Access denied
    """
    requesting_user_id = int(get_jwt_identity())
    requester = User.query.get(requesting_user_id)

    if requester.role != UserRole.ADMIN and requesting_user_id != user_id:
        return error_response("Access denied", "FORBIDDEN", 403)

    user = User.query.get(user_id)
    if not user:
        return error_response("User not found", "NOT_FOUND", 404)

    return success_response(user_schema.dump(user))


@users_bp.put("/users/<int:user_id>")
@jwt_required()
def update_user(user_id):
    """
    Update user profile.
    ---
    tags:
      - Users
    security:
      - Bearer: []
    responses:
      200:
        description: User updated
    """
    requesting_user_id = int(get_jwt_identity())
    requester = User.query.get(requesting_user_id)

    if requester.role != UserRole.ADMIN and requesting_user_id != user_id:
        return error_response("Access denied", "FORBIDDEN", 403)

    user = User.query.get(user_id)
    if not user:
        return error_response("User not found", "NOT_FOUND", 404)

    try:
        data = UserUpdateSchema().load(request.get_json() or {})
    except ValidationError as err:
        return error_response("Validation failed", "VALIDATION_ERROR", 400, err.messages)

    if "name" in data:
        user.name = data["name"]
    if "availability_status" in data:
        user.availability_status = AvailabilityStatus(data["availability_status"])
    if "expertise_areas" in data:
        user.expertise_areas = data["expertise_areas"]

    db.session.commit()
    cache.delete("users_list")
    cache.delete("agents_list")

    return success_response(user_schema.dump(user))


@users_bp.get("/agents")
@jwt_required()
@cache.cached(timeout=600, key_prefix="agents_list")
def list_agents():
    """
    List all active agents.
    ---
    tags:
      - Agents
    security:
      - Bearer: []
    responses:
      200:
        description: List of agents
    """
    agents = User.query.filter_by(role=UserRole.AGENT, is_active=True).all()
    return success_response(user_schema.dump(agents, many=True))


@users_bp.get("/agents/<int:agent_id>/tickets")
@jwt_required()
def get_agent_tickets(agent_id):
    """
    Get tickets assigned to a specific agent.
    ---
    tags:
      - Agents
    security:
      - Bearer: []
    responses:
      200:
        description: Agent's tickets
    """
    requesting_user_id = int(get_jwt_identity())
    requester = User.query.get(requesting_user_id)

    if requester.role not in (UserRole.ADMIN, UserRole.AGENT):
        return error_response("Access denied", "FORBIDDEN", 403)
    if requester.role == UserRole.AGENT and requesting_user_id != agent_id:
        return error_response("Access denied", "FORBIDDEN", 403)

    agent = User.query.get(agent_id)
    if not agent or agent.role != UserRole.AGENT:
        return error_response("Agent not found", "NOT_FOUND", 404)

    tickets = agent.assigned_tickets.order_by(db.desc("created_at")).all()
    return success_response(ticket_schema.dump(tickets, many=True))


@users_bp.put("/agents/<int:agent_id>/availability")
@jwt_required()
def update_availability(agent_id):
    """
    Update agent availability status (FR-034).
    ---
    tags:
      - Agents
    security:
      - Bearer: []
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required: [availability_status]
            properties:
              availability_status:
                type: string
                enum: [available, busy, offline]
    responses:
      200:
        description: Availability updated
    """
    requesting_user_id = int(get_jwt_identity())
    requester = User.query.get(requesting_user_id)

    if requester.role not in (UserRole.ADMIN, UserRole.AGENT):
        return error_response("Access denied", "FORBIDDEN", 403)
    if requester.role == UserRole.AGENT and requesting_user_id != agent_id:
        return error_response("Access denied", "FORBIDDEN", 403)

    agent = User.query.get(agent_id)
    if not agent or agent.role != UserRole.AGENT:
        return error_response("Agent not found", "NOT_FOUND", 404)

    body = request.get_json() or {}
    status_val = body.get("availability_status")
    try:
        agent.availability_status = AvailabilityStatus(status_val)
    except ValueError:
        return error_response(
            f"Invalid status. Must be one of: {[s.value for s in AvailabilityStatus]}",
            "VALIDATION_ERROR",
            400,
        )

    db.session.commit()
    cache.delete("agents_list")
    return success_response(user_schema.dump(agent), "Availability updated")
