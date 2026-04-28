"""
Tests: Shopping Cart & Discounts (FR 5.3, 5.4)
Covers TC-P-001 to TC-P-007 and TC-N-005 to TC-N-007.
"""
import pytest
from tests.conftest import auth_headers


PROD_ID = "prod-001-000-000"
CHEAP_PROD_ID = "prod-cheap-0-000"
OOS_PROD_ID = "prod-oos-00-000"


def _clear_cart(client, token):
    """Helper: remove all items from the user's cart."""
    cart = client.get("/api/v1/cart", headers=auth_headers(token)).get_json()
    for item in cart.get("items", []):
        client.delete(f"/api/v1/cart/items/{item['id']}", headers=auth_headers(token))
    # Also remove any discount
    client.delete("/api/v1/cart/discount", headers=auth_headers(token))


class TestGetCart:
    def test_get_empty_cart(self, client, user2_token):
        """CART-FR-006 – GET /cart returns empty items array for new user."""
        _clear_cart(client, user2_token)
        resp = client.get("/api/v1/cart", headers=auth_headers(user2_token))
        assert resp.status_code == 200
        data = resp.get_json()
        assert "items" in data
        assert data["subtotal"] == 0.0
        assert data["total"] == 0.0


class TestAddItem:
    def test_add_single_item(self, client, user_token):
        """TC-P-001 – add one in-stock item returns cart with quantity 1."""
        _clear_cart(client, user_token)
        resp = client.post(
            "/api/v1/cart/items",
            json={"productId": PROD_ID, "quantity": 1},
            headers=auth_headers(user_token),
        )
        assert resp.status_code == 200
        cart = resp.get_json()
        assert len(cart["items"]) == 1
        assert cart["items"][0]["productId"] == PROD_ID
        assert cart["items"][0]["quantity"] == 1

    def test_add_multiple_items(self, client, user_token):
        """TC-P-002 – add two distinct items; cart contains both."""
        _clear_cart(client, user_token)
        client.post(
            "/api/v1/cart/items",
            json={"productId": PROD_ID, "quantity": 1},
            headers=auth_headers(user_token),
        )
        resp = client.post(
            "/api/v1/cart/items",
            json={"productId": CHEAP_PROD_ID, "quantity": 1},
            headers=auth_headers(user_token),
        )
        cart = resp.get_json()
        product_ids = [i["productId"] for i in cart["items"]]
        assert PROD_ID in product_ids
        assert CHEAP_PROD_ID in product_ids

    def test_add_out_of_stock_item(self, client, user_token):
        """CART-FR-008 – out-of-stock item returns 400."""
        _clear_cart(client, user_token)
        resp = client.post(
            "/api/v1/cart/items",
            json={"productId": OOS_PROD_ID, "quantity": 1},
            headers=auth_headers(user_token),
        )
        assert resp.status_code == 400

    def test_add_nonexistent_product(self, client, user_token):
        """Adding a non-existent product returns 404."""
        _clear_cart(client, user_token)
        resp = client.post(
            "/api/v1/cart/items",
            json={"productId": "does-not-exist", "quantity": 1},
            headers=auth_headers(user_token),
        )
        assert resp.status_code == 404


class TestUpdateItem:
    def test_update_quantity(self, client, user_token):
        """TC-P-003 – updating quantity recalculates subtotal."""
        _clear_cart(client, user_token)
        add_resp = client.post(
            "/api/v1/cart/items",
            json={"productId": PROD_ID, "quantity": 1},
            headers=auth_headers(user_token),
        )
        item_id = add_resp.get_json()["items"][0]["id"]
        initial_total = add_resp.get_json()["subtotal"]

        update_resp = client.put(
            f"/api/v1/cart/items/{item_id}",
            json={"quantity": 3},
            headers=auth_headers(user_token),
        )
        assert update_resp.status_code == 200
        updated = update_resp.get_json()
        assert updated["items"][0]["quantity"] == 3
        assert updated["subtotal"] > initial_total

    def test_quantity_limit_exceeded(self, client, user_token):
        """TC-E-004, CART-FR-007 – setting qty > 10 returns 400."""
        _clear_cart(client, user_token)
        add_resp = client.post(
            "/api/v1/cart/items",
            json={"productId": PROD_ID, "quantity": 1},
            headers=auth_headers(user_token),
        )
        item_id = add_resp.get_json()["items"][0]["id"]

        resp = client.put(
            f"/api/v1/cart/items/{item_id}",
            json={"quantity": 11},
            headers=auth_headers(user_token),
        )
        assert resp.status_code == 400
        assert "maximum quantity" in resp.get_json()["error"].lower()


