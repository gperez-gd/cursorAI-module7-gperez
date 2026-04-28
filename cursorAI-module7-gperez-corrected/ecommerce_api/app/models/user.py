import uuid
from datetime import datetime

from werkzeug.security import check_password_hash, generate_password_hash

from ..extensions import db


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(255), nullable=True)
    last_name = db.Column(db.String(255), nullable=True)
    role = db.Column(db.String(20), nullable=False, default="user")  # "user" | "admin"
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    # JSON-serialised list of address dicts
    saved_addresses = db.Column(db.JSON, nullable=True, default=list)
    # User notification/privacy settings stored as JSON
    settings = db.Column(db.JSON, nullable=True, default=dict)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    cart = db.relationship("Cart", back_populates="user", uselist=False, lazy="select")
    orders = db.relationship("Order", back_populates="user", lazy="dynamic")

    def set_password(self, plain: str) -> None:
        self.password_hash = generate_password_hash(plain)

    def check_password(self, plain: str) -> bool:
        return check_password_hash(self.password_hash, plain)

    def to_dict(self, include_private: bool = False) -> dict:
        data = {
            "id": self.id,
            "email": self.email,
            "firstName": self.first_name,
            "lastName": self.last_name,
            "role": self.role,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }
        if include_private:
            data["savedAddresses"] = self.saved_addresses or []
            data["settings"] = self.settings or {}
        return data
