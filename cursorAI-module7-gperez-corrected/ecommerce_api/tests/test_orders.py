"""
Tests: Order Management (FR 5.6)
Covers ORD-FR-001 to ORD-FR-008 and ORDER-001 to ORDER-005.
"""
import pytest
from tests.conftest import auth_headers, csrf_headers

PROD_ID = "prod-001-000-000"

VALID_SHIPPING = {
    "firstName": "Alice",
    "lastName": "Smith",
    "email": "alice@example.com",
    "street": "99 Oak St",
    "city": "Dallas",
    "state": "TX",
    "zip": "75201",
    "country": "US",
}


def _place_order(client, user_token, user_csrf) -> str:
    """Helper: place a single-item order and return the orderId."""
    # Ensure cart has an item
    cart = client.get("/api/v1/cart", headers=auth_headers(user_token)).get_json()
    for item in cart.get("items", []):
        client.delete(f"/api/v1/cart/items/{item['id']}", headers=auth_headers(user_token))
    client.post(
        "/api/v1/cart/items",
        json={"productId": PROD_ID, "quantity": 1},
        headers=auth_headers(user_token),
    )
    resp = client.post(
        "/api/v1/checkout",
        json={"shippingAddress": VALID_SHIPPING, "paymentToken": "tok_visa"},
        headers=csrf_headers(user_token, user_csrf),
    )
    assert resp.status_code == 201, resp.get_json()
    return resp.get_json()["orderId"]


class TestListOrders:
    def test_list_own_orders(self, client, user_token, user_csrf):
        """ORD-FR-001, ORDER-003 – authenticated user sees their orders."""
        _place_order(client, user_token, user_csrf)
        resp = client.get("/api/v1/orders", headers=auth_headers(user_token))
        assert resp.status_code == 200
        data = resp.get_json()
        assert "orders" in data
        assert isinstance(data["orders"], list)
        assert data["total"] >= 1

    def test_list_orders_unauthenticated(self, client):
        """Unauthenticated request returns 401."""
        resp = client.get("/api/v1/orders")
        assert resp.status_code == 401


class TestGetOrder:
    def test_get_own_order(self, client, user_token, user_csrf):
        """ORD-FR-002, ORDER-002 – user retrieves their own order."""
        order_id = _place_order(client, user_token, user_csrf)
        resp = client.get(f"/api/v1/orders/{order_id}", headers=auth_headers(user_token))
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["orderId"] == order_id
        assert "items" in data
        assert "shippingAddress" in data
        assert "paymentMethod" in data
        assert data["status"] == "Processing"

    def test_get_nonexistent_order(self, client, user_token):
        """ERR-002 – nonexistent order returns 404."""
        resp = client.get(
            "/api/v1/orders/does-not-exist-99999", headers=auth_headers(user_token)
        )
        assert resp.status_code == 404

    def test_get_other_users_order_returns_403(self, client, user_token, user2_token, user_csrf):
        """ORD-FR-003, SEC-006 – user cannot access another user's order."""
        # Create an order belonging to user2
        user2_resp = client.post(
            "/api/v1/auth/login",
            json={"email": "user2@example.com", "password": "User1234!"},
        )
        user2_data = user2_resp.get_json()
        u2_token = user2_data["token"]
        u2_csrf = user2_data["csrfToken"]

        order_id = _place_order(client, u2_token, u2_csrf)

        # user (not user2) tries to access user2's order
        resp = client.get(f"/api/v1/orders/{order_id}", headers=auth_headers(user_token))
        assert resp.status_code == 403


class TestAdminOrderManagement:
    def test_admin_update_order_status(self, client, user_token, user_csrf, admin_token):
        """ORD-FR-005, ORDER-004 – admin updates order status to Shipped."""
        order_id = _place_order(client, user_token, user_csrf)
        resp = client.put(
            f"/api/v1/orders/{order_id}",
            json={"status": "Shipped"},
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "Shipped"

    def test_admin_update_invalid_status(self, client, user_token, user_csrf, admin_token):
        """Invalid status value returns 400."""
        order_id = _place_order(client, user_token, user_csrf)
        resp = client.put(
            f"/api/v1/orders/{order_id}",
            json={"status": "FLYING"},
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 400

    def test_admin_cancel_order(self, client, user_token, user_csrf, admin_token):
        """ORD-FR-006, ORDER-005 – admin cancels an order."""
        order_id = _place_order(client, user_token, user_csrf)
        resp = client.delete(
            f"/api/v1/orders/{order_id}", headers=auth_headers(admin_token)
        )
        assert resp.status_code == 200

        # Verify status changed
        get_resp = client.get(
            f"/api/v1/orders/{order_id}", headers=auth_headers(admin_token)
        )
        assert get_resp.get_json()["status"] == "Cancelled"

    def test_user_cannot_update_order_status(self, client, user_token, user_csrf):
        """Regular user cannot update order status (403)."""
        order_id = _place_order(client, user_token, user_csrf)
        resp = client.put(
            f"/api/v1/orders/{order_id}",
            json={"status": "Shipped"},
            headers=auth_headers(user_token),
        )
        assert resp.status_code == 403


class TestOrderContents:
    def test_order_has_required_fields(self, client, user_token, user_csrf):
        """ORD-FR-004 – order object contains all required fields."""
        order_id = _place_order(client, user_token, user_csrf)
        resp = client.get(f"/api/v1/orders/{order_id}", headers=auth_headers(user_token))
        data = resp.get_json()

        required_fields = [
            "orderId", "status", "items", "shippingAddress",
            "paymentMethod", "subtotal", "discount", "total",
            "estimatedDelivery", "createdAt",
        ]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"

    def test_order_initial_status_is_processing(self, client, user_token, user_csrf):
        """ORD-FR-008 – freshly created order has status Processing."""
        order_id = _place_order(client, user_token, user_csrf)
        resp = client.get(f"/api/v1/orders/{order_id}", headers=auth_headers(user_token))
        assert resp.get_json()["status"] == "Processing"
