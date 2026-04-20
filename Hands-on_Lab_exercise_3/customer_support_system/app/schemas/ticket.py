import re
from marshmallow import Schema, fields, validate, validates, ValidationError, post_dump
from ..models.ticket import TicketStatus, TicketPriority, TicketCategory


SUBJECT_PATTERN = re.compile(r"^[\w\s.,!?;:()\-'\"]+$")


def _enum_value(val):
    """Return the string value of an enum (or the raw value if already a str)."""
    if val is None:
        return None
    return val.value if hasattr(val, "value") else str(val)


class TicketSchema(Schema):
    id = fields.Int(dump_only=True)
    ticket_number = fields.Str(dump_only=True)
    subject = fields.Str(required=True)
    description = fields.Str(required=True)
    status = fields.Function(serialize=lambda obj: _enum_value(obj.status), dump_only=True)
    priority = fields.Function(serialize=lambda obj: _enum_value(obj.priority))
    category = fields.Function(serialize=lambda obj: _enum_value(obj.category))
    customer_email = fields.Email(required=True)
    assigned_to_id = fields.Int(dump_only=True, allow_none=True)
    created_by_id = fields.Int(dump_only=True, allow_none=True)
    sla_response_due = fields.DateTime(dump_only=True, allow_none=True)
    sla_resolution_due = fields.DateTime(dump_only=True, allow_none=True)
    first_response_at = fields.DateTime(dump_only=True, allow_none=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)
    resolved_at = fields.DateTime(dump_only=True, allow_none=True)
    closed_at = fields.DateTime(dump_only=True, allow_none=True)


class TicketCreateSchema(Schema):
    """FR-001 validation rules."""

    subject = fields.Str(
        required=True,
        validate=validate.Length(min=5, max=200, error="Subject must be 5-200 characters."),
    )
    description = fields.Str(
        required=True,
        validate=validate.Length(min=20, max=5000, error="Description must be 20-5000 characters."),
    )
    priority = fields.Str(
        load_default="medium",
        validate=validate.OneOf(
            [p.value for p in TicketPriority],
            error="Priority must be one of: low, medium, high, urgent.",
        ),
    )
    category = fields.Str(
        required=True,
        validate=validate.OneOf(
            [c.value for c in TicketCategory],
            error="Category must be one of: technical, billing, general, feature_request.",
        ),
    )
    customer_email = fields.Email(required=True, error_messages={"validator_failed": "Invalid email address."})

    @validates("subject")
    def validate_subject_chars(self, value):
        if not SUBJECT_PATTERN.match(value):
            raise ValidationError("Subject contains invalid characters. Use alphanumeric and common punctuation only.")


class TicketUpdateSchema(Schema):
    subject = fields.Str(validate=validate.Length(min=5, max=200))
    description = fields.Str(validate=validate.Length(min=20, max=5000))
    category = fields.Str(
        validate=validate.OneOf([c.value for c in TicketCategory])
    )

    @validates("subject")
    def validate_subject_chars(self, value):
        if value and not SUBJECT_PATTERN.match(value):
            raise ValidationError("Subject contains invalid characters.")


class TicketStatusUpdateSchema(Schema):
    """FR-011, FR-012."""

    status = fields.Str(
        required=True,
        validate=validate.OneOf(
            [s.value for s in TicketStatus],
            error="Invalid status value.",
        ),
    )
    comment = fields.Str(validate=validate.Length(max=1000))


class TicketPriorityUpdateSchema(Schema):
    """FR-023, FR-024 — agents and admins only, reason required."""

    priority = fields.Str(
        required=True,
        validate=validate.OneOf([p.value for p in TicketPriority]),
    )
    reason = fields.Str(
        required=True,
        validate=validate.Length(min=5, max=500, error="A reason (5-500 characters) is required when changing priority."),
    )


class TicketFilterSchema(Schema):
    status = fields.Str(validate=validate.OneOf([s.value for s in TicketStatus]))
    priority = fields.Str(validate=validate.OneOf([p.value for p in TicketPriority]))
    category = fields.Str(validate=validate.OneOf([c.value for c in TicketCategory]))
    assigned_to_id = fields.Int()
    customer_email = fields.Email()
    search = fields.Str(validate=validate.Length(max=200))
    page = fields.Int(load_default=1, validate=validate.Range(min=1))
    per_page = fields.Int(load_default=20, validate=validate.Range(min=1, max=100))
    sort_by = fields.Str(
        load_default="created_at",
        validate=validate.OneOf(["created_at", "updated_at", "priority", "status"]),
    )
    order = fields.Str(load_default="desc", validate=validate.OneOf(["asc", "desc"]))
