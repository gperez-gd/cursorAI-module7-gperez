"""
Asynchronous Celery tasks for email notifications (FR-035).

All tasks retry up to 3 times with exponential back-off on transient failures.
"""
import logging
from datetime import datetime, timezone

from ..extensions import celery

logger = logging.getLogger(__name__)


def _send_email(to: str, subject: str, body: str):
    """Low-level email sender — replace with real SMTP/SendGrid integration."""
    logger.info("EMAIL → %s | Subject: %s", to, subject)
    # In production wire up Flask-Mail or a transactional email service here.
    return True


@celery.task(bind=True, max_retries=3, default_retry_delay=60)
def send_ticket_created_email(self, ticket_id: int):
    """FR-003: Notify customer when a ticket is created."""
    try:
        from ..models.ticket import Ticket
        ticket = Ticket.query.get(ticket_id)
        if not ticket:
            logger.warning("send_ticket_created_email: ticket %s not found", ticket_id)
            return

        subject = f"[Support] Ticket {ticket.ticket_number} created"
        body = (
            f"Dear Customer,\n\n"
            f"Your support ticket has been created successfully.\n\n"
            f"Ticket Number: {ticket.ticket_number}\n"
            f"Subject: {ticket.subject}\n"
            f"Priority: {ticket.priority.value}\n\n"
            f"We will get back to you as soon as possible.\n\n"
            f"Support Team"
        )
        _send_email(ticket.customer_email, subject, body)
        logger.info("Ticket created email sent for %s", ticket.ticket_number)
    except Exception as exc:
        logger.error("send_ticket_created_email failed: %s", exc)
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@celery.task(bind=True, max_retries=3, default_retry_delay=60)
def send_assignment_email(self, ticket_id: int, agent_id: int):
    """FR-007: Notify assigned agent."""
    try:
        from ..models.ticket import Ticket
        from ..models.user import User

        ticket = Ticket.query.get(ticket_id)
        agent = User.query.get(agent_id)
        if not ticket or not agent:
            return

        subject = f"[Support] Ticket {ticket.ticket_number} assigned to you"
        body = (
            f"Hi {agent.name},\n\n"
            f"A new ticket has been assigned to you.\n\n"
            f"Ticket: {ticket.ticket_number}\n"
            f"Subject: {ticket.subject}\n"
            f"Priority: {ticket.priority.value}\n"
            f"Category: {ticket.category.value}\n\n"
            f"Please log in to the portal to review.\n\nSupport Team"
        )
        _send_email(agent.email, subject, body)
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@celery.task(bind=True, max_retries=3, default_retry_delay=60)
def send_status_change_email(self, ticket_id: int, old_status: str, new_status: str):
    """FR-014: Notify customer and assigned agent on status changes."""
    try:
        from ..models.ticket import Ticket

        ticket = Ticket.query.get(ticket_id)
        if not ticket:
            return

        subject = f"[Support] Ticket {ticket.ticket_number} status updated"
        body = (
            f"Ticket {ticket.ticket_number} status changed:\n"
            f"  {old_status.upper()} → {new_status.upper()}\n\n"
            f"Subject: {ticket.subject}\n\nSupport Team"
        )
        recipients = [ticket.customer_email]
        if ticket.assigned_to:
            recipients.append(ticket.assigned_to.email)

        for email in set(recipients):
            _send_email(email, subject, body)
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@celery.task(bind=True, max_retries=3, default_retry_delay=60)
def send_comment_notification(self, comment_id: int):
    """FR-018: Notify relevant parties when a new comment is added."""
    try:
        from ..models.comment import Comment

        comment = Comment.query.get(comment_id)
        if not comment:
            return

        ticket = comment.ticket
        author = comment.author

        if comment.is_internal:
            # Internal notes only go to agents/admins — skip customer
            return

        subject = f"[Support] New update on Ticket {ticket.ticket_number}"
        body = (
            f"A new comment has been added to Ticket {ticket.ticket_number}.\n\n"
            f"From: {author.name}\n"
            f"Message: {comment.content[:500]}\n\nSupport Team"
        )
        recipients = [ticket.customer_email]
        if ticket.assigned_to and ticket.assigned_to.id != author.id:
            recipients.append(ticket.assigned_to.email)

        for email in set(recipients):
            _send_email(email, subject, body)
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@celery.task
def check_sla_deadlines():
    """
    FR-021, FR-022: Periodic task (every 15 min) to flag approaching SLA
    deadlines and trigger escalation for missed SLAs.
    """
    from ..models.ticket import Ticket, TicketStatus
    from ..models.user import User, UserRole

    now = datetime.now(timezone.utc)

    open_statuses = [
        TicketStatus.OPEN,
        TicketStatus.ASSIGNED,
        TicketStatus.IN_PROGRESS,
        TicketStatus.WAITING,
        TicketStatus.REOPENED,
    ]

    tickets = Ticket.query.filter(Ticket.status.in_(open_statuses)).all()

    admins = User.query.filter_by(role=UserRole.ADMIN, is_active=True).all()
    admin_emails = [a.email for a in admins]

    for ticket in tickets:
        if ticket.is_sla_missed():
            _escalate_sla_missed(ticket, admin_emails)
        elif ticket.is_sla_resolution_approaching() or ticket.is_sla_response_approaching():
            _warn_sla_approaching(ticket, admin_emails)

    logger.info("SLA check completed. Checked %d tickets.", len(tickets))


def _escalate_sla_missed(ticket, admin_emails):
    """FR-022: Escalate tickets that have missed SLA."""
    subject = f"[ESCALATION] SLA Missed – Ticket {ticket.ticket_number}"
    body = (
        f"The following ticket has exceeded its SLA resolution deadline.\n\n"
        f"Ticket: {ticket.ticket_number}\n"
        f"Priority: {ticket.priority.value}\n"
        f"Status: {ticket.status.value}\n"
        f"SLA Due: {ticket.sla_resolution_due}\n\n"
        f"Immediate action required."
    )
    recipients = list(admin_emails)
    if ticket.assigned_to:
        recipients.append(ticket.assigned_to.email)
    for email in set(recipients):
        _send_email(email, subject, body)


def _warn_sla_approaching(ticket, admin_emails):
    """FR-021: Warn when SLA deadline is approaching."""
    subject = f"[WARNING] SLA Approaching – Ticket {ticket.ticket_number}"
    body = (
        f"Ticket {ticket.ticket_number} is approaching its SLA deadline.\n\n"
        f"Priority: {ticket.priority.value}\n"
        f"Resolution Due: {ticket.sla_resolution_due}\n\n"
        f"Please take action soon."
    )
    recipients = list(admin_emails)
    if ticket.assigned_to:
        recipients.append(ticket.assigned_to.email)
    for email in set(recipients):
        _send_email(email, subject, body)
