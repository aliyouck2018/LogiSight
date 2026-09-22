"""Shipment model — core entity."""
from datetime import datetime, timezone

from sqlalchemy import (Boolean, DateTime, Float, ForeignKey, Index,
                        Numeric, String, Text)

from app import db

SHIPMENT_STATUSES = [
    "BOOKED", "IN_TRANSIT", "AT_CUSTOMS", "CUSTOMS_CLEARED",
    "OUT_FOR_DELIVERY", "DELIVERED", "DELAYED", "CANCELLED",
]

ACTIVE_STATUSES = [s for s in SHIPMENT_STATUSES if s not in ("DELIVERED", "CANCELLED")]


class Shipment(db.Model):
    __tablename__ = "shipments"

    id = db.Column(db.Integer, primary_key=True)
    shipment_id = db.Column(db.String(20), unique=True, nullable=False, index=True)
    customer_id = db.Column(db.Integer, ForeignKey("customers.id"), nullable=False, index=True)
    origin = db.Column(db.String(80), nullable=False, index=True)
    destination = db.Column(db.String(80), nullable=False, index=True)
    country_of_origin = db.Column(db.String(80))
    country_of_destination = db.Column(db.String(80))
    cargo_type = db.Column(db.String(40), nullable=False, index=True)
    container_type = db.Column(db.String(40))
    declared_value = db.Column(db.Numeric(14, 2), default=0)
    weight_kg = db.Column(db.Float)
    volume_m3 = db.Column(db.Float)
    planned_departure = db.Column(db.DateTime, nullable=False, index=True)
    actual_departure = db.Column(db.DateTime)
    planned_arrival = db.Column(db.DateTime, index=True)
    actual_arrival = db.Column(db.DateTime, index=True)
    status = db.Column(db.String(20), nullable=False, index=True)
    cost = db.Column(db.Numeric(14, 2), default=0)
    delay_hours = db.Column(db.Float)          # actual_arrival - planned_arrival (hours)
    transit_hours = db.Column(db.Float)        # actual_arrival - actual_departure (hours)
    risk_score = db.Column(db.Float)           # 0..100
    risk_level = db.Column(db.String(10))      # LOW / MEDIUM / HIGH / CRITICAL
    delay_cause = db.Column(db.String(40))     # None when on time
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    customer = db.relationship("Customer", back_populates="shipments")
    customs_declaration = db.relationship("CustomsDeclaration", back_populates="shipment", uselist=False)
    trips = db.relationship("Trip", back_populates="shipment", lazy="dynamic")
    warehouse_transactions = db.relationship("WarehouseTransaction", back_populates="shipment", lazy="dynamic")
    shipment_alerts = db.relationship("Alert", primaryjoin="and_(Alert.entity_type=='SHIPMENT', foreign(Alert.entity_id)==Shipment.shipment_id)", viewonly=True)

    __table_args__ = (
        Index("ix_shipments_customer_status", "customer_id", "status"),
        Index("ix_shipments_route", "origin", "destination"),
        Index("ix_shipments_planned_dep", "planned_departure"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "shipment_id": self.shipment_id,
            "customer_id": self.customer_id,
            "customer_name": self.customer.name if self.customer else None,
            "origin": self.origin,
            "destination": self.destination,
            "country_of_origin": self.country_of_origin,
            "country_of_destination": self.country_of_destination,
            "cargo_type": self.cargo_type,
            "container_type": self.container_type,
            "declared_value": float(self.declared_value or 0),
            "cost": float(self.cost or 0),
            "weight_kg": self.weight_kg,
            "volume_m3": self.volume_m3,
            "planned_departure": self.planned_departure.isoformat() if self.planned_departure else None,
            "actual_departure": self.actual_departure.isoformat() if self.actual_departure else None,
            "planned_arrival": self.planned_arrival.isoformat() if self.planned_arrival else None,
            "actual_arrival": self.actual_arrival.isoformat() if self.actual_arrival else None,
            "status": self.status,
            "delay_hours": self.delay_hours,
            "transit_hours": self.transit_hours,
            "risk_score": self.risk_score,
            "risk_level": self.risk_level,
            "delay_cause": self.delay_cause,
        }
