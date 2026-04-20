"""
Integration tests for Celery email tasks (FR-035).
Tasks run eagerly (CELERY_TASK_ALWAYS_EAGER=True) in the test config.
"""
import pytest
from unittest.mock import patch, MagicMock


class TestEmailTasks:
    def test_send_ticket_created_email_called(self, app, db, sample_ticket):
        """FR-003: Email sent when ticket is created."""
        from app.tasks.email_tasks import send_ticket_created_email
        with patch("app.tasks.email_tasks._send_email") as mock_email:
            send_ticket_created_email(sample_ticket.id)
        mock_email.assert_called_once()
        args = mock_email.call_args[0]
        assert sample_ticket.customer_email == args[0]
        assert sample_ticket.ticket_number in args[1]

    def test_send_assignment_email_called(self, app, db, sample_ticket, agent_user):
        """FR-007: Agent notified on assignment."""
        from app.tasks.email_tasks import send_assignment_email
        with patch("app.tasks.email_tasks._send_email") as mock_email:
            send_assignment_email(sample_ticket.id, agent_user.id)
        mock_email.assert_called_once()
        args = mock_email.call_args[0]
        assert agent_user.email == args[0]

    def test_send_status_change_email(self, app, db, sample_ticket):
        """FR-014: Customer notified on status change."""
        from app.tasks.email_tasks import send_status_change_email
        with patch("app.tasks.email_tasks._send_email") as mock_email:
            send_status_change_email(sample_ticket.id, "open", "assigned")
        mock_email.assert_called()
        recipients = [call[0][0] for call in mock_email.call_args_list]
        assert sample_ticket.customer_email in recipients

    def test_check_sla_deadlines_runs(self, app, db, admin_user, sample_ticket):
        """FR-021, FR-022: SLA check task escalates overdue tickets to admins."""
        from app.tasks.email_tasks import check_sla_deadlines
        from datetime import datetime, timezone, timedelta
        # Push the SLA deadline into the past so the ticket is "missed"
        sample_ticket.sla_resolution_due = datetime.now(timezone.utc) - timedelta(hours=1)
        db.session.commit()
        # db fixture already provides an active app context; run task directly
        with patch("app.tasks.email_tasks._send_email") as mock_email:
            check_sla_deadlines()
        # admin_user should receive the escalation email
        assert mock_email.called  # Escalation email sent for overdue ticket

    def test_send_comment_notification(self, app, db, sample_ticket, customer_user, agent_user):
        """FR-018: Comment notification sent to relevant parties."""
        from app.tasks.email_tasks import send_comment_notification
        from app.models.comment import Comment
        comment = Comment(
            ticket_id=sample_ticket.id,
            user_id=agent_user.id,
            content="Here is an update on your issue.",
            is_internal=False,
        )
        db.session.add(comment)
        db.session.commit()

        with patch("app.tasks.email_tasks._send_email") as mock_email:
            send_comment_notification(comment.id)
        mock_email.assert_called()
