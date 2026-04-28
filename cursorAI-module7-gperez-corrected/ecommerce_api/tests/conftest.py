"""
Pytest configuration and shared fixtures.

Redis is replaced with fakeredis so tests run without a live Redis instance.
The database uses an in-memory SQLite, created fresh for every test session.
"""
import pytest
import fakeredis

from app import create_app
from app.extensions import db as _db
import app.extensions as ext_module
from app.models import User, Product, DiscountCode


# ---------------------------------------------------------------------------
# App / client fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def app():
    """Create the Flask test application (single instance for the session)."""
    application = create_app("testing")

    # Patch Redis with fakeredis for the entire test session
    fake_redis = fakeredis.FakeRedis(decode_responses=True)
    ext_module.redis_client = fake_redis

    with application.app_context():
        _db.create_all()
        _seed_data()
        yield application
        _db.drop_all()


@pytest.fixture(scope="session")
def client(app):
    return app.test_client()


# ---------------------------------------------------------------------------
# Seeded test data
# ---------------------------------------------------------------------------

def _seed_data():
    """Insert admin user, regular user, products and discount codes."""
    # Admin
    admin = User(
        id="admin-000-000-000",
        email="admin@example.com",
        role="admin",
    )
    admin.set_password("Admin1234!")
    _db.session.add(admin)

    # Regular user
    user = User(
        id="user-000-000-000",
        email="user@example.com",
        role="user",
    )
    user.set_password("User1234!")
    _db.session.add(user)

    # Second regular user (used for cross-user access tests)
    user2 = User(
        id="user2-00-000-000",
        email="user2@example.com",
        role="user",
    )
    user2.set_password("User1234!")
    _db.session.add(user2)

    # Products
    products = [
        Product(
            id="prod-001-000-000",
            name="Wireless Headphones",
            description="Premium audio experience",
            price=149.99,
            stock=50,
            category="Electronics",
            rating=4.5,
            review_count=120,
        ),
        Product(
            id="prod-002-000-000",
            name="Running Shoes",
            description="Lightweight and durable",
            price=89.99,
            stock=30,
            category="Footwear",
            rating=4.2,
            review_count=85,
        ),
        Product(
            id="prod-cheap-0-000",
            name="Cheap Item",
            description="Very affordable",
            price=5.00,
            stock=100,
            category="Accessories",
        ),
        Product(
            id="prod-oos-00-000",
            name="Out of Stock Item",
            description="Unavailable",
            price=50.00,
            stock=0,
            category="Accessories",
        ),
    ]
    for p in products:
        _db.session.add(p)

    # Discount codes
    from datetime import datetime, timedelta

    codes = [
        DiscountCode(
            id="dc-save10-000",
            code="SAVE10",
            type="percentage",
            value=10,
            expires_at=None,
            is_single_use=False,
        ),
        DiscountCode(
            id="dc-flat5-0000",
            code="FLAT5",
            type="fixed",
            value=5,
            expires_at=None,
            is_single_use=False,
        ),
        DiscountCode(
            id="dc-summer21-0",
            code="SUMMER21",
            type="percentage",
            value=20,
            expires_at=datetime(2021, 9, 1),  # expired
            is_single_use=False,
        ),
        DiscountCode(
            id="dc-newuser-00",
            code="NEWUSER",
            type="fixed",
            value=15,
            expires_at=None,
            is_single_use=True,
        ),
        DiscountCode(
            id="dc-twenty-000",
            code="TWENTY_OFF",
            type="fixed",
            value=20,
            expires_at=None,
            is_single_use=False,
        ),
    ]
    for dc in codes:
        _db.session.add(dc)

    _db.session.commit()


# ---------------------------------------------------------------------------
# Auth helpers (tokens)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def admin_token(client):
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "Admin1234!"},
    )
    assert resp.status_code == 200
    return resp.get_json()["token"]


@pytest.fixture(scope="session")
def user_token(client):
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "User1234!"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    return data["token"]


@pytest.fixture(scope="session")
def user_csrf(client):
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "User1234!"},
    )
    assert resp.status_code == 200
    return resp.get_json()["csrfToken"]


@pytest.fixture(scope="session")
def user2_token(client):
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "user2@example.com", "password": "User1234!"},
    )
    assert resp.status_code == 200
    return resp.get_json()["token"]


# ---------------------------------------------------------------------------
# Convenience header builders
# ---------------------------------------------------------------------------

def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def csrf_headers(token: str, csrf: str) -> dict:
    return {"Authorization": f"Bearer {token}", "X-CSRF-Token": csrf}
