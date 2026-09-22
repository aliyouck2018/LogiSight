"""Operational alerts engine — deterministic rule-based generation.

Rules (evaluated against the most recent data):
    WAREHOUSE_CAPACITY  — utilization thresholds (85% / 95%)
    SLA_BREACH          — cleared declarations exceeding SLA (recent window)
    CUSTOMS_DELAY       — pending declarations past their SLA
    DELIVERY_DELAY      — shipments with large delivery delays
    TRANSPORT_DELAY     — trips with actual >> planned duration
    ANOMALOUS_PERFORMANCE — statistical outliers (routes, vehicles)

Severity mapping is documented in docs/kpis.md.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, select

from app import db
from app.analytics.stats import mean, std
from app.models import (Alert, CustomsDeclaration, Shipment, Trip,
                        Vehicle, Warehouse)

RECENT_DAYS = 30


def _days_ago(n: int) -> datetime:
    return datetime.now() - timedelta(days=n)


def warehouse_capacity_alerts() -> list[dict]:
    alerts = []
    rows = db.session.execute(select(Warehouse)).scalars().all()
    for w in rows:
        if not w.capacity_units:
            continue
        util = w.occupied_units / w.capacity_units * 100
        if util > 95:
            severity = "CRITICAL"
            action = "Libérer des capacités ou transférer le stock vers un entrepôt voisin."
        elif util > 85:
            severity = "HIGH"
            action = "Planifier des sorties de stock et geler les nouvelles entrées non prioritaires."
        else:
            continue
        alerts.append({
            "alert_type": "WAREHOUSE_CAPACITY",
            "severity": severity,
            "title": f"{w.warehouse_code} — Capacité entrepôt",
            "description": f"L'entrepôt {w.warehouse_code} ({w.city}) atteint {util:.0f}% d'occupation "
                           f"({int(w.occupied_units)} / {int(w.capacity_units)} unités).",
            "entity_type": "WAREHOUSE",
            "entity_id": w.warehouse_code,
            "recommended_action": action,
        })
    return alerts


def sla_breach_alerts(limit: int = 15) -> list[dict]:
    cutoff = _days_ago(RECENT_DAYS)
    rows = db.session.execute(
        select(CustomsDeclaration)
        .where(CustomsDeclaration.sla_status == "BREACHED",
               CustomsDeclaration.clearance_date >= cutoff,
               CustomsDeclaration.clearance_duration_hours.is_not(None))
        .order_by((CustomsDeclaration.clearance_duration_hours /
                   CustomsDeclaration.sla_hours).desc())
        .limit(limit)
    ).scalars().all()
    alerts = []
    for d in rows:
        ratio = d.clearance_duration_hours / d.sla_hours if d.sla_hours else 0
        if ratio >= 2:
            severity = "CRITICAL"
        elif ratio >= 1.5:
            severity = "HIGH"
        else:
            severity = "WARNING"
        alerts.append({
            "alert_type": "SLA_BREACH",
            "severity": severity,
            "title": f"Déclaration {d.declaration_id} — SLA dépassé",
            "description": f"La déclaration douanière {d.declaration_id} a dépassé le SLA de "
                           f"{d.clearance_duration_hours - d.sla_hours:.1f} h "
                           f"({d.clearance_duration_hours:.0f} h pour un SLA de {d.sla_hours:.0f} h).",
            "entity_type": "DECLARATION",
            "entity_id": d.declaration_id,
            "recommended_action": "Contacter le commissionnaire en douane et prioriser le dossier.",
        })
    return alerts


def pending_customs_alerts(limit: int = 10) -> list[dict]:
    rows = db.session.execute(
        select(CustomsDeclaration)
        .where(CustomsDeclaration.customs_status == "PENDING",
               CustomsDeclaration.declaration_date < _days_ago(3))
        .order_by(CustomsDeclaration.declaration_date.asc())
        .limit(limit)
    ).scalars().all()
    alerts = []
    now = datetime.now()
    for d in rows:
        overdue_h = (now - d.declaration_date).total_seconds() / 3600 - (d.sla_hours or 0)
        if overdue_h <= 0:
            continue
        severity = "CRITICAL" if overdue_h > 48 else "HIGH"
        alerts.append({
            "alert_type": "CUSTOMS_DELAY",
            "severity": severity,
            "title": f"Déclaration {d.declaration_id} — Dédouanement en attente",
            "description": f"La déclaration {d.declaration_id} est en attente depuis "
                           f"{(now - d.declaration_date).total_seconds() / 3600:.0f} h "
                           f"(SLA {d.sla_hours:.0f} h dépassé de {overdue_h:.0f} h).",
            "entity_type": "DECLARATION",
            "entity_id": d.declaration_id,
            "recommended_action": "Vérifier les documents et relancer le service douane.",
        })
    return alerts


def delivery_delay_alerts(limit: int = 15) -> list[dict]:
    rows = db.session.execute(
        select(Shipment)
        .where(Shipment.delay_hours > 48,
               Shipment.planned_departure >= _days_ago(RECENT_DAYS * 2),
               Shipment.status.in_(["DELIVERED", "DELAYED"]))
        .order_by(Shipment.delay_hours.desc())
        .limit(limit)
    ).scalars().all()
    alerts = []
    for s in rows:
        if s.delay_hours > 168:
            severity = "CRITICAL"
        elif s.delay_hours > 96:
            severity = "HIGH"
        else:
            severity = "WARNING"
        alerts.append({
            "alert_type": "DELIVERY_DELAY",
            "severity": severity,
            "title": f"Expédition {s.shipment_id} — Retard de livraison",
            "description": f"L'expédition {s.shipment_id} ({s.origin} → {s.destination}) présente "
                           f"un retard de {s.delay_hours:.0f} h par rapport à l'arrivée prévue.",
            "entity_type": "SHIPMENT",
            "entity_id": s.shipment_id,
            "recommended_action": "Informer le client et identifier la cause du retard.",
        })
    return alerts


def transport_delay_alerts(limit: int = 10) -> list[dict]:
    rows = db.session.execute(
        select(Trip)
        .where(Trip.trip_status == "COMPLETED",
               Trip.departure_time >= _days_ago(RECENT_DAYS),
               Trip.actual_duration_hours > Trip.planned_duration_hours * 1.5)
        .order_by((Trip.actual_duration_hours / Trip.planned_duration_hours).desc())
        .limit(limit)
    ).scalars().all()
    alerts = []
    for t in rows:
        ratio = t.actual_duration_hours / t.planned_duration_hours if t.planned_duration_hours else 0
        severity = "CRITICAL" if ratio >= 2 else "HIGH"
        alerts.append({
            "alert_type": "TRANSPORT_DELAY",
            "severity": severity,
            "title": f"Tournée {t.trip_id} — Transport en retard",
            "description": f"La tournée {t.trip_id} ({t.origin} → {t.destination}) a duré "
                           f"{t.actual_duration_hours:.0f} h au lieu de {t.planned_duration_hours:.0f} h "
                           f"prévues ({(ratio - 1) * 100:.0f}% au-dessus).",
            "entity_type": "TRIP",
            "entity_id": t.trip_id,
            "recommended_action": "Analyser les conditions de la tournée (route, véhicule, conducteur).",
        })
    return alerts


def anomalous_performance_alerts() -> list[dict]:
    """Statistical outliers: route delays (z-score > 2) and fuel consumption."""
    alerts = []
    cutoff = _days_ago(60)

    # --- routes: average delay per route over recent window ---
    rows = db.session.execute(
        select(Shipment.origin, Shipment.destination,
               func.avg(Shipment.delay_hours).label("avg_delay"),
               func.count(Shipment.id).label("n"))
        .where(Shipment.planned_departure >= cutoff,
               Shipment.delay_hours.is_not(None))
        .group_by(Shipment.origin, Shipment.destination)
        .having(func.count(Shipment.id) >= 20)
    ).all()
    if len(rows) >= 5:
        values = [r.avg_delay for r in rows]
        mu, sigma = mean(values), std(values)
        if sigma > 0:
            for r in rows:
                z = (r.avg_delay - mu) / sigma
                if z > 2:
                    alerts.append({
                        "alert_type": "ANOMALOUS_PERFORMANCE",
                        "severity": "HIGH",
                        "title": f"Corridor {r.origin} → {r.destination} — Retards anormaux",
                        "description": f"Le corridor {r.origin} → {r.destination} présente un retard moyen "
                                       f"de {r.avg_delay:.1f} h (z-score {z:.1f}), significativement au-dessus "
                                       f"de la moyenne des corridors ({mu:.1f} h).",
                        "entity_type": "ROUTE",
                        "entity_id": f"{r.origin}|{r.destination}",
                        "recommended_action": "Mener une revue du corridor avec les transporteurs concernés.",
                    })

    # --- vehicles: fuel efficiency outliers ---
    rows = db.session.execute(
        select(Vehicle.vehicle_id, Vehicle.registration_number,
               func.sum(Trip.distance_km).label("distance"),
               func.sum(Trip.fuel_liters).label("fuel"))
        .join(Trip, Trip.vehicle_id == Vehicle.vehicle_id)
        .where(Trip.trip_status == "COMPLETED", Trip.fuel_liters.is_not(None))
        .group_by(Vehicle.vehicle_id)
        .having(func.sum(Trip.fuel_liters) > 0)
    ).all()
    if len(rows) >= 5:
        effs = [r.distance / r.fuel for r in rows if r.fuel]
        mu, sigma = mean(effs), std(effs)
        if sigma > 0:
            for r in rows:
                if not r.fuel:
                    continue
                eff = r.distance / r.fuel
                z = (eff - mu) / sigma
                if z < -2:
                    alerts.append({
                        "alert_type": "ANOMALOUS_PERFORMANCE",
                        "severity": "WARNING",
                        "title": f"Véhicule {r.registration_number} — Surconsommation",
                        "description": f"Le véhicule {r.registration_number} consomme {eff:.2f} km/L, "
                                       f"très en dessous de la moyenne de la flotte ({mu:.2f} km/L).",
                        "entity_type": "VEHICLE",
                        "entity_id": r.vehicle_id,
                        "recommended_action": "Programmer une inspection technique du véhicule.",
                    })
    return alerts


def generate_all_alerts() -> int:
    """Regenerate OPEN alerts. Existing ACKNOWLEDGED/RESOLVED alerts are kept."""
    now = datetime.now()
    db.session.query(Alert).filter(Alert.status == "OPEN").delete()

    generated = (
        warehouse_capacity_alerts()
        + sla_breach_alerts()
        + pending_customs_alerts()
        + delivery_delay_alerts()
        + transport_delay_alerts()
        + anomalous_performance_alerts()
    )

    severity_order = {"CRITICAL": 0, "HIGH": 1, "WARNING": 2, "INFO": 3}
    generated.sort(key=lambda a: severity_order.get(a["severity"], 4))

    rows = []
    for a in generated:
        rows.append({
            "alert_type": a["alert_type"],
            "severity": a["severity"],
            "title": a["title"],
            "description": a["description"],
            "entity_type": a["entity_type"],
            "entity_id": a["entity_id"],
            "status": "OPEN",
            "recommended_action": a["recommended_action"],
            "created_at": now,
        })
    if rows:
        db.session.execute(Alert.__table__.insert(), rows)
    db.session.commit()
    return len(rows)
