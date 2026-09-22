"""API v1 blueprint registry."""
from flask import Blueprint

api_bp = Blueprint("api", __name__)


def _register():
    from app.routes import (api_alerts, api_customs, api_dashboard,
                            api_misc, api_reports, api_shipments,
                            api_transport, api_warehouses)

    api_dashboard.register(api_bp)
    api_shipments.register(api_bp)
    api_customs.register(api_bp)
    api_transport.register(api_bp)
    api_warehouses.register(api_bp)
    api_alerts.register(api_bp)
    api_reports.register(api_bp)
    api_misc.register(api_bp)


_register()
