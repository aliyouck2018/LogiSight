"""Vehicle and trip models."""
from datetime import datetime, timezone

from sqlalchemy import (Boolean, DateTime, Float, ForeignKey, Index,
                        Numeric, String)

from app import db


class Vehicle(db.Model):
    __tablename__ = "vehicles"

    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.String(20), unique=True, nullable=False, index=True)
    registration_number = db.Column(db.String(30), unique=True, nullable=False)
    vehicle_type = db.Column(db.String(30), nullable=False)
    transporter = db.Column(db.String(100), nullable=False, index=True)
    capacity_kg = db.Column(db.Float)
    fuel_type = db.Column(db.String(20))
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    trips = db.relationship("Trip", back_populates="vehicle", lazy="dynamic")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "vehicle_id": self.vehicle_id,
            "registration_number": self.registration_number,
            "vehicle_type": self.vehicle_type,
            "transporter": self.transporter,
            "capacity_kg": self.capacity_kg,
            "fuel_type": self.fuel_type,
            "active": self.active,
        }


class Trip(db.Model):
    __tablename__ = "trips"

    id = db.Column(db.Integer, primary_key=True)
    trip_id = db.Column(db.String(20), unique=True, nullable=False, index=True)
    shipment_id = db.Column(db.String(20), ForeignKey("shipments.shipment_id"), nullable=False, index=True)
    vehicle_id = db.Column(db.String(20), ForeignKey("vehicles.vehicle_id"), nullable=False, index=True)
    driver_name = db.Column(db.String(120))
    origin = db.Column(db.String(80), nullable=False)
    destination = db.Column(db.String(80), nullable=False)
    departure_time = db.Column(db.DateTime, nullable=False, index=True)
    planned_arrival = db.Column(db.DateTime)
    actual_arrival = db.Column(db.DateTime)
    planned_duration_hours = db.Column(db.Float, nullable=False)
    actual_duration_hours = db.Column(db.Float)
    distance_km = db.Column(db.Float)
    fuel_liters = db.Column(db.Float)
    trip_status = db.Column(db.String(20), nullable=False, index=True)  # PLANNED / IN_PROGRESS / COMPLETED / CANCELLED
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    shipment = db.relationship("Shipment", back_populates="trips")
    vehicle = db.relationship("Vehicle", back_populates="trips")

    __table_args__ = (
        Index("ix_trips_vehicle_dep", "vehicle_id", "departure_time"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "trip_id": self.trip_id,
            "shipment_id": self.shipment_id,
            "vehicle_id": self.vehicle_id,
            "vehicle_registration": self.vehicle.registration_number if self.vehicle else None,
            "transporter": self.vehicle.transporter if self.vehicle else None,
            "driver_name": self.driver_name,
            "origin": self.origin,
            "destination": self.destination,
            "departure_time": self.departure_time.isoformat() if self.departure_time else None,
            "planned_arrival": self.planned_arrival.isoformat() if self.planned_arrival else None,
            "actual_arrival": self.actual_arrival.isoformat() if self.actual_arrival else None,
            "planned_duration_hours": self.planned_duration_hours,
            "actual_duration_hours": self.actual_duration_hours,
            "distance_km": self.distance_km,
            "fuel_liters": self.fuel_liters,
            "trip_status": self.trip_status,
        }
