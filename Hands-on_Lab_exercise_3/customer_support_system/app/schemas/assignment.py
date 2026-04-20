from marshmallow import Schema, fields, validate


class AssignmentSchema(Schema):
    id = fields.Int(dump_only=True)
    ticket_id = fields.Int(dump_only=True)
    assigned_to_id = fields.Int(dump_only=True)
    assigned_by_id = fields.Int(dump_only=True)
    assigned_at = fields.DateTime(dump_only=True)
    notes = fields.Str(dump_only=True, allow_none=True)


class AssignmentCreateSchema(Schema):
    """FR-005 — admin manually assigns a ticket."""

    agent_id = fields.Int(required=True)
    notes = fields.Str(validate=validate.Length(max=500))
    auto_assign = fields.Bool(load_default=False)
