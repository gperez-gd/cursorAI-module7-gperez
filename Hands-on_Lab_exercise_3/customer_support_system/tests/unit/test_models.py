"""Unit tests for data models (FR-002, FR-011, FR-012, FR-020)."""
import pytest
from datetime import datetime, timezone, timedelta
from app.models.ticket import Ticket, TicketStatus, TicketPriority, TicketCategory, VALID_TRANSITIONS
from app.models.user import User, UserRole


class TestUserModel:
    def test_password_hashing(self, db):
        """Passwords are hashed with bcrypt (NFR-005)."""
        user = User(name="Test", email="test@example.com", role=UserRole.CUSTOMER)
        user.set_password("SecurePass1")
        db.session.add(user)
        db.session.commit()
        assert user.password_hash != "SecurePass1"
        assert user.check_password("SecurePass1") is True
        assert user.check_password("WrongPassword") is False

    def test_user_roles(self, db):
        for role in UserRole:
            user = User(name="U", email=f"{role.value}@test.com", role=role)
            user.set_password("Passw0rd!")
            db.session.add(user)
        db.session.commit()
        agents = User.query.filter_by(role=UserRole.AGENT).all()
        assert all(u.role == UserRole.AGENT for u in agents)

    def test_repr(self, customer_user):
        assert "alice@example.com" in repr(customer_user)


class TestTicketModel:
    def test_ticket_number_format(self, sample_ticket):
        """FR-002: Ticket number matches TICK-YYYYMMDD-XXXX format."""
        import re
        assert re.match(r"TICK-\d{8}-\d{4}", sample_ticket.ticket_number)

    def test_default_status_is_open(self, sample_ticket):
        """FR-004: Default status is OPEN."""
        assert sample_ticket.status == TicketStatus.OPEN

    def test_sla_deadlines_set(self, sample_ticket):
        """FR-020: SLA deadlines calculated on creation."""
        assert sample_ticket.sla_response_due is not None
        assert sample_ticket.sla_resolution_due is not None
        # HIGH priority: 4h response, 48h resolution
        diff_response = (sample_ticket.sla_response_due - sample_ticket.created_at).total_seconds() / 3600
        assert 3.9 <= diff_response <= 4.1

    def test_valid_status_transitions(self, sample_ticket):
        """FR-012: Valid transitions are permitted."""
        assert sample_ticket.can_transition_to(TicketStatus.ASSIGNED) is True
        assert sample_ticket.can_transition_to(TicketStatus.CLOSED) is True

    def test_invalid_status_transition(self, sample_ticket):
        """FR-012: Invalid transitions are rejected."""
        assert sample_ticket.can_transition_to(TicketStatus.IN_PROGRESS) is False
        assert sample_ticket.can_transition_to(TicketStatus.RESOLVED) is False
        assert sample_ticket.can_transition_to(TicketStatus.WAITING) is False

    def test_closed_to_reopened_within_7_days(self, db, sample_ticket):
        """FR-012: Closed → Reopened allowed within 7 days."""
        sample_ticket.status = TicketStatus.CLOSED
        sample_ticket.closed_at = datetime.now(timezone.utc) - timedelta(days=3)
        db.session.commit()
        assert sample_ticket.can_transition_to(TicketStatus.REOPENED) is True

    def test_closed_to_reopened_after_7_days(self, db, sample_ticket):
        """FR-012: Closed → Reopened rejected after 7 days."""
        sample_ticket.status = TicketStatus.CLOSED
        sample_ticket.closed_at = datetime.now(timezone.utc) - timedelta(days=8)
        db.session.commit()
        assert sample_ticket.can_transition_to(TicketStatus.REOPENED) is False

    def test_sla_missed_detection(self, db, sample_ticket):
        """FR-022: SLA missed when deadline has passed."""
        sample_ticket.sla_resolution_due = datetime.now(timezone.utc) - timedelta(hours=1)
        db.session.commit()
        assert sample_ticket.is_sla_missed() is True

    def test_all_valid_transitions_table(self):
        """FR-012: Spot-check the full transition table."""
        assert TicketStatus.WAITING in VALID_TRANSITIONS[TicketStatus.IN_PROGRESS]
        assert TicketStatus.RESOLVED in VALID_TRANSITIONS[TicketStatus.IN_PROGRESS]
        assert TicketStatus.IN_PROGRESS in VALID_TRANSITIONS[TicketStatus.WAITING]
        assert TicketStatus.REOPENED in VALID_TRANSITIONS[TicketStatus.RESOLVED]
        assert TicketStatus.IN_PROGRESS in VALID_TRANSITIONS[TicketStatus.REOPENED]
