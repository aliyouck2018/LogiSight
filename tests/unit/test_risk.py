"""Unit tests for the shipment risk scoring model."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.analytics.risk import (compute_risk_score, customs_component,
                                delay_component, risk_level)


def _score(delay=0, transit=24, sla=72, clearance=None, route=0.0, cause=None):
    return compute_risk_score(
        delay_hours=delay, transit_hours=transit, sla_hours=sla,
        clearance_hours=clearance, route_badness=route, delay_cause=cause,
    )


def test_risk_level_bands():
    assert risk_level(0) == "LOW"
    assert risk_level(24.9) == "LOW"
    assert risk_level(25) == "MEDIUM"
    assert risk_level(49.9) == "MEDIUM"
    assert risk_level(50) == "HIGH"
    assert risk_level(74.9) == "HIGH"
    assert risk_level(75) == "CRITICAL"
    assert risk_level(100) == "CRITICAL"


def test_healthy_shipment_is_low():
    assert risk_level(_score()) == "LOW"


def test_delayed_shipment_scores_higher():
    healthy = _score()
    late = _score(delay=30, transit=48)
    assert late > healthy
    assert risk_level(late) in ("MEDIUM", "HIGH", "CRITICAL")


def test_delay_component_saturation():
    # No delay -> 0 ; beyond the reference window, the component saturates at 1.0
    assert delay_component(0, 48) == 0.0
    assert delay_component(-5, 48) == 0.0
    assert delay_component(200, 48) == 1.0


def test_customs_component_breach_increases_risk():
    within_sla = customs_component(72, 36)
    breached = customs_component(72, 120)
    assert breached > within_sla
    assert breached == 1.0


def test_warehouse_delay_cause_adds_risk():
    with_cause = _score(delay=5, transit=48, cause="ENTREPOT")
    without = _score(delay=5, transit=48)
    assert with_cause > without


def test_bad_route_adds_risk():
    assert _score(route=0.9) > _score(route=0.0)


def test_score_bounds():
    assert 0 <= _score(delay=500, transit=48, route=1.0, cause="ENTREPOT", clearance=500) <= 100
