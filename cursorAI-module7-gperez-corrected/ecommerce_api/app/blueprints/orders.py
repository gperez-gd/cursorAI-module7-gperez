from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt

from ..extensions import db
from ..models import Order
from sqlalchemy import select
from ..models.order import VALID_STATUSES
from ..utils.errors import err
from ..utils.security import admin_required
from ..utils.validators import OrderStatusUpdateSchema, load_or_400

orders_bp = Blueprint("orders", __name__)


# ---------------------------------------------------------------------------
# GET /orders  – own orders, paginated (ORD-FR-001)
# ---------------------------------------------------------------------------
@orders_bp.route("", methods=["GET"])
@jwt_required()
def list_orders():
    """
    List the authenticated user's orders (paginated).
    ---
    tags: [Orders]
    security:
      - BearerAuth: []
    parameters:
      - {name: page, in: query, schema: {type: integer, default: 1}}
      - {name: limit, in: query, schema: {type: integer, default: 10}}
    responses:
      200:
        description: List of orders.
    """
    user_id = get_jwt_identity()
    claims = get_jwt()
    page = max(int(request.args.get("page", 1)), 1)
    limit = min(int(request.args.get("limit", 10)), 100)

    query = Order.query.filter_by(user_id=user_id).order_by(Order.created_at.desc())
    total = query.count()
    orders = query.offset((page - 1) * limit).limit(limit).all()

    return jsonify({
        "orders": [o.to_dict() for o in orders],
        "total": total,
        "page": page,
        "limit": limit,
    }), 200


# ---------------------------------------------------------------------------
# GET /orders/:id  – own order (ORD-FR-002, ORD-FR-003)
# ---------------------------------------------------------------------------
@orders_bp.route("/<order_id>", methods=["GET"])
@jwt_required()
def get_order(order_id):
    """
    Get a single order by ID (user can only see own orders).
    ---
    tags: [Orders]
    security:
      - BearerAuth: []
    parameters:
      - {name: order_id, in: path, required: true, schema: {type: string}}
    responses:
      200:
        description: Order object.
      403:
        description: Access denied.
      404:
        description: Order not found.
    """
    user_id = get_jwt_identity()
    claims = get_jwt()
    order = db.session.get(Order, order_id)

    if not order:
        return err("Order not found.", 404)

    # ORD-FR-003 / SEC-006: non-admin users cannot access others' orders
    if claims.get("role") != "admin" and order.user_id != user_id:
        return err("Access denied.", 403)

    return jsonify(order.to_dict()), 200


# ---------------------------------------------------------------------------
# PUT /orders/:id  – Admin: update status (ORD-FR-005)
# ---------------------------------------------------------------------------
@orders_bp.route("/<order_id>", methods=["PUT"])
@jwt_required()
@admin_required
def update_order(order_id):
    """
    Update order status (admin only).
    ---
    tags: [Orders]
    security:
      - BearerAuth: []
    parameters:
      - {name: order_id, in: path, required: true, schema: {type: string}}
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
                enum: [Processing, Shipped, Delivered, Cancelled]
    responses:
      200:
        description: Updated order.
      400:
        description: Invalid status.
      404:
        description: Order not found.
    """
    data, errors = load_or_400(OrderStatusUpdateSchema(), request.get_json(silent=True) or {})
    if errors:
        return err("; ".join(errors), 400)

    order = Order.query.get_or_404(order_id)
    new_status = data["status"]
    order.status = new_status
    db.session.commit()

    # EMAIL-FR-003: when status moves to "Shipped", a notification should fire.
    # In production: dispatch to a Celery/SQS task. Here we log it.
    if new_status == "Shipped":
        import logging
        logging.getLogger(__name__).info(
            "Shipping notification queued for order %s", order_id
        )

    return jsonify(order.to_dict()), 200


# ---------------------------------------------------------------------------
# DELETE /orders/:id  – Admin: cancel order (ORD-FR-006)
# ---------------------------------------------------------------------------
@orders_bp.route("/<order_id>", methods=["DELETE"])
@jwt_required()
@admin_required
def cancel_order(order_id):
    """
    Cancel an order (admin only).
    ---
    tags: [Orders]
    security:
      - BearerAuth: []
    parameters:
      - {name: order_id, in: path, required: true, schema: {type: string}}
    responses:
      200:
        description: Order cancelled.
      404:
        description: Order not found.
    """
    order = Order.query.get_or_404(order_id)
    order.status = "Cancelled"
    db.session.commit()
    return jsonify({"message": "Order cancelled.", "orderId": order.id}), 200
