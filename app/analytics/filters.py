"""Shared query filter construction for analytics and API routes."""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import Select

from app.models import Customer, Shipment

DATE_FORMAT = "%Y-%m-%d"


def parse_date(value: str | None, end_of_day: bool = False) -> datetime | None:
    if not value:
        return None
    dt = datetime.strptime(value, DATE_FORMAT)
    if end_of_day:
        dt = dt + timedelta(days=1) - timedelta(seconds=1)
    return dt


def apply_shipment_filters(
    query: Select,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    origin: str | None = None,
    destination: str | None = None,
    status: str | None = None,
    cargo_type: str | None = None,
    customer_id: str | int | None = None,
    date_field="planned_departure",
    exclude_cancelled: bool = False,
) -> Select:
    """Attach standard filters to a query over Shipment.

    The date range always applies to `date_field` (planned_departure by default).
    """
    start = parse_date(start_date)
    end = parse_date(end_date, end_of_day=True)
    if start is not None:
        query = query.where(getattr(Shipment, date_field) >= start)
    if end is not None:
        query = query.where(getattr(Shipment, date_field) <= end)
    if origin:
        query = query.where(Shipment.origin == origin)
    if destination:
        query = query.where(Shipment.destination == destination)
    if status:
        query = query.where(Shipment.status == status)
    if cargo_type:
        query = query.where(Shipment.cargo_type == cargo_type)
    if customer_id:
        query = query.where(Shipment.customer_id == int(customer_id))
    if exclude_cancelled:
        query = query.where(Shipment.status != "CANCELLED")
    return query


def previous_window(start_date: str | None, end_date: str | None) -> tuple[datetime | None, datetime | None]:
    """Given an explicit period, return the preceding equal-length window."""
    start = parse_date(start_date)
    end = parse_date(end_date, end_of_day=True)
    if not start or not end:
        return (None, None)
    span = end - start
    return (start - span, start - timedelta(seconds=1))


DEFAULT_RECENT_DAYS = 30
