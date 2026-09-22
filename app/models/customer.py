"""Customer model."""
from datetime import datetime, timezone

from sqlalchemy import DateTime, Index, String

from app import db


class Customer(db.Model):
    __tablename__ = "customers"

    id = db.Column(db.Integer, primary_key=True)
    customer_code = db.Column(db.String(20), unique=True, nullable=False, index=True)
    name = db.Column(db.String(160), nullable=False)
    customer_type = db.Column(db.String(20), nullable=False)  # CORPORATE / SME / GOVERNMENT / INTERNATIONAL
    industry = db.Column(db.String(80))
    city = db.Column(db.String(80))
    country = db.Column(db.String(80), default="Cameroun")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    shipments = db.relationship("Shipment", back_populates="customer", lazy="dynamic")

    __table_args__ = (
        Index("ix_customers_type", "customer_type"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "customer_code": self.customer_code,
            "name": self.name,
            "customer_type": self.customer_type,
            "industry": self.industry,
            "city": self.city,
            "country": self.country,
        }
