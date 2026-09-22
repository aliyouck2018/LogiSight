"""Shipment risk scoring — deterministic, documented model.

Risk score composition (0..100):
    - Delay component        40%  — delay vs planned arrival
    - Customs component      25%  — customs SLA pressure
    - Route component        20%  — historical route reliability
    - Operational component  15%  — warehouse / misc signals

Risk levels:
    0-24   LOW
    25-49  MEDIUM
    50-74  HIGH
    75-100 CRITICAL
"""

from __future__ import annotations

from typing import Optional

DELAY_WEIGHT = 0.40
CUSTOMS_WEIGHT = 0.25
ROUTE_WEIGHT = 0.20
OPERATIONAL_WEIGHT = 0.15

RISK_LEVELS = [
    (75, "CRITICAL"),
    (50, "HIGH"),
    (25, "MEDIUM"),
    (0, "LOW"),
]


def risk_level(score: Optional[float]) -> str:
    if score is None:
        return "LOW"
    for threshold, level in RISK_LEVELS:
        if score >= threshold:
            return level
    return "LOW"


def delay_component(delay_hours: Optional[float], transit_hours: Optional[float]) -> float:
    """Normalize delay to 0..1.

    A shipment is considered fully delayed (1.0) when delay exceeds
    50% of its planned transit or 48 hours, whichever is smaller.
    """
    if delay_hours is None or delay_hours <= 0:
        return 0.0
    reference = min((transit_hours or 24) * 0.5, 48.0)
    reference = max(reference, 6.0)
    return min(delay_hours / reference, 1.0)


def customs_component(sla_hours: Optional[float], clearance_hours: Optional[float]) -> float:
    """Ratio of clearance duration against SLA, capped at 1."""
    if not sla_hours:
        return 0.25 if clearance_hours else 0.0
    if not clearance_hours:
        return 0.0  # not cleared yet — neutral
    return min(clearance_hours / sla_hours, 1.0)


def route_component(route_badness: Optional[float]) -> float:
    """route_badness: 0 (excellent) .. 1 (historically problematic)."""
    if route_badness is None:
        return 0.0
    return min(max(route_badness, 0.0), 1.0)


def operational_component(delay_cause: Optional[str]) -> float:
    """Operational signal: warehouse-related or unknown delays score higher."""
    if delay_cause == "ENTREPOT":
        return 0.8
    if delay_cause in ("DOCUMENTATION", "AUTRES"):
        return 0.5
    return 0.0


def compute_risk_score(
    *,
    delay_hours: Optional[float],
    transit_hours: Optional[float],
    sla_hours: Optional[float],
    clearance_hours: Optional[float],
    route_badness: Optional[float],
    delay_cause: Optional[str],
) -> float:
    """Compute the 0..100 risk score for one shipment."""
    score = (
        DELAY_WEIGHT * delay_component(delay_hours, transit_hours)
        + CUSTOMS_WEIGHT * customs_component(sla_hours, clearance_hours)
        + ROUTE_WEIGHT * route_component(route_badness)
        + OPERATIONAL_WEIGHT * operational_component(delay_cause)
    ) * 100
    return round(min(max(score, 0.0), 100.0), 1)
