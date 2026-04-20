"""
Tickets blueprint — full CRUD, status, priority, comments, assignment, history.

FR-001 through FR-024 implemented here.
"""
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import ValidationError
from sqlalchemy import or_

from ..extensions import db, cache
from ..models.user import User, UserRole
from ..models.ticket import Ticket, TicketStatus, TicketPriority, TicketCategory
from ..models.comment import Comment
from ..models.assignment import Assignment
from ..schemas.ticket import (
    TicketSchema,
    TicketCreateSchema,
    TicketUpdateSchema,
    TicketStatusUpdateSchema,
    TicketPriorityUpdateSchema,
    TicketFilterSchema,
)
from ..schemas.comment import CommentSchema, CommentCreateSchema
from ..schemas.assignment import AssignmentSchema, AssignmentCreateSchema
from ..utils.decorators import error_response, success_response, agent_or_admin_required, admin_required
from ..utils.helpers import generate_ticket_number, auto_assign_agent, paginate_query, format_pagination_meta, sanitize_html

tickets_bp = Blueprint("tickets", __name__)

ticket_schema = TicketSchema()
comment_schema = CommentSchema()
assignment_schema = AssignmentSchema()


# ---------------------------------------------------------------------------
# Helper: get ticket and verify ownership / access (FR-033)
# ---------------------------------------------------------------------------

def _get_ticket_or_404(ticket_id):
    ticket = Ticket.query.get(ticket_id)
    if not ticket:
        return None, error_response("Ticket not found", "NOT_FOUND", 404)
    return ticket, None


def _can_view_ticket(user: User, ticket: Ticket) -> bool:
    if user.role == UserRole.ADMIN:
        return True
    if user.role == UserRole.AGENT:
        return ticket.assigned_to_id == user.id or ticket.status == TicketStatus.OPEN
    # Customer can only see own tickets
    return ticket.created_by_id == user.id or ticket.customer_email == user.email


# ---------------------------------------------------------------------------
# GET /api/tickets
# ---------------------------------------------------------------------------

@tickets_bp.get("")
@jwt_required()
def list_tickets():
    """
    List and filter tickets (FR-025, FR-026, FR-027).
    ---
    tags:
      - Tickets
    security:
      - Bearer: []
    parameters:
      - in: query
        name: status
        schema:
          type: string
      - in: query
        name: priority
        schema:
          type: string
      - in: query
        name: page
        schema:
          type: integer
          default: 1
      - in: query
        name: per_page
        schema:
          type: integer
          default: 20
    responses:
      200:
        description: List of tickets
    """
    try:
        filters = TicketFilterSchema().load(request.args)
    except ValidationError as err:
        return error_response("Validation failed", "VALIDATION_ERROR", 400, err.messages)

    user_id = get_jwt_identity()
    user = User.query.get(user_id)

    query = Ticket.query

    # RBAC filtering (FR-033)
    if user.role == UserRole.CUSTOMER:
        query = query.filter(
            or_(Ticket.created_by_id == user.id, Ticket.customer_email == user.email)
        )
    elif user.role == UserRole.AGENT:
        query = query.filter(
            or_(Ticket.assigned_to_id == user.id, Ticket.status == TicketStatus.OPEN)
        )

    if filters.get("status"):
        query = query.filter(Ticket.status == TicketStatus(filters["status"]))
    if filters.get("priority"):
        query = query.filter(Ticket.priority == TicketPriority(filters["priority"]))
    if filters.get("category"):
        query = query.filter(Ticket.category == TicketCategory(filters["category"]))
    if filters.get("assigned_to_id"):
        query = query.filter(Ticket.assigned_to_id == filters["assigned_to_id"])
    if filters.get("customer_email"):
        query = query.filter(Ticket.customer_email == filters["customer_email"])
    if filters.get("search"):
        term = f"%{filters['search']}%"
        query = query.filter(
            or_(Ticket.subject.ilike(term), Ticket.description.ilike(term), Ticket.ticket_number.ilike(term))
        )

    # Sorting
    sort_col = getattr(Ticket, filters.get("sort_by", "created_at"), Ticket.created_at)
    if filters.get("order", "desc") == "asc":
        query = query.order_by(sort_col.asc())
    else:
        query = query.order_by(sort_col.desc())

    pagination = paginate_query(query, filters["page"], filters["per_page"])
    return jsonify({
        "status": "success",
        "data": ticket_schema.dump(pagination.items, many=True),
        "meta": format_pagination_meta(pagination),
    }), 200


