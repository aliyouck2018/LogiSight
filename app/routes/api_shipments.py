"""Shipments API endpoints."""
from flask import request

from sqlalchemy import func, or_, select

from app import db
from app.analytics import shipments as ship_analytics
from app.analytics.filters import apply_shipment_filters
from app.models import Customer, Shipment
from app.utils.api import err, ok, paginate_query


def register(bp):
    bp.add_url_rule("/shipments", "shipments_list", _list)
    bp.add_url_rule("/shipments/<shipment_id>", "shipment_detail", _detail)
    bp.add_url_rule("/shipments/<shipment_id>/timeline", "shipment_timeline", _timeline)


def _list():
    args = request.args.to_dict()
    stmt = select(Shipment).join(Customer, Customer.id == Shipment.customer_id)

    # free-text search on shipment id / customer name / cities
    q = args.get("q")
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(
            Shipment.shipment_id.ilike(like),
            Customer.name.ilike(like),
            Shipment.origin.ilike(like),
            Shipment.destination.ilike(like),
        ))

    stmt = apply_shipment_filters(
        stmt,
        start_date=args.get("start_date"),
        end_date=args.get("end_date"),
        origin=args.get("origin"),
        destination=args.get("destination"),
        status=args.get("status"),
        cargo_type=args.get("cargo_type"),
        customer_id=args.get("customer_id"),
    )

    # sorting
    sort_key = args.get("sort", "planned_departure")
    direction = args.get("order", "desc")
    sort_map = {
        "planned_departure": Shipment.planned_departure,
        "planned_arrival": Shipment.planned_arrival,
        "delay_hours": Shipment.delay_hours,
        "risk_score": Shipment.risk_score,
        "cost": Shipment.cost,
        "declared_value": Shipment.declared_value,
        "status": Shipment.status,
        "shipment_id": Shipment.shipment_id,
    }
    col = sort_map.get(sort_key, Shipment.planned_departure)
    stmt = stmt.order_by(col.desc() if direction == "desc" else col.asc())

    items, meta = paginate_query(stmt)
    return ok([s.to_dict() for s in items], meta)


def _detail(shipment_id: str):
    shipment = db.session.execute(
        select(Shipment).where(Shipment.shipment_id == shipment_id)
    ).scalar_one_or_none()
    if shipment is None:
        return err("NOT_FOUND", f"Expédition {shipment_id} introuvable.", 404)
    data = shipment.to_dict()
    data["customer"] = shipment.customer.to_dict() if shipment.customer else None

    decl = shipment.customs_declaration
    data["customs"] = decl.to_dict() if decl else None

    trips = shipment.trips.order_by(Trip.departure_time.asc()).all()
    data["trips"] = [t.to_dict() for t in trips]

    wtrans = shipment.warehouse_transactions.order_by(
        WarehouseTransaction.transaction_date.asc()).all()
    data["warehouse_transactions"] = [t.to_dict() for t in wtrans]
    data["timeline"] = ship_analytics.shipment_timeline(shipment)
    return ok(data)


from app.models import Trip, WarehouseTransaction  # noqa: E402


def _timeline(shipment_id: str):
    shipment = db.session.execute(
        select(Shipment).where(Shipment.shipment_id == shipment_id)
    ).scalar_one_or_none()
    if shipment is None:
        return err("NOT_FOUND", f"Expédition {shipment_id} introuvable.", 404)
    return ok(ship_analytics.shipment_timeline(shipment))
