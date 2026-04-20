"""Comment endpoint tests — Arrange / Act / Assert."""


def _create_post(client, auth_headers, category_id):
    resp = client.post(
        "/api/posts",
        json={"title": "Post for Comments", "body": "Body text", "category_id": category_id},
        headers=auth_headers,
    )
    return resp.get_json()["id"]


def _add_comment(client, auth_headers, post_id, body="Nice post!"):
    return client.post(
        f"/api/posts/{post_id}/comments",
        json={"body": body},
        headers=auth_headers,
    )


def test_add_comment_authenticated(client, auth_headers, category_id):
    """POST /api/posts/<id>/comments returns 201 and links comment to post."""
    # Arrange
    post_id = _create_post(client, auth_headers, category_id)

    # Act
    resp = _add_comment(client, auth_headers, post_id)
    data = resp.get_json()

    # Assert
    assert resp.status_code == 201
    assert data["body"] == "Nice post!"
    assert data["post_id"] == post_id


def test_get_comments_paginated(client, auth_headers, category_id):
    """GET /api/posts/<id>/comments returns 200 with pagination."""
    # Arrange
    post_id = _create_post(client, auth_headers, category_id)
    _add_comment(client, auth_headers, post_id, body="Comment 1")
    _add_comment(client, auth_headers, post_id, body="Comment 2")

    # Act
    resp = client.get(f"/api/posts/{post_id}/comments")
    data = resp.get_json()

    # Assert
    assert resp.status_code == 200
    assert data["total"] >= 2
    assert "page" in data
    assert "results" in data


def test_delete_comment_by_author(client, auth_headers, category_id):
    """DELETE /api/comments/<id> by the author returns 204."""
    # Arrange
    post_id = _create_post(client, auth_headers, category_id)
    comment_id = _add_comment(client, auth_headers, post_id).get_json()["id"]

    # Act
    resp = client.delete(f"/api/comments/{comment_id}", headers=auth_headers)

    # Assert
    assert resp.status_code == 204
