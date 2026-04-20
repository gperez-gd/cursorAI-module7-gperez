from marshmallow import Schema, fields, validate


class CommentSchema(Schema):
    id = fields.Int(dump_only=True)
    ticket_id = fields.Int(dump_only=True)
    user_id = fields.Int(dump_only=True)
    content = fields.Str(required=True)
    is_internal = fields.Bool(dump_only=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)


class CommentCreateSchema(Schema):
    """FR-015, FR-016."""

    content = fields.Str(
        required=True,
        validate=validate.Length(min=1, max=10000, error="Comment content must be 1-10000 characters."),
    )
    is_internal = fields.Bool(load_default=False)
