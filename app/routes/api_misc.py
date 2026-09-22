"""Misc API endpoints: insights, filter metadata, map data, data quality."""
from flask import request
from sqlalchemy import case, func, select

from app import db
from app.analytics import insights as insights_analytics
from app.models import (CustomsDeclaration, Customer, Route, Shipment, Trip,
                        Vehicle, Warehouse)
from app.utils.api import ok

# City coordinates for the logistics flow map
CITY_COORDS = {
    "Douala": [4.0483, 9.7043], "Yaoundé": [3.8480, 11.5021],
    "Kribi": [2.9400, 9.9100], "Bafoussam": [5.4781, 10.4176],
    "Bamenda": [5.9597, 10.1459], "Bertoua": [4.5772, 13.6846],
    "Garoua": [9.3016, 13.3921], "Ngaoundéré": [7.3167, 13.5833],
    "Shanghai": [31.2304, 121.4737], "Dubaï": [25.2048, 55.2708],
    "Lagos": [6.5244, 3.3792], "Abidjan": [5.3599, -4.0083],
    "Le Havre": [49.4938, 0.1077], "Anvers": [51.2194, 4.4025],
}


def register(bp):
    bp.add_url_rule("/insights", "insights_list", _insights)
    bp.add_url_rule("/meta/filters", "meta_filters", _filters)
    bp.add_url_rule("/map/routes", "map_routes", _map_routes)
    bp.add_url_rule("/data-quality", "data_quality", _data_quality)


def _insights():
    return ok(insights_analytics.generate_insights())


def _filters():
    """Distinct filter options for the global filter bar."""
    origins = [r[0] for r in db.session.execute(
        select(Shipment.origin).distinct().order_by(Shipment.origin)).all()]
    destinations = [r[0] for r in db.session.execute(
        select(Shipment.destination).distinct().order_by(Shipment.destination)).all()]
    cargo_types = [r[0] for r in db.session.execute(
        select(Shipment.cargo_type).distinct().order_by(Shipment.cargo_type)).all()]
    statuses = [r[0] for r in db.session.execute(
        select(Shipment.status).distinct()).all()]
    customers = [
        {"id": r[0], "name": r[1]}
        for r in db.session.execute(
            select(Customer.id, Customer.name).order_by(Customer.name)).all()
    ]
    return ok({
        "origins": origins,
        "destinations": destinations,
        "cargo_types": cargo_types,
        "statuses": statuses,
        "customers": customers,
    })


def _map_routes():
    """Route aggregates for the flow map (volume, OTD, avg delay)."""
    delivered = case((Shipment.status.in_(["DELIVERED", "DELAYED"]), 1), else_=0)
    on_time = case((Shipment.actual_arrival <= Shipment.planned_arrival, 1), else_=0)
    rows = db.session.execute(
        select(
            Shipment.origin, Shipment.destination,
            func.count(Shipment.id).label("volume"),
            func.sum(delivered).label("delivered"),
            func.sum(on_time).label("on_time"),
            func.avg(Shipment.delay_hours).label("avg_delay"),
        )
        .group_by(Shipment.origin, Shipment.destination)
        .having(func.count(Shipment.id) >= 5)
    ).all()
    routes = []
    for r in rows:
        if r.origin not in CITY_COORDS or r.destination not in CITY_COORDS:
            continue
        routes.append({
            "origin": r.origin,
            "destination": r.destination,
            "from": CITY_COORDS[r.origin],
            "to": CITY_COORDS[r.destination],
            "volume": r.volume,
            "otd": round(r.on_time / r.delivered * 100, 1) if r.delivered else None,
            "avg_delay": round(r.avg_delay or 0, 1),
        })
    return ok({"cities": CITY_COORDS, "routes": routes})


def _data_quality():
    """Basic data-quality report (missing/invalid/suspicious records)."""
    checks = []

    def add(name, value, status):
        checks.append({"check": name, "value": value, "status": status})

    total = db.session.execute(select(func.count(Shipment.id))).scalar()

    arrival_before_departure = db.session.execute(
        select(func.count(Shipment.id)).where(
            Shipment.actual_arrival.is_not(None),
            Shipment.actual_departure.is_not(None),
            Shipment.actual_arrival < Shipment.actual_departure)
    ).scalar()
    add("Arrivée avant départ", arrival_before_departure,
        "OK" if arrival_before_departure == 0 else "INVALID")

    clearance_before_declaration = db.session.execute(
        select(func.count(CustomsDeclaration.id)).where(
            CustomsDeclaration.clearance_date.is_not(None),
            CustomsDeclaration.clearance_date < CustomsDeclaration.declaration_date)
    ).scalar()
    add("Dédouanement avant déclaration", clearance_before_declaration,
        "OK" if clearance_before_declaration == 0 else "INVALID")

    negative_distance = db.session.execute(
        select(func.count(Route.id)).where(Route.distance_km < 0)).scalar()
    add("Distance négative", negative_distance,
        "OK" if negative_distance == 0 else "INVALID")

    negative_weight = db.session.execute(
        select(func.count(Shipment.id)).where(Shipment.weight_kg < 0)).scalar()
    add("Poids négatif", negative_weight, "OK" if negative_weight == 0 else "INVALID")

    negative_fuel = db.session.execute(
        select(func.count(Trip.id)).where(Trip.fuel_liters < 0)).scalar()
    add("Consommation négative", negative_fuel, "OK" if negative_fuel == 0 else "INVALID")

    over_capacity = db.session.execute(
        select(func.count(Warehouse.id)).where(
            Warehouse.occupied_units > Warehouse.capacity_units * 1.05)).scalar()
    add("Occupation > capacité (+5%)", over_capacity,
        "OK" if over_capacity == 0 else "SUSPICIOUS")

    missing_risk = db.session.execute(
        select(func.count(Shipment.id)).where(Shipment.risk_score.is_(None))).scalar()
    add("Score de risque manquant", missing_risk,
        "OK" if missing_risk == 0 else "WARNING")

    duplicate_vehicle = db.session.execute(
        select(func.count())
        .select_from(
            select(Vehicle.vehicle_id)
            .group_by(Vehicle.vehicle_id)
            .having(func.count() > 1)
            .subquery()
        )
    ).scalar() or 0
    add("Véhicules en doublon", duplicate_vehicle,
        "OK" if duplicate_vehicle == 0 else "INVALID")

    ok_count = sum(1 for c in checks if c["status"] == "OK")
    return ok({
        "total_shipments": total,
        "checks": checks,
        "summary": f"{ok_count}/{len(checks)} contrôles OK",
    })
