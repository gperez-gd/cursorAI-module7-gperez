import hashlib

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt, verify_jwt_in_request
from sqlalchemy import asc, desc

from ..extensions import db
from ..models import Product
from ..services.cache import CacheService
from ..utils.errors import err
from ..utils.security import admin_required, sanitize
from ..utils.validators import ProductCreateSchema, ProductUpdateSchema, load_or_400

products_bp = Blueprint("products", __name__)

SORT_COLUMN_MAP = {
    "name": Product.name,
    "price": Product.price,
    "rating": Product.rating,
    "createdAt": Product.created_at,
}


# ---------------------------------------------------------------------------
# GET /products
# ---------------------------------------------------------------------------
@products_bp.route("", methods=["GET"])
def list_products():
    """
    List products with search, filter, sort and pagination (public).
    ---
    tags: [Products]
    parameters:
      - {name: page, in: query, schema: {type: integer, default: 1}}
      - {name: limit, in: query, schema: {type: integer, default: 10}}
      - {name: search, in: query, schema: {type: string}}
      - {name: category, in: query, schema: {type: string}}
      - {name: minPrice, in: query, schema: {type: number}}
      - {name: maxPrice, in: query, schema: {type: number}}
      - {name: sortBy, in: query, schema: {type: string, enum: [name, price, rating, createdAt]}}
      - {name: sortOrder, in: query, schema: {type: string, enum: [asc, desc]}}
    responses:
      200:
        description: Paginated product list.
    """
    page = max(int(request.args.get("page", 1)), 1)
    limit = min(int(request.args.get("limit", 10)), 100)
    search = request.args.get("search", "").strip()
    category = request.args.get("category", "").strip()
    min_price = request.args.get("minPrice")
    max_price = request.args.get("maxPrice")
    sort_by = request.args.get("sortBy", "createdAt")
    sort_order = request.args.get("sortOrder", "desc").lower()

    # Build cache key from query params
    cache_key = "products:" + hashlib.md5(
        f"{page}{limit}{search}{category}{min_price}{max_price}{sort_by}{sort_order}".encode()
    ).hexdigest()

    cached = CacheService.get_products(cache_key)
    if cached:
        return jsonify(cached), 200

    query = Product.query.filter_by(is_deleted=False)

    if search:
        like = f"%{search}%"
        query = query.filter(
            db.or_(Product.name.ilike(like), Product.description.ilike(like))
        )
    if category:
        query = query.filter(Product.category == category)
    if min_price is not None:
        try:
            query = query.filter(Product.price >= float(min_price))
        except ValueError:
            pass
    if max_price is not None:
        try:
            query = query.filter(Product.price <= float(max_price))
        except ValueError:
            pass

    sort_col = SORT_COLUMN_MAP.get(sort_by, Product.created_at)
    direction = asc if sort_order == "asc" else desc
    query = query.order_by(direction(sort_col))

    total = query.count()
    products = query.offset((page - 1) * limit).limit(limit).all()

    result = {
        "products": [p.to_dict() for p in products],
        "total": total,
        "page": page,
        "limit": limit,
    }
    CacheService.set_products(cache_key, result)
    return jsonify(result), 200


# ---------------------------------------------------------------------------
# GET /products/:id
# ---------------------------------------------------------------------------
@products_bp.route("/<product_id>", methods=["GET"])
def get_product(product_id):
    """
    Get a single product by ID (public).
    ---
    tags: [Products]
    parameters:
      - {name: product_id, in: path, required: true, schema: {type: string}}
    responses:
      200:
        description: Product object.
      404:
        description: Product not found.
    """
    cached = CacheService.get_product(product_id)
    if cached:
        return jsonify(cached), 200

    product = Product.query.filter_by(id=product_id, is_deleted=False).first()
    if not product:
        return err("Product not found.", 404)

    data = product.to_dict()
    CacheService.set_product(product_id, data)
    return jsonify(data), 200


# ---------------------------------------------------------------------------
# POST /products  – Admin only
# ---------------------------------------------------------------------------
@products_bp.route("", methods=["POST"])
@jwt_required()
@admin_required
def create_product():
    """
    Create a new product (admin only).
    ---
    tags: [Products]
    security:
      - BearerAuth: []
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required: [name, price, stock, category]
            properties:
              name: {type: string}
              description: {type: string}
              price: {type: number, minimum: 0}
              stock: {type: integer, minimum: 0}
              category: {type: string, enum: [Electronics, Accessories, Footwear, Office]}
              imageUrl: {type: string}
              badge: {type: string}
    responses:
      201:
        description: Product created.
      400:
        description: Validation error.
      403:
        description: Admin required.
    """
    data, errors = load_or_400(ProductCreateSchema(), request.get_json(silent=True) or {})
    if errors:
        return err("; ".join(errors), 400)

    product = Product(
        name=sanitize(data["name"]),
        description=sanitize(data.get("description")),
        price=data["price"],
        stock=data["stock"],
        category=data["category"],
        image_url=sanitize(data.get("imageUrl")),
        badge=sanitize(data.get("badge")),
    )
    db.session.add(product)
    db.session.commit()
    CacheService.invalidate_products()
    return jsonify(product.to_dict()), 201


# ---------------------------------------------------------------------------
# PUT /products/:id  – Admin only
# ---------------------------------------------------------------------------
@products_bp.route("/<product_id>", methods=["PUT"])
@jwt_required()
@admin_required
def update_product(product_id):
    """
    Update a product (admin only, partial update supported).
    ---
    tags: [Products]
    security:
      - BearerAuth: []
    parameters:
      - {name: product_id, in: path, required: true, schema: {type: string}}
    responses:
      200:
        description: Updated product.
      400:
        description: Validation error.
      404:
        description: Product not found.
    """
    product = Product.query.filter_by(id=product_id, is_deleted=False).first()
    if not product:
        return err("Product not found.", 404)

    data, errors = load_or_400(ProductUpdateSchema(), request.get_json(silent=True) or {})
    if errors:
        return err("; ".join(errors), 400)

    if "name" in data:
        product.name = sanitize(data["name"])
    if "description" in data:
        product.description = sanitize(data["description"])
    if "price" in data:
        product.price = data["price"]
    if "stock" in data:
        product.stock = data["stock"]
    if "category" in data:
        product.category = data["category"]
    if "imageUrl" in data:
        product.image_url = sanitize(data["imageUrl"])
    if "badge" in data:
        product.badge = sanitize(data["badge"])

    db.session.commit()
    CacheService.invalidate_product(product_id)
    return jsonify(product.to_dict()), 200


# ---------------------------------------------------------------------------
# DELETE /products/:id  – Admin only (soft delete)
# ---------------------------------------------------------------------------
@products_bp.route("/<product_id>", methods=["DELETE"])
@jwt_required()
@admin_required
def delete_product(product_id):
    """
    Soft-delete a product (admin only). Preserves order history.
    ---
    tags: [Products]
    security:
      - BearerAuth: []
    parameters:
      - {name: product_id, in: path, required: true, schema: {type: string}}
    responses:
      200:
        description: Product deleted.
      404:
        description: Product not found.
    """
    product = Product.query.filter_by(id=product_id, is_deleted=False).first()
    if not product:
        return err("Product not found.", 404)

    product.is_deleted = True
    db.session.commit()
    CacheService.invalidate_product(product_id)
    return jsonify({"message": "Product deleted."}), 200
