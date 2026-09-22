"""Warehouse and warehouse transaction models."""
from datetime import datetime, timezone

from sqlalchemy import (DateTime, Float, ForeignKey, Index, Numeric,
                        String, UniqueConstraint)

from app import db


class Warehouse(db.Model):
    __tablename__ = "warehouses"

    id = db.Column(db.Integer, primary_key=True)
    warehouse_code = db.Column(db.String(20), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    city = db.Column(db.String(80), nullable=False)
    capacity_units = db.Column(db.Float, nullable=False)
    occupied_units = db.Column(db.Float, nullable=False, default=0)
    warehouse_type = db.Column(db.String(30))
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    transactions = db.relationship("WarehouseTransaction", back_populates="warehouse", lazy="dynamic")

    def to_dict(self) -> dict:
        utilization = (self.occupied_units / self.capacity_units * 100) if self.capacity_units else 0
        return {
            "id": self.id,
            "warehouse_code": self.warehouse_code,
            "name": self.name,
            "city": self.city,
            "capacity_units": self.capacity_units,
            "occupied_units": self.occupied_units,
            "utilization": round(utilization, 1),
            "warehouse_type": self.warehouse_type,
            "active": self.active,
        }


class WarehouseTransaction(db.Model):
    __tablename__ = "warehouse_transactions"

    id = db.Column(db.Integer, primary_key=True)
    warehouse_id = db.Column(db.Integer, ForeignKey("warehouses.id"), nullable=False, index=True)
    shipment_id = db.Column(db.String(20), ForeignKey("shipments.shipment_id"), nullable=False, index=True)
    transaction_type = db.Column(db.String(15), nullable=False)  # IN / OUT / ADJUSTMENT
    quantity = db.Column(db.Float, nullable=False)
    transaction_date = db.Column(db.DateTime, nullable=False, index=True)
    storage_duration_days = db.Column(db.Float)
    storage_cost = db.Column(db.Numeric(12, 2))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    warehouse = db.relationship("Warehouse", back_populates="transactions")
    shipment = db.relationship("Shipment", back_populates="warehouse_transactions")

    __table_args__ = (
        Index("ix_wtrans_type_date", "transaction_type", "transaction_date"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "warehouse_id": self.warehouse_id,
            "shipment_id": self.shipment_id,
            "transaction_type": self.transaction_type,
            "quantity": self.quantity,
            "transaction_date": self.transaction_date.isoformat() if self.transaction_date else None,
            "storage_duration_days": self.storage_duration_days,
            "storage_cost": float(self.storage_cost or 0),
        }
