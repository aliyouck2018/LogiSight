"""Transport API endpoints."""
from flask import request

from app.analytics import transport as transport_analytics
from app.models import Trip
from app.utils.api import ok, paginate_query


def register(bp):
    bp.add_url_rule("/transport/summary", "transport_summary", _summary)
    bp.add_url_rule("/transport/routes", "transport_routes", _routes)
    bp.add_url_rule("/transport/vehicles", "transport_vehicles", _vehicles)
    bp.add_url_rule("/transport/transporters", "transport_transporters", _transporters)
    bp.add_url_rule("/transport/delays", "transport_delays", _delays)
    bp.add_url_rule("/transport/planned-vs-actual", "transport_pva", _pva)
    bp.add_url_rule("/transport/trips", "transport_trips", _trips)


def _args() -> dict:
    return request.args.to_dict()


def _summary():
    return ok(transport_analytics.transport_summary(_args()))


def _routes():
    return ok(transport_analytics.performance_by_dimension("route"))


def _vehicles():
    return ok(transport_analytics.performance_by_dimension("vehicle"))


def _transporters():
    return ok(transport_analytics.performance_by_dimension("transporter"))


def _delays():
    return ok(transport_analytics.delay_distribution())


def _pva():
    months = int(request.args.get("months", 12))
    return ok(transport_analytics.planned_vs_actual_by_month(months=months))


def _trips():
    args = _args()
    from app.analytics.filters import parse_date
    from sqlalchemy import select
    conds = []
    start = parse_date(args.get("start_date"))
    end = parse_date(args.get("end_date"), end_of_day=True)
    if start:
        conds.append(Trip.departure_time >= start)
    if end:
        conds.append(Trip.departure_time <= end)
    if args.get("trip_status"):
        conds.append(Trip.trip_status == args["trip_status"])
    if args.get("vehicle_id"):
        conds.append(Trip.vehicle_id == args["vehicle_id"])
    stmt = select(Trip).where(*conds).order_by(Trip.departure_time.desc())
    items, meta = paginate_query(stmt)
    return ok([t.to_dict() for t in items], meta)
