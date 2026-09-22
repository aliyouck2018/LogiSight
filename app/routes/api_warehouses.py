"""Warehouses API endpoints."""
from flask import request

from app.analytics import warehouses as wh_analytics
from app.models import WarehouseTransaction
from app.utils.api import ok


def register(bp):
    bp.add_url_rule("/warehouses/summary", "warehouses_summary", _summary)
    bp.add_url_rule("/warehouses/utilization", "warehouses_utilization", _utilization)
    bp.add_url_rule("/warehouses/trends", "warehouses_trends", _trends)
    bp.add_url_rule("/warehouses/storage-duration", "warehouses_storage_duration", _storage_duration)
    bp.add_url_rule("/warehouses/transactions", "warehouses_transactions", _transactions)


def _summary():
    return ok(wh_analytics.warehouse_summary())


def _utilization():
    return ok(wh_analytics.warehouse_summary()["warehouses"])


def _trends():
    months = int(request.args.get("months", 12))
    return ok(wh_analytics.storage_trends(months=months))


def _storage_duration():
    return ok(wh_analytics.storage_duration_distribution())


def _transactions():
    args = request.args.to_dict()
    from app.analytics.filters import parse_date
    from sqlalchemy import select
    conds = []
    start = parse_date(args.get("start_date"))
    end = parse_date(args.get("end_date"), end_of_day=True)
    if start:
        conds.append(WarehouseTransaction.transaction_date >= start)
    if end:
        conds.append(WarehouseTransaction.transaction_date <= end)
    if args.get("transaction_type"):
        conds.append(WarehouseTransaction.transaction_type == args["transaction_type"])
    if args.get("warehouse_code"):
        from app.models import Warehouse
        wid = db.session.execute(
            select(Warehouse.id).where(Warehouse.warehouse_code == args["warehouse_code"])
        ).scalar_one_or_none()
        conds.append(WarehouseTransaction.warehouse_id == wid)
    stmt = select(WarehouseTransaction).where(*conds).order_by(
        WarehouseTransaction.transaction_date.desc())
    items, meta = paginate_query(stmt)
    return ok([t.to_dict() for t in items], meta)


from app import db  # noqa: E402
from app.utils.api import paginate_query  # noqa: E402
