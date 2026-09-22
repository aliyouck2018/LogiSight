"""Dashboard analytics: KPI summary, trends, distributions.

All aggregates are computed in SQL — the full dataset is never loaded
into memory. Shipments are attributed to a period by planned_departure.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import and_, case, func, select

from app import db
from app.analytics.filters import (DEFAULT_RECENT_DAYS, parse_date,
                                   previous_window)
from app.models import Customer, Shipment, Warehouse

ACTIVE_EXCLUDED = ("DELIVERED", "CANCELLED")


def _resolve_period(args: dict) -> tuple[datetime, datetime, datetime | None, datetime | None]:
    """Return (start, end, prev_start, prev_end).

    No explicit dates -> full history; deltas computed on the last 30 days.
    Explicit dates    -> window vs preceding equal-length window.
    """
    if args.get("start_date") or args.get("end_date"):
        start = parse_date(args.get("start_date")) or datetime(2000, 1, 1)
        end = parse_date(args.get("end_date"), end_of_day=True) or datetime.now()
        prev_start, prev_end = previous_window(args.get("start_date"), args.get("end_date"))
        return start, end, prev_start, prev_end

    end = datetime.now()
    start = datetime(2000, 1, 1)
    prev_start = end - timedelta(days=DEFAULT_RECENT_DAYS)
    prev_end = end
    return start, end, prev_start, prev_end


def _period_filters(start: datetime | None, end: datetime | None):
    conds = []
    if start:
        conds.append(Shipment.planned_departure >= start)
    if end:
        conds.append(Shipment.planned_departure <= end)
    return conds


def _entity_filters(args: dict):
    conds = []
    if args.get("origin"):
        conds.append(Shipment.origin == args["origin"])
    if args.get("destination"):
        conds.append(Shipment.destination == args["destination"])
    if args.get("cargo_type"):
        conds.append(Shipment.cargo_type == args["cargo_type"])
    if args.get("customer_id"):
        conds.append(Shipment.customer_id == int(args["customer_id"]))
    if args.get("status"):
        conds.append(Shipment.status == args["status"])
    return conds


def _base_query(args: dict):
    return select(Shipment).where(*_entity_filters(args)).subquery()


def dashboard_summary(args: dict) -> dict:
    """Compute the 10 executive KPIs + deltas vs previous period."""
    start, end, prev_start, prev_end = _resolve_period(args)
    entity = _entity_filters(args)

    def kpis_for(start_dt: datetime | None, end_dt: datetime | None) -> dict:
        conds = list(entity) + _period_filters(start_dt, end_dt)
        delivered = case((Shipment.status.in_(["DELIVERED", "DELAYED"]), 1), else_=0)
        on_time = case(
            (and_(Shipment.actual_arrival.is_not(None), Shipment.actual_arrival <= Shipment.planned_arrival), 1),
            else_=0,
        )
        q = db.session.execute(
            select(
                func.count(Shipment.id).label("total"),
                func.sum(case((Shipment.status.notin_(ACTIVE_EXCLUDED), 1), else_=0)).label("active"),
                func.sum(delivered).label("delivered"),
                func.sum(on_time).label("on_time"),
                func.avg(case((and_(Shipment.actual_arrival.is_not(None), Shipment.transit_hours.is_not(None)),
                               Shipment.transit_hours), else_=None)).label("avg_transit"),
                func.avg(Shipment.delay_hours).label("avg_delay"),
                func.sum(case((and_(Shipment.delay_hours.is_not(None), Shipment.delay_hours > 0), 1), else_=0)).label("delayed"),
                func.avg(Shipment.cost).label("avg_cost"),
                func.sum(Shipment.cost).label("total_cost"),
            ).where(*conds)
        ).one()
        return q._asdict() if hasattr(q, "_asdict") else dict(q._mapping)

    value = kpis_for(start, end)

    # Delta basis: for the default (unbounded) period, compare the last 30
    # days against the previous 30 days; otherwise use the preceding window.
    if not (args.get("start_date") or args.get("end_date")):
        now = datetime.now()
        recent_start = now - timedelta(days=DEFAULT_RECENT_DAYS)
        mid = now - timedelta(days=DEFAULT_RECENT_DAYS * 2)
        cur = kpis_for(recent_start, now)
        prev = kpis_for(mid, recent_start)
    else:
        cur = value
        prev = kpis_for(prev_start, prev_end)

    delivered_cur = cur["delivered"] or 0
    delivered_prev = prev["delivered"] or 0
    otd_cur = (cur["on_time"] or 0) / delivered_cur * 100 if delivered_cur else None
    otd_prev = (prev["on_time"] or 0) / delivered_prev * 100 if delivered_prev else None

    def delta(c_v, p_v, as_pct=False):
        if c_v is None or p_v in (None, 0):
            return None
        d = (c_v - p_v)
        if as_pct:
            return round(d / p_v * 100, 1)
        return round(d, 1)

    total_delta = delta(cur["total"], prev["total"], as_pct=True)
    # "active" is a stock metric — window deltas are not meaningful
    otd_delta = round(otd_cur - otd_prev, 1) if otd_cur is not None and otd_prev is not None else None
    transit_delta = delta(cur["avg_transit"], prev["avg_transit"], as_pct=True)
    cost_delta = delta(cur["avg_cost"], prev["avg_cost"], as_pct=True)
    delay_delta = delta(cur["avg_delay"], prev["avg_delay"], as_pct=True)

    # warehouse utilization (not time-filtered)
    wh = db.session.execute(
        select(func.coalesce(func.sum(Warehouse.capacity_units), 0),
               func.coalesce(func.sum(Warehouse.occupied_units), 0))
    ).one()
    capacity, occupied = float(wh[0]), float(wh[1])
    utilization = round(occupied / capacity * 100, 1) if capacity else None

    # customs clearance average (joined via declaration table is done in customs module;
    # here we expose the shipment-level view)
    from app.models import CustomsDeclaration
    decl_conds = [CustomsDeclaration.declaration_date >= start] if start else []
    if end:
        decl_conds.append(CustomsDeclaration.declaration_date <= end)
    customs_avg = db.session.execute(
        select(func.avg(CustomsDeclaration.clearance_duration_hours))
        .where(CustomsDeclaration.customs_status == "CLEARED", *decl_conds)
    ).scalar()

    return {
        "period": {
            "start": start.isoformat() if start.year > 2000 else None,
            "end": end.isoformat(),
            "previous_start": prev_start.isoformat() if prev_start else None,
            "previous_end": prev_end.isoformat() if prev_end else None,
        },
        "kpis": [
            {"key": "total_shipments", "label": "Total des expéditions", "value": value["total"] or 0, "delta": total_delta, "unit": "", "icon": "box"},
            {"key": "active_shipments", "label": "Expéditions en cours", "value": value["active"] or 0, "delta": None, "unit": "", "icon": "truck"},
            {"key": "delivered", "label": "Livrées", "value": value["delivered"] or 0, "delta": None, "unit": "", "icon": "check"},
            {"key": "otd_rate", "label": "Taux de livraison à temps", "value": round(otd_cur, 1) if otd_cur is not None else None, "delta": otd_delta, "unit": "%", "icon": "clock"},
            {"key": "avg_delivery_time", "label": "Délai de livraison moyen", "value": round((value["avg_transit"] or 0) / 24, 1), "delta": transit_delta, "unit": "jours", "icon": "clock"},
            {"key": "avg_customs_clearance", "label": "Délai moyen douane", "value": round((customs_avg or 0) / 24, 1), "delta": None, "unit": "jours", "icon": "shield"},
            {"key": "avg_transit_delay", "label": "Retard moyen", "value": round(value["avg_delay"] or 0, 1), "delta": delay_delta, "unit": "h", "icon": "clock"},
            {"key": "delayed_shipments", "label": "Expéditions retardées", "value": value["delayed"] or 0, "delta": None, "unit": "", "icon": "alert"},
            {"key": "warehouse_utilization", "label": "Taux d'occupation entrepôts", "value": utilization, "delta": None, "unit": "%", "icon": "warehouse"},
            {"key": "avg_cost", "label": "Coût moyen / expédition", "value": round(value["avg_cost"] or 0, 0), "delta": cost_delta, "unit": "XAF", "icon": "coins"},
        ],
    }


def shipment_trends(args: dict, months: int = 12) -> dict:
    """Monthly shipment volume + OTD trend."""
    entity = _entity_filters(args)
    start, end, _, _ = _resolve_period(args)
    trend_start = max(start, end - timedelta(days=months * 31))

    delivered = case((Shipment.status.in_(["DELIVERED", "DELAYED"]), 1), else_=0)
    on_time = case(
        (and_(Shipment.actual_arrival.is_not(None), Shipment.actual_arrival <= Shipment.planned_arrival), 1), else_=0)
    month = func.strftime("%Y-%m", Shipment.planned_departure).label("month")

    rows = db.session.execute(
        select(month,
               func.count(Shipment.id).label("volume"),
               func.sum(delivered).label("delivered"),
               func.sum(on_time).label("on_time"))
        .where(*entity, Shipment.planned_departure >= trend_start, Shipment.planned_departure <= end)
        .group_by(month).order_by(month)
    ).all()

    labels, volume, otd = [], [], []
    for r in rows:
        labels.append(r.month)
        volume.append(r.volume)
        otd.append(round(r.on_time / r.delivered * 100, 1) if r.delivered else None)
    return {"labels": labels, "volume": volume, "otd": otd}


def status_distribution(args: dict) -> dict:
    entity = _entity_filters(args)
    start, end, _, _ = _resolve_period(args)
    rows = db.session.execute(
        select(Shipment.status, func.count(Shipment.id))
        .where(*entity, *_period_filters(start, end))
        .group_by(Shipment.status)
    ).all()
    return {status: count for status, count in rows}


def delay_causes(args: dict) -> dict:
    entity = _entity_filters(args)
    start, end, _, _ = _resolve_period(args)
    rows = db.session.execute(
        select(Shipment.delay_cause, func.count(Shipment.id))
        .where(*entity, *_period_filters(start, end), Shipment.delay_cause.is_not(None))
        .group_by(Shipment.delay_cause)
        .order_by(func.count(Shipment.id).desc())
    ).all()
    total = sum(c for _, c in rows) or 1
    return {
        "labels": [r[0] for r in rows],
        "counts": [r[1] for r in rows],
        "shares": [round(r[1] / total * 100, 1) for r in rows],
    }


def route_performance(args: dict, limit: int = 8) -> dict:
    """Per-route OTD and average delay, for the selected period."""
    entity = _entity_filters(args)
    start, end, _, _ = _resolve_period(args)
    delivered = case((Shipment.status.in_(["DELIVERED", "DELAYED"]), 1), else_=0)
    on_time = case(
        (and_(Shipment.actual_arrival.is_not(None), Shipment.actual_arrival <= Shipment.planned_arrival), 1), else_=0)
    rows = db.session.execute(
        select(Shipment.origin, Shipment.destination,
               func.count(Shipment.id).label("volume"),
               func.sum(delivered).label("delivered"),
               func.sum(on_time).label("on_time"),
               func.avg(Shipment.delay_hours).label("avg_delay"))
        .where(*entity, *_period_filters(start, end))
        .group_by(Shipment.origin, Shipment.destination)
        .having(func.count(Shipment.id) >= 10)
        .order_by(func.count(Shipment.id).desc())
        .limit(limit * 3)
    ).all()
    routes = []
    for r in rows:
        if not r.delivered:
            continue
        routes.append({
            "route": f"{r.origin} → {r.destination}",
            "origin": r.origin,
            "destination": r.destination,
            "volume": r.volume,
            "otd": round(r.on_time / r.delivered * 100, 1),
            "avg_delay": round(r.avg_delay or 0, 1),
        })
    routes.sort(key=lambda x: x["volume"], reverse=True)
    return routes[:limit]


def customs_clearance_trend(args: dict, months: int = 12) -> dict:
    from app.models import CustomsDeclaration
    month = func.strftime("%Y-%m", CustomsDeclaration.declaration_date).label("month")
    end = datetime.now()
    start = end - timedelta(days=months * 31)
    breach = case((CustomsDeclaration.sla_status == "BREACHED", 1), else_=0)
    rows = db.session.execute(
        select(month,
               func.avg(CustomsDeclaration.clearance_duration_hours).label("avg_clearance"),
               func.sum(breach).label("breaches"),
               func.count(CustomsDeclaration.id).label("total"))
        .where(CustomsDeclaration.declaration_date >= start,
               CustomsDeclaration.customs_status == "CLEARED")
        .group_by(month).order_by(month)
    ).all()
    return {
        "labels": [r.month for r in rows],
        "avg_clearance_hours": [round(r.avg_clearance, 1) if r.avg_clearance else None for r in rows],
        "breach_rate": [round(r.breaches / r.total * 100, 1) if r.total else None for r in rows],
    }


def warehouse_utilization_by_warehouse() -> list[dict]:
    rows = db.session.execute(
        select(Warehouse.warehouse_code, Warehouse.name, Warehouse.city,
               Warehouse.capacity_units, Warehouse.occupied_units)
        .where(Warehouse.active.is_(True))
        .order_by(Warehouse.warehouse_code)
    ).all()
    return [
        {
            "warehouse_code": r.warehouse_code,
            "name": r.name,
            "city": r.city,
            "capacity": float(r.capacity_units),
            "occupied": float(r.occupied_units),
            "utilization": round(r.occupied_units / r.capacity_units * 100, 1) if r.capacity_units else None,
        }
        for r in rows
    ]


def recent_shipments(args: dict, limit: int = 8) -> list[dict]:
    entity = _entity_filters(args)
    rows = db.session.execute(
        select(Shipment).where(*entity).order_by(Shipment.planned_departure.desc()).limit(limit)
    ).scalars().all()
    return [s.to_dict() for s in rows]
