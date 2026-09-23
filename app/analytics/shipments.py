"""Shipment analytics: listing support, detail timeline, route stats."""
from __future__ import annotations

from sqlalchemy import String, and_, case, func, select

from app import db
from app.utils.sql import month_key
from app.models import CustomsDeclaration, Shipment, Trip, WarehouseTransaction


def shipment_timeline(shipment: Shipment) -> list[dict]:
    """Build the visual timeline for a shipment detail page."""
    steps = []

    departure_ok = shipment.actual_departure is not None
    steps.append({
        "key": "departure",
        "label": "Départ",
        "location": shipment.origin,
        "planned": shipment.planned_departure.isoformat() if shipment.planned_departure else None,
        "actual": shipment.actual_departure.isoformat() if departure_ok else None,
    })

    decl: CustomsDeclaration | None = shipment.customs_declaration
    if decl is not None:
        steps.append({
            "key": "customs",
            "label": "Douane",
            "location": shipment.destination if shipment.origin in ("Douala", "Kribi") else shipment.destination,
            "planned": decl.declaration_date.isoformat() if decl.declaration_date else None,
            "actual": decl.clearance_date.isoformat() if decl.clearance_date else None,
            "sla_status": decl.sla_status,
            "duration_hours": decl.clearance_duration_hours,
            "declaration_id": decl.declaration_id,
        })

    main_trip = shipment.trips.order_by(Trip.departure_time.desc()).first()
    if main_trip is not None:
        steps.append({
            "key": "transport",
            "label": "Transport",
            "location": f"{main_trip.origin} → {main_trip.destination}",
            "planned": main_trip.planned_arrival.isoformat() if main_trip.planned_arrival else None,
            "actual": main_trip.actual_arrival.isoformat() if main_trip.actual_arrival else None,
            "duration_hours": main_trip.actual_duration_hours,
            "trip_id": main_trip.trip_id,
        })

    steps.append({
        "key": "delivery",
        "label": "Livraison",
        "location": shipment.destination,
        "planned": shipment.planned_arrival.isoformat() if shipment.planned_arrival else None,
        "actual": shipment.actual_arrival.isoformat() if shipment.actual_arrival else None,
    })
    return steps


def route_monthly_stats(origin: str, destination: str, months: int = 12) -> dict:
    """Monthly volume + OTD for a specific route (drill-down)."""
    delivered = case((Shipment.status.in_(["DELIVERED", "DELAYED"]), 1), else_=0)
    on_time = case(
        (and_(Shipment.actual_arrival.is_not(None), Shipment.actual_arrival <= Shipment.planned_arrival), 1), else_=0)
    month = month_key(Shipment.planned_departure).label("month")
    rows = db.session.execute(
        select(month, func.count(Shipment.id).label("n"),
               func.sum(delivered).label("d"), func.sum(on_time).label("o"))
        .where(Shipment.origin == origin, Shipment.destination == destination)
        .group_by(month).order_by(month)
    ).all()
    return {
        "labels": [r.month for r in rows],
        "volume": [r.n for r in rows],
        "otd": [round(r.o / r.d * 100, 1) if r.d else None for r in rows],
    }
