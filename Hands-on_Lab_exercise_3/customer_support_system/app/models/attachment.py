from datetime import datetime, timezone
from ..extensions import db


class Attachment(db.Model):
    __tablename__ = "attachments"

    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey("tickets.id"), nullable=False, index=True)
    comment_id = db.Column(db.Integer, db.ForeignKey("comments.id"), nullable=True)
    filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    file_size = db.Column(db.Integer, nullable=False)
    file_type = db.Column(db.String(50), nullable=False)
    uploaded_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    uploaded_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    ticket = db.relationship("Ticket", back_populates="attachments")
    comment = db.relationship("Comment", back_populates="attachments")

    def __repr__(self):
        return f"<Attachment {self.filename} on Ticket {self.ticket_id}>"
