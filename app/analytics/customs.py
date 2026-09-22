"""Customs analytics: summary KPIs, trends, breaches."""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import case, func, select

from app import db
from app.models import CustomsDeclaration, Shipment


def customs_summary(args: dict) -> dict:
    """KPIs: declarations, cleared, pending, avg clearance, SLA breach rate, longest."""
    start = args.get("start_date")
    end = args.get("end_date")

    conds = []
    if start:
        conds.append(CustomsDeclaration.declaration_date >= start)
    if end:
        conds.append(CustomsDeclaration.declaration_date <= end + " 23:59:59")

    breach = case((CustomsDeclaration.sla_status == "BREACHED", 1), else_=0)
    cleared = case((CustomsDeclaration.customs_status == "CLEARED", 1), else_=0)
    pending = case((CustomsDeclaration.customs_status == "PENDING", 1), else_=0)

    row = db.session.execute(
        select(
            func.count(CustomsDeclaration.id).label("total"),
            func.sum(cleared).label("cleared"),
            func.sum(pending).label("pending"),
            func.avg(case(
                (CustomsDeclaration.customs_status == "CLEARED",
                 CustomsDeclaration.clearance_duration_hours), else_=None)).label("avg_clearance"),
            func.sum(breach).label("breached"),
            func.max(CustomsDeclaration.clearance_duration_hours).label("longest"),
        ).where(*conds)
    ).one()
    m = row._mapping

    cleared_n = m["cleared"] or 0
    breached_n = m["breached"] or 0

    # previous-period comparison for the breach rate
    prev_conds = []
    if start and end:
        from app.analytics.filters import previous_window
        ps, pe = previous_window(start, end)
        if ps and pe:
            prev_conds = [CustomsDeclaration.declaration_date >= ps,
                          CustomsDeclaration.declaration_date <= pe]
    prev_breach_rate = None
    if prev_conds:
        prow = db.session.execute(
            select(func.count(CustomsDeclaration.id).label("total"),
                   func.sum(breach).label("breached"),
                   func.sum(cleared).label("cleared")).where(*prev_conds)
        ).one()
        if prow.cleared:
            prev_breach_rate = round(prow.breached / prow.cleared * 100, 1)

    from app.analytics.kpis import customs_sla_breach_rate
    breach_rate = customs_sla_breach_rate(breached_n, cleared_n)

    return {
        "total_declarations": m["total"] or 0,
        "cleared": cleared_n,
        "pending": m["pending"] or 0,
        "avg_clearance_hours": round(m["avg_clearance"], 1) if m["avg_clearance"] else None,
        "sla_breach_rate": breach_rate,
        "sla_breach_rate_previous": prev_breach_rate,
        "longest_clearance_hours": round(m["longest"], 1) if m["longest"] else None,
    }


def customs_trends(months: int = 12) -> dict:
    """Clearance time trend + SLA breaches by period."""
    end = datetime.now()
    start = end - timedelta(days=months * 31)
    month = func.strftime("%Y-%m", CustomsDeclaration.declaration_date).label("month")
    breach = case((CustomsDeclaration.sla_status == "BREACHED", 1), else_=0)
    rows = db.session.execute(
        select(month,
               func.avg(CustomsDeclaration.clearance_duration_hours).label("avg_h"),
               func.sum(breach).label("breaches"),
               func.count(CustomsDeclaration.id).label("total"))
        .where(CustomsDeclaration.declaration_date >= start,
               CustomsDeclaration.customs_status == "CLEARED")
        .group_by(month).order_by(month)
    ).all()
    return {
        "labels": [r.month for r in rows],
        "avg_clearance_hours": [round(r.avg_h, 1) if r.avg_h else None for r in rows],
        "breaches": [r.breaches for r in rows],
        "breach_rate": [round(r.breaches / r.total * 100, 1) if r.total else None for r in rows],
    }


def clearance_by_dimension(dimension: str, limit: int = 10) -> list[dict]:
    """Avg clearance time grouped by cargo_type or destination."""
    if dimension == "cargo":
        group_col = Shipment.cargo_type
    else:
        group_col = Shipment.destination
    rows = db.session.execute(
        select(group_col.label("dim"),
               func.avg(CustomsDeclaration.clearance_duration_hours).label("avg_h"),
               func.count(CustomsDeclaration.id).label("n"))
        .join(Shipment, Shipment.shipment_id == CustomsDeclaration.shipment_id)
        .where(CustomsDeclaration.customs_status == "CLEARED")
        .group_by(group_col)
        .order_by(func.avg(CustomsDeclaration.clearance_duration_hours).desc())
        .limit(limit)
    ).all()
    return [{"label": r.dim, "avg_clearance_hours": round(r.avg_h, 1), "count": r.n} for r in rows]


def sla_breaches(args: dict, page: int = 1, per_page: int = 25):
    """Paginated list of breached declarations."""
    conds = [CustomsDeclaration.sla_status == "BREACHED"]
    if args.get("start_date"):
        conds.append(CustomsDeclaration.declaration_date >= args["start_date"])
    if args.get("end_date"):
        conds.append(CustomsDeclaration.declaration_date <= args["end_date"] + " 23:59:59")
    query = select(CustomsDeclaration).where(*conds).order_by(
        CustomsDeclaration.clearance_duration_hours.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False) \
        if hasattr(query, "paginate") else None
    return query, conds