class TestRemoveItem:
    def test_remove_item(self, client, user_token):
        """TC-P-004 – removing an item leaves the other item in the cart."""
        _clear_cart(client, user_token)
        client.post(
            "/api/v1/cart/items",
            json={"productId": PROD_ID, "quantity": 1},
            headers=auth_headers(user_token),
        )
        add_resp = client.post(
            "/api/v1/cart/items",
            json={"productId": CHEAP_PROD_ID, "quantity": 1},
            headers=auth_headers(user_token),
        )
        items = add_resp.get_json()["items"]
        item_to_remove = next(i for i in items if i["productId"] == PROD_ID)

        del_resp = client.delete(
            f"/api/v1/cart/items/{item_to_remove['id']}",
            headers=auth_headers(user_token),
        )
        assert del_resp.status_code == 200
        remaining_ids = [i["productId"] for i in del_resp.get_json()["items"]]
        assert PROD_ID not in remaining_ids
        assert CHEAP_PROD_ID in remaining_ids


class TestDiscountCodes:
    def test_apply_percentage_discount(self, client, user_token):
        """TC-P-005 – SAVE10 applies 10 % discount to subtotal."""
        _clear_cart(client, user_token)
        add_resp = client.post(
            "/api/v1/cart/items",
            json={"productId": PROD_ID, "quantity": 1},
            headers=auth_headers(user_token),
        )
        subtotal = add_resp.get_json()["subtotal"]

        disc_resp = client.post(
            "/api/v1/cart/discount",
            json={"code": "SAVE10"},
            headers=auth_headers(user_token),
        )
        assert disc_resp.status_code == 200
        cart = disc_resp.get_json()
        expected_total = round(subtotal * 0.9, 2)
        assert round(cart["total"], 2) == expected_total

    def test_apply_fixed_discount(self, client, user_token):
        """TC-P-006 – FLAT5 deducts $5 from subtotal."""
        _clear_cart(client, user_token)
        client.post(
            "/api/v1/cart/items",
            json={"productId": PROD_ID, "quantity": 1},
            headers=auth_headers(user_token),
        )
        disc_resp = client.post(
            "/api/v1/cart/discount",
            json={"code": "FLAT5"},
            headers=auth_headers(user_token),
        )
        assert disc_resp.status_code == 200
        cart = disc_resp.get_json()
        assert cart["discount"] == 5.0

    def test_remove_discount(self, client, user_token):
        """TC-P-007 – removing discount restores original subtotal."""
        _clear_cart(client, user_token)
        client.post(
            "/api/v1/cart/items",
            json={"productId": PROD_ID, "quantity": 1},
            headers=auth_headers(user_token),
        )
        client.post(
            "/api/v1/cart/discount",
            json={"code": "SAVE10"},
            headers=auth_headers(user_token),
        )
        rem_resp = client.delete(
            "/api/v1/cart/discount", headers=auth_headers(user_token)
        )
        assert rem_resp.status_code == 200
        cart = rem_resp.get_json()
        assert cart["discount"] == 0.0
        assert cart["discountCode"] is None

    def test_expired_discount_code(self, client, user_token):
        """TC-N-005 – expired code returns 400."""
        _clear_cart(client, user_token)
        resp = client.post(
            "/api/v1/cart/discount",
            json={"code": "SUMMER21"},
            headers=auth_headers(user_token),
        )
        assert resp.status_code == 400
        assert "expired" in resp.get_json()["error"].lower()

    def test_invalid_discount_code(self, client, user_token):
        """TC-N-006 – non-existent code returns 400."""
        _clear_cart(client, user_token)
        resp = client.post(
            "/api/v1/cart/discount",
            json={"code": "FAKE99"},
            headers=auth_headers(user_token),
        )
        assert resp.status_code == 400
        assert "invalid" in resp.get_json()["error"].lower()

    def test_sql_injection_in_discount_code(self, client, user_token):
        """TC-S-001 – SQL injection payload is sanitised; returns invalid error."""
        _clear_cart(client, user_token)
        resp = client.post(
            "/api/v1/cart/discount",
            json={"code": "'; DROP TABLE orders;--"},
            headers=auth_headers(user_token),
        )
        assert resp.status_code == 400
        # DB must still be intact: cart can still be fetched
        cart_resp = client.get("/api/v1/cart", headers=auth_headers(user_token))
        assert cart_resp.status_code == 200
