"""Model registry — import all models so Alembic/SQLAlchemy sees them."""
from app.models.alert import Alert  # noqa: F401
from app.models.base import generate_public_id  # noqa: F401
from app.models.customs import CustomsDeclaration  # noqa: F401
from app.models.customer import Customer  # noqa: F401
from app.models.route import Route  # noqa: F401
from app.models.shipment import ACTIVE_STATUSES, SHIPMENT_STATUSES, Shipment  # noqa: F401
from app.models.vehicle import Trip, Vehicle  # noqa: F401
from app.models.warehouse import Warehouse, WarehouseTransaction  # noqa: F401
