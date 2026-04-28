"""
Payment simulation layer.

In production this would call Stripe/PayPal. Here we map token values
to deterministic outcomes so the full checkout flow can be tested
without a live gateway.

Token → Outcome mapping (mirrors Stripe's test-mode conventions):
  tok_visa              → success  (Visa 4242, last4=4242)
  tok_mastercard        → success  (Mastercard 5555, last4=4444)
  tok_paypal            → success  (PayPal)
  tok_declined          → generic decline
  tok_insufficient_funds→ insufficient funds
  tok_expired_card      → expired card
  tok_wrong_cvv         → incorrect security code
  tok_lost_card         → lost/stolen card
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass
class PaymentResult:
    success: bool
    token: str | None = None
    last4: str | None = None
    type: str | None = None
    error: str | None = None


_TOKEN_MAP: dict[str, PaymentResult] = {
    "tok_visa": PaymentResult(
        success=True, token="ch_visa_" + uuid.uuid4().hex[:8],
        last4="4242", type="card"
    ),
    "tok_mastercard": PaymentResult(
        success=True, token="ch_mc_" + uuid.uuid4().hex[:8],
        last4="4444", type="card"
    ),
    "tok_paypal": PaymentResult(
        success=True, token="pp_" + uuid.uuid4().hex[:8],
        last4=None, type="paypal"
    ),
    "tok_declined": PaymentResult(
        success=False, error="Your card has been declined."
    ),
    "tok_insufficient_funds": PaymentResult(
        success=False, error="Your card has insufficient funds."
    ),
    "tok_expired_card": PaymentResult(
        success=False, error="Your card has expired."
    ),
    "tok_wrong_cvv": PaymentResult(
        success=False, error="Security code incorrect."
    ),
    "tok_lost_card": PaymentResult(
        success=False, error="Your card has been declined."
    ),
}


class PaymentService:
    @staticmethod
    def process(
        *,
        payment_token: str | None,
        paypal_token: str | None,
        saved_card_id: str | None,
        amount: float,
    ) -> PaymentResult:
        # PayPal path
        if paypal_token:
            return PaymentResult(
                success=True,
                token="pp_" + uuid.uuid4().hex[:10],
                last4=None,
                type="paypal",
            )

        # Saved card path  (simplified – just confirm success)
        if saved_card_id:
            return PaymentResult(
                success=True,
                token="ch_saved_" + uuid.uuid4().hex[:8],
                last4="0000",
                type="saved_card",
            )

        # Token-based path
        if payment_token:
            result = _TOKEN_MAP.get(payment_token)
            if result is None:
                return PaymentResult(success=False, error="Your card has been declined.")
            # Return a fresh copy so the singleton token isn't mutated
            if result.success:
                return PaymentResult(
                    success=True,
                    token="ch_" + uuid.uuid4().hex[:12],
                    last4=result.last4,
                    type=result.type,
                )
            return PaymentResult(success=False, error=result.error)

        return PaymentResult(success=False, error="No payment method provided.")
