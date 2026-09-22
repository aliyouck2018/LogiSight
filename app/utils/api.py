"""Shared API helpers: pagination, filtering, responses."""
from typing import Any

from flask import request
from sqlalchemy import Select

from app import db
from app.config import Config


def ok(data: Any, meta: dict | None = None) -> dict:
    return {"success": True, "data": data, "meta": meta or {}}


def err(code: str, message: str, status: int = 400):
    from flask import jsonify

    response = jsonify({"success": False, "error": {"code": code, "message": message}})
    response.status_code = status
    return response


def get_pagination() -> tuple[int, int]:
    """Return (page, per_page) validated from query params."""
    try:
        page = max(1, int(request.args.get("page", 1)))
        per_page = min(
            Config.MAX_PAGE_SIZE,
            max(1, int(request.args.get("per_page", Config.DEFAULT_PAGE_SIZE))),
        )
    except (TypeError, ValueError):
        raise ValueError("Paramètres de pagination invalides.")
    return page, per_page


def paginate_query(stmt: Select):
    """Paginate a SQLAlchemy select statement, return (items, meta)."""
    page, per_page = get_pagination()
    pagination = db.paginate(stmt, page=page, per_page=per_page, error_out=False)
    meta = {
        "page": pagination.page,
        "per_page": pagination.per_page,
        "total": pagination.total,
        "pages": pagination.pages or 1,
    }
    return pagination.items, meta


def get_date_filters() -> dict:
    """Extract standard filters from query params."""
    return {
        "start_date": request.args.get("start_date"),
        "end_date": request.args.get("end_date"),
        "origin": request.args.get("origin"),
        "destination": request.args.get("destination"),
        "status": request.args.get("status"),
        "cargo_type": request.args.get("cargo_type"),
        "customer_id": request.args.get("customer_id"),
    }


def commit_or_rollback():
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
