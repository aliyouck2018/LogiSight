"""Reports API endpoints — implemented in Phase 7."""
from flask import request



def register(bp):
    bp.add_url_rule("/reports/generate", "reports_generate", _generate, methods=["POST"])
    bp.add_url_rule("/reports/export", "reports_export", _export, methods=["POST"])


def _generate():
    from app.services.reports import generate_report
    payload = request.get_json(silent=True) or {}
    try:
        return generate_report(payload)
    except ValueError as e:
        from app.utils.api import err
        return err("VALIDATION_ERROR", str(e), 422)


def _export():
    from app.services.reports import export_report
    payload = request.get_json(silent=True) or {}
    try:
        return export_report(payload)
    except ValueError as e:
        from app.utils.api import err
        return err("VALIDATION_ERROR", str(e), 422)
