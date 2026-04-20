"""Shared pytest fixtures for the Blog API test suite."""
import pytest

from app import create_app, db as _db
from app.models.category import Category
from app.models.comment import Comment
from app.models.post import Post
from app.models.user import User


@pytest.fixture(scope="session")
def app():
    """Create the application once for the whole test session."""
    flask_app = create_app("testing")
    with flask_app.app_context():
        _db.create_all()
        yield flask_app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture(autouse=True)
def clean_db(app):
    """Truncate all tables and re-seed the category before every test."""
    with app.app_context():
        # Delete in dependency order (children first)
        Comment.query.delete()
        Post.query.delete()
        User.query.delete()
        Category.query.delete()
        _db.session.commit()

        cat = Category(name="General")
        _db.session.add(cat)
        _db.session.commit()

    yield


@pytest.fixture()
def client(app):
    """A test client for the app."""
    return app.test_client()


@pytest.fixture()
def category_id(app):
    """Return the id of the seeded General category."""
    with app.app_context():
        cat = Category.query.filter_by(name="General").first()
        return cat.id


def _register_and_login(client, username, email, password):
    client.post(
        "/api/auth/register",
        json={"username": username, "email": email, "password": password},
    )
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    token = resp.get_json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def auth_headers(client):
    """Register a user and return its JWT Authorization header."""
    return _register_and_login(client, "testuser", "test@example.com", "password123")


@pytest.fixture()
def alt_auth_headers(client):
    """Register a second user and return its JWT Authorization header."""
    return _register_and_login(client, "otheruser", "other@example.com", "password123")
