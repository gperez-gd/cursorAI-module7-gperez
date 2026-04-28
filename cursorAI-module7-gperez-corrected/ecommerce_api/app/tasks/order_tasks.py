"""
Celery tasks for order lifecycle events.

Start a worker locally:
    celery -A app.tasks.order_tasks worker --loglevel=info
"""

from __future__ import annotations

import logging

from ..extensions import celery

logger = logging.getLogger(__name__)


def _send_email(to: str, subject: str, body: str) -> None:
    """Placeholder email dispatcher — swap for SendGrid / SES / SMTP."""
    logger.info("EMAIL to=%s  subject=%r\n%s", to, subject, body)


@celery.task(bind=True, max_retries=3, default_retry_delay=60, name="orders.send_confirmation")
def send_order_confirmation(self, order_id: str, user_email: str, confirmation_number: str | None = None) -> dict:
    """
    Send an order-confirmation email after a successful checkout.

    Retried up to 3 times (60-second back-off) on transient failures.
    Returns a status dict so the result can be inspected in tests.
    """
    try:
        ref = confirmation_number or order_id
        subject = f"Order {ref} confirmed"
        body = (
            f"Hi,\n\n"
            f"Your order {ref} has been placed successfully.\n"
            f"We will notify you when it ships.\n\n"
            f"Thank you for shopping with us!"
        )
        _send_email(user_email, subject, body)
        logger.info("Order confirmation sent: order_id=%s email=%s", order_id, user_email)
        return {"status": "sent", "order_id": order_id, "email": user_email}
    except Exception as exc:
        logger.error("Failed to send confirmation for order %s: %s", order_id, exc)
        raise self.retry(exc=exc)