# ---------------------------------------------------------------------------
# POST /api/tickets
# ---------------------------------------------------------------------------

@tickets_bp.post("")
@jwt_required()
def create_ticket():
    """
    Create a new support ticket (FR-001, FR-002, FR-004).
    ---
    tags:
      - Tickets
    security:
      - Bearer: []
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required: [subject, description, category, customer_email]
            properties:
              subject:
                type: string
                minLength: 5
                maxLength: 200
              description:
                type: string
                minLength: 20
              priority:
                type: string
                enum: [low, medium, high, urgent]
              category:
                type: string
                enum: [technical, billing, general, feature_request]
              customer_email:
                type: string
                format: email
    responses:
      201:
        description: Ticket created
      400:
        description: Validation error
    """
    try:
        data = TicketCreateSchema().load(request.get_json() or {})
    except ValidationError as err:
        return error_response("Validation failed", "VALIDATION_ERROR", 400, err.messages)

    user_id = get_jwt_identity()
    user = User.query.get(user_id)

    # Generate unique ticket number (FR-002)
    today_prefix = datetime.now(timezone.utc).strftime("%Y%m%d")
    count = Ticket.query.filter(Ticket.ticket_number.like(f"TICK-{today_prefix}-%")).count()
    ticket_number = generate_ticket_number(count + 1)

    ticket = Ticket(
        ticket_number=ticket_number,
        subject=sanitize_html(data["subject"]),
        description=sanitize_html(data["description"]),
        priority=TicketPriority(data["priority"]),
        category=TicketCategory(data["category"]),
        customer_email=data["customer_email"],
        created_by_id=user.id,
        status=TicketStatus.OPEN,  # FR-004
    )
    ticket.set_sla_deadlines()  # FR-020
    db.session.add(ticket)
    db.session.commit()

    # FR-006: Auto-assign if eligible agents exist
    agent = auto_assign_agent(data["category"])
    if agent:
        _do_assign(ticket, agent, user)

    # FR-003: Async email confirmation
    try:
        from ..tasks.email_tasks import send_ticket_created_email
        send_ticket_created_email.delay(ticket.id)
    except Exception:
        pass

    return jsonify({
        "status": "success",
        "message": "Ticket created successfully",
        "data": ticket_schema.dump(ticket),
    }), 201


# ---------------------------------------------------------------------------
# GET /api/tickets/<id>
# ---------------------------------------------------------------------------

@tickets_bp.get("/<int:ticket_id>")
@jwt_required()
@cache.cached(timeout=300, key_prefix=lambda: f"ticket:{request.view_args['ticket_id']}")
def get_ticket(ticket_id):
    """
    Get ticket details (cached 5 minutes).
    ---
    tags:
      - Tickets
    security:
      - Bearer: []
    parameters:
      - in: path
        name: ticket_id
        required: true
        schema:
          type: integer
    responses:
      200:
        description: Ticket details
      403:
        description: Access denied
      404:
        description: Ticket not found
    """
    ticket, err = _get_ticket_or_404(ticket_id)
    if err:
        return err

    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not _can_view_ticket(user, ticket):
        return error_response("Access denied", "FORBIDDEN", 403)

    return success_response(ticket_schema.dump(ticket))


# ---------------------------------------------------------------------------
# PUT /api/tickets/<id>
# ---------------------------------------------------------------------------

