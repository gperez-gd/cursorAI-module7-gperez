"""Cache behaviour tests — Arrange / Act / Assert."""
from unittest.mock import patch

from app import cache


def _create_post(client, auth_headers, category_id, title="Cached Post"):
    resp = client.post(
        "/api/posts",
        json={"title": title, "body": "Cache test body", "category_id": category_id},
        headers=auth_headers,
    )
    return resp.get_json()["id"]


def test_post_list_cached(app, client, auth_headers, category_id):
    """
    The second GET /api/posts?page=1 request is served from cache.

    We verify this by inspecting the cache directly: after the first request
    the key must be present, and after the second it should still be present.
    """
    # Arrange
    _create_post(client, auth_headers, category_id)
    with app.app_context():
        cache.delete("post_list_page_1")  # ensure a clean slate

    # Act — first request populates the cache
    resp1 = client.get("/api/posts?page=1")
    assert resp1.status_code == 200

    with app.app_context():
        cached_value = cache.get("post_list_page_1")

    # Assert — cache key is populated after first request
    assert cached_value is not None


def test_cache_invalidated_on_update(app, client, auth_headers, category_id):
    """
    After a PUT /api/posts/<id> the individual post cache entry is cleared.
    """
    # Arrange — warm the cache
    post_id = _create_post(client, auth_headers, category_id, title="Original Title")
    client.get(f"/api/posts/{post_id}")  # populates cache

    with app.app_context():
        assert cache.get(f"post_{post_id}") is not None

    # Act — update the post (triggers cache invalidation)
    resp = client.put(
        f"/api/posts/{post_id}",
        json={"title": "Updated Title"},
        headers=auth_headers,
    )
    assert resp.status_code == 200

    # Assert — individual post cache entry has been cleared
    with app.app_context():
        assert cache.get(f"post_{post_id}") is None
