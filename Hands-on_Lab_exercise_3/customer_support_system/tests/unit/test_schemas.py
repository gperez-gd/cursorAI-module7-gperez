"""Unit tests for Marshmallow schema validation (FR-001, NFR-013, NFR-014)."""
import pytest
from marshmallow import ValidationError
from app.schemas.ticket import TicketCreateSchema, TicketStatusUpdateSchema, TicketPriorityUpdateSchema
from app.schemas.user import UserRegisterSchema
from app.schemas.comment import CommentCreateSchema


class TestTicketCreateSchema:
    schema = TicketCreateSchema()

    def test_valid_ticket(self):
        data = self.schema.load({
            "subject": "Cannot login to my account",
            "description": "I have been unable to access my account for the past two hours.",
            "priority": "high",
            "category": "technical",
            "customer_email": "user@example.com",
        })
        assert data["subject"] == "Cannot login to my account"
        assert data["priority"] == "high"

    def test_subject_too_short(self):
        with pytest.raises(ValidationError) as exc:
            self.schema.load({
                "subject": "Hi",
                "description": "This is a long enough description for the system.",
                "category": "technical",
                "customer_email": "u@example.com",
            })
        assert "subject" in exc.value.messages

    def test_subject_too_long(self):
        with pytest.raises(ValidationError):
            self.schema.load({
                "subject": "A" * 201,
                "description": "Sufficient description with enough characters.",
                "category": "billing",
                "customer_email": "u@example.com",
            })

    def test_description_too_short(self):
        with pytest.raises(ValidationError) as exc:
            self.schema.load({
                "subject": "Valid subject here",
                "description": "Too short.",
                "category": "general",
                "customer_email": "u@example.com",
            })
        assert "description" in exc.value.messages

    def test_invalid_priority(self):
        with pytest.raises(ValidationError) as exc:
            self.schema.load({
                "subject": "Valid subject here",
                "description": "Long enough description to pass validation check.",
                "priority": "extreme",
                "category": "technical",
                "customer_email": "u@example.com",
            })
        assert "priority" in exc.value.messages

    def test_invalid_category(self):
        with pytest.raises(ValidationError) as exc:
            self.schema.load({
                "subject": "Valid subject here",
                "description": "Long enough description to pass validation check.",
                "category": "unknown_category",
                "customer_email": "u@example.com",
            })
        assert "category" in exc.value.messages

    def test_invalid_email(self):
        with pytest.raises(ValidationError) as exc:
            self.schema.load({
                "subject": "Valid subject here",
                "description": "Long enough description for the form validation.",
                "category": "billing",
                "customer_email": "not-an-email",
            })
        assert "customer_email" in exc.value.messages

    def test_default_priority_is_medium(self):
        data = self.schema.load({
            "subject": "Valid subject",
            "description": "Long enough description for this validation test.",
            "category": "general",
            "customer_email": "u@example.com",
        })
        assert data["priority"] == "medium"


class TestUserRegisterSchema:
    schema = UserRegisterSchema()

    def test_valid_registration(self):
        data = self.schema.load({
            "name": "John Doe",
            "email": "john@example.com",
            "password": "Secure123",
        })
        assert data["name"] == "John Doe"

    def test_password_no_uppercase(self):
        with pytest.raises(ValidationError) as exc:
            self.schema.load({
                "name": "Jane",
                "email": "jane@example.com",
                "password": "nouppercase1",
            })
        assert "password" in exc.value.messages

    def test_password_no_digit(self):
        with pytest.raises(ValidationError) as exc:
            self.schema.load({
                "name": "Jane",
                "email": "jane@example.com",
                "password": "NoDigitsHere",
            })
        assert "password" in exc.value.messages

    def test_password_too_short(self):
        with pytest.raises(ValidationError):
            self.schema.load({
                "name": "Jane",
                "email": "jane@example.com",
                "password": "Short1",
            })

    def test_invalid_email_format(self):
        with pytest.raises(ValidationError):
            self.schema.load({
                "name": "Jane",
                "email": "not-valid",
                "password": "Password1",
            })


class TestTicketStatusUpdateSchema:
    schema = TicketStatusUpdateSchema()

    def test_valid_status(self):
        data = self.schema.load({"status": "in_progress"})
        assert data["status"] == "in_progress"

    def test_invalid_status(self):
        with pytest.raises(ValidationError):
            self.schema.load({"status": "flying"})


class TestTicketPriorityUpdateSchema:
    schema = TicketPriorityUpdateSchema()

    def test_reason_required(self):
        """FR-024: Reason is mandatory when changing priority."""
        with pytest.raises(ValidationError) as exc:
            self.schema.load({"priority": "urgent"})
        assert "reason" in exc.value.messages

    def test_valid_priority_change(self):
        data = self.schema.load({"priority": "urgent", "reason": "Customer escalated this issue."})
        assert data["priority"] == "urgent"


class TestCommentCreateSchema:
    schema = CommentCreateSchema()

    def test_valid_comment(self):
        data = self.schema.load({"content": "This is a helpful comment."})
        assert data["is_internal"] is False

    def test_empty_comment_fails(self):
        with pytest.raises(ValidationError):
            self.schema.load({"content": ""})

    def test_internal_flag(self):
        data = self.schema.load({"content": "Agent note.", "is_internal": True})
        assert data["is_internal"] is True