@tickets_bp.put("/<int:ticket_id>")
@jwt_required()
def update_ticket(ticket_id):
    """
    Update ticket subject, description, or category.
    ---
    tags:
      - Tickets
    security:
      - Bearer: []
    responses:
      200:
        description: Ticket updated
    """
    ticket, err = _get_ticket_or_404(ticket_id)
    if err:
        return err

    user_id = get_jwt_identity()
    user = User.query.get(user_id)

    if user.role == UserRole.CUSTOMER and ticket.created_by_id != user.id:
        return error_response("Access denied", "FORBIDDEN", 403)

    try:
        data = TicketUpdateSchema().load(request.get_json() or {})
    except ValidationError as err:
        return error_response("Validation failed", "VALIDATION_ERROR", 400, err.messages)

    for field, value in data.items():
        if field == "subject":
            ticket.subject = sanitize_html(value)
        elif field == "description":
            ticket.description = sanitize_html(value)
        elif field == "category":
            ticket.category = TicketCategory(value)

    db.session.commit()
    cache.delete(f"ticket:{ticket_id}")

    return success_response(ticket_schema.dump(ticket))


# ---------------------------------------------------------------------------
# DELETE /api/tickets/<id>  (admin only)
# ---------------------------------------------------------------------------

@tickets_bp.delete("/<int:ticket_id>")
@jwt_required()
@admin_required
def delete_ticket(ticket_id):
    """
    Delete a ticket (admin only).
    ---
    tags:
      - Tickets
    security:
      - Bearer: []
    responses:
      200:
        description: Ticket deleted
      403:
        description: Admin only
    """
    ticket, err = _get_ticket_or_404(ticket_id)
    if err:
        return err

    db.session.delete(ticket)
    db.session.commit()
    cache.delete(f"ticket:{ticket_id}")

    return jsonify({"status": "success", "message": "Ticket deleted"}), 200


# ---------------------------------------------------------------------------
# PUT /api/tickets/<id>/status  (FR-011, FR-012)
# ---------------------------------------------------------------------------

@tickets_bp.put("/<int:ticket_id>/status")
@jwt_required()
@agent_or_admin_required
def update_status(ticket_id):
    """
    Update ticket status with transition validation (FR-011, FR-012).
    ---
    tags:
      - Tickets
    security:
      - Bearer: []
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required: [status]
            properties:
              status:
                type: string
                enum: [open, assigned, in_progress, waiting, resolved, closed, reopened]
              comment:
                type: string
    responses:
      200:
        description: Status updated
      400:
        description: Invalid transition
    """
    ticket, err = _get_ticket_or_404(ticket_id)
    if err:
        return err

    try:
        data = TicketStatusUpdateSchema().load(request.get_json() or {})
    except ValidationError as err:
        return error_response("Validation failed", "VALIDATION_ERROR", 400, err.messages)

    new_status = TicketStatus(data["status"])
    if not ticket.can_transition_to(new_status):
        return error_response(
            f"Cannot transition from '{ticket.status.value}' to '{new_status.value}'",
            "VALIDATION_ERROR",
            400,
        )

    old_status = ticket.status
    ticket.status = new_status
    now = datetime.now(timezone.utc)

    if new_status == TicketStatus.RESOLVED:
        ticket.resolved_at = now
        if ticket.sla_resolution_due:
            due = ticket.sla_resolution_due
            if due.tzinfo is None:
                due = due.replace(tzinfo=timezone.utc)
            ticket.sla_resolution_met = now <= due
    elif new_status == TicketStatus.CLOSED:
        ticket.closed_at = now
    elif new_status == TicketStatus.REOPENED:
        ticket.resolved_at = None
        ticket.closed_at = None

    db.session.commit()
    cache.delete(f"ticket:{ticket_id}")

    # FR-014: Notify customer and agent
    try:
        from ..tasks.email_tasks import send_status_change_email
        send_status_change_email.delay(ticket.id, old_status.value, new_status.value)
    except Exception:
        pass

    return success_response(ticket_schema.dump(ticket), "Status updated successfully")


