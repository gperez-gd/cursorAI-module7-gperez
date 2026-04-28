"""
Tests: Product Catalog (FR 5.2)
Covers PROD-FR-001 to PROD-FR-010 and PROD-001 to PROD-005.
"""
import pytest
from tests.conftest import auth_headers


class TestListProducts:
    def test_list_products_public(self, client):
        """PROD-001 – GET /products returns paginated list without auth."""
        resp = client.get("/api/v1/products?page=1&limit=10")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "products" in data
        assert isinstance(data["products"], list)
        assert "total" in data

    def test_search_by_name(self, client):
        """PROD-FR-002 – search by product name (case-insensitive)."""
        resp = client.get("/api/v1/products?search=headphones")
        assert resp.status_code == 200
        products = resp.get_json()["products"]
        assert any("Headphones" in p["name"] for p in products)

    def test_filter_by_category(self, client):
        """PROD-FR-003 – filter by category returns only matching products."""
        resp = client.get("/api/v1/products?category=Electronics")
        assert resp.status_code == 200
        products = resp.get_json()["products"]
        assert all(p["category"] == "Electronics" for p in products)

    def test_filter_by_price_range(self, client):
        """PROD-FR-003 – filter by minPrice / maxPrice."""
        resp = client.get("/api/v1/products?minPrice=100&maxPrice=200")
        assert resp.status_code == 200
        products = resp.get_json()["products"]
        assert all(100 <= p["price"] <= 200 for p in products)

    def test_sort_by_price_asc(self, client):
        """PROD-FR-004 – sortBy=price sortOrder=asc returns ascending prices."""
        resp = client.get("/api/v1/products?sortBy=price&sortOrder=asc")
        assert resp.status_code == 200
        prices = [p["price"] for p in resp.get_json()["products"]]
        assert prices == sorted(prices)

    def test_search_no_results(self, client):
        """Search for nonexistent product returns empty list."""
        resp = client.get("/api/v1/products?search=xyznonexistentproduct123")
        assert resp.status_code == 200
        assert resp.get_json()["total"] == 0


class TestGetProduct:
    def test_get_product_by_id(self, client):
        """PROD-002 – GET /products/:id returns the product."""
        resp = client.get("/api/v1/products/prod-001-000-000")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["id"] == "prod-001-000-000"
        assert data["name"] == "Wireless Headphones"

    def test_get_nonexistent_product_404(self, client):
        """ERR-001 – nonexistent product returns 404 with error field."""
        resp = client.get("/api/v1/products/does-not-exist-99999")
        assert resp.status_code == 404
        assert "error" in resp.get_json()


class TestAdminProductCRUD:
    def test_admin_create_product(self, client, admin_token):
        """PROD-003, AUTHZ-007 – admin can create a product."""
        resp = client.post(
            "/api/v1/products",
            json={
                "name": "Admin Product",
                "description": "Created by admin",
                "price": 99.99,
                "stock": 50,
                "category": "Electronics",
            },
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["name"] == "Admin Product"
        assert "id" in data

    def test_create_product_negative_price(self, client, admin_token):
        """PROD-FR-009 – negative price returns 400."""
        resp = client.post(
            "/api/v1/products",
            json={"name": "Bad", "price": -5, "stock": 10, "category": "Office"},
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_user_cannot_create_product(self, client, user_token):
        """AUTHZ-008 – regular user cannot create products (403)."""
        resp = client.post(
            "/api/v1/products",
            json={"name": "Attempt", "price": 1, "stock": 1, "category": "Office"},
            headers=auth_headers(user_token),
        )
        assert resp.status_code == 403

    def test_admin_update_product_price(self, client, admin_token):
        """PROD-004 – admin updates a product's price."""
        resp = client.put(
            "/api/v1/products/prod-001-000-000",
            json={"price": 129.99},
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 200
        assert resp.get_json()["price"] == 129.99

    def test_admin_soft_delete_product(self, client, admin_token):
        """PROD-005 – admin soft-deletes a product; it disappears from listings."""
        # Create a product to delete
        create_resp = client.post(
            "/api/v1/products",
            json={"name": "ToDelete", "price": 10, "stock": 5, "category": "Office"},
            headers=auth_headers(admin_token),
        )
        pid = create_resp.get_json()["id"]

        del_resp = client.delete(
            f"/api/v1/products/{pid}", headers=auth_headers(admin_token)
        )
        assert del_resp.status_code == 200

        # Deleted product should return 404
        get_resp = client.get(f"/api/v1/products/{pid}")
        assert get_resp.status_code == 404
