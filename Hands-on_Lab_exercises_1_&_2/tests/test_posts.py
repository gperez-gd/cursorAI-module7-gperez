"""Post CRUD endpoint tests — Arrange / Act / Assert."""
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_post(client, auth_headers, category_id, title="Test Post", body="Test body"):
    resp = client.post(
        "/api/posts",
        json={"title": title, "body": body, "category_id": category_id},
        headers=auth_headers,
    )
    return resp


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_create_post_authenticated(client, auth_headers, category_id):
    """POST /api/posts with a valid JWT returns 201 and persists the post."""
    # Act
    resp = _create_post(client, auth_headers, category_id)
    data = resp.get_json()

    # Assert
    assert resp.status_code == 201
    assert data["title"] == "Test Post"
    assert data["id"] is not None


def test_create_post_unauthenticated(client, category_id):
    """POST /api/posts without a JWT returns 401."""
    # Act
    resp = client.post(
        "/api/posts",
        json={"title": "No Auth", "body": "body", "category_id": category_id},
    )

    # Assert
    assert resp.status_code == 401


def test_get_post_list_paginated(client, auth_headers, category_id):
    """GET /api/posts returns 200 with pagination metadata."""
    # Arrange — create at least one post
    _create_post(client, auth_headers, category_id)

    # Act
    resp = client.get("/api/posts")
    data = resp.get_json()

    # Assert
    assert resp.status_code == 200
    assert "total" in data
    assert "page" in data
    assert "pages" in data
    assert isinstance(data["results"], list)


def test_get_single_post(client, auth_headers, category_id):
    """GET /api/posts/<id> returns 200 with correct fields."""
    # Arrange
    create_resp = _create_post(client, auth_headers, category_id, title="Single Post")
    post_id = create_resp.get_json()["id"]

    # Act
    resp = client.get(f"/api/posts/{post_id}")
    data = resp.get_json()

    # Assert
    assert resp.status_code == 200
    assert data["title"] == "Single Post"
    assert "comment_count" in data


def test_update_post_by_owner(client, auth_headers, category_id):
    """PUT /api/posts/<id> by the owner returns 200 with updated fields."""
    # Arrange
    post_id = _create_post(client, auth_headers, category_id).get_json()["id"]

    # Act
    resp = client.put(
        f"/api/posts/{post_id}",
        json={"title": "Updated Title"},
        headers=auth_headers,
    )
    data = resp.get_json()

    # Assert
    assert resp.status_code == 200
    assert data["title"] == "Updated Title"


def test_update_post_by_non_owner(client, auth_headers, alt_auth_headers, category_id):
    """PUT /api/posts/<id> by a different user returns 403."""
    # Arrange — post created by auth_headers user
    post_id = _create_post(client, auth_headers, category_id).get_json()["id"]

    # Act — attempted by alt_auth_headers user
    resp = client.put(
        f"/api/posts/{post_id}",
        json={"title": "Hacked"},
        headers=alt_auth_headers,
    )

    # Assert
    assert resp.status_code == 403


def test_delete_post_by_owner(client, auth_headers, category_id):
    """DELETE /api/posts/<id> by the owner returns 204."""
    # Arrange
    post_id = _create_post(client, auth_headers, category_id).get_json()["id"]

    # Act
    resp = client.delete(f"/api/posts/{post_id}", headers=auth_headers)

    # Assert
    assert resp.status_code == 204
    # Verify it's gone
    get_resp = client.get(f"/api/posts/{post_id}")
    assert get_resp.status_code == 404