# ---------------------------------------------------------------------------
# PUT /api/tickets/<id>/priority  (FR-023, FR-024)
# ---------------------------------------------------------------------------

@tickets_bp.put("/<int:ticket_id>/priority")
@jwt_required()
@agent_or_admin_required
def update_priority(ticket_id):
    """
    Update ticket priority (agents and admins only, reason required) (FR-023, FR-024).
    ---
    tags:
      - Tickets
    security:
      - Bearer: []
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required: [priority, reason]
            properties:
              priority:
                type: string
                enum: [low, medium, high, urgent]
              reason:
                type: string
    responses:
      200:
        description: Priority updated
    """
    ticket, err = _get_ticket_or_404(ticket_id)
    if err:
        return err

    try:
        data = TicketPriorityUpdateSchema().load(request.get_json() or {})
    except ValidationError as err:
        return error_response("Validation failed", "VALIDATION_ERROR", 400, err.messages)

    user_id = get_jwt_identity()
    user = User.query.get(user_id)

    ticket.priority = TicketPriority(data["priority"])
    ticket.set_sla_deadlines()

    # Add an internal comment with the reason (FR-024)
    reason_comment = Comment(
        ticket_id=ticket.id,
        user_id=user.id,
        content=f"Priority changed to {data['priority']}. Reason: {data['reason']}",
        is_internal=True,
    )
    db.session.add(reason_comment)
    db.session.commit()
    cache.delete(f"ticket:{ticket_id}")

    return success_response(ticket_schema.dump(ticket), "Priority updated")


# ---------------------------------------------------------------------------
# POST /api/tickets/<id>/assign  (FR-005, FR-006)
# ---------------------------------------------------------------------------

@tickets_bp.post("/<int:ticket_id>/assign")
@jwt_required()
@admin_required
def assign_ticket(ticket_id):
    """
    Assign or reassign ticket to an agent (admin only) (FR-005, FR-009).
    ---
    tags:
      - Tickets
    security:
      - Bearer: []
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            properties:
              agent_id:
                type: integer
              auto_assign:
                type: boolean
                default: false
              notes:
                type: string
    responses:
      200:
        description: Ticket assigned
    """
    ticket, err = _get_ticket_or_404(ticket_id)
    if err:
        return err

    try:
        data = AssignmentCreateSchema().load(request.get_json() or {})
    except ValidationError as err:
        return error_response("Validation failed", "VALIDATION_ERROR", 400, err.messages)

    user_id = get_jwt_identity()
    admin_user = User.query.get(user_id)

    if data.get("auto_assign"):
        agent = auto_assign_agent(ticket.category.value if ticket.category else None)
        if not agent:
            return error_response("No available agents found for auto-assignment", "NOT_FOUND", 404)
    else:
        agent = User.query.get(data["agent_id"])
        if not agent or agent.role != UserRole.AGENT:
            return error_response("Agent not found", "NOT_FOUND", 404)

    _do_assign(ticket, agent, admin_user, notes=data.get("notes"))
    cache.delete(f"ticket:{ticket_id}")

    return success_response(ticket_schema.dump(ticket), "Ticket assigned successfully")


def _do_assign(ticket: Ticket, agent: User, assigned_by: User, notes: str = None):
    """Shared assignment logic for manual and auto-assign (FR-005, FR-006, FR-008, FR-010)."""
    ticket.assigned_to_id = agent.id
    if ticket.status == TicketStatus.OPEN:
        ticket.status = TicketStatus.ASSIGNED  # FR-008

    record = Assignment(
        ticket_id=ticket.id,
        assigned_to_id=agent.id,
        assigned_by_id=assigned_by.id,
        notes=notes,
    )
    db.session.add(record)
    db.session.commit()

    # FR-007: Notify agent
    try:
        from ..tasks.email_tasks import send_assignment_email
        send_assignment_email.delay(ticket.id, agent.id)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# GET /api/tickets/<id>/history  (FR-010, FR-013)
