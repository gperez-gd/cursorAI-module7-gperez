from datetime import datetime, timezone
from ..models.user import User, UserRole, AvailabilityStatus
from ..models.ticket import TicketPriority


def generate_ticket_number(sequence: int) -> str:
    """
    FR-002: Generate unique ticket numbers in the format TICK-YYYYMMDD-XXXX.
    """
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"TICK-{today}-{sequence:04d}"


def auto_assign_agent(category: str = None) -> User | None:
    """
    FR-006: Auto-assign tickets based on agent workload, category expertise,
    and availability.
    """
    from ..models.ticket import TicketStatus

    agents = User.query.filter_by(
        role=UserRole.AGENT,
        availability_status=AvailabilityStatus.AVAILABLE,
        is_active=True,
    ).all()

    if not agents:
        # Fall back to busy agents if no available agents exist
        agents = User.query.filter(
            User.role == UserRole.AGENT,
            User.availability_status != AvailabilityStatus.OFFLINE,
            User.is_active.is_(True),
        ).all()

    if not agents:
        return None

    # Prefer agents with matching expertise
    if category:
        experts = [a for a in agents if category in (a.expertise_areas or [])]
        if experts:
            agents = experts

    # Sort by open ticket count (ascending) to balance workload
    agents.sort(key=lambda a: a.open_ticket_count)
    return agents[0] if agents else None


def paginate_query(query, page: int, per_page: int):
    """Return a Flask-SQLAlchemy Pagination object."""
    return query.paginate(page=page, per_page=per_page, error_out=False)


def format_pagination_meta(pagination):
    return {
        "page": pagination.page,
        "per_page": pagination.per_page,
        "total": pagination.total,
        "pages": pagination.pages,
        "has_next": pagination.has_next,
        "has_prev": pagination.has_prev,
    }


def sanitize_html(text: str) -> str:
    """Strip unsafe HTML tags from user-generated content (NFR-009, NFR-016)."""
    import bleach
    allowed_tags = ["b", "i", "u", "em", "strong", "p", "br", "ul", "ol", "li", "code", "pre"]
    allowed_attributes = {}
    return bleach.clean(text, tags=allowed_tags, attributes=allowed_attributes, strip=True)
