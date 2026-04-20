from marshmallow import Schema, fields, validate

from app.schemas.user import UserSchema


class CommentSchema(Schema):
    id = fields.Int(dump_only=True)
    body = fields.Str(dump_only=True)
    author = fields.Nested(UserSchema, dump_only=True)
    post_id = fields.Int(dump_only=True)
    created_at = fields.DateTime(dump_only=True)


class CommentCreateSchema(Schema):
    body = fields.Str(required=True, validate=validate.Length(min=1))
