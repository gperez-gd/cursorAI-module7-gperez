import uuid
from datetime import datetime

from ..extensions import db


class DiscountCode(db.Model):
    __tablename__ = "discount_codes"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code = db.Column(db.String(50), unique=True, nullable=False, index=True)
    type = db.Column(db.String(20), nullable=False)  # "percentage" | "fixed"
    value = db.Column(db.Numeric(10, 2), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=True)
    is_single_use = db.Column(db.Boolean, nullable=False, default=False)
    max_uses = db.Column(db.Integer, nullable=True)  # None = unlimited
    uses_count = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    redemptions = db.relationship("DiscountRedemption", back_populates="discount_code")

    def is_expired(self) -> bool:
        return self.expires_at is not None and datetime.utcnow() > self.expires_at

    def is_exhausted(self) -> bool:
        if self.max_uses is not None and self.uses_count >= self.max_uses:
            return True
        return False

    def is_valid(self) -> bool:
        return not self.is_expired() and not self.is_exhausted()

    def user_has_redeemed(self, user_id: str) -> bool:
        if not self.is_single_use:
            return False
        return any(r.user_id == user_id for r in self.redemptions)


class DiscountRedemption(db.Model):
    __tablename__ = "discount_redemptions"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    discount_code_id = db.Column(
        db.String(36), db.ForeignKey("discount_codes.id"), nullable=False
    )
    redeemed_at = db.Column(db.DateTime, default=datetime.utcnow)

    discount_code = db.relationship("DiscountCode", back_populates="redemptions")
