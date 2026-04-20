"""API tests for Authentication endpoints."""
import json
import pytest


class TestRegister:
    def test_register_success(self, client, db):
        resp = client.post("/api/auth/register", json={
            "name": "New User",
            "email": "newuser@example.com",
            "password": "Secure123",
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["status"] == "success"
        assert "access_token" in data["data"]
        assert data["data"]["user"]["email"] == "newuser@example.com"

    def test_register_duplicate_email(self, client, db, customer_user):
        resp = client.post("/api/auth/register", json={
            "name": "Duplicate",
            "email": customer_user.email,
            "password": "Password1",
        })
        assert resp.status_code == 409
        assert resp.get_json()["code"] == "CONFLICT"

    def test_register_missing_fields(self, client, db):
        resp = client.post("/api/auth/register", json={"name": "Test"})
        assert resp.status_code == 400
        assert resp.get_json()["code"] == "VALIDATION_ERROR"

    def test_register_invalid_password(self, client, db):
        resp = client.post("/api/auth/register", json={
            "name": "Bad Password User",
            "email": "badpw@example.com",
            "password": "weakpwd",
        })
        assert resp.status_code == 400

    def test_register_invalid_email(self, client, db):
        resp = client.post("/api/auth/register", json={
            "name": "Bad Email",
            "email": "not-an-email",
            "password": "Password1",
        })
        assert resp.status_code == 400


class TestLogin:
    def test_login_success(self, client, db, customer_user):
        resp = client.post("/api/auth/login", json={
            "email": customer_user.email,
            "password": "Password1",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert "access_token" in data["data"]
        assert "refresh_token" in data["data"]

    def test_login_wrong_password(self, client, db, customer_user):
        resp = client.post("/api/auth/login", json={
            "email": customer_user.email,
            "password": "WrongPassword1",
        })
        assert resp.status_code == 401
        assert resp.get_json()["code"] == "UNAUTHORIZED"

    def test_login_unknown_email(self, client, db):
        resp = client.post("/api/auth/login", json={
            "email": "ghost@example.com",
            "password": "Password1",
        })
        assert resp.status_code == 401


class TestMe:
    def test_get_profile(self, client, db, customer_user, customer_headers):
        resp = client.get("/api/auth/me", headers=customer_headers)
        assert resp.status_code == 200
        assert resp.get_json()["data"]["email"] == customer_user.email

    def test_unauthenticated_access(self, client, db):
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401


class TestLogout:
    def test_logout_requires_auth(self, client, db):
        resp = client.post("/api/auth/logout")
        assert resp.status_code == 401

    def test_logout_success(self, client, db, customer_headers):
        resp = client.post("/api/auth/logout", headers=customer_headers)
        assert resp.status_code == 200
