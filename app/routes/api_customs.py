"""Customs API endpoints."""
from flask import request

from app.analytics import customs as customs_analytics
from app.models import CustomsDeclaration
from app.utils.api import ok, paginate_query


def register(bp):
    bp.add_url_rule("/customs/summary", "customs_summary", _summary)
    bp.add_url_rule("/customs/trends", "customs_trends", _trends)
    bp.add_url_rule("/customs/breaches", "customs_breaches", _breaches)
    bp.add_url_rule("/customs/by-cargo", "customs_by_cargo", _by_cargo)
    bp.add_url_rule("/customs/by-destination", "customs_by_dest", _by_dest)
    bp.add_url_rule("/customs/declarations", "customs_declarations", _declarations)


def _args() -> dict:
    return request.args.to_dict()


def _summary():
    return ok(customs_analytics.customs_summary(_args()))


def _trends():
    months = int(request.args.get("months", 12))
    return ok(customs_analytics.customs_trends(months=months))


def _by_cargo():
    return ok(customs_analytics.clearance_by_dimension("cargo"))


def _by_dest():
    return ok(customs_analytics.clearance_by_dimension("destination"))


def _breaches():
    args = _args()
    from app.analytics.filters import parse_date
    conds = [CustomsDeclaration.sla_status == "BREACHED"]
    start = parse_date(args.get("start_date"))
    end = parse_date(args.get("end_date"), end_of_day=True)
    if start:
        conds.append(CustomsDeclaration.declaration_date >= start)
    if end:
        conds.append(CustomsDeclaration.declaration_date <= end)
    stmt = (
        CustomDeclarations_query(conds)
        .order_by(CustomsDeclaration.clearance_duration_hours.desc())
    )
    items, meta = paginate_query(stmt)
    return ok([d.to_dict() for d in items], meta)


def CustomDeclarations_query(conds):
    from sqlalchemy import select
    return select(CustomsDeclaration).where(*conds)


def _declarations():
    args = _args()
    from app.analytics.filters import parse_date
    conds = []
    start = parse_date(args.get("start_date"))
    end = parse_date(args.get("end_date"), end_of_day=True)
    if start:
        conds.append(CustomsDeclaration.declaration_date >= start)
    if end:
        conds.append(CustomsDeclaration.declaration_date <= end)
    if args.get("sla_status"):
        conds.append(CustomsDeclaration.sla_status == args["sla_status"])
    if args.get("customs_status"):
        conds.append(CustomsDeclaration.customs_status == args["customs_status"])
    from sqlalchemy import select
    stmt = select(CustomsDeclaration).where(*conds).order_by(
        CustomsDeclaration.declaration_date.desc())
    items, meta = paginate_query(stmt)
    return ok([d.to_dict() for d in items], meta)
