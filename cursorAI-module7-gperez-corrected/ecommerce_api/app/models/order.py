import uuid
from datetime import datetime

from ..extensions import db

VALID_STATUSES = ("Processing", "Shipped", "Delivered", "Cancelled")


class Order(db.Model):
    __tablename__ = "orders"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    confirmation_number = db.Column(db.String(20), unique=True, nullable=False)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default="Processing")
    shipping_address = db.Column(db.JSON, nullable=False)
    # Stored as {type, token, last4} – never contains raw card number or CVV
    payment_method = db.Column(db.JSON, nullable=False)
    subtotal = db.Column(db.Numeric(10, 2), nullable=False)
    discount = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    total = db.Column(db.Numeric(10, 2), nullable=False)
    estimated_delivery = db.Column(db.DateTime, nullable=True)
    idempotency_key = db.Column(db.String(128), nullable=True, unique=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship("User", back_populates="orders")
    items = db.relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")

    def to_dict(self) -> dict:
        return {
            "orderId": self.id,
            "confirmationNumber": self.confirmation_number,
            "status": self.status,
            "items": [i.to_dict() for i in self.items],
            "shippingAddress": self.shipping_address,
            "paymentMethod": self.payment_method,
            "subtotal": float(self.subtotal),
            "discount": float(self.discount),
            "total": float(self.total),
            "estimatedDelivery": (
                self.estimated_delivery.isoformat() if self.estimated_delivery else None
            ),
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }


class OrderItem(db.Model):
    __tablename__ = "order_items"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    order_id = db.Column(db.String(36), db.ForeignKey("orders.id"), nullable=False)
    product_id = db.Column(db.String(36), db.ForeignKey("products.id"), nullable=True)
    # Price/name snapshotted at order time so product edits don't corrupt history
    product_name = db.Column(db.String(255), nullable=False)
    product_price = db.Column(db.Numeric(10, 2), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    line_total = db.Column(db.Numeric(10, 2), nullable=False)

    order = db.relationship("Order", back_populates="items")
    product = db.relationship("Product", back_populates="order_items")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "productId": self.product_id,
            "productName": self.product_name,
            "productPrice": float(self.product_price),
            "quantity": self.quantity,
            "lineTotal": float(self.line_total),
        }
