import pytest
from app import create_app
from app.extensions import db as _db
from app.models.user import User, UserRole, AvailabilityStatus
from app.models.ticket import Ticket, TicketStatus, TicketPriority, TicketCategory
from flask_jwt_extended import create_access_token


@pytest.fixture(scope="session")
def app():
    app = create_app("testing")
    with app.app_context():
        _db.create_all()
        yield app
        _db.drop_all()


@pytest.fixture(scope="function")
def db(app):
    with app.app_context():
        yield _db
        _db.session.remove()
        # Clean tables between tests
        for table in reversed(_db.metadata.sorted_tables):
            _db.session.execute(table.delete())
        _db.session.commit()


@pytest.fixture
def client(app):
    return app.test_client()


# ------------------------------------------------------------------
# User fixtures
# ------------------------------------------------------------------

def _make_user(db, name, email, role, password="Password1"):
    user = User(name=name, email=email, role=role)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def customer_user(db):
    return _make_user(db, "Alice Customer", "alice@example.com", UserRole.CUSTOMER)


@pytest.fixture
def agent_user(db):
    user = _make_user(db, "Bob Agent", "bob@example.com", UserRole.AGENT)
    user.availability_status = AvailabilityStatus.AVAILABLE
    user.expertise_areas = ["technical"]
    db.session.commit()
    return user


@pytest.fixture
def admin_user(db):
    return _make_user(db, "Carol Admin", "carol@example.com", UserRole.ADMIN)


# ------------------------------------------------------------------
# JWT header helpers
# ------------------------------------------------------------------

def _auth_headers(app, user):
    with app.app_context():
        token = create_access_token(identity=str(user.id))
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture
def customer_headers(app, customer_user):
    return _auth_headers(app, customer_user)


@pytest.fixture
def agent_headers(app, agent_user):
    return _auth_headers(app, agent_user)


@pytest.fixture
def admin_headers(app, admin_user):
    return _auth_headers(app, admin_user)


# ------------------------------------------------------------------
# Ticket fixture
# ------------------------------------------------------------------

@pytest.fixture
def sample_ticket(db, customer_user):
    from datetime import datetime, timezone
    ticket = Ticket(
        ticket_number="TICK-20260420-0001",
        subject="Cannot login to my account",
        description="I have been trying to login for the past hour without success.",
        priority=TicketPriority.HIGH,
        category=TicketCategory.TECHNICAL,
        customer_email=customer_user.email,
        created_by_id=customer_user.id,
        status=TicketStatus.OPEN,
    )
    ticket.set_sla_deadlines()
    db.session.add(ticket)
    db.session.commit()
    return ticket
