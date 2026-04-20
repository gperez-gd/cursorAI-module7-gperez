from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from marshmallow import ValidationError

from app import cache, db
from app.models.category import Category
from app.models.post import Post
from app.schemas.post import PostCreateSchema, PostSchema, PostUpdateSchema

posts_bp = Blueprint("posts", __name__)

_post_schema = PostSchema()
_posts_schema = PostSchema(many=True)
_create_schema = PostCreateSchema()
_update_schema = PostUpdateSchema()

POSTS_PER_PAGE = 20


def _post_list_cache_key(page: int) -> str:
    return f"post_list_page_{page}"


def _post_cache_key(post_id: int) -> str:
    return f"post_{post_id}"


def _invalidate_post_list_cache() -> None:
    """Delete all paginated post-list cache entries."""
    try:
        cache.delete_many(*[_post_list_cache_key(p) for p in range(1, 201)])
    except Exception:
        pass


def _invalidate_post_cache(post_id: int) -> None:
    try:
        cache.delete(_post_cache_key(post_id))
    except Exception:
        pass


def _serialize_post(post: Post) -> dict:
    data = _post_schema.dump(post)
    data["comment_count"] = post.comments.count()
    return data


@posts_bp.route("", methods=["GET"])
def list_posts():
    """
    List all posts (paginated).
    ---
    tags:
      - Posts
    summary: Retrieve a paginated list of blog posts
    parameters:
      - name: page
        in: query
        type: integer
        default: 1
        description: Page number
    responses:
      200:
        description: Paginated list of posts
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
    """
    page = request.args.get("page", 1, type=int)
    ttl = current_app.config.get("CACHE_DEFAULT_TIMEOUT", 300)
    cache_key = _post_list_cache_key(page)

    cached = cache.get(cache_key)
    if cached is not None:
        return jsonify(cached), 200

    pagination = Post.query.order_by(Post.created_at.desc()).paginate(
        page=page, per_page=POSTS_PER_PAGE, error_out=False
    )
    results = [_serialize_post(p) for p in pagination.items]
    payload = {
        "total": pagination.total,
        "page": pagination.page,
        "pages": pagination.pages,
        "results": results,
    }
    cache.set(cache_key, payload, timeout=ttl)
    return jsonify(payload), 200


@posts_bp.route("/<int:post_id>", methods=["GET"])
def get_post(post_id: int):
    """
    Get a single post by ID.
    ---
    tags:
      - Posts
    summary: Retrieve a single blog post
    parameters:
      - name: post_id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: Post object
      404:
        description: Post not found
    """
    ttl = current_app.config.get("CACHE_DEFAULT_TIMEOUT", 300)
    cache_key = _post_cache_key(post_id)

    cached = cache.get(cache_key)
    if cached is not None:
        return jsonify(cached), 200

    post = db.get_or_404(Post, post_id)
    payload = _serialize_post(post)
    cache.set(cache_key, payload, timeout=ttl)
    return jsonify(payload), 200


@posts_bp.route("", methods=["POST"])
@jwt_required()
def create_post():
    """
    Create a new blog post.
    ---
    tags:
      - Posts
    summary: Create a new blog post (requires authentication)
    security:
      - Bearer: []
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - title
            - body
            - category_id
          properties:
            title:
              type: string
              example: My First Post
            body:
              type: string
              example: Hello, world!
            category_id:
              type: integer
              example: 1
    responses:
      201:
        description: Post created
      400:
        description: Validation error
      401:
        description: Unauthorized
      404:
        description: Category not found
    """
    json_data = request.get_json(silent=True)
    if not json_data:
        return jsonify({"error": "No input data provided"}), 400

    try:
        data = _create_schema.load(json_data)
    except ValidationError as err:
        return jsonify({"error": "Validation failed", "details": err.messages}), 400

    category = db.session.get(Category, data["category_id"])
    if not category:
        return jsonify({"error": "Not found", "details": "Category not found."}), 404

    author_id = int(get_jwt_identity())
    post = Post(
        title=data["title"],
        body=data["body"],
        author_id=author_id,
        category_id=data["category_id"],
    )
    db.session.add(post)
    db.session.commit()

    _invalidate_post_list_cache()

    return jsonify(_serialize_post(post)), 201


@posts_bp.route("/<int:post_id>", methods=["PUT", "PATCH"])
@jwt_required()
def update_post(post_id: int):
    """
    Update a blog post.
    ---
    tags:
      - Posts
    summary: Update a blog post (only the author can update)
    security:
      - Bearer: []
    consumes:
      - application/json
    parameters:
      - name: post_id
        in: path
        type: integer
        required: true
      - in: body
        name: body
        schema:
          type: object
          properties:
            title:
              type: string
            body:
              type: string
            category_id:
              type: integer
    responses:
      200:
        description: Updated post
      400:
        description: Validation error
      401:
        description: Unauthorized
      403:
        description: Forbidden (not the author)
      404:
        description: Post not found
    """
    post = db.get_or_404(Post, post_id)
    current_user_id = int(get_jwt_identity())

    if post.author_id != current_user_id:
        return jsonify({"error": "Forbidden", "details": "You are not the author of this post."}), 403

    json_data = request.get_json(silent=True) or {}
    try:
        data = _update_schema.load(json_data)
    except ValidationError as err:
        return jsonify({"error": "Validation failed", "details": err.messages}), 400

    if "title" in data:
        post.title = data["title"]
    if "body" in data:
        post.body = data["body"]
    if "category_id" in data:
        category = db.session.get(Category, data["category_id"])
        if not category:
            return jsonify({"error": "Not found", "details": "Category not found."}), 404
        post.category_id = data["category_id"]

    post.updated_at = datetime.now(timezone.utc)
    db.session.commit()

    _invalidate_post_cache(post_id)
    _invalidate_post_list_cache()

    return jsonify(_serialize_post(post)), 200


@posts_bp.route("/<int:post_id>", methods=["DELETE"])
@jwt_required()
def delete_post(post_id: int):
    """
    Delete a blog post.
    ---
    tags:
      - Posts
    summary: Delete a blog post (only the author can delete)
    security:
      - Bearer: []
    parameters:
      - name: post_id
        in: path
        type: integer
        required: true
    responses:
      204:
        description: Post deleted
      401:
        description: Unauthorized
      403:
        description: Forbidden (not the author)
      404:
        description: Post not found
    """
    post = db.get_or_404(Post, post_id)
    current_user_id = int(get_jwt_identity())

    if post.author_id != current_user_id:
        return jsonify({"error": "Forbidden", "details": "You are not the author of this post."}), 403

    db.session.delete(post)
    db.session.commit()

    _invalidate_post_cache(post_id)
    _invalidate_post_list_cache()

    return "", 204
