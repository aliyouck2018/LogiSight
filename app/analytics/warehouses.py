"""Warehouse analytics: utilization KPIs, storage trends, transactions."""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import case, func, select

from app import db
from app.utils.sql import month_key
from app.models import Warehouse, WarehouseTransaction


def warehouse_summary() -> dict:
    rows = db.session.execute(
        select(Warehouse.warehouse_code, Warehouse.name, Warehouse.city,
               Warehouse.capacity_units, Warehouse.occupied_units, Warehouse.warehouse_type)
        .where(Warehouse.active.is_(True))
    ).all()

    total_capacity = sum(float(r.capacity_units) for r in rows)
    total_occupied = sum(float(r.occupied_units) for r in rows)

    warehouses = []
    at_risk = 0
    for r in rows:
        util = round(r.occupied_units / r.capacity_units * 100, 1) if r.capacity_units else 0
        risk = warehouse_risk(util)
        if risk in ("AT_RISK", "CRITICAL"):
            at_risk += 1
        warehouses.append({
            "warehouse_code": r.warehouse_code,
            "name": r.name,
            "city": r.city,
            "capacity": float(r.capacity_units),
            "occupied": float(r.occupied_units),
            "utilization": util,
            "risk": risk,
            "warehouse_type": r.warehouse_type,
        })

    # avg storage duration & total cost from OUT transactions (last 12 months)
    year_ago = datetime.now() - timedelta(days=365)
    stats = db.session.execute(
        select(func.avg(WarehouseTransaction.storage_duration_days),
               func.sum(WarehouseTransaction.storage_cost))
        .where(WarehouseTransaction.transaction_type == "OUT",
               WarehouseTransaction.transaction_date >= year_ago)
    ).one()

    return {
        "total_capacity": total_capacity,
        "total_occupied": total_occupied,
        "utilization": round(total_occupied / total_capacity * 100, 1) if total_capacity else None,
        "avg_storage_days": round(stats[0], 1) if stats[0] else None,
        "total_storage_cost": round(float(stats[1] or 0), 0),
        "warehouses_at_risk": at_risk,
        "warehouses": warehouses,
    }


def warehouse_risk(utilization: float) -> str:
    """Risk level by utilization: <70 LOW, 70-85 NORMAL, 85-95 AT_RISK, >95 CRITICAL."""
    if utilization is None:
        return "LOW"
    if utilization > 95:
        return "CRITICAL"
    if utilization > 85:
        return "AT_RISK"
    if utilization >= 70:
        return "NORMAL"
    return "LOW"


def storage_trends(months: int = 12) -> dict:
    """Monthly storage cost + in/out volumes."""
    end = datetime.now()
    start = end - timedelta(days=months * 31)
    month = month_key(WarehouseTransaction.transaction_date).label("month")
    in_qty = case((WarehouseTransaction.transaction_type == "IN", WarehouseTransaction.quantity), else_=0)
    out_qty = case((WarehouseTransaction.transaction_type == "OUT", WarehouseTransaction.quantity), else_=0)
    rows = db.session.execute(
        select(month,
               func.sum(in_qty).label("in_qty"),
               func.sum(out_qty).label("out_qty"),
               func.sum(WarehouseTransaction.storage_cost).label("cost"))
        .where(WarehouseTransaction.transaction_date >= start)
        .group_by(month).order_by(month)
    ).all()
    return {
        "labels": [r.month for r in rows],
        "in": [round(r.in_qty or 0, 0) for r in rows],
        "out": [round(r.out_qty or 0, 0) for r in rows],
        "cost": [round(float(r.cost or 0), 0) for r in rows],
    }


def storage_duration_distribution() -> dict:
    durations = db.session.execute(
        select(WarehouseTransaction.storage_duration_days)
        .where(WarehouseTransaction.transaction_type == "OUT",
               WarehouseTransaction.storage_duration_days.is_not(None))
    ).scalars().all()
    buckets = {"0-5j": 0, "5-10j": 0, "10-20j": 0, "20-30j": 0, "30-45j": 0, "> 45j": 0}
    for d in durations:
        if d < 5:
            buckets["0-5j"] += 1
        elif d < 10:
            buckets["5-10j"] += 1
        elif d < 20:
            buckets["10-20j"] += 1
        elif d < 30:
            buckets["20-30j"] += 1
        elif d < 45:
            buckets["30-45j"] += 1
        else:
            buckets["> 45j"] += 1
    return {"labels": list(buckets.keys()), "counts": list(buckets.values())}
