"""Transport analytics: trips KPIs, route/vehicle/transporter performance."""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import case, func, select

from app import db
from app.models import Trip, Vehicle

COMPLETED = "COMPLETED"


def transport_summary(args: dict) -> dict:
    conds = [Trip.trip_status == COMPLETED]
    if args.get("start_date"):
        conds.append(Trip.departure_time >= args["start_date"])
    if args.get("end_date"):
        conds.append(Trip.departure_time <= args["end_date"] + " 23:59:59")

    on_time = case((Trip.actual_arrival <= Trip.planned_arrival, 1), else_=0)
    row = db.session.execute(
        select(
            func.count(Trip.id).label("total"),
            func.sum(on_time).label("on_time"),
            func.avg(Trip.actual_duration_hours - Trip.planned_duration_hours).label("avg_delay"),
            func.avg(Trip.distance_km / Trip.actual_duration_hours).label("avg_speed"),
            func.sum(Trip.distance_km).label("distance"),
            func.sum(Trip.fuel_liters).label("fuel"),
        ).where(*conds)
    ).one()
    m = row._mapping

    distance = m["distance"] or 0
    fuel = m["fuel"] or 0
    return {
        "total_trips": m["total"] or 0,
        "on_time_trips": m["on_time"] or 0,
        "on_time_rate": round((m["on_time"] or 0) / (m["total"] or 1) * 100, 1),
        "avg_delay_hours": round(m["avg_delay"], 1) if m["avg_delay"] is not None else None,
        "avg_speed_kmh": round(m["avg_speed"], 1) if m["avg_speed"] else None,
        "total_distance_km": round(distance, 0),
        "total_fuel_liters": round(fuel, 0),
        "fuel_efficiency_km_l": round(distance / fuel, 2) if fuel else None,
    }


def performance_by_dimension(dimension: str, limit: int = 10) -> list[dict]:
    """Trip performance grouped by route, vehicle or transporter."""
    joins_vehicle = dimension in ("vehicle", "transporter")
    if dimension == "route":
        group_cols = [Trip.origin, Trip.destination]
        label = lambda r: f"{r.origin} → {r.destination}"  # noqa: E731
    elif dimension == "vehicle":
        group_cols = [Vehicle.vehicle_id, Vehicle.registration_number]
        label = lambda r: r.registration_number or r.vehicle_id  # noqa: E731
    else:
        group_cols = [Vehicle.transporter]
        label = lambda r: r.transporter  # noqa: E731

    on_time = case((Trip.actual_arrival <= Trip.planned_arrival, 1), else_=0)
    query = (
        select(*group_cols,
               func.count(Trip.id).label("trips"),
               func.sum(on_time).label("on_time"),
               func.avg(Trip.actual_duration_hours - Trip.planned_duration_hours).label("avg_delay"),
               func.sum(Trip.distance_km).label("distance"),
               func.sum(Trip.fuel_liters).label("fuel"))
        .where(Trip.trip_status == COMPLETED)
        .group_by(*group_cols)
        .having(func.count(Trip.id) >= 10)
    )
    if joins_vehicle:
        query = query.join(Vehicle, Vehicle.vehicle_id == Trip.vehicle_id)
    rows = db.session.execute(query.order_by(func.count(Trip.id).desc()).limit(limit)).all()

    out = []
    for r in rows:
        m = r._mapping
        fuel = m["fuel"] or 0
        out.append({
            "label": label(r),
            "trips": m["trips"],
            "otd_rate": round(m["on_time"] / m["trips"] * 100, 1),
            "avg_delay_hours": round(m["avg_delay"] or 0, 1),
            "distance_km": round(m["distance"] or 0, 0),
            "fuel_efficiency_km_l": round(m["distance"] / fuel, 2) if fuel else None,
        })
    return out


def delay_distribution() -> dict:
    """Histogram of trip delays (actual - planned) in hours."""
    delays = db.session.execute(
        select(Trip.actual_duration_hours - Trip.planned_duration_hours)
        .where(Trip.trip_status == COMPLETED)
    ).scalars().all()
    buckets = {"< -2h": 0, "-2h..0": 0, "0..4h": 0, "4h..12h": 0, "12h..24h": 0, "> 24h": 0}
    for d in delays:
        if d is None:
            continue
        if d < -2:
            buckets["< -2h"] += 1
        elif d < 0:
            buckets["-2h..0"] += 1
        elif d < 4:
            buckets["0..4h"] += 1
        elif d < 12:
            buckets["4h..12h"] += 1
        elif d < 24:
            buckets["12h..24h"] += 1
        else:
            buckets["> 24h"] += 1
    return {"labels": list(buckets.keys()), "counts": list(buckets.values())}


def planned_vs_actual_by_month(months: int = 12) -> dict:
    end = datetime.now()
    start = end - timedelta(days=months * 31)
    month = func.strftime("%Y-%m", Trip.departure_time).label("month")
    rows = db.session.execute(
        select(month,
               func.avg(Trip.planned_duration_hours).label("planned"),
               func.avg(Trip.actual_duration_hours).label("actual"))
        .where(Trip.trip_status == COMPLETED, Trip.departure_time >= start)
        .group_by(month).order_by(month)
    ).all()
    return {
        "labels": [r.month for r in rows],
        "planned": [round(r.planned, 1) for r in rows],
        "actual": [round(r.actual, 1) for r in rows],
    }
