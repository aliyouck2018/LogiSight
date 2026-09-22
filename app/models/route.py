"""Route (corridor) model."""
from sqlalchemy import Boolean, Float, String, UniqueConstraint

from app import db


class Route(db.Model):
    __tablename__ = "routes"

    id = db.Column(db.Integer, primary_key=True)
    origin = db.Column(db.String(80), nullable=False)
    destination = db.Column(db.String(80), nullable=False)
    distance_km = db.Column(db.Float, nullable=False)
    expected_duration_hours = db.Column(db.Float, nullable=False)
    route_type = db.Column(db.String(20))   # DOMESTIC / REGIONAL / INTERNATIONAL
    active = db.Column(db.Boolean, default=True)

    __table_args__ = (
        UniqueConstraint("origin", "destination", name="uq_route_origin_dest"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "origin": self.origin,
            "destination": self.destination,
            "distance_km": self.distance_km,
            "expected_duration_hours": self.expected_duration_hours,
            "route_type": self.route_type,
            "active": self.active,
        }
