import enum
from datetime import datetime, timezone
from ..extensions import db, bcrypt


class UserRole(str, enum.Enum):
    CUSTOMER = "customer"
    AGENT = "agent"
    ADMIN = "admin"


class AvailabilityStatus(str, enum.Enum):
    AVAILABLE = "available"
    BUSY = "busy"
    OFFLINE = "offline"


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum(UserRole), nullable=False, default=UserRole.CUSTOMER)
    availability_status = db.Column(
        db.Enum(AvailabilityStatus),
        nullable=False,
        default=AvailabilityStatus.AVAILABLE,
    )
    expertise_areas = db.Column(db.JSON, default=list)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    created_tickets = db.relationship(
        "Ticket", foreign_keys="Ticket.created_by_id", back_populates="created_by", lazy="dynamic"
    )
    assigned_tickets = db.relationship(
        "Ticket", foreign_keys="Ticket.assigned_to_id", back_populates="assigned_to", lazy="dynamic"
    )
    comments = db.relationship("Comment", back_populates="author", lazy="dynamic")
    assignments_made = db.relationship(
        "Assignment", foreign_keys="Assignment.assigned_by_id", back_populates="assigned_by", lazy="dynamic"
    )
    assignments_received = db.relationship(
        "Assignment", foreign_keys="Assignment.assigned_to_id", back_populates="assigned_to", lazy="dynamic"
    )

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password, rounds=12).decode("utf-8")

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)

    @property
    def open_ticket_count(self):
        from .ticket import TicketStatus
        return self.assigned_tickets.filter(
            Ticket.status.notin_([TicketStatus.CLOSED, TicketStatus.RESOLVED])
        ).count()

    def __repr__(self):
        return f"<User {self.email} ({self.role.value})>"
