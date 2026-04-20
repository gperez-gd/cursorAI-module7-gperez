from flask import Blueprint, jsonify

from app import db
from app.models.category import Category
from app.schemas.category import CategorySchema

categories_bp = Blueprint("categories", __name__)

_categories_schema = CategorySchema(many=True)
_category_schema = CategorySchema()


@categories_bp.route("", methods=["GET"])
def list_categories():
    """
    List all categories.
    ---
    tags:
      - Categories
    summary: Retrieve all post categories
    responses:
      200:
        description: List of categories
        schema:
          type: array
          items:
            type: object
            properties:
              id:
                type: integer
              name:
                type: string
              slug:
                type: string
    """
    categories = Category.query.order_by(Category.name.asc()).all()
    return jsonify(_categories_schema.dump(categories)), 200
