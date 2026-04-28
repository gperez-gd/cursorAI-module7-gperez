from decimal import Decimal

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from ..extensions import db
from ..models import Cart, CartItem, Product, DiscountCode, DiscountRedemption
from ..models.cart import MAX_QUANTITY_PER_ITEM
from ..utils.errors import err
from ..utils.security import sanitize
from ..utils.validators import CartItemAddSchema, CartItemUpdateSchema, DiscountApplySchema, load_or_400

cart_bp = Blueprint("cart", __name__)


def _get_or_create_cart(user_id: str) -> Cart:
    cart = Cart.query.filter_by(user_id=user_id).first()
    if not cart:
        cart = Cart(user_id=user_id)
        db.session.add(cart)
        db.session.flush()
    return cart


# ---------------------------------------------------------------------------
# GET /cart
# ---------------------------------------------------------------------------
@cart_bp.route("", methods=["GET"])
@jwt_required()
def get_cart():
    """
    Get the current user's cart.
    ---
    tags: [Cart]
    security:
      - BearerAuth: []
    responses:
      200:
        description: Cart with items, subtotal, discount and total.
    """
    cart = _get_or_create_cart(get_jwt_identity())
    db.session.commit()
    return jsonify(cart.to_dict()), 200


# ---------------------------------------------------------------------------
# POST /cart/items
# ---------------------------------------------------------------------------
@cart_bp.route("/items", methods=["POST"])
@jwt_required()
def add_item():
    """
    Add an item to the cart.
    ---
    tags: [Cart]
    security:
      - BearerAuth: []
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required: [productId, quantity]
            properties:
              productId: {type: string}
              quantity: {type: integer, minimum: 1, maximum: 10}
    responses:
      200:
        description: Updated cart.
      400:
        description: Validation or stock error.
      404:
        description: Product not found.
    """
    data, errors = load_or_400(CartItemAddSchema(), request.get_json(silent=True) or {})
    if errors:
        return err("; ".join(errors), 400)

    product = Product.query.filter_by(id=data["productId"], is_deleted=False).first()
    if not product:
        return err("Product not found.", 404)
    if product.stock < 1:
        return err(f"{product.name} is out of stock.", 400)

    cart = _get_or_create_cart(get_jwt_identity())

    existing = next((i for i in cart.items if i.product_id == product.id), None)
    if existing:
        new_qty = existing.quantity + data["quantity"]
        if new_qty > MAX_QUANTITY_PER_ITEM:
            return err(f"Maximum quantity allowed is {MAX_QUANTITY_PER_ITEM}.", 400)
        existing.quantity = new_qty
    else:
        if data["quantity"] > MAX_QUANTITY_PER_ITEM:
            return err(f"Maximum quantity allowed is {MAX_QUANTITY_PER_ITEM}.", 400)
        item = CartItem(
            cart_id=cart.id, product_id=product.id, quantity=data["quantity"]
        )
        db.session.add(item)

    db.session.commit()
    db.session.refresh(cart)
    return jsonify(cart.to_dict()), 200


# ---------------------------------------------------------------------------
# PUT /cart/items/:itemId
# ---------------------------------------------------------------------------
@cart_bp.route("/items/<item_id>", methods=["PUT"])
@jwt_required()
def update_item(item_id):
    """
    Update cart item quantity. Setting quantity to 0 removes the item.
    ---
    tags: [Cart]
    security:
      - BearerAuth: []
    parameters:
      - {name: item_id, in: path, required: true, schema: {type: string}}
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required: [quantity]
            properties:
              quantity: {type: integer, minimum: 0, maximum: 10}
    responses:
      200:
        description: Updated cart.
      400:
        description: Quantity exceeds max.
    """
    data, errors = load_or_400(CartItemUpdateSchema(), request.get_json(silent=True) or {})
    if errors:
        return err("; ".join(errors), 400)

    cart = _get_or_create_cart(get_jwt_identity())
    item = CartItem.query.filter_by(id=item_id, cart_id=cart.id).first()
    if not item:
        return err("Cart item not found.", 404)

    qty = data["quantity"]
    if qty == 0:
        db.session.delete(item)
    elif qty > MAX_QUANTITY_PER_ITEM:
        return err(f"Maximum quantity allowed is {MAX_QUANTITY_PER_ITEM}.", 400)
    else:
        item.quantity = qty

    db.session.commit()
    db.session.refresh(cart)
    return jsonify(cart.to_dict()), 200


# ---------------------------------------------------------------------------
# DELETE /cart/items/:itemId
# ---------------------------------------------------------------------------
@cart_bp.route("/items/<item_id>", methods=["DELETE"])
@jwt_required()
def remove_item(item_id):
    """
    Remove an item from the cart.
    ---
    tags: [Cart]
    security:
      - BearerAuth: []
    parameters:
      - {name: item_id, in: path, required: true, schema: {type: string}}
    responses:
      200:
        description: Updated cart.
      404:
        description: Item not found.
    """
    cart = _get_or_create_cart(get_jwt_identity())
    item = CartItem.query.filter_by(id=item_id, cart_id=cart.id).first()
    if not item:
        return err("Cart item not found.", 404)
    db.session.delete(item)
    db.session.commit()
    db.session.refresh(cart)
    return jsonify(cart.to_dict()), 200


# ---------------------------------------------------------------------------
# POST /cart/discount
# ---------------------------------------------------------------------------
@cart_bp.route("/discount", methods=["POST"])
@jwt_required()
def apply_discount():
    """
    Apply a discount code to the cart.
    ---
    tags: [Cart]
    security:
      - BearerAuth: []
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required: [code]
            properties:
              code: {type: string}
    responses:
      200:
        description: Discount applied; updated cart returned.
      400:
        description: Invalid, expired or already-used code.
    """
    data, errors = load_or_400(DiscountApplySchema(), request.get_json(silent=True) or {})
    if errors:
        return err("; ".join(errors), 400)

    # SEC-001: sanitise before DB lookup
    code = sanitize(data["code"]).strip().upper()
    user_id = get_jwt_identity()

    discount_code = DiscountCode.query.filter_by(code=code).first()
    if not discount_code:
        return err("Invalid discount code.", 400)
    if discount_code.is_expired():
        return err("This discount code has expired.", 400)
    if discount_code.is_exhausted():
        return err("This discount code is no longer available.", 400)
    if discount_code.user_has_redeemed(user_id):
        return err("This code has already been used.", 400)

    cart = _get_or_create_cart(user_id)
    subtotal = cart.compute_subtotal()

    if discount_code.type == "percentage":
        discount_amount = (subtotal * Decimal(str(discount_code.value)) / 100).quantize(
            Decimal("0.01")
        )
    else:
        discount_amount = min(Decimal(str(discount_code.value)), subtotal)

    cart.discount_code = code
    cart.discount_amount = float(discount_amount)
    db.session.commit()
    db.session.refresh(cart)
    return jsonify(cart.to_dict()), 200


# ---------------------------------------------------------------------------
# DELETE /cart/discount
# ---------------------------------------------------------------------------
@cart_bp.route("/discount", methods=["DELETE"])
@jwt_required()
def remove_discount():
    """
    Remove the applied discount code from the cart.
    ---
    tags: [Cart]
    security:
      - BearerAuth: []
    responses:
      200:
        description: Discount removed; updated cart returned.
    """
    cart = _get_or_create_cart(get_jwt_identity())
    cart.discount_code = None
    cart.discount_amount = 0
    db.session.commit()
    db.session.refresh(cart)
    return jsonify(cart.to_dict()), 200