# ---------------------------------------------------------------------------

@tickets_bp.get("/<int:ticket_id>/history")
@jwt_required()
def get_history(ticket_id):
    """
    Retrieve assignment history for a ticket (FR-010, FR-013).
    ---
    tags:
      - Tickets
    security:
      - Bearer: []
    responses:
      200:
        description: Assignment history
    """
    ticket, err = _get_ticket_or_404(ticket_id)
    if err:
        return err

    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not _can_view_ticket(user, ticket):
        return error_response("Access denied", "FORBIDDEN", 403)

    assignments = ticket.assignments.order_by(Assignment.assigned_at.asc()).all()
    return success_response(assignment_schema.dump(assignments, many=True))


# ---------------------------------------------------------------------------
# POST /api/tickets/<id>/comments  (FR-015, FR-016)
# ---------------------------------------------------------------------------

@tickets_bp.post("/<int:ticket_id>/comments")
@jwt_required()
def add_comment(ticket_id):
    """
    Add a comment to a ticket (FR-015, FR-016).
    ---
    tags:
      - Comments
    security:
      - Bearer: []
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required: [content]
            properties:
              content:
                type: string
              is_internal:
                type: boolean
                default: false
    responses:
      201:
        description: Comment added
    """
    ticket, err = _get_ticket_or_404(ticket_id)
    if err:
        return err

    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not _can_view_ticket(user, ticket):
        return error_response("Access denied", "FORBIDDEN", 403)

    try:
        data = CommentCreateSchema().load(request.get_json() or {})
    except ValidationError as err:
        return error_response("Validation failed", "VALIDATION_ERROR", 400, err.messages)

    # Customers cannot post internal comments (FR-016)
    if data.get("is_internal") and user.role == UserRole.CUSTOMER:
        return error_response("Customers cannot post internal comments", "FORBIDDEN", 403)

    comment = Comment(
        ticket_id=ticket.id,
        user_id=user.id,
        content=sanitize_html(data["content"]),
        is_internal=data.get("is_internal", False),
    )
    db.session.add(comment)

    # Track first public response for SLA (FR-020)
    if not comment.is_internal and not ticket.first_response_at and user.role != UserRole.CUSTOMER:
        ticket.first_response_at = datetime.now(timezone.utc)
        if ticket.sla_response_due:
            due = ticket.sla_response_due
            if due.tzinfo is None:
                due = due.replace(tzinfo=timezone.utc)
            ticket.sla_response_met = ticket.first_response_at <= due

    db.session.commit()
    cache.delete(f"ticket:{ticket_id}")

    # FR-018: Notify relevant parties
    try:
        from ..tasks.email_tasks import send_comment_notification
        send_comment_notification.delay(comment.id)
    except Exception:
        pass

    return jsonify({
        "status": "success",
        "message": "Comment added",
        "data": comment_schema.dump(comment),
    }), 201


# ---------------------------------------------------------------------------
# GET /api/tickets/<id>/comments  (FR-019)
# ---------------------------------------------------------------------------

@tickets_bp.get("/<int:ticket_id>/comments")
@jwt_required()
def get_comments(ticket_id):
    """
    Get all comments for a ticket (FR-019).
    ---
    tags:
      - Comments
    security:
      - Bearer: []
    responses:
      200:
        description: List of comments
    """
    ticket, err = _get_ticket_or_404(ticket_id)
    if err:
        return err

    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not _can_view_ticket(user, ticket):
        return error_response("Access denied", "FORBIDDEN", 403)

    query = ticket.comments.order_by(Comment.created_at.asc())

    # Customers cannot see internal comments (FR-016)
    if user.role == UserRole.CUSTOMER:
        query = query.filter_by(is_internal=False)

    return success_response(comment_schema.dump(query.all(), many=True))
