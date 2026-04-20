"""
API tests for Ticket endpoints (FR-001 through FR-024).
Covers creation, validation, RBAC, status transitions, priority, assignment, comments.
"""
import json
import pytest
from app.models.ticket import Ticket, TicketStatus, TicketPriority


class TestCreateTicket:
    endpoint = "/api/tickets"

    def test_customer_creates_ticket(self, client, db, customer_user, customer_headers):
        """FR-001, FR-002, FR-004: Ticket created with auto-generated number and OPEN status."""
        resp = client.post(self.endpoint, headers=customer_headers, json={
            "subject": "My billing is incorrect",
            "description": "I was charged twice for the same service last month.",
            "priority": "high",
            "category": "billing",
            "customer_email": customer_user.email,
        })
        assert resp.status_code == 201
        data = resp.get_json()["data"]
        assert data["status"] == "open"
        assert data["ticket_number"].startswith("TICK-")
        assert data["sla_response_due"] is not None  # FR-020

    def test_unauthenticated_create_fails(self, client, db):
        resp = client.post(self.endpoint, json={
            "subject": "Test ticket",
            "description": "Test description for this support ticket.",
            "category": "general",
            "customer_email": "x@example.com",
        })
        assert resp.status_code == 401

    def test_subject_too_short_rejected(self, client, db, customer_headers):
        """FR-001 validation: Subject must be 5+ chars."""
        resp = client.post(self.endpoint, headers=customer_headers, json={
            "subject": "Hi",
            "description": "Long enough description for validation test.",
            "category": "technical",
            "customer_email": "u@example.com",
        })
        assert resp.status_code == 400
        assert resp.get_json()["code"] == "VALIDATION_ERROR"

    def test_description_too_short_rejected(self, client, db, customer_headers):
        """FR-001 validation: Description must be 20+ chars."""
        resp = client.post(self.endpoint, headers=customer_headers, json={
            "subject": "Valid subject text",
            "description": "Too short.",
            "category": "general",
            "customer_email": "u@example.com",
        })
        assert resp.status_code == 400

    def test_invalid_priority_rejected(self, client, db, customer_headers):
        resp = client.post(self.endpoint, headers=customer_headers, json={
            "subject": "Valid ticket subject",
            "description": "Long enough description for validation testing.",
            "priority": "extreme",
            "category": "technical",
            "customer_email": "u@example.com",
        })
        assert resp.status_code == 400

    def test_invalid_email_rejected(self, client, db, customer_headers):
        resp = client.post(self.endpoint, headers=customer_headers, json={
            "subject": "Valid ticket subject",
            "description": "Long enough description for validation testing here.",
            "category": "technical",
            "customer_email": "bad-email",
        })
        assert resp.status_code == 400


class TestGetTicket:
    def test_customer_can_view_own_ticket(self, client, db, sample_ticket, customer_headers):
        resp = client.get(f"/api/tickets/{sample_ticket.id}", headers=customer_headers)
        assert resp.status_code == 200

    def test_agent_can_view_open_ticket(self, client, db, sample_ticket, agent_headers):
        resp = client.get(f"/api/tickets/{sample_ticket.id}", headers=agent_headers)
        assert resp.status_code == 200

    def test_404_on_missing_ticket(self, client, db, customer_headers):
        resp = client.get("/api/tickets/99999", headers=customer_headers)
        assert resp.status_code == 404

    def test_unauthenticated_rejected(self, client, db, sample_ticket):
        resp = client.get(f"/api/tickets/{sample_ticket.id}")
        assert resp.status_code == 401


class TestListTickets:
    def test_customer_only_sees_own_tickets(self, client, db, sample_ticket, customer_headers):
        """FR-033: Customers see only their own tickets."""
        resp = client.get("/api/tickets", headers=customer_headers)
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        for t in data:
            assert t["customer_email"] == sample_ticket.customer_email

    def test_admin_sees_all_tickets(self, client, db, sample_ticket, admin_headers):
        resp = client.get("/api/tickets", headers=admin_headers)
        assert resp.status_code == 200
        assert len(resp.get_json()["data"]) >= 1

    def test_filter_by_status(self, client, db, sample_ticket, admin_headers):
        resp = client.get("/api/tickets?status=open", headers=admin_headers)
        assert resp.status_code == 200
        for t in resp.get_json()["data"]:
            assert t["status"] == "open"


class TestStatusUpdate:
    def test_valid_status_transition(self, client, db, sample_ticket, agent_headers):
        """FR-011, FR-012: open → assigned is valid."""
        sample_ticket.status = TicketStatus.ASSIGNED
        db.session.commit()
        resp = client.put(
            f"/api/tickets/{sample_ticket.id}/status",
            headers=agent_headers,
            json={"status": "in_progress"},
        )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["status"] == "in_progress"

    def test_invalid_status_transition_rejected(self, client, db, sample_ticket, agent_headers):
        """FR-012: open → in_progress is invalid."""
        resp = client.put(
            f"/api/tickets/{sample_ticket.id}/status",
            headers=agent_headers,
            json={"status": "in_progress"},
        )
        assert resp.status_code == 400
        assert "Cannot transition" in resp.get_json()["message"]

    def test_customer_cannot_update_status(self, client, db, sample_ticket, customer_headers):
        """FR-033: Customers cannot change ticket status."""
        resp = client.put(
            f"/api/tickets/{sample_ticket.id}/status",
            headers=customer_headers,
            json={"status": "closed"},
        )
        assert resp.status_code == 403


