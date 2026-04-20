from datetime import datetime, timezone
from ..extensions import db


class Comment(db.Model):
    __tablename__ = "comments"

    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey("tickets.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_internal = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    ticket = db.relationship("Ticket", back_populates="comments")
    author = db.relationship("User", back_populates="comments")
    attachments = db.relationship(
        "Attachment",
        back_populates="comment",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        visibility = "internal" if self.is_internal else "public"
        return f"<Comment {self.id} on Ticket {self.ticket_id} [{visibility}]>"
