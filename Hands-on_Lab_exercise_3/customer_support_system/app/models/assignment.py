from datetime import datetime, timezone
from ..extensions import db


class Assignment(db.Model):
    """Tracks the full assignment history for each ticket (FR-010)."""

    __tablename__ = "assignments"

    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey("tickets.id"), nullable=False, index=True)
    assigned_to_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    assigned_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    assigned_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    notes = db.Column(db.String(500), nullable=True)

    # Relationships
    ticket = db.relationship("Ticket", back_populates="assignments")
    assigned_to = db.relationship("User", foreign_keys=[assigned_to_id], back_populates="assignments_received")
    assigned_by = db.relationship("User", foreign_keys=[assigned_by_id], back_populates="assignments_made")

    def __repr__(self):
        return f"<Assignment ticket={self.ticket_id} to={self.assigned_to_id}>"