class TestPriorityUpdate:
    def test_agent_can_change_priority_with_reason(self, client, db, sample_ticket, agent_headers):
        """FR-023, FR-024: Agent changes priority with required reason."""
        resp = client.put(
            f"/api/tickets/{sample_ticket.id}/priority",
            headers=agent_headers,
            json={"priority": "urgent", "reason": "Customer CEO is escalating this."},
        )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["priority"] == "urgent"

    def test_priority_change_without_reason_rejected(self, client, db, sample_ticket, agent_headers):
        """FR-024: Reason field is mandatory."""
        resp = client.put(
            f"/api/tickets/{sample_ticket.id}/priority",
            headers=agent_headers,
            json={"priority": "urgent"},
        )
        assert resp.status_code == 400

    def test_customer_cannot_change_priority(self, client, db, sample_ticket, customer_headers):
        """FR-023: Customers cannot change priority."""
        resp = client.put(
            f"/api/tickets/{sample_ticket.id}/priority",
            headers=customer_headers,
            json={"priority": "urgent", "reason": "I want it faster."},
        )
        assert resp.status_code == 403


class TestAssignment:
    def test_admin_can_assign_ticket(self, client, db, sample_ticket, agent_user, admin_headers):
        """FR-005: Admin manually assigns ticket to agent."""
        resp = client.post(
            f"/api/tickets/{sample_ticket.id}/assign",
            headers=admin_headers,
            json={"agent_id": agent_user.id},
        )
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["assigned_to_id"] == agent_user.id
        assert data["status"] == "assigned"  # FR-008

    def test_agent_cannot_assign_ticket(self, client, db, sample_ticket, agent_user, agent_headers):
        """FR-033: Only admins can assign tickets."""
        resp = client.post(
            f"/api/tickets/{sample_ticket.id}/assign",
            headers=agent_headers,
            json={"agent_id": agent_user.id},
        )
        assert resp.status_code == 403

    def test_customer_cannot_assign_ticket(self, client, db, sample_ticket, agent_user, customer_headers):
        resp = client.post(
            f"/api/tickets/{sample_ticket.id}/assign",
            headers=customer_headers,
            json={"agent_id": agent_user.id},
        )
        assert resp.status_code == 403


class TestDeleteTicket:
    def test_admin_can_delete(self, client, db, sample_ticket, admin_headers):
        resp = client.delete(f"/api/tickets/{sample_ticket.id}", headers=admin_headers)
        assert resp.status_code == 200
        assert Ticket.query.get(sample_ticket.id) is None

    def test_customer_cannot_delete(self, client, db, sample_ticket, customer_headers):
        resp = client.delete(f"/api/tickets/{sample_ticket.id}", headers=customer_headers)
        assert resp.status_code == 403


class TestComments:
    def test_customer_add_public_comment(self, client, db, sample_ticket, customer_headers):
        """FR-015: Customer can add public comments."""
        resp = client.post(
            f"/api/tickets/{sample_ticket.id}/comments",
            headers=customer_headers,
            json={"content": "Please help me resolve this issue."},
        )
        assert resp.status_code == 201
        assert resp.get_json()["data"]["is_internal"] is False

    def test_customer_cannot_add_internal_comment(self, client, db, sample_ticket, customer_headers):
        """FR-016: Customers cannot post internal comments."""
        resp = client.post(
            f"/api/tickets/{sample_ticket.id}/comments",
            headers=customer_headers,
            json={"content": "This should be internal.", "is_internal": True},
        )
        assert resp.status_code == 403

    def test_agent_can_add_internal_comment(self, client, db, sample_ticket, agent_headers):
        """FR-016: Agents can post internal comments."""
        resp = client.post(
            f"/api/tickets/{sample_ticket.id}/comments",
            headers=agent_headers,
            json={"content": "Internal agent note.", "is_internal": True},
        )
        assert resp.status_code == 201
        assert resp.get_json()["data"]["is_internal"] is True

    def test_customer_cannot_see_internal_comments(self, client, db, sample_ticket, agent_headers, customer_headers):
        """FR-016: Internal comments hidden from customers."""
        client.post(
            f"/api/tickets/{sample_ticket.id}/comments",
            headers=agent_headers,
            json={"content": "Secret internal note.", "is_internal": True},
        )
        resp = client.get(f"/api/tickets/{sample_ticket.id}/comments", headers=customer_headers)
        assert resp.status_code == 200
        for c in resp.get_json()["data"]:
            assert c["is_internal"] is False

    def test_get_comments_chronological_order(self, client, db, sample_ticket, customer_headers):
        """FR-019: Comments ordered chronologically."""
        for msg in ["First comment text.", "Second comment text.", "Third comment text."]:
            client.post(
                f"/api/tickets/{sample_ticket.id}/comments",
                headers=customer_headers,
                json={"content": msg},
            )
        resp = client.get(f"/api/tickets/{sample_ticket.id}/comments", headers=customer_headers)
        assert resp.status_code == 200
        comments = resp.get_json()["data"]
        assert len(comments) >= 3
