"""Search endpoint test — Arrange / Act / Assert."""


def test_search_posts_by_keyword(client, auth_headers, category_id):
    """GET /api/search?q=<keyword> returns 200 and matching posts only."""
    # Arrange — create two posts; only one matches the keyword
    client.post(
        "/api/posts",
        json={"title": "Flask is awesome", "body": "Flask content", "category_id": category_id},
        headers=auth_headers,
    )
    client.post(
        "/api/posts",
        json={"title": "Django tutorial", "body": "Django content", "category_id": category_id},
        headers=auth_headers,
    )

    # Act
    resp = client.get("/api/search?q=Flask")
    data = resp.get_json()

    # Assert
    assert resp.status_code == 200
    assert data["total"] >= 1
    titles = [p["title"] for p in data["results"]]
    assert all("Flask" in t or "flask" in t.lower() for t in titles)
