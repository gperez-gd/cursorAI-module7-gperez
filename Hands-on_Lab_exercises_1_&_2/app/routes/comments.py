from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from marshmallow import ValidationError

from app import cache, db
from app.models.comment import Comment
from app.models.post import Post
from app.schemas.comment import CommentCreateSchema, CommentSchema

comments_bp = Blueprint("comments", __name__)

_comment_schema = CommentSchema()
_comments_schema = CommentSchema(many=True)
_create_schema = CommentCreateSchema()

COMMENTS_PER_PAGE = 10


def _invalidate_post_cache(post_id: int) -> None:
    try:
        cache.delete(f"post_{post_id}")
    except Exception:
        pass


@comments_bp.route("/<int:comment_id>", methods=["DELETE"])
@jwt_required()
def delete_comment(comment_id: int):
    """
    Delete a comment.
    ---
    tags:
      - Comments
    summary: Delete a comment (only the comment author can delete)
    security:
      - Bearer: []
    parameters:
      - name: comment_id
        in: path
        type: integer
        required: true
    responses:
      204:
        description: Comment deleted
      401:
        description: Unauthorized
      403:
        description: Forbidden (not the comment author)
      404:
        description: Comment not found
    """
    comment = db.get_or_404(Comment, comment_id)
    current_user_id = int(get_jwt_identity())

    if comment.author_id != current_user_id:
        return jsonify({"error": "Forbidden", "details": "You are not the author of this comment."}), 403

    post_id = comment.post_id
    db.session.delete(comment)
    db.session.commit()

    _invalidate_post_cache(post_id)

    return "", 204


# Post-scoped comment routes are registered on the posts blueprint under /posts/<id>/comments
def register_post_comments(posts_bp):
    @posts_bp.route("/<int:post_id>/comments", methods=["POST"])
    @jwt_required()
    def create_comment(post_id: int):
        """
        Add a comment to a post.
        ---
        tags:
          - Comments
        summary: Add a comment to a specific post (requires authentication)
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
            required: true
            schema:
              type: object
              required:
                - body
              properties:
                body:
                  type: string
                  example: Great article!
        responses:
          201:
            description: Comment created
          400:
            description: Validation error
          401:
            description: Unauthorized
          404:
            description: Post not found
        """
        post = db.get_or_404(Post, post_id)
        json_data = request.get_json(silent=True)
        if not json_data:
            return jsonify({"error": "No input data provided"}), 400

        try:
            data = _create_schema.load(json_data)
        except ValidationError as err:
            return jsonify({"error": "Validation failed", "details": err.messages}), 400

        author_id = int(get_jwt_identity())
        comment = Comment(body=data["body"], author_id=author_id, post_id=post.id)
        db.session.add(comment)
        db.session.commit()

        _invalidate_post_cache(post.id)

        return jsonify(_comment_schema.dump(comment)), 201

    @posts_bp.route("/<int:post_id>/comments", methods=["GET"])
    def list_comments(post_id: int):
        """
        List comments for a post.
        ---
        tags:
          - Comments
        summary: Retrieve paginated comments for a post
        parameters:
          - name: post_id
            in: path
            type: integer
            required: true
          - name: page
            in: query
            type: integer
            default: 1
        responses:
          200:
            description: Paginated list of comments
          404:
            description: Post not found
        """
        post = db.get_or_404(Post, post_id)
        page = request.args.get("page", 1, type=int)
        pagination = (
            Comment.query.filter_by(post_id=post.id)
            .order_by(Comment.created_at.asc())
            .paginate(page=page, per_page=COMMENTS_PER_PAGE, error_out=False)
        )
        return jsonify(
            {
                "total": pagination.total,
                "page": pagination.page,
                "pages": pagination.pages,
                "results": _comments_schema.dump(pagination.items),
            }
        ), 200
