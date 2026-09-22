"""API endpoint tests (integration with a seeded in-memory database)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.get_json()["status"] == "ok"


def test_dashboard_summary(client):
    res = client.get("/api/v1/dashboard/summary")
    assert res.status_code == 200
    body = res.get_json()
    assert body["success"] is True
    kpis = {k["key"]: k["value"] for k in body["data"]["kpis"]}
    assert kpis["total_shipments"] > 0
    assert "otd_rate" in kpis


def test_dashboard_trends(client):
    res = client.get("/api/v1/dashboard/trends")
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert len(data["labels"]) == len(data["volume"])
    assert len(data["otd"]) == len(data["labels"])


def test_status_distribution(client):
    res = client.get("/api/v1/dashboard/status-distribution")
    assert res.status_code == 200
    dist = res.get_json()["data"]
    assert any(count > 0 for count in dist.values())


def test_shipments_list_pagination(client):
    res = client.get("/api/v1/shipments?per_page=5&page=1")
    assert res.status_code == 200
    body = res.get_json()
    assert len(body["data"]) <= 5
    assert body["meta"]["page"] == 1
    assert body["meta"]["total"] > 0


def test_shipments_filter_status(client):
    res = client.get("/api/v1/shipments?status=DELIVERED")
    assert res.status_code == 200
    for s in res.get_json()["data"]:
        assert s["status"] == "DELIVERED"


def test_shipments_search(client):
    res = client.get("/api/v1/shipments?q=SHP-000001")
    assert res.status_code == 200
    ids = [s["shipment_id"] for s in res.get_json()["data"]]
    assert "SHP-000001" in ids


def test_shipment_detail_and_timeline(client):
    res = client.get("/api/v1/shipments/SHP-000001")
    assert res.status_code == 200
    shipment = res.get_json()["data"]
    assert shipment["shipment_id"] == "SHP-000001"
    assert "timeline" in shipment

    res = client.get("/api/v1/shipments/SHP-000001/timeline")
    assert res.status_code == 200
    steps = res.get_json()["data"]
    assert steps[0]["key"] == "departure"


def test_shipment_not_found(client):
    res = client.get("/api/v1/shipments/SHP-DOESNOTEXIST")
    assert res.status_code == 404
    body = res.get_json()
    assert body["success"] is False
    assert body["error"]["code"] == "NOT_FOUND"


def test_customs_summary(client):
    res = client.get("/api/v1/customs/summary")
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert data["total_declarations"] > 0
    assert "sla_breach_rate" in data


def test_transport_summary(client):
    res = client.get("/api/v1/transport/summary")
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert data["total_trips"] >= 0


def test_warehouses_summary(client):
    res = client.get("/api/v1/warehouses/summary")
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert data["total_capacity"] > 0
    assert len(data["warehouses"]) > 0
    for w in data["warehouses"]:
        assert w["risk"] in ("LOW", "NORMAL", "AT_RISK", "CRITICAL")


def test_alerts_flow(client):
    res = client.get("/api/v1/alerts")
    assert res.status_code == 200
    alerts = res.get_json()["data"]
    if not alerts:
        return
    alert_id = alerts[0]["id"]

    # acknowledge
    res = client.patch(f"/api/v1/alerts/{alert_id}", json={"status": "ACKNOWLEDGED"})
    assert res.status_code == 200
    assert res.get_json()["data"]["status"] == "ACKNOWLEDGED"

    # resolve
    res = client.patch(f"/api/v1/alerts/{alert_id}", json={"status": "RESOLVED"})
    assert res.status_code == 200
    assert res.get_json()["data"]["status"] == "RESOLVED"

    # invalid transition
    res = client.patch(f"/api/v1/alerts/{alert_id}", json={"status": "OPEN"})
    assert res.status_code == 409


def test_alert_invalid_payload(client):
    res = client.patch("/api/v1/alerts/1", json={"status": "WEIRD"})
    assert res.status_code == 422


def test_insights(client):
    res = client.get("/api/v1/insights")
    assert res.status_code == 200
    for insight in res.get_json()["data"]:
        for key in ("severity", "title", "description", "metric", "current_value", "threshold", "recommended_action"):
            assert key in insight


def test_report_generation_and_exports(client):
    res = client.post("/api/v1/reports/generate", json={"report_type": "executive"})
    assert res.status_code == 200
    report = res.get_json()["data"]
    assert report["title"]
    assert len(report["kpis"]) > 0

    for fmt, mimetype in (("csv", "text/csv"),
                          ("xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
                          ("pdf", "application/pdf")):
        res = client.post("/api/v1/reports/export", json={"report_type": "executive", "format": fmt})
        assert res.status_code == 200, fmt
        assert mimetype in res.content_type


def test_report_invalid_type(client):
    res = client.post("/api/v1/reports/generate", json={"report_type": "unknown"})
    assert res.status_code == 422


def test_data_quality(client):
    res = client.get("/api/v1/data-quality")
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert data["total_shipments"] > 0
    assert len(data["checks"]) > 0
