"""
Tests: Checkout & Payment Processing (FR 5.5)
Covers CHK-FR-001 to CHK-FR-013, TC-P-008 to TC-P-012, TC-N-001 to TC-N-010,
TC-E-001/003/008/010, TC-S-007/010.
"""
import pytest
from tests.conftest import auth_headers, csrf_headers

PROD_ID = "prod-001-000-000"
CHEAP_PROD_ID = "prod-cheap-0-000"

VALID_SHIPPING = {
    "firstName": "John",
    "lastName": "Doe",
    "email": "john.doe@example.com",
    "street": "123 Main St",
    "city": "Austin",
    "state": "TX",
    "zip": "78701",
    "country": "US",
}


def _add_item(client, token, product_id=PROD_ID, qty=1):
    return client.post(
        "/api/v1/cart/items",
        json={"productId": product_id, "quantity": qty},
        headers=auth_headers(token),
    )


def _clear_cart(client, token):
    cart = client.get("/api/v1/cart", headers=auth_headers(token)).get_json()
    for item in cart.get("items", []):
        client.delete(f"/api/v1/cart/items/{item['id']}", headers=auth_headers(token))
    client.delete("/api/v1/cart/discount", headers=auth_headers(token))


class TestCheckoutSuccess:
    def test_checkout_with_valid_visa(self, client, user_token, user_csrf):
        """TC-P-008 – valid Visa token returns 201 with orderId."""
        _clear_cart(client, user_token)
        _add_item(client, user_token)
        resp = client.post(
            "/api/v1/checkout",
            json={
                "shippingAddress": VALID_SHIPPING,
                "paymentToken": "tok_visa",
            },
            headers=csrf_headers(user_token, user_csrf),
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert "orderId" in data
        assert "confirmationNumber" in data
        assert data["total"] > 0

    def test_checkout_with_paypal(self, client, user_token, user_csrf):
        """TC-P-010 – PayPal token returns 201."""
        _clear_cart(client, user_token)
        _add_item(client, user_token)
        resp = client.post(
            "/api/v1/checkout",
            json={
                "shippingAddress": VALID_SHIPPING,
                "paypalToken": "paypal-test-token",
            },
            headers=csrf_headers(user_token, user_csrf),
        )
        assert resp.status_code == 201

    def test_checkout_free_item_no_payment_required(self, client, user_token, user_csrf):
        """TC-E-008 – discount brings total to $0; no payment method needed."""
        _clear_cart(client, user_token)
        _add_item(client, user_token, product_id=CHEAP_PROD_ID)  # $5 item
        # Apply $20 off coupon → total = $0
        client.post(
            "/api/v1/cart/discount",
            json={"code": "TWENTY_OFF"},
            headers=auth_headers(user_token),
        )
        resp = client.post(
            "/api/v1/checkout",
            json={"shippingAddress": VALID_SHIPPING},  # no paymentToken
            headers=csrf_headers(user_token, user_csrf),
        )
        assert resp.status_code == 201
        assert resp.get_json()["total"] == 0.0


class TestCheckoutPaymentFailures:
    def test_declined_card(self, client, user_token, user_csrf):
        """TC-N-001 – declined card returns 402; no order created."""
        _clear_cart(client, user_token)
        _add_item(client, user_token)
        resp = client.post(
            "/api/v1/checkout",
            json={
                "shippingAddress": VALID_SHIPPING,
                "paymentToken": "tok_declined",
            },
            headers=csrf_headers(user_token, user_csrf),
        )
        assert resp.status_code == 402
        assert "declined" in resp.get_json()["error"].lower()

    def test_insufficient_funds(self, client, user_token, user_csrf):
        """TC-N-001 variant – insufficient funds token returns 402."""
        _clear_cart(client, user_token)
        _add_item(client, user_token)
        resp = client.post(
            "/api/v1/checkout",
            json={
                "shippingAddress": VALID_SHIPPING,
                "paymentToken": "tok_insufficient_funds",
            },
            headers=csrf_headers(user_token, user_csrf),
        )
        assert resp.status_code == 402
        assert "insufficient" in resp.get_json()["error"].lower()

    def test_expired_card(self, client, user_token, user_csrf):
        """TC-N-002 – expired card token returns 402."""
        _clear_cart(client, user_token)
        _add_item(client, user_token)
        resp = client.post(
            "/api/v1/checkout",
            json={
                "shippingAddress": VALID_SHIPPING,
                "paymentToken": "tok_expired_card",
            },
            headers=csrf_headers(user_token, user_csrf),
        )
        assert resp.status_code == 402
        assert "expired" in resp.get_json()["error"].lower()

    def test_wrong_cvv(self, client, user_token, user_csrf):
        """TC-N-003 – wrong CVV token returns 402."""
        _clear_cart(client, user_token)
        _add_item(client, user_token)
        resp = client.post(
            "/api/v1/checkout",
            json={
                "shippingAddress": VALID_SHIPPING,
                "paymentToken": "tok_wrong_cvv",
            },
            headers=csrf_headers(user_token, user_csrf),
        )
        assert resp.status_code == 402
        assert "security code" in resp.get_json()["error"].lower()


class TestCheckoutValidation:
    def test_empty_cart_returns_400(self, client, user_token, user_csrf):
        """TC-E-001, CHK-FR-002 – checkout with empty cart returns 400."""
        _clear_cart(client, user_token)
        resp = client.post(
            "/api/v1/checkout",
            json={"shippingAddress": VALID_SHIPPING, "paymentToken": "tok_visa"},
            headers=csrf_headers(user_token, user_csrf),
        )
        assert resp.status_code == 400
        assert "empty" in resp.get_json()["error"].lower()

    def test_missing_shipping_address(self, client, user_token, user_csrf):
        """TC-N-008, CHK-FR-004 – missing shipping address returns 400."""
        _clear_cart(client, user_token)
        _add_item(client, user_token)
        resp = client.post(
            "/api/v1/checkout",
            json={"paymentToken": "tok_visa"},
            headers=csrf_headers(user_token, user_csrf),
        )
        assert resp.status_code == 400

    def test_unauthenticated_checkout_returns_401(self, client):
        """CHK-FR-001 – guest user cannot checkout."""
        resp = client.post(
            "/api/v1/checkout",
            json={"shippingAddress": VALID_SHIPPING, "paymentToken": "tok_visa"},
            headers={"X-CSRF-Token": "any"},
        )
        assert resp.status_code == 401


class TestCheckoutSecurity:
    def test_csrf_missing_returns_403(self, client, user_token):
        """TC-S-007 – checkout without X-CSRF-Token header returns 403."""
        _clear_cart(client, user_token)
        _add_item(client, user_token)
        resp = client.post(
            "/api/v1/checkout",
            json={"shippingAddress": VALID_SHIPPING, "paymentToken": "tok_visa"},
            headers=auth_headers(user_token),  # no X-CSRF-Token
        )
        assert resp.status_code == 403

    def test_csrf_invalid_returns_403(self, client, user_token):
        """TC-S-007 – checkout with wrong CSRF token returns 403."""
        _clear_cart(client, user_token)
        _add_item(client, user_token)
        resp = client.post(
            "/api/v1/checkout",
            json={"shippingAddress": VALID_SHIPPING, "paymentToken": "tok_visa"},
            headers={**auth_headers(user_token), "X-CSRF-Token": "INVALID_CSRF_TOKEN"},
        )
        assert resp.status_code == 403

    def test_price_manipulation_rejected(self, client, user_token, user_csrf):
        """TC-S-010 – client-submitted total is ignored; server uses correct price."""
        _clear_cart(client, user_token)
        _add_item(client, user_token)
        resp = client.post(
            "/api/v1/checkout",
            json={
                "shippingAddress": VALID_SHIPPING,
                "paymentToken": "tok_visa",
                "tamperedTotal": -1,   # should be completely ignored
            },
            headers=csrf_headers(user_token, user_csrf),
        )
        # Order should succeed and have the real price (not -1)
        assert resp.status_code == 201
        assert resp.get_json()["total"] > 0

    def test_pci_card_not_in_order(self, client, user_token, user_csrf):
        """TC-S-004 – raw card number must never appear in stored order."""
        _clear_cart(client, user_token)
        _add_item(client, user_token)
        resp = client.post(
            "/api/v1/checkout",
            json={"shippingAddress": VALID_SHIPPING, "paymentToken": "tok_visa"},
            headers=csrf_headers(user_token, user_csrf),
        )
        assert resp.status_code == 201
        order_id = resp.get_json()["orderId"]

        order_resp = client.get(
            f"/api/v1/orders/{order_id}", headers=auth_headers(user_token)
        )
        order = order_resp.get_json()
        # Payment method should contain only token and last4, NOT a full card number
        pm = order.get("paymentMethod", {})
        assert "4242424242424242" not in str(pm)
        assert "cvv" not in str(pm).lower()


class TestCheckoutIdempotency:
    def test_idempotency_key_prevents_duplicate_orders(self, client, user_token, user_csrf):
        """TC-E-010 – same idempotencyKey returns the same orderId without double-charging."""
        _clear_cart(client, user_token)
        _add_item(client, user_token)

        idem_key = "test-idem-key-unique-12345"
        first = client.post(
            "/api/v1/checkout",
            json={
                "shippingAddress": VALID_SHIPPING,
                "paymentToken": "tok_visa",
                "idempotencyKey": idem_key,
            },
            headers=csrf_headers(user_token, user_csrf),
        )
        assert first.status_code == 201
        first_order_id = first.get_json()["orderId"]

        # Second submission with same key
        second = client.post(
            "/api/v1/checkout",
            json={
                "shippingAddress": VALID_SHIPPING,
                "paymentToken": "tok_visa",
                "idempotencyKey": idem_key,
            },
            headers=csrf_headers(user_token, user_csrf),
        )
        assert second.status_code in (200, 201)
        assert second.get_json()["orderId"] == first_order_id
