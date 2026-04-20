"""
Admin & reporting blueprint (FR-029, FR-030, FR-031).

GET  /api/admin/dashboard
GET  /api/admin/reports/tickets
GET  /api/admin/reports/agents
GET  /api/admin/reports/sla
POST /api/admin/reports/export
"""
import csv
import io
from datetime import datetime, timezone, timedelta
from flask import Blueprint, request, jsonify, Response
from flask_jwt_extended import jwt_required
from sqlalchemy import func

from ..extensions import db, cache
from ..models.ticket import Ticket, TicketStatus, TicketPriority, TicketCategory
from ..models.user import User, UserRole
from ..utils.decorators import admin_required, error_response, success_response

admin_bp = Blueprint("admin", __name__)


@admin_bp.get("/dashboard")
@jwt_required()
@admin_required
@cache.cached(timeout=120, key_prefix="admin_dashboard")
def dashboard():
    """
    Admin dashboard metrics (FR-029).
    ---
    tags:
      - Admin
    security:
      - Bearer: []
    responses:
      200:
        description: Dashboard metrics
    """
    total = Ticket.query.count()
    by_status = {
        s.value: Ticket.query.filter_by(status=s).count()
        for s in TicketStatus
    }
    by_priority = {
        p.value: Ticket.query.filter_by(priority=p).count()
        for p in TicketPriority
    }
    by_category = {
        c.value: Ticket.query.filter_by(category=c).count()
        for c in TicketCategory
    }

    # Average resolution time (hours)
    resolved = Ticket.query.filter(Ticket.resolved_at.isnot(None)).all()
    avg_resolution_hours = None
    if resolved:
        durations = []
        for t in resolved:
            created = t.created_at
            resolved_at = t.resolved_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            if resolved_at.tzinfo is None:
                resolved_at = resolved_at.replace(tzinfo=timezone.utc)
            durations.append((resolved_at - created).total_seconds() / 3600)
        avg_resolution_hours = round(sum(durations) / len(durations), 2)

    # SLA compliance
    tickets_with_sla = Ticket.query.filter(Ticket.sla_resolution_met.isnot(None)).all()
    sla_met = sum(1 for t in tickets_with_sla if t.sla_resolution_met)
    sla_rate = round(sla_met / len(tickets_with_sla) * 100, 1) if tickets_with_sla else None

    # Agent performance
    agents = User.query.filter_by(role=UserRole.AGENT, is_active=True).all()
    agent_metrics = []
    for agent in agents:
        open_count = agent.assigned_tickets.filter(
            Ticket.status.notin_([TicketStatus.CLOSED, TicketStatus.RESOLVED])
        ).count()
        resolved_count = agent.assigned_tickets.filter_by(status=TicketStatus.RESOLVED).count()
        agent_metrics.append({
            "id": agent.id,
            "name": agent.name,
            "open_tickets": open_count,
            "resolved_tickets": resolved_count,
            "availability": agent.availability_status.value,
        })

    return success_response({
        "total_tickets": total,
        "by_status": by_status,
        "by_priority": by_priority,
        "by_category": by_category,
        "avg_resolution_hours": avg_resolution_hours,
        "sla_compliance_rate": sla_rate,
        "agent_metrics": agent_metrics,
    })


@admin_bp.get("/reports/tickets")
@jwt_required()
@admin_required
def ticket_report():
    """
    Ticket volume report by date range (FR-030).
    ---
    tags:
      - Admin
    security:
      - Bearer: []
    parameters:
      - in: query
        name: days
        schema:
          type: integer
          default: 30
    responses:
      200:
        description: Ticket report
    """
    days = request.args.get("days", 30, type=int)
    since = datetime.now(timezone.utc) - timedelta(days=days)

    tickets = Ticket.query.filter(Ticket.created_at >= since).order_by(Ticket.created_at.asc()).all()

    data = []
    for t in tickets:
        data.append({
            "ticket_number": t.ticket_number,
            "subject": t.subject,
            "status": t.status.value,
            "priority": t.priority.value,
            "category": t.category.value,
            "customer_email": t.customer_email,
            "created_at": t.created_at.isoformat(),
            "resolved_at": t.resolved_at.isoformat() if t.resolved_at else None,
        })

    return success_response({"period_days": days, "count": len(data), "tickets": data})


@admin_bp.get("/reports/agents")
@jwt_required()
@admin_required
def agent_report():
    """
    Agent performance report (FR-030).
    ---
    tags:
      - Admin
    security:
      - Bearer: []
    responses:
      200:
        description: Agent performance data
    """
    agents = User.query.filter_by(role=UserRole.AGENT).all()
    result = []
    for agent in agents:
        all_assigned = agent.assigned_tickets.count()
        resolved = agent.assigned_tickets.filter_by(status=TicketStatus.RESOLVED).count()
        closed = agent.assigned_tickets.filter_by(status=TicketStatus.CLOSED).count()
        result.append({
            "id": agent.id,
            "name": agent.name,
            "email": agent.email,
            "availability": agent.availability_status.value,
            "expertise_areas": agent.expertise_areas or [],
            "total_assigned": all_assigned,
            "resolved": resolved,
            "closed": closed,
        })

    return success_response(result)


@admin_bp.get("/reports/sla")
@jwt_required()
@admin_required
def sla_report():
    """
    SLA compliance report (FR-030).
    ---
    tags:
      - Admin
    security:
      - Bearer: []
    responses:
      200:
        description: SLA compliance breakdown
    """
    result = {}
    for priority in TicketPriority:
        tickets = Ticket.query.filter(
            Ticket.priority == priority,
            Ticket.sla_resolution_due.isnot(None),
        ).all()
        total = len(tickets)
        met = sum(1 for t in tickets if t.sla_resolution_met is True)
        missed = sum(1 for t in tickets if t.sla_resolution_met is False or t.is_sla_missed())
        result[priority.value] = {
            "total": total,
            "met": met,
            "missed": missed,
            "compliance_rate": round(met / total * 100, 1) if total else None,
        }

    return success_response(result)


@admin_bp.post("/reports/export")
@jwt_required()
@admin_required
def export_report():
    """
    Export ticket report as CSV (FR-031).
    ---
    tags:
      - Admin
    security:
      - Bearer: []
    requestBody:
      content:
        application/json:
          schema:
            type: object
            properties:
              days:
                type: integer
                default: 30
    responses:
      200:
        description: CSV file
        content:
          text/csv:
            schema:
              type: string
    """
    body = request.get_json() or {}
    days = body.get("days", 30)
    since = datetime.now(timezone.utc) - timedelta(days=days)

    tickets = Ticket.query.filter(Ticket.created_at >= since).order_by(Ticket.created_at.asc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Ticket #", "Subject", "Status", "Priority", "Category",
                     "Customer Email", "Assigned To", "Created At", "Resolved At", "SLA Met"])

    for t in tickets:
        writer.writerow([
            t.ticket_number,
            t.subject,
            t.status.value,
            t.priority.value,
            t.category.value,
            t.customer_email,
            t.assigned_to.name if t.assigned_to else "",
            t.created_at.isoformat(),
            t.resolved_at.isoformat() if t.resolved_at else "",
            str(t.sla_resolution_met) if t.sla_resolution_met is not None else "",
        ])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=tickets_last_{days}_days.csv"},
    )
