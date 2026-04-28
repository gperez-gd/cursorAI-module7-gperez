import random
import string
import uuid
from datetime import datetime, timedelta
from decimal import Decimal

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity

from ..extensions import db
from ..models import Cart, CartItem, DiscountCode, DiscountRedemption, Order, OrderItem, Product, User
from ..services.cache import CacheService
from ..services.payment import PaymentService
from ..utils.errors import err
from ..utils.security import require_csrf, sanitize
from ..utils.validators import CheckoutSchema, load_or_400

checkout_bp = Blueprint("checkout", __name__)


def _confirmation_number() -> str:
    return "ORD-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=10))


# ---------------------------------------------------------------------------
# POST /checkout  – CHK-FR-001 through CHK-FR-013
# ---------------------------------------------------------------------------
@checkout_bp.route("", methods=["POST"])
@checkout_bp.route("/submit", methods=["POST"])   # alias tested by TC-S-007
@jwt_required()
@require_csrf
def place_order():
    """
    Place an order from the current cart.
    ---
    tags: [Checkout]
    security:
      - BearerAuth: []
    parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema: {type: string}
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required: [shippingAddress]
            properties:
              shippingAddress:
                type: object
                required: [firstName, lastName, email, street, city, state, zip, country]
              paymentToken: {type: string}
              paypalToken: {type: string}
              savedCardId: {type: string}
              discountCode: {type: string}
              idempotencyKey: {type: string}
    responses:
      201:
        description: Order placed successfully.
      400:
        description: Validation error, empty cart or stock issue.
      402:
        description: Payment declined.
      403:
        description: CSRF token invalid.
    """
    body = request.get_json(silent=True) or {}
    data, errors = load_or_400(CheckoutSchema(), body)
    if errors:
        return err("; ".join(errors), 400)

    user_id = get_jwt_identity()

    # ── Idempotency check (CHK-FR-011) ───────────────────────────────────────
    idempotency_key = data.get("idempotencyKey")
    if idempotency_key:
        cached_order = CacheService.get_idempotency(idempotency_key)
        if cached_order:
            return jsonify(cached_order), 200
        existing_order = Order.query.filter_by(idempotency_key=idempotency_key).first()
        if existing_order:
            return jsonify(existing_order.to_dict()), 200

    # ── Load cart (CHK-FR-002) ────────────────────────────────────────────────
    cart = Cart.query.filter_by(user_id=user_id).first()
    if not cart or not cart.items:
        return err("Your cart is empty.", 400)

    # ── Validate stock & build line items (CART-FR-009, CHK-FR-009) ──────────
    line_items = []
    subtotal = Decimal("0")
    for ci in cart.items:
        product = Product.query.filter_by(id=ci.product_id, is_deleted=False).first()
        if not product:
            return err(f"A product in your cart is no longer available.", 400)
        if product.stock < ci.quantity:
            return err(f"{product.name} is no longer available in the requested quantity.", 400)
        line_total = Decimal(str(product.price)) * ci.quantity
        subtotal += line_total
        line_items.append(
            {"product": product, "quantity": ci.quantity, "line_total": line_total}
        )

    # ── Apply discount ────────────────────────────────────────────────────────
    discount_amount = Decimal("0")
    discount_code_str = data.get("discountCode") or cart.discount_code
    if discount_code_str:
        dc = DiscountCode.query.filter_by(code=discount_code_str.upper()).first()
        if dc and dc.is_valid() and not dc.user_has_redeemed(user_id):
            if dc.type == "percentage":
                discount_amount = (subtotal * Decimal(str(dc.value)) / 100).quantize(
                    Decimal("0.01")
                )
            else:
                discount_amount = min(Decimal(str(dc.value)), subtotal)

    # CHK-FR-007: total capped at 0 (DISC-FR-007)
    total = max(subtotal - discount_amount, Decimal("0"))

    # ── Payment processing (CHK-FR-005, CHK-FR-008, CHK-FR-012) ─────────────
    payment_method_data: dict
    if total == Decimal("0"):
        # Free order – no payment required
        payment_method_data = {"type": "free", "token": None, "last4": None}
    else:
        result = PaymentService.process(
            payment_token=data.get("paymentToken"),
            paypal_token=data.get("paypalToken"),
            saved_card_id=data.get("savedCardId"),
            amount=float(total),
        )
        if not result.success:
            return err(result.error or "Payment declined.", 402)
        payment_method_data = {
            "type": result.type,
            "token": result.token,
            "last4": result.last4,
        }

    # ── Create order atomically ───────────────────────────────────────────────
    order = Order(
        id=str(uuid.uuid4()),
        confirmation_number=_confirmation_number(),
        user_id=user_id,
        status="Processing",
        shipping_address=data["shippingAddress"],
        payment_method=payment_method_data,
        subtotal=float(subtotal),
        discount=float(discount_amount),
        total=float(total),
        estimated_delivery=datetime.utcnow() + timedelta(days=7),
        idempotency_key=idempotency_key,
    )
    db.session.add(order)

    for li in line_items:
        product = li["product"]
        oi = OrderItem(
            id=str(uuid.uuid4()),
            order_id=order.id,
            product_id=product.id,
            product_name=product.name,       # snapshot
            product_price=float(product.price),  # snapshot
            quantity=li["quantity"],
            line_total=float(li["line_total"]),
        )
        db.session.add(oi)
        product.stock -= li["quantity"]   # decrement inventory

    # Mark discount as redeemed if single-use
    if discount_code_str and discount_amount > 0:
        dc = DiscountCode.query.filter_by(code=discount_code_str.upper()).first()
        if dc:
            dc.uses_count += 1
            if dc.is_single_use:
                redemption = DiscountRedemption(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    discount_code_id=dc.id,
                )
                db.session.add(redemption)

    # Clear cart
    for ci in list(cart.items):
        db.session.delete(ci)
    cart.discount_code = None
    cart.discount_amount = 0

    db.session.commit()

    response_data = {
        "orderId": order.id,
        "confirmationNumber": order.confirmation_number,
        "total": float(order.total),
        "estimatedDelivery": order.estimated_delivery.isoformat(),
        "status": order.status,
    }

    # Queue confirmation email (best-effort; Celery broker may be unavailable in dev)
    buyer = db.session.get(User, user_id)
    if buyer and buyer.email:
        try:
            from ..tasks.order_tasks import send_order_confirmation

            send_order_confirmation.delay(
                str(order.id),
                buyer.email,
                order.confirmation_number,
            )
        except Exception as exc:
            current_app.logger.warning("Could not queue order confirmation email: %s", exc)

    # Cache for idempotency
    if idempotency_key:
        CacheService.set_idempotency(idempotency_key, response_data)

    return jsonify(response_data), 201
