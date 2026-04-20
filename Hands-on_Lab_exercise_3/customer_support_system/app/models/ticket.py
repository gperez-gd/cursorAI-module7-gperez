import enum
from datetime import datetime, timezone, timedelta
from flask import current_app
from ..extensions import db


class TicketStatus(str, enum.Enum):
    OPEN = "open"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    WAITING = "waiting"
    RESOLVED = "resolved"
    CLOSED = "closed"
    REOPENED = "reopened"


class TicketPriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class TicketCategory(str, enum.Enum):
    TECHNICAL = "technical"
    BILLING = "billing"
    GENERAL = "general"
    FEATURE_REQUEST = "feature_request"


# FR-012: Allowed status transitions
VALID_TRANSITIONS = {
    TicketStatus.OPEN: [TicketStatus.ASSIGNED, TicketStatus.CLOSED],
    TicketStatus.ASSIGNED: [TicketStatus.IN_PROGRESS, TicketStatus.CLOSED],
    TicketStatus.IN_PROGRESS: [TicketStatus.WAITING, TicketStatus.RESOLVED, TicketStatus.CLOSED],
    TicketStatus.WAITING: [TicketStatus.IN_PROGRESS],
    TicketStatus.RESOLVED: [TicketStatus.CLOSED, TicketStatus.REOPENED],
    TicketStatus.CLOSED: [TicketStatus.REOPENED],
    TicketStatus.REOPENED: [TicketStatus.IN_PROGRESS],
}

# SLA hours by priority (FR-020)
SLA_HOURS = {
    TicketPriority.URGENT: {"response": 2, "resolution": 24},
    TicketPriority.HIGH: {"response": 4, "resolution": 48},
    TicketPriority.MEDIUM: {"response": 8, "resolution": 120},
    TicketPriority.LOW: {"response": 24, "resolution": 240},
}


class Ticket(db.Model):
    __tablename__ = "tickets"

    id = db.Column(db.Integer, primary_key=True)
    ticket_number = db.Column(db.String(30), unique=True, nullable=False, index=True)
    subject = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.Enum(TicketStatus), nullable=False, default=TicketStatus.OPEN)
    priority = db.Column(db.Enum(TicketPriority), nullable=False, default=TicketPriority.MEDIUM)
    category = db.Column(db.Enum(TicketCategory), nullable=False)
    customer_email = db.Column(db.String(255), nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    assigned_to_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    sla_response_due = db.Column(db.DateTime, nullable=True)
    sla_resolution_due = db.Column(db.DateTime, nullable=True)
    sla_response_met = db.Column(db.Boolean, default=None, nullable=True)
    sla_resolution_met = db.Column(db.Boolean, default=None, nullable=True)
    first_response_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    resolved_at = db.Column(db.DateTime, nullable=True)
    closed_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    created_by = db.relationship("User", foreign_keys=[created_by_id], back_populates="created_tickets")
    assigned_to = db.relationship("User", foreign_keys=[assigned_to_id], back_populates="assigned_tickets")
    comments = db.relationship("Comment", back_populates="ticket", lazy="dynamic", cascade="all, delete-orphan")
    assignments = db.relationship("Assignment", back_populates="ticket", lazy="dynamic", cascade="all, delete-orphan")
    attachments = db.relationship("Attachment", back_populates="ticket", lazy="dynamic", cascade="all, delete-orphan")

    def can_transition_to(self, new_status: TicketStatus) -> bool:
        """Check if current status can transition to new_status (FR-012)."""
        allowed = VALID_TRANSITIONS.get(self.status, [])
        if new_status == TicketStatus.REOPENED and self.status == TicketStatus.CLOSED:
            # Closed → Reopened only within 7 days
            if self.closed_at:
                closed_at = self.closed_at
                if closed_at.tzinfo is None:
                    closed_at = closed_at.replace(tzinfo=timezone.utc)
                delta = datetime.now(timezone.utc) - closed_at
                return delta.days <= 7
            return False
        return new_status in allowed

    def set_sla_deadlines(self):
        """Compute and store SLA response/resolution deadlines (FR-020)."""
        sla = SLA_HOURS.get(self.priority, SLA_HOURS[TicketPriority.MEDIUM])
        now = datetime.now(timezone.utc)
        self.sla_response_due = now + timedelta(hours=sla["response"])
        self.sla_resolution_due = now + timedelta(hours=sla["resolution"])

    def is_sla_response_approaching(self) -> bool:
        """True when within 25% of response SLA window remaining (FR-021)."""
        if not self.sla_response_due or self.first_response_at:
            return False
        due = self.sla_response_due
        if due.tzinfo is None:
            due = due.replace(tzinfo=timezone.utc)
        remaining = (due - datetime.now(timezone.utc)).total_seconds()
        sla_hours = SLA_HOURS[self.priority]["response"] * 3600
        return 0 < remaining < sla_hours * 0.25

    def is_sla_resolution_approaching(self) -> bool:
        """True when within 25% of resolution SLA window remaining (FR-021)."""
        if not self.sla_resolution_due or self.resolved_at:
            return False
        due = self.sla_resolution_due
        if due.tzinfo is None:
            due = due.replace(tzinfo=timezone.utc)
        remaining = (due - datetime.now(timezone.utc)).total_seconds()
        sla_hours = SLA_HOURS[self.priority]["resolution"] * 3600
        return 0 < remaining < sla_hours * 0.25

    def is_sla_missed(self) -> bool:
        """True when resolution SLA has been exceeded (FR-022)."""
        if not self.sla_resolution_due or self.resolved_at or self.closed_at:
            return False
        due = self.sla_resolution_due
        if due.tzinfo is None:
            due = due.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) > due

    def __repr__(self):
        return f"<Ticket {self.ticket_number} [{self.status.value}]>"
