from marshmallow import Schema, fields, validate

from app.schemas.user import UserSchema
from app.schemas.category import CategorySchema


class PostSchema(Schema):
    id = fields.Int(dump_only=True)
    title = fields.Str(dump_only=True)
    body = fields.Str(dump_only=True)
    author = fields.Nested(UserSchema, dump_only=True)
    category = fields.Nested(CategorySchema, dump_only=True)
    comment_count = fields.Int(dump_only=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)


class PostCreateSchema(Schema):
    title = fields.Str(required=True, validate=validate.Length(min=1, max=255))
    body = fields.Str(required=True, validate=validate.Length(min=1))
    category_id = fields.Int(required=True)


class PostUpdateSchema(Schema):
    title = fields.Str(validate=validate.Length(min=1, max=255))
    body = fields.Str(validate=validate.Length(min=1))
    category_id = fields.Int()
