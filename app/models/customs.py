"""Customs declaration model."""
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Index, Numeric, String

from app import db


class CustomsDeclaration(db.Model):
    __tablename__ = "customs_declarations"

    id = db.Column(db.Integer, primary_key=True)
    declaration_id = db.Column(db.String(20), unique=True, nullable=False, index=True)
    shipment_id = db.Column(db.String(20), ForeignKey("shipments.shipment_id"), nullable=False, index=True)
    declaration_date = db.Column(db.DateTime, nullable=False, index=True)
    clearance_date = db.Column(db.DateTime)
    customs_status = db.Column(db.String(20), nullable=False)   # PENDING / CLEARED / REJECTED
    declared_value = db.Column(db.Numeric(14, 2))
    duties_amount = db.Column(db.Numeric(14, 2))
    clearance_duration_hours = db.Column(db.Float)
    sla_hours = db.Column(db.Float, nullable=False)
    sla_status = db.Column(db.String(10))                       # ON_TIME / AT_RISK / BREACHED
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    shipment = db.relationship("Shipment", back_populates="customs_declaration")

    __table_args__ = (
        Index("ix_customs_status_date", "customs_status", "declaration_date"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "declaration_id": self.declaration_id,
            "shipment_id": self.shipment_id,
            "declaration_date": self.declaration_date.isoformat() if self.declaration_date else None,
            "clearance_date": self.clearance_date.isoformat() if self.clearance_date else None,
            "customs_status": self.customs_status,
            "declared_value": float(self.declared_value or 0),
            "duties_amount": float(self.duties_amount or 0),
            "clearance_duration_hours": self.clearance_duration_hours,
            "sla_hours": self.sla_hours,
            "sla_status": self.sla_status,
        }
