from marshmallow import Schema, fields, validate


class UserSchema(Schema):
    id = fields.Int(dump_only=True)
    username = fields.Str(dump_only=True)
    email = fields.Str(dump_only=True)
    created_at = fields.DateTime(dump_only=True)


class RegisterSchema(Schema):
    username = fields.Str(
        required=True,
        validate=validate.Length(min=3, max=80),
    )
    email = fields.Email(required=True)
    password = fields.Str(
        required=True,
        load_only=True,
        validate=validate.Length(min=6),
    )


class LoginSchema(Schema):
    email = fields.Email(required=True)
    password = fields.Str(required=True, load_only=True)
