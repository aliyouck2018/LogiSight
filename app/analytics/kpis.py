"""KPI calculation functions.

Every KPI has a documented definition — see docs/kpis.md.
Functions are pure where practical and operate on SQL aggregates.
"""
from __future__ import annotations

from sqlalchemy import Select, func

from app.models import Shipment


def otd_rate(delivered_on_time: int, delivered_total: int) -> float | None:
    """On-Time Delivery Rate = on-time delivered / delivered."""
    if not delivered_total:
        return None
    return round(delivered_on_time / delivered_total * 100, 1)


def warehouse_utilization(occupied: float, capacity: float) -> float | None:
    """Utilization = occupied / capacity * 100."""
    if not capacity:
        return None
    return round(occupied / capacity * 100, 1)


def fuel_efficiency(distance_km: float, fuel_liters: float) -> float | None:
    """Fuel efficiency = distance / fuel."""
    if not fuel_liters:
        return None
    return round(distance_km / fuel_liters, 2)


def customs_sla_breach_rate(breached: int, cleared: int) -> float | None:
    """SLA breach rate = breached declarations / cleared declarations."""
    if not cleared:
        return None
    return round(breached / cleared * 100, 1)
