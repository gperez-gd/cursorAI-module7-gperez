from flask import Blueprint, jsonify, request

from app.models.post import Post
from app.schemas.post import PostSchema

search_bp = Blueprint("search", __name__)

_post_schema = PostSchema()

POSTS_PER_PAGE = 20


def _serialize_post(post: Post) -> dict:
    data = _post_schema.dump(post)
    data["comment_count"] = post.comments.count()
    return data


@search_bp.route("", methods=["GET"])
def search_posts():
    """
    Search posts by keyword.
    ---
    tags:
      - Search
    summary: Full-text search across post titles and bodies
    parameters:
      - name: q
        in: query
        type: string
        required: true
        description: Search keyword
        example: flask
      - name: page
        in: query
        type: integer
        default: 1
        description: Page number
    responses:
      200:
        description: Paginated search results
        schema:
          type: object
          properties:
            total:
              type: integer
            page:
              type: integer
            pages:
              type: integer
            results:
              type: array
      400:
        description: Missing search query parameter
    """
    keyword = request.args.get("q", "").strip()
    if not keyword:
        return jsonify({"error": "Bad request", "details": "Query parameter 'q' is required."}), 400

    page = request.args.get("page", 1, type=int)
    pattern = f"%{keyword}%"

    pagination = (
        Post.query.filter(
            Post.title.ilike(pattern) | Post.body.ilike(pattern)
        )
        .order_by(Post.created_at.desc())
        .paginate(page=page, per_page=POSTS_PER_PAGE, error_out=False)
    )

    results = [_serialize_post(p) for p in pagination.items]
    return jsonify(
        {
            "total": pagination.total,
            "page": pagination.page,
            "pages": pagination.pages,
            "query": keyword,
            "results": results,
        }
    ), 200
