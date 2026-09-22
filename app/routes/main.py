"""Page routes (server-rendered templates)."""
from flask import Blueprint, render_template

main_bp = Blueprint("main", __name__)

PAGES = {
    "dashboard": "Tableau de bord",
    "shipments": "Expéditions",
    "customs": "Douane",
    "transport": "Transport",
    "warehouses": "Entrepôts",
    "alerts": "Alertes",
    "insights": "Insights",
    "reports": "Rapports",
}


def _render(page_key: str, **extra):
    return render_template(
        "pages/{}.html".format(page_key),
        active_page=page_key,
        pages=PAGES,
        page_title=PAGES[page_key],
        **extra,
    )


@main_bp.route("/")
@main_bp.route("/dashboard")
def dashboard():
    return _render("dashboard")


@main_bp.route("/shipments")
def shipments():
    return _render("shipments")


@main_bp.route("/shipments/<shipment_id>")
def shipment_detail(shipment_id: str):
    return render_template(
        "pages/shipment_detail.html",
        active_page="shipments",
        pages=PAGES,
        page_title="Détail expédition",
        shipment_id=shipment_id,
    )


@main_bp.route("/customs")
def customs():
    return _render("customs")


@main_bp.route("/transport")
def transport():
    return _render("transport")


@main_bp.route("/warehouses")
def warehouses():
    return _render("warehouses")


@main_bp.route("/alerts")
def alerts():
    return _render("alerts")


@main_bp.route("/insights")
def insights():
    return _render("insights")


@main_bp.route("/reports")
def reports():
    return _render("reports")
