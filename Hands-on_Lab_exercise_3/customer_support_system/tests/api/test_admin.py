"""API tests for Admin endpoints (FR-029, FR-030, FR-031)."""
import pytest


class TestDashboard:
    def test_admin_can_access_dashboard(self, client, db, sample_ticket, admin_headers):
        resp = client.get("/api/admin/dashboard", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert "total_tickets" in data
        assert "by_status" in data
        assert "by_priority" in data
        assert "sla_compliance_rate" in data or data.get("sla_compliance_rate") is None

    def test_non_admin_cannot_access_dashboard(self, client, db, agent_headers):
        resp = client.get("/api/admin/dashboard", headers=agent_headers)
        assert resp.status_code == 403

    def test_customer_cannot_access_dashboard(self, client, db, customer_headers):
        resp = client.get("/api/admin/dashboard", headers=customer_headers)
        assert resp.status_code == 403


class TestReports:
    def test_ticket_report(self, client, db, sample_ticket, admin_headers):
        resp = client.get("/api/admin/reports/tickets?days=30", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert "tickets" in data
        assert "count" in data

    def test_agent_report(self, client, db, agent_user, admin_headers):
        resp = client.get("/api/admin/reports/agents", headers=admin_headers)
        assert resp.status_code == 200
        agents = resp.get_json()["data"]
        assert isinstance(agents, list)

    def test_sla_report(self, client, db, admin_headers):
        resp = client.get("/api/admin/reports/sla", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        for priority in ["low", "medium", "high", "urgent"]:
            assert priority in data

    def test_export_csv(self, client, db, sample_ticket, admin_headers):
        """FR-031: Export report to CSV."""
        resp = client.post(
            "/api/admin/reports/export",
            headers=admin_headers,
            json={"days": 30},
        )
        assert resp.status_code == 200
        assert "text/csv" in resp.content_type
        content = resp.data.decode("utf-8")
        assert "Ticket #" in content
        assert sample_ticket.ticket_number in content
