import uuid
from datetime import datetime
from decimal import Decimal

from ..extensions import db

MAX_QUANTITY_PER_ITEM = 10


class Cart(db.Model):
    __tablename__ = "carts"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=True, unique=True)
    session_id = db.Column(db.String(64), nullable=True, index=True)
    discount_code = db.Column(db.String(50), nullable=True)
    discount_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship("User", back_populates="cart")
    items = db.relationship("CartItem", back_populates="cart", cascade="all, delete-orphan")

    def compute_subtotal(self) -> Decimal:
        total = Decimal("0")
        for item in self.items:
            if item.product and not item.product.is_deleted:
                total += Decimal(str(item.product.price)) * item.quantity
        return total

    def to_dict(self) -> dict:
        subtotal = self.compute_subtotal()
        discount = Decimal(str(self.discount_amount)) if self.discount_amount else Decimal("0")
        total = max(subtotal - discount, Decimal("0"))
        return {
            "id": self.id,
            "items": [i.to_dict() for i in self.items],
            "subtotal": float(subtotal),
            "discount": float(discount),
            "total": float(total),
            "discountCode": self.discount_code,
        }


class CartItem(db.Model):
    __tablename__ = "cart_items"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    cart_id = db.Column(db.String(36), db.ForeignKey("carts.id"), nullable=False)
    product_id = db.Column(db.String(36), db.ForeignKey("products.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)

    cart = db.relationship("Cart", back_populates="items")
    product = db.relationship("Product")

    def to_dict(self) -> dict:
        product = self.product
        return {
            "id": self.id,
            "productId": self.product_id,
            "name": product.name if product else None,
            "price": float(product.price) if product else 0,
            "quantity": self.quantity,
            "lineTotal": float(product.price) * self.quantity if product else 0,
            "imageUrl": product.image_url if product else None,
        }
