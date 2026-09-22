"""Alerts API endpoints."""
from datetime import datetime, timezone

from flask import request
from sqlalchemy import select

from app import db
from app.models import Alert
from app.utils.api import err, ok, paginate_query


def register(bp):
    bp.add_url_rule("/alerts", "alerts_list", _list)
    bp.add_url_rule("/alerts/<int:alert_id>", "alert_patch", _patch, methods=["PATCH"])
    bp.add_url_rule("/alerts/counts", "alerts_counts", _counts)


def _list():
    args = request.args.to_dict()
    conds = []
    if args.get("status"):
        conds.append(Alert.status == args["status"])
    if args.get("severity"):
        conds.append(Alert.severity == args["severity"])
    if args.get("alert_type"):
        conds.append(Alert.alert_type == args["alert_type"])
    stmt = select(Alert).where(*conds).order_by(Alert.created_at.desc())
    items, meta = paginate_query(stmt)
    return ok([a.to_dict() for a in items], meta)


def _counts():
    rows = db.session.execute(
        select(Alert.status, Alert.severity, Alert.alert_type).where(Alert.status == "OPEN")
    ).all()
    by_severity = {}
    by_type = {}
    for status, severity, alert_type in rows:
        by_severity[severity] = by_severity.get(severity, 0) + 1
        by_type[alert_type] = by_type.get(alert_type, 0) + 1
    return ok({
        "open_total": len(rows),
        "by_severity": by_severity,
        "by_type": by_type,
    })


ALLOWED_TRANSITIONS = {
    "OPEN": ["ACKNOWLEDGED", "RESOLVED"],
    "ACKNOWLEDGED": ["RESOLVED", "OPEN"],
    "RESOLVED": [],
}


def _patch(alert_id: int):
    alert = db.session.get(Alert, alert_id)
    if alert is None:
        return err("NOT_FOUND", f"Alerte {alert_id} introuvable.", 404)

    payload = request.get_json(silent=True) or {}
    new_status = payload.get("status")
    if not new_status:
        return err("VALIDATION_ERROR", "Le champ 'status' est requis.", 422)
    if new_status not in ("OPEN", "ACKNOWLEDGED", "RESOLVED"):
        return err("VALIDATION_ERROR", "Statut invalide.", 422)
    if new_status not in ALLOWED_TRANSITIONS.get(alert.status, []):
        return err("VALIDATION_ERROR",
                   f"Transition {alert.status} → {new_status} non autorisée.", 409)

    alert.status = new_status
    now = datetime.now(timezone.utc)
    if new_status == "ACKNOWLEDGED":
        alert.acknowledged_at = now
    elif new_status == "RESOLVED":
        alert.resolved_at = now
    db.session.commit()
    return ok(alert.to_dict())
