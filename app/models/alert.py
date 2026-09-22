"""Operational alert model."""
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, Text

from app import db

ALERT_CATEGORIES = [
    "CUSTOMS_DELAY", "TRANSPORT_DELAY", "DELIVERY_DELAY",
    "WAREHOUSE_CAPACITY", "SLA_BREACH", "ANOMALOUS_PERFORMANCE",
]

ALERT_SEVERITIES = ["INFO", "WARNING", "HIGH", "CRITICAL"]
ALERT_STATUSES = ["OPEN", "ACKNOWLEDGED", "RESOLVED"]


class Alert(db.Model):
    __tablename__ = "alerts"

    id = db.Column(db.Integer, primary_key=True)
    alert_type = db.Column(db.String(40), nullable=False, index=True)
    severity = db.Column(db.String(10), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(Text)
    entity_type = db.Column(db.String(30))   # SHIPMENT / DECLARATION / WAREHOUSE / ROUTE / VEHICLE / TRIP
    entity_id = db.Column(db.String(20))
    status = db.Column(db.String(15), nullable=False, default="OPEN", index=True)
    recommended_action = db.Column(Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    acknowledged_at = db.Column(db.DateTime)
    resolved_at = db.Column(db.DateTime)

    __table_args__ = (
        Index("ix_alerts_status_severity", "status", "severity"),
        Index("ix_alerts_entity", "entity_type", "entity_id"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "alert_type": self.alert_type,
            "severity": self.severity,
            "title": self.title,
            "description": self.description,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "status": self.status,
            "recommended_action": self.recommended_action,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }
