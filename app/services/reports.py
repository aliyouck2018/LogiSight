"""Report generation and export services (CSV / Excel / PDF).

Reports reuse the analytics engine — KPI logic is never duplicated.
"""
from __future__ import annotations

import io
from datetime import datetime, timedelta

from flask import Response, jsonify
from sqlalchemy import select

from app import db
from app.analytics import customs as customs_analytics
from app.analytics import transport as transport_analytics
from app.analytics import warehouses as warehouse_analytics
from app.analytics.dashboard import (dashboard_summary, delay_causes,
                                     route_performance, shipment_trends,
                                     status_distribution)
from app.analytics.insights import generate_insights
from app.models import Alert

REPORT_TITLES = {
    "executive": "Rapport hebdomadaire de direction",
    "shipments": "Rapport de performance des expéditions",
    "customs": "Rapport de performance douane",
    "transport": "Rapport de performance transport",
    "warehouse": "Rapport de capacité entrepôts",
}


def _period_label(start_date, end_date) -> str:
    end_label = end_date or "aujourd'hui"
    if start_date:
        return f"du {start_date} au {end_label}"
    return f"Historique jusqu'au {end_label} (deltas sur 30 jours)"


def build_report(payload: dict) -> dict:
    """Build the report structure for preview and exports."""
    report_type = payload.get("report_type", "executive")
    if report_type not in REPORT_TITLES:
        raise ValueError(f"Type de rapport inconnu : {report_type}")

    args = {k: payload.get(k) for k in ("start_date", "end_date")}
    args = {k: v for k, v in args.items() if v}

    period = _period_label(args.get("start_date"), args.get("end_date"))
    extras: dict = {}
    kpis: list[dict] = []
    findings: list[str] = []

    if report_type == "executive":
        if not args:
            end = datetime.now().date()
            start = end - timedelta(days=182)
            args = {"start_date": start.isoformat(), "end_date": end.isoformat()}
        summary = dashboard_summary({**args, "status": None})
        insights = generate_insights()
        for k in summary["kpis"]:
            kpis.append({"label": k["label"], "value": _fmt_value(k["value"]), "unit": ""})
        trends = shipment_trends(args, months=6)
        if trends["volume"]:
            findings.append(f"Volume sur 6 mois : {sum(trends['volume'])} expéditions.")
        for i in insights[:4]:
            findings.append(f"{i['title']} — {i['description']}")
        extras = _executive_extras(summary, insights, args)

    elif report_type == "shipments":
        summary = dashboard_summary(args)
        key_kpis = {"total_shipments", "otd_rate", "avg_delivery_time", "avg_transit_delay", "delayed_shipments"}
        for k in summary["kpis"]:
            if k["key"] in key_kpis:
                kpis.append({"label": k["label"], "value": _fmt_value(k["value"]), "unit": k["unit"] if k["unit"] == "%" else ""})
        dist = status_distribution(args)
        for status, count in sorted(dist.items(), key=lambda x: -x[1]):
            findings.append(f"{status}: {count} expéditions.")
        routes = route_performance(args, limit=5)
        if routes:
            worst = min(routes, key=lambda r: r["otd"])
            findings.append(f"Corridor le plus performant en volume : {routes[0]['route']} ({routes[0]['otd']} % OTD).")
            findings.append(f"Corridor le plus en retard : {worst['route']} ({worst['otd']} % OTD).")

    elif report_type == "customs":
        s = customs_analytics.customs_summary(args)
        kpis = [
            {"label": "Déclarations totales", "value": _fmt_value(s["total_declarations"]), "unit": ""},
            {"label": "Dédouanées", "value": _fmt_value(s["cleared"]), "unit": ""},
            {"label": "En attente", "value": _fmt_value(s["pending"]), "unit": ""},
            {"label": "Délai moyen de dédouanement", "value": _fmt_value(s["avg_clearance_hours"]), "unit": "h"},
            {"label": "Taux de dépassement SLA", "value": _fmt_value(s["sla_breach_rate"]), "unit": "%"},
            {"label": "Délai le plus long", "value": _fmt_value(s["longest_clearance_hours"]), "unit": "h"},
        ]
        t = customs_analytics.customs_trends(months=6)
        if t["avg_clearance_hours"]:
            findings.append(f"Délai moyen sur 6 mois : {t['avg_clearance_hours'][-1]} h.")
        by_cargo = customs_analytics.clearance_by_dimension("cargo", limit=3)
        for c in by_cargo:
            findings.append(f"Marchandise {c['label']} : {c['avg_clearance_hours']} h en moyenne ({c['count']} déclarations).")

    elif report_type == "transport":
        s = transport_analytics.transport_summary(args)
        kpis = [
            {"label": "Tournées", "value": _fmt_value(s["total_trips"]), "unit": ""},
            {"label": "Ponctualité", "value": _fmt_value(s["on_time_rate"]), "unit": "%"},
            {"label": "Retard moyen", "value": _fmt_value(s["avg_delay_hours"]), "unit": "h"},
            {"label": "Distance totale", "value": _fmt_value(s["total_distance_km"]), "unit": "km"},
            {"label": "Rendement carburant", "value": _fmt_value(s["fuel_efficiency_km_l"]), "unit": "km/L"},
        ]
        for r in transport_analytics.performance_by_dimension("vehicle", limit=3):
            findings.append(f"Véhicule {r['label']} : {r['otd_rate']} % ponctualité, "
                            f"{r['fuel_efficiency_km_l']} km/L.")
        for r in transport_analytics.performance_by_dimension("transporter", limit=3):
            findings.append(f"Transporteur {r['label']} : {r['otd_rate']} % ponctualité sur {r['trips']} tournées.")

    elif report_type == "warehouse":
        s = warehouse_analytics.warehouse_summary()
        kpis = [
            {"label": "Capacité totale", "value": _fmt_value(s["total_capacity"]), "unit": "unités"},
            {"label": "Occupation", "value": _fmt_value(s["total_occupied"]), "unit": "unités"},
            {"label": "Taux d'occupation", "value": _fmt_value(s["utilization"]), "unit": "%"},
            {"label": "Durée moyenne de stockage", "value": _fmt_value(s["avg_storage_days"]), "unit": "j"},
            {"label": "Coût de stockage (12 mois)", "value": _fmt_value(s["total_storage_cost"]), "unit": "XAF"},
            {"label": "Entrepôts à risque", "value": _fmt_value(s["warehouses_at_risk"]), "unit": ""},
        ]
        for w in s["warehouses"]:
            if w["risk"] in ("AT_RISK", "CRITICAL"):
                findings.append(f"Entrepôt {w['warehouse_code']} ({w['city']}) : {w['utilization']} % d'occupation.")

    alerts = [
        {"severity": a.severity, "title": a.title, "description": a.description}
        for a in db_alerts()
    ]

    return {
        "title": REPORT_TITLES[report_type],
        "report_type": report_type,
        "period": period,
        "generated_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "kpis": kpis,
        "findings": findings,
        "alerts": alerts[:8],
        **(extras if report_type == "executive" else {}),
    }


