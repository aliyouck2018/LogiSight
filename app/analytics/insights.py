"""Management insights engine — deterministic, rule-based.

Each insight follows the same contract:
    {severity, title, description, metric, current_value, threshold,
     recommended_action}

Rules use simple thresholds and period-over-period comparisons so that
insights are reproducible and explainable.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import and_, case, func, select

from app import db
from app.models import CustomsDeclaration, Shipment, Trip, Vehicle, Warehouse

THRESHOLD_OTD_TARGET = 90.0
THRESHOLD_OTD_CRITICAL = 80.0
THRESHOLD_CUSTOMS_BREACH = 10.0
THRESHOLD_WAREHOUSE_WARNING = 90.0


def _period_counts(start: datetime, end: datetime | None) -> dict:
    conds = [Shipment.planned_departure >= start]
    if end:
        conds.append(Shipment.planned_departure <= end)
    delivered = case((Shipment.status.in_(["DELIVERED", "DELAYED"]), 1), else_=0)
    on_time = case((and_(Shipment.actual_arrival.is_not(None),
                         Shipment.actual_arrival <= Shipment.planned_arrival), 1), else_=0)
    row = db.session.execute(
        select(func.count(Shipment.id).label("total"),
               func.sum(delivered).label("delivered"),
               func.sum(on_time).label("on_time"),
               func.avg(Shipment.cost).label("avg_cost"))
        .where(*conds)
    ).one()
    m = row._mapping
    otd = round(m["on_time"] / m["delivered"] * 100, 1) if m["delivered"] else None
    return {"total": m["total"] or 0, "delivered": m["delivered"] or 0,
            "otd": otd, "avg_cost": m["avg_cost"]}


def generate_insights() -> list[dict]:
    insights: list[dict] = []
    now = datetime.now()

    cur = _period_counts(now - timedelta(days=30), now)
    prev = _period_counts(now - timedelta(days=60), now - timedelta(days=30))

    # ---- OTD level ----
    if cur["otd"] is not None:
        if cur["otd"] < THRESHOLD_OTD_CRITICAL:
            insights.append({
                "severity": "HIGH",
                "title": "Performance de livraison critique",
                "description": f"Le taux de livraison à temps est de {cur['otd']} %, très en dessous "
                               f"de la cible de {THRESHOLD_OTD_TARGET:.0f} %.",
                "metric": "otd_rate", "current_value": cur["otd"], "threshold": THRESHOLD_OTD_TARGET,
                "recommended_action": "Lancer un plan d'action sur les corridors et partenaires les plus impactés.",
            })
        elif cur["otd"] < THRESHOLD_OTD_TARGET:
            insights.append({
                "severity": "WARNING",
                "title": "Livraison à temps sous la cible",
                "description": f"Le taux de livraison à temps est de {cur['otd']} % "
                               f"(cible : {THRESHOLD_OTD_TARGET:.0f} %).",
                "metric": "otd_rate", "current_value": cur["otd"], "threshold": THRESHOLD_OTD_TARGET,
                "recommended_action": "Identifier les causes principales de retard via le tableau de bord douane/transport.",
            })

    # ---- OTD trend ----
    if cur["otd"] is not None and prev["otd"] is not None:
        drop = prev["otd"] - cur["otd"]
        if drop > 2:
            insights.append({
                "severity": "HIGH" if drop > 5 else "WARNING",
                "title": "Dégradation de la livraison à temps",
                "description": f"Le taux de livraison à temps a baissé de {drop:.1f} points "
                               f"par rapport à la période précédente ({prev['otd']} % → {cur['otd']} %).",
                "metric": "otd_trend", "current_value": cur["otd"], "threshold": prev["otd"],
                "recommended_action": "Analyser les périodes et corridors concernés dans les alertes opérationnelles.",
            })
        elif drop < -2:
            insights.append({
                "severity": "INFO",
                "title": "Amélioration de la livraison à temps",
                "description": f"Le taux de livraison à temps a progressé de {abs(drop):.1f} points "
                               f"({prev['otd']} % → {cur['otd']} %).",
                "metric": "otd_trend", "current_value": cur["otd"], "threshold": prev["otd"],
                "recommended_action": "Capitaliser sur les bonnes pratiques de la période.",
            })

    # ---- volume trend ----
    if prev["total"] > 0:
        vol_change = (cur["total"] - prev["total"]) / prev["total"] * 100
        if abs(vol_change) >= 5:
            direction = "augmenté" if vol_change > 0 else "diminué"
            insights.append({
                "severity": "INFO",
                "title": "Évolution du volume d'expéditions",
                "description": f"Le volume d'expéditions a {direction} de {abs(vol_change):.1f} % "
                               f"par rapport au mois précédent.",
                "metric": "volume", "current_value": cur["total"], "threshold": prev["total"],
                "recommended_action": "Vérifier l'adéquation des capacités de transport et d'entreposage.",
            })

    # ---- customs ----
    breach = case((CustomsDeclaration.sla_status == "BREACHED", 1), else_=0)
    cleared = case((CustomsDeclaration.customs_status == "CLEARED", 1), else_=0)
    row = db.session.execute(
        select(func.sum(breach).label("b"), func.sum(cleared).label("c"))
        .where(CustomsDeclaration.declaration_date >= now - timedelta(days=30))
    ).one()
    if row.c:
        breach_rate = round(row.b / row.c * 100, 1)
        if breach_rate > THRESHOLD_CUSTOMS_BREACH:
            insights.append({
                "severity": "HIGH",
                "title": "La douane contribue fortement aux retards",
                "description": f"Le taux de dépassement de SLA douanier atteint {breach_rate} % "
                               f"sur les 30 derniers jours (seuil : {THRESHOLD_CUSTOMS_BREACH:.0f} %).",
                "metric": "customs_breach_rate", "current_value": breach_rate,
                "threshold": THRESHOLD_CUSTOMS_BREACH,
                "recommended_action": "Renforcer le suivi des dossiers sensibles et anticiper les déclarations.",
            })

    # ---- warehouses ----
    rows = db.session.execute(
        select(Warehouse.warehouse_code, Warehouse.city,
               Warehouse.occupied_units, Warehouse.capacity_units)
        .where(Warehouse.active.is_(True))
    ).all()
    for w in rows:
        if not w.capacity_units:
            continue
        util = round(w.occupied_units / w.capacity_units * 100, 1)
        if util > THRESHOLD_WAREHOUSE_WARNING:
            insights.append({
                "severity": "HIGH" if util > 95 else "WARNING",
                "title": f"L'entrepôt {w.warehouse_code} approche de la capacité maximale",
                "description": f"L'entrepôt {w.warehouse_code} ({w.city}) affiche {util} % d'occupation.",
                "metric": "warehouse_utilization", "current_value": util,
                "threshold": THRESHOLD_WAREHOUSE_WARNING,
                "recommended_action": "Organiser des sorties de stock ou rediriger les entrées vers d'autres sites.",
            })

    # ---- worst route (recent window, enough volume) ----
    delivered = case((Shipment.status.in_(["DELIVERED", "DELAYED"]), 1), else_=0)
    on_time = case((and_(Shipment.actual_arrival.is_not(None),
                         Shipment.actual_arrival <= Shipment.planned_arrival), 1), else_=0)
    route_rows = db.session.execute(
        select(Shipment.origin, Shipment.destination,
               func.count(Shipment.id).label("n"),
               func.sum(delivered).label("d"),
               func.sum(on_time).label("o"))
        .where(Shipment.planned_departure >= now - timedelta(days=60))
        .group_by(Shipment.origin, Shipment.destination)
        .having(func.count(Shipment.id) >= 30)
    ).all()
    scored = [(r, r.o / r.d * 100) for r in route_rows if r.d]
    if scored:
        worst, worst_otd = min(scored, key=lambda x: x[1])
        if worst_otd < THRESHOLD_OTD_TARGET - 5:
            insights.append({
                "severity": "HIGH",
                "title": f"Corridor {worst.origin} → {worst.destination} sous-performant",
                "description": f"Le corridor {worst.origin} → {worst.destination} affiche un taux de "
                               f"livraison à temps de {worst_otd:.1f} % sur {worst.n} expéditions (60 jours).",
                "metric": "route_otd", "current_value": round(worst_otd, 1),
                "threshold": THRESHOLD_OTD_TARGET,
                "recommended_action": "Réaliser une revue opérationnelle du corridor avec les transporteurs.",
            })

    # ---- fleet fuel outliers ----
    veh_rows = db.session.execute(
        select(Vehicle.registration_number,
               func.sum(Trip.distance_km).label("distance"),
               func.sum(Trip.fuel_liters).label("fuel"))
        .join(Trip, Trip.vehicle_id == Vehicle.vehicle_id)
        .where(Trip.trip_status == "COMPLETED", Trip.fuel_liters.is_not(None))
        .group_by(Vehicle.id, Vehicle.vehicle_id, Vehicle.registration_number)
    ).all()
    effs = [(v, v.distance / v.fuel) for v in veh_rows if v.fuel]
    if len(effs) >= 5:
        worst_v, worst_eff = min(effs, key=lambda x: x[1])
        avg_eff = sum(e for _, e in effs) / len(effs)
        if worst_eff < avg_eff * 0.8:
            insights.append({
                "severity": "WARNING",
                "title": "Véhicule à la surconsommation anormale",
                "description": f"Le véhicule {worst_v.registration_number} consomme {worst_eff:.2f} km/L "
                               f"contre {avg_eff:.2f} km/L en moyenne flotte.",
                "metric": "fuel_efficiency", "current_value": round(worst_eff, 2),
                "threshold": round(avg_eff * 0.8, 2),
                "recommended_action": "Inspecter le véhicule et revoir son affectation.",
            })

    severity_order = {"HIGH": 0, "WARNING": 1, "INFO": 2}
    insights.sort(key=lambda i: severity_order.get(i["severity"], 3))
    return insights
