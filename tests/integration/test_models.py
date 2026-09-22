"""Integration tests: data model, data quality, alert generation."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402

from sqlalchemy import func, select  # noqa: E402

from app import db  # noqa: E402
from app.analytics.alerts import generate_all_alerts  # noqa: E402
from app.models import (Alert, CustomsDeclaration, Customer, Shipment,  # noqa: E402
                        Trip, Vehicle, Warehouse)


def test_models_present(app):
    with app.app_context():
        for model in (Customer, Shipment, CustomsDeclaration, Vehicle, Trip,
                      Warehouse, Alert):
            count = db.session.execute(select(func.count(model.id))).scalar()
            assert count is not None


def test_seed_volumes(app):
    with app.app_context():
        shipments = db.session.execute(select(func.count(Shipment.id))).scalar()
        declarations = db.session.execute(
            select(func.count(CustomsDeclaration.id))).scalar()
        trips = db.session.execute(select(func.count(Trip.id))).scalar()
        assert shipments >= 50
        assert declarations > 0
        assert trips > 0


def test_shipment_risk_scores_assigned(app):
    with app.app_context():
        missing = db.session.execute(
            select(func.count(Shipment.id)).where(Shipment.risk_score.is_(None))
        ).scalar()
        assert missing == 0
        levels = db.session.execute(
            select(Shipment.risk_level, func.count(Shipment.id))
            .group_by(Shipment.risk_level)
        ).all()
        assert all(level in ("LOW", "MEDIUM", "HIGH", "CRITICAL") for level, _ in levels)


def test_shipment_actual_arrival_not_before_departure(app):
    with app.app_context():
        invalid = db.session.execute(
            select(func.count(Shipment.id)).where(
                Shipment.actual_arrival.is_not(None),
                Shipment.actual_departure.is_not(None),
                Shipment.actual_arrival < Shipment.actual_departure)
        ).scalar()
        assert invalid == 0


def test_customs_clearance_not_before_declaration(app):
    with app.app_context():
        invalid = db.session.execute(
            select(func.count(CustomsDeclaration.id)).where(
                CustomsDeclaration.clearance_date.is_not(None),
                CustomsDeclaration.clearance_date < CustomsDeclaration.declaration_date)
        ).scalar()
        assert invalid == 0


def test_alert_generation(app):
    with app.app_context():
        before = db.session.execute(select(func.count(Alert.id))).scalar()
        generated = generate_all_alerts()
        assert generated > 0
        after = db.session.execute(select(func.count(Alert.id))).scalar()
        assert after > before or before == 0

        # every open alert has required fields
        for a in db.session.execute(select(Alert).where(Alert.status == "OPEN")).scalars():
            assert a.title
            assert a.severity in ("INFO", "WARNING", "HIGH", "CRITICAL")
            assert a.alert_type in (
                "CUSTOMS_DELAY", "TRANSPORT_DELAY", "DELIVERY_DELAY",
                "WAREHOUSE_CAPACITY", "SLA_BREACH", "ANOMALOUS_PERFORMANCE")