def db_alerts():
    return db.session.execute(
        select(Alert).where(Alert.status == "OPEN").limit(8)
    ).scalars().all()


MOIS_FR = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
           "août", "septembre", "octobre", "novembre", "décembre"]

_BADGES = {
    "otd_rate": ("PERFORMANCE", "red"),
    "otd_trend": ("DÉGRADATION", "red"),
    "volume": ("VOLUME", "blue"),
    "customs_breach_rate": ("DOUANE", "amber"),
    "warehouse_utilization": ("ENTREPÔT", "navy"),
    "route_otd": ("CORRIDOR", "red"),
    "fuel_efficiency": ("FLOTTE", "amber"),
}


def _executive_extras(summary: dict, insights: list[dict], args: dict) -> dict:
    """Rich layout data consumed by the branded PDF renderer."""
    raw = {k["key"]: k for k in summary["kpis"]}
    total = (raw.get("total_shipments", {}).get("value") or 0)

    def share(key: str) -> float:
        v = raw.get(key, {}).get("value") or 0
        return round(v / total * 100, 1) if total else 0.0

    accent_by_key = {
        "total_shipments": "TEAL", "active_shipments": "BLUE", "delivered": "GREEN",
        "otd_rate": "RED", "avg_delivery_time": "AMBER", "avg_customs_clearance": "AMBER",
        "avg_transit_delay": "RED", "delayed_shipments": "RED",
        "warehouse_utilization": "NAVY", "avg_cost": "NAVY",
    }
    from app.services.report_pdf import palette_hex
    palette = palette_hex()

    units = {"jours": "j"}
    subs = {
        "total_shipments": "sur 6 mois",
        "active_shipments": f"{share('active_shipments')} % du volume",
        "delivered": f"{share('delivered')} % du volume",
        "otd_rate": "cible 90 %",
        "avg_delivery_time": "bout en bout",
        "avg_transit_delay": "vs. planifié",
        "delayed_shipments": f"{share('delayed_shipments')} % du volume",
        "warehouse_utilization": "capacité disponible",
        "avg_cost": "toutes zones",
    }
    cards = []
    for k in summary["kpis"]:
        unit = units.get(k["unit"], k["unit"])
        cards.append({
            "label": k["label"], "value": k["value"], "unit": unit,
            "sub": subs.get(k["key"], ""),
            "accent": palette.get(accent_by_key.get(k["key"], "NAVY")),
        })

    otd = raw.get("otd_rate", {}).get("value")
    if otd is None:
        status, tone = None, "red"
    elif otd < 75:
        tone, text = "red", "Performance de livraison critique — cible non atteinte"
    elif otd < 90:
        tone, text = "amber", "Livraison à temps sous la cible de 90 %"
    else:
        tone, text = "green", "Performance conforme — cible de livraison atteinte"

    highlights = []
    for i in insights:
        if i.get("metric") == "route_otd":
            highlights.append({
                "label": "Corridor le plus critique", "big": f"{i['current_value']} %".replace(".", ","),
                "caption": i["description"], "tone": "red", "bar": min(i["current_value"] / 100, 1),
            })
        elif i.get("metric") == "customs_breach_rate":
            v = round(i["current_value"], 1)
            highlights.append({
                "label": "Dépassement SLA douane (30j)", "big": f"{v} %".replace(".", ","),
                "caption": i["description"], "tone": "red" if v > 10 else "amber",
                "bar": min(v / 100, 1),
            })

    findings_rich = [
        {"badge": _BADGES.get(i.get("metric"), ("CONSTAT", "blue"))[0],
         "tone": _BADGES.get(i.get("metric"), ("", "blue"))[1],
         "text": f"{i['title']} — {i['description']}"}
        for i in insights[:4]
    ]

    start = args.get("start_date")
    end = args.get("end_date")
    period_label = period_friendly(start, end)

    return {"kpi_cards": cards, "status": (tone, text), "highlights": highlights,
            "findings_rich": findings_rich, "period_label": period_label}


