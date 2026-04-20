from marshmallow import Schema, fields, validate, validates, ValidationError, post_load
from ..models.user import UserRole, AvailabilityStatus


def _enum_value(val):
    return val.value if hasattr(val, "value") else str(val) if val is not None else None


class UserSchema(Schema):
    id = fields.Int(dump_only=True)
    name = fields.Str(required=True, validate=validate.Length(min=2, max=100))
    email = fields.Email(required=True)
    role = fields.Function(serialize=lambda obj: _enum_value(obj.role), dump_only=True)
    availability_status = fields.Function(serialize=lambda obj: _enum_value(obj.availability_status))
    expertise_areas = fields.List(fields.Str())
    is_active = fields.Bool(dump_only=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)


class UserRegisterSchema(Schema):
    name = fields.Str(required=True, validate=validate.Length(min=2, max=100))
    email = fields.Email(required=True)
    password = fields.Str(
        required=True,
        load_only=True,
        validate=validate.Length(min=8, max=128),
    )
    role = fields.Str(
        load_default="customer",
        validate=validate.OneOf([r.value for r in UserRole]),
    )

    @validates("password")
    def validate_password(self, value):
        if not any(c.isupper() for c in value):
            raise ValidationError("Password must contain at least one uppercase letter.")
        if not any(c.isdigit() for c in value):
            raise ValidationError("Password must contain at least one digit.")


class UserLoginSchema(Schema):
    email = fields.Email(required=True)
    password = fields.Str(required=True, load_only=True)


class UserUpdateSchema(Schema):
    name = fields.Str(validate=validate.Length(min=2, max=100))
    availability_status = fields.Str(
        validate=validate.OneOf([s.value for s in AvailabilityStatus])
    )
    expertise_areas = fields.List(fields.Str(validate=validate.Length(max=50)))

    @validates("expertise_areas")
    def validate_expertise(self, value):
        if len(value) > 10:
            raise ValidationError("Maximum 10 expertise areas allowed.")
