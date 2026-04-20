"""Auth endpoint tests — Arrange / Act / Assert."""


def test_register_success(client):
    """POST /api/auth/register returns 201 and a user object."""
    # Arrange
    payload = {"username": "newuser", "email": "newuser@example.com", "password": "secret123"}

    # Act
    resp = client.post("/api/auth/register", json=payload)
    data = resp.get_json()

    # Assert
    assert resp.status_code == 201
    assert data["user"]["username"] == "newuser"
    assert data["user"]["email"] == "newuser@example.com"
    assert "id" in data["user"]


def test_register_duplicate_email(client):
    """POST /api/auth/register returns 409 when email already exists."""
    # Arrange
    payload = {"username": "user1", "email": "dup@example.com", "password": "secret123"}
    client.post("/api/auth/register", json=payload)
    payload2 = {"username": "user2", "email": "dup@example.com", "password": "secret123"}

    # Act
    resp = client.post("/api/auth/register", json=payload2)

    # Assert
    assert resp.status_code == 409


def test_login_success(client):
    """POST /api/auth/login returns 200 and a JWT access_token."""
    # Arrange
    client.post(
        "/api/auth/register",
        json={"username": "loginuser", "email": "login@example.com", "password": "secret123"},
    )

    # Act
    resp = client.post("/api/auth/login", json={"email": "login@example.com", "password": "secret123"})
    data = resp.get_json()

    # Assert
    assert resp.status_code == 200
    assert "access_token" in data


def test_login_invalid_password(client):
    """POST /api/auth/login returns 401 when password is wrong."""
    # Arrange
    client.post(
        "/api/auth/register",
        json={"username": "pwuser", "email": "pw@example.com", "password": "correctpass"},
    )

    # Act
    resp = client.post("/api/auth/login", json={"email": "pw@example.com", "password": "wrongpass"})

    # Assert
    assert resp.status_code == 401