def period_friendly(start, end) -> str:
    def fmt(d):
        if not d:
            return "aujourd'hui"
        d = datetime.fromisoformat(d).date()
        return f"{d.day} {MOIS_FR[d.month - 1]} {d.year}"
    if start and end:
        return f"{start and datetime.fromisoformat(start).strftime('%d')} {MOIS_FR[datetime.fromisoformat(start).month - 1]} {datetime.fromisoformat(start).year} → {datetime.fromisoformat(end).strftime('%d')} {MOIS_FR[datetime.fromisoformat(end).month - 1]} {datetime.fromisoformat(end).year}"
    return "6 derniers mois"


def _fmt_value(v) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:,.1f}".replace(",", " ")
    if isinstance(v, int):
        return f"{v:,}".replace(",", " ")
    return str(v)


def generate_report(payload: dict) -> Response:
    report = build_report(payload)
    return jsonify({"success": True, "data": report})


def export_report(payload: dict) -> Response:
    report_type = payload.get("report_type", "executive")
    fmt = payload.get("format", "csv")
    args = {k: payload.get(k) for k in ("start_date", "end_date") if payload.get(k)}

    if fmt == "csv":
        return _export_csv(report_type, args)
    if fmt in ("xlsx", "excel"):
        return _export_xlsx(report_type, args)
    if fmt == "pdf":
        return _export_pdf(report_type, args)
    raise ValueError(f"Format d'export inconnu : {fmt}")


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------

def _export_csv(report_type: str, args: dict) -> Response:
    report = build_report({"report_type": report_type, **args})
    lines = [f"Rapport;{report['title']}", f"Periode;{report['period']}", ""]
    lines.append("Indicateur;Valeur")
    for k in report["kpis"]:
        lines.append(f"{k['label']};{k['value']}{k['unit']}")
    lines.append("")
    lines.append("Constats")
    for f in report["findings"]:
        lines.append(f.replace(";", ","))
    lines.append("")
    lines.append("Alertes")
    for a in report["alerts"]:
        lines.append(f"{a['severity']};{a['title']};{a['description'].replace(';', ',')}")
    csv = "\n".join(lines)
    return Response(
        "\ufeff" + csv,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=logisight_{report_type}.csv"},
    )


# ---------------------------------------------------------------------------
# Excel
# ---------------------------------------------------------------------------

def _export_xlsx(report_type: str, args: dict) -> Response:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    report = build_report({"report_type": report_type, **args})
    wb = Workbook()
    ws = wb.active
    ws.title = "Rapport"

    header_fill = PatternFill("solid", fgColor="0D1B3E")
    title_font = Font(bold=True, size=14, color="0D1B3E")

    ws["A1"] = report["title"]
    ws["A1"].font = title_font
    ws["A2"] = f"Période : {report['period']}"
    ws["A3"] = f"Généré le {report['generated_at']}"

    ws["A5"] = "Indicateur"
    ws["B5"] = "Valeur"
    for cell in ("A5", "B5"):
        ws[cell].font = Font(bold=True, color="FFFFFF")
        ws[cell].fill = header_fill
    for i, k in enumerate(report["kpis"], start=6):
        ws[f"A{i}"] = k["label"]
        ws[f"B{i}"] = f"{k['value']} {k['unit']}".strip()

    row = 6 + len(report["kpis"]) + 1
    ws[f"A{row}"] = "Constats clés"
    ws[f"A{row}"].font = Font(bold=True)
    for i, f in enumerate(report["findings"], start=row + 1):
        ws[f"A{i}"] = f

    row = row + len(report["findings"]) + 2
    ws[f"A{row}"] = "Alertes opérationnelles"
    ws[f"A{row}"].font = Font(bold=True)
    for i, a in enumerate(report["alerts"], start=row + 1):
        ws[f"A{i}"] = f"[{a['severity']}] {a['title']} — {a['description']}"

    ws.column_dimensions["A"].width = 60
    ws.column_dimensions["B"].width = 24

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return Response(
        buf.read(),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=logisight_{report_type}.xlsx"},
    )


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------

def _export_pdf(report_type: str, args: dict) -> Response:
    from app.services.report_pdf import build_pdf

    report = build_report({"report_type": report_type, **args})
    return Response(
        build_pdf(report),
        mimetype="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=logisight_{report_type}.pdf"},
    )
