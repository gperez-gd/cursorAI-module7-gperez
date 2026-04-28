"""
Tests: Authentication (FR 5.1)
Covers AUTH-FR-001 to AUTH-FR-009 and AUTH-001 to AUTH-007.
"""
import pytest
from tests.conftest import auth_headers


class TestRegister:
    def test_register_success(self, client):
        """AUTH-FR-001, AUTH-FR-002 – valid registration returns 201 with JWT."""
        resp = client.post(
            "/api/v1/auth/register",
            json={
                "email": "newuser_test@example.com",
                "password": "Secure1234!",
                "firstName": "Jane",
                "lastName": "Doe",
            },
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert "token" in data
        assert data["user"]["email"] == "newuser_test@example.com"
        assert data["user"]["role"] == "user"

    def test_register_duplicate_email(self, client):
        """AUTH-FR-003 – duplicate email returns 409."""
        client.post(
            "/api/v1/auth/register",
            json={"email": "dup@example.com", "password": "Secure1234!"},
        )
        resp = client.post(
            "/api/v1/auth/register",
            json={"email": "dup@example.com", "password": "Secure1234!"},
        )
        assert resp.status_code == 409

    def test_register_weak_password_no_digit(self, client):
        """AUTH-FR-001 – password without digit returns 400."""
        resp = client.post(
            "/api/v1/auth/register",
            json={"email": "weakpwd@example.com", "password": "NoDigitHere!"},
        )
        assert resp.status_code == 400

    def test_register_weak_password_too_short(self, client):
        """AUTH-FR-001 – password shorter than 8 chars returns 400."""
        resp = client.post(
            "/api/v1/auth/register",
            json={"email": "short@example.com", "password": "A1!"},
        )
        assert resp.status_code == 400

    def test_register_invalid_email(self, client):
        """Registration with malformed email returns 400."""
        resp = client.post(
            "/api/v1/auth/register",
            json={"email": "not-an-email", "password": "Valid1234!"},
        )
        assert resp.status_code == 400


class TestLogin:
    def test_login_valid_credentials(self, client):
        """AUTH-001 – valid login returns 200 with JWT."""
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "user@example.com", "password": "User1234!"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "token" in data
        assert isinstance(data["token"], str)
        assert "csrfToken" in data

    def test_login_invalid_password(self, client):
        """AUTH-002 – wrong password returns 401 without token."""
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "user@example.com", "password": "WrongPassword!"},
        )
        assert resp.status_code == 401
        assert "token" not in resp.get_json()

    def test_login_nonexistent_email(self, client):
        """AUTH-003 – unknown email returns 401."""
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.com", "password": "AnyPassword!"},
        )
        assert resp.status_code == 401

    def test_login_missing_fields(self, client):
        """Login without body fields returns 401 (not 500)."""
        resp = client.post("/api/v1/auth/login", json={})
        assert resp.status_code == 401


class TestProtectedEndpoints:
    def test_no_token_returns_401(self, client):
        """AUTH-004 – missing token on protected endpoint."""
        resp = client.get("/api/v1/users/me")
        assert resp.status_code == 401

    def test_malformed_token_returns_401(self, client):
        """AUTH-006 – malformed JWT returns 401."""
        resp = client.get(
            "/api/v1/users/me",
            headers={"Authorization": "Bearer not.a.valid.jwt.at.all"},
        )
        assert resp.status_code == 401


class TestLogout:
    def test_logout_invalidates_token(self, client):
        """AUTH-007 – logout blacklists JWT; subsequent request returns 401."""
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "user@example.com", "password": "User1234!"},
        )
        temp_token = resp.get_json()["token"]

        logout_resp = client.post(
            "/api/v1/auth/logout", headers=auth_headers(temp_token)
        )
        assert logout_resp.status_code == 200

        # Token should now be blacklisted
        me_resp = client.get("/api/v1/users/me", headers=auth_headers(temp_token))
        assert me_resp.status_code == 401
