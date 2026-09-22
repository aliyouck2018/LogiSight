"""Dashboard API endpoints."""
from flask import request

from app.analytics import dashboard as dash
from app.utils.api import ok


def register(bp):
    bp.add_url_rule("/dashboard/summary", "dashboard_summary", _summary)
    bp.add_url_rule("/dashboard/trends", "dashboard_trends", _trends)
    bp.add_url_rule("/dashboard/status-distribution", "dashboard_status", _status_distribution)
    bp.add_url_rule("/dashboard/delay-causes", "dashboard_causes", _delay_causes)
    bp.add_url_rule("/dashboard/routes", "dashboard_routes", _routes)
    bp.add_url_rule("/dashboard/customs-trend", "dashboard_customs_trend", _customs_trend)
    bp.add_url_rule("/dashboard/warehouses", "dashboard_warehouses", _warehouses)
    bp.add_url_rule("/dashboard/recent-shipments", "dashboard_recent", _recent)


def _args() -> dict:
    return request.args.to_dict()


def _summary():
    return ok(dash.dashboard_summary(_args()))


def _trends():
    months = int(request.args.get("months", 12))
    return ok(dash.shipment_trends(_args(), months=months))


def _status_distribution():
    return ok(dash.status_distribution(_args()))


def _delay_causes():
    return ok(dash.delay_causes(_args()))


def _routes():
    return ok(dash.route_performance(_args()))


def _customs_trend():
    return ok(dash.customs_clearance_trend(_args()))


def _warehouses():
    return ok(dash.warehouse_utilization_by_warehouse())


def _recent():
    return ok(dash.recent_shipments(_args()))
