import re

from marshmallow import EXCLUDE, Schema, ValidationError, fields, validate, validates


# ---------------------------------------------------------------------------
# Reusable field helpers
# ---------------------------------------------------------------------------

def _password_complexity(value: str) -> None:
    """AUTH-FR-001: min 8 chars, at least one digit, one special char."""
    if len(value) < 8:
        raise ValidationError("Password must be at least 8 characters long.")
    if not re.search(r"\d", value):
        raise ValidationError("Password must contain at least one digit.")
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>_\-+=\[\]\\\/`~;']", value):
        raise ValidationError("Password must contain at least one special character.")


# ---------------------------------------------------------------------------
# Auth schemas
# ---------------------------------------------------------------------------

class RegisterSchema(Schema):
    email = fields.Email(required=True)
    password = fields.String(required=True, load_only=True)
    firstName = fields.String(load_default=None, validate=validate.Length(max=255))
    lastName = fields.String(load_default=None, validate=validate.Length(max=255))

    @validates("password")
    def validate_password(self, value):
        _password_complexity(value)


class LoginSchema(Schema):
    email = fields.Email(required=True)
    password = fields.String(required=True, load_only=True)


# ---------------------------------------------------------------------------
# User schemas
# ---------------------------------------------------------------------------

class UserUpdateSchema(Schema):
    firstName = fields.String(load_default=None, validate=validate.Length(max=255))
    lastName = fields.String(load_default=None, validate=validate.Length(max=255))
    savedAddresses = fields.List(fields.Dict(), load_default=None)


class AdminUserCreateSchema(Schema):
    email = fields.Email(required=True)
    password = fields.String(required=True, load_only=True)
    role = fields.String(load_default="user", validate=validate.OneOf(["user", "admin"]))

    @validates("password")
    def validate_password(self, value):
        _password_complexity(value)


# ---------------------------------------------------------------------------
# Product schemas
# ---------------------------------------------------------------------------

VALID_SORT_FIELDS = {"name", "price", "rating", "createdAt"}
VALID_SORT_ORDERS = {"asc", "desc"}
VALID_CATEGORIES = {"Electronics", "Accessories", "Footwear", "Office"}


class ProductCreateSchema(Schema):
    name = fields.String(required=True, validate=validate.Length(min=1, max=255))
    description = fields.String(load_default=None)
    price = fields.Decimal(required=True, as_string=False)
    stock = fields.Integer(required=True, validate=validate.Range(min=0))
    category = fields.String(
        required=True, validate=validate.OneOf(list(VALID_CATEGORIES))
    )
    imageUrl = fields.String(load_default=None, validate=validate.Length(max=500))
    badge = fields.String(load_default=None, validate=validate.Length(max=50))

    @validates("price")
    def validate_price(self, value):
        if value < 0:
            raise ValidationError("price must be a non-negative value.")


class ProductUpdateSchema(Schema):
    name = fields.String(validate=validate.Length(min=1, max=255))
    description = fields.String()
    price = fields.Decimal(as_string=False)
    stock = fields.Integer(validate=validate.Range(min=0))
    category = fields.String(validate=validate.OneOf(list(VALID_CATEGORIES)))
    imageUrl = fields.String(validate=validate.Length(max=500))
    badge = fields.String(validate=validate.Length(max=50))

    @validates("price")
    def validate_price(self, value):
        if value < 0:
            raise ValidationError("price must be a non-negative value.")


# ---------------------------------------------------------------------------
# Cart schemas
# ---------------------------------------------------------------------------

class CartItemAddSchema(Schema):
    productId = fields.String(required=True)
    quantity = fields.Integer(required=True, validate=validate.Range(min=1, max=10))


class CartItemUpdateSchema(Schema):
    quantity = fields.Integer(required=True, validate=validate.Range(min=0))


class DiscountApplySchema(Schema):
    code = fields.String(required=True, validate=validate.Length(min=1, max=50))


# ---------------------------------------------------------------------------
# Shipping address schema
# ---------------------------------------------------------------------------

class ShippingAddressSchema(Schema):
    firstName = fields.String(required=True, validate=validate.Length(min=1, max=100))
    lastName = fields.String(required=True, validate=validate.Length(min=1, max=100))
    email = fields.Email(required=True)
    street = fields.String(required=True, validate=validate.Length(min=1, max=255))
    city = fields.String(required=True, validate=validate.Length(min=1, max=100))
    state = fields.String(required=True, validate=validate.Length(min=1, max=100))
    zip = fields.String(required=True, validate=validate.Length(min=1, max=20))
    country = fields.String(required=True, validate=validate.Length(min=2, max=2))


# ---------------------------------------------------------------------------
# Checkout schema
# ---------------------------------------------------------------------------

class CheckoutSchema(Schema):
    # CHK-FR-009 / TC-S-010: unknown fields (e.g. tamperedTotal, tamperedPrice)
    # must be silently ignored so the server always uses its own pricing.
    class Meta:
        unknown = EXCLUDE

    shippingAddress = fields.Nested(ShippingAddressSchema, required=True)
    paymentToken = fields.String(load_default=None)
    paypalToken = fields.String(load_default=None)
    savedCardId = fields.String(load_default=None)
    discountCode = fields.String(load_default=None, validate=validate.Length(max=50))
    idempotencyKey = fields.String(load_default=None, validate=validate.Length(max=128))


# ---------------------------------------------------------------------------
# Order status schema
# ---------------------------------------------------------------------------

VALID_ORDER_STATUSES = {"Processing", "Shipped", "Delivered", "Cancelled"}


class OrderStatusUpdateSchema(Schema):
    status = fields.String(
        required=True, validate=validate.OneOf(list(VALID_ORDER_STATUSES))
    )


# ---------------------------------------------------------------------------
# Utility: load-or-abort
# ---------------------------------------------------------------------------

def load_or_400(schema: Schema, data: dict) -> tuple[dict, list]:
    """Return (loaded_data, errors). Caller must check errors and return 400."""
    try:
        return schema.load(data), []
    except ValidationError as exc:
        flat_errors = []
        for field, msgs in exc.messages.items():
            if isinstance(msgs, list):
                flat_errors.extend(f"{field}: {m}" for m in msgs)
            elif isinstance(msgs, dict):
                for sub_field, sub_msgs in msgs.items():
                    flat_errors.extend(f"{field}.{sub_field}: {m}" for m in sub_msgs)
        return {}, flat_errors
