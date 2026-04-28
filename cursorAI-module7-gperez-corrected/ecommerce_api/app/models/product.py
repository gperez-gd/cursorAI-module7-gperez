import uuid
from datetime import datetime

from ..extensions import db

VALID_CATEGORIES = {"Electronics", "Accessories", "Footwear", "Office"}


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(255), nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    stock = db.Column(db.Integer, nullable=False, default=0)
    category = db.Column(db.String(100), nullable=False, index=True)
    image_url = db.Column(db.String(500), nullable=True)
    rating = db.Column(db.Numeric(3, 2), nullable=False, default=0.0)
    review_count = db.Column(db.Integer, nullable=False, default=0)
    badge = db.Column(db.String(50), nullable=True)
    is_deleted = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    order_items = db.relationship("OrderItem", back_populates="product", lazy="dynamic")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "price": float(self.price),
            "stock": self.stock,
            "category": self.category,
            "imageUrl": self.image_url,
            "rating": float(self.rating),
            "reviewCount": self.review_count,
            "badge": self.badge,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }
