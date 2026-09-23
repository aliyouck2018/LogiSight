/**
 * LogiSight — Transport performance page
 */

const PLOT = (el, data, layout = {}) =>
    Plotly.newPlot(prepPlotEl(el), data, {
        margin: { l: 48, r: 12, t: 8, b: 40 },
        font: { family: "Inter, sans-serif", size: 11, color: "#6b7a90" },
        paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)",
        ...layout,
    }, { displayModeBar: false, responsive: true });

const TRIP_STATUS = {
    PLANNED: ["Planifiée", "neutral"], IN_PROGRESS: ["En cours", "info"],
    COMPLETED: ["Terminée", "success"], CANCELLED: ["Annulée", "neutral"],
};

let tripPage = 1;

document.addEventListener("DOMContentLoaded", () => {
    GlobalFilters.onChange(refresh);
    refresh();
});

async function refresh() {
    const params = GlobalFilters.apiParams(["origin", "destination", "customer_id", "cargo_type", "status"]);
    loadSummary(params);
    loadCharts();
    loadTrips();
}

async function loadSummary(params) {
    try {
        const res = await API.get("/api/v1/transport/summary", params);
        const d = res.data;
        const kpis = [
            { label: "Tournées totales", value: fmt.num(d.total_trips), icon: "🚚", color: "blue" },
            { label: "Tournées à l'heure", value: fmt.num(d.on_time_trips), icon: "✅", color: "green" },
            { label: "Ponctualité", value: fmt.pct(d.on_time_rate), icon: "🕒", color: "cyan" },
            { label: "Retard moyen", value: d.avg_delay_hours != null ? fmt.hours(d.avg_delay_hours) : "—", icon: "⚠️", color: "orange" },
            { label: "Vitesse moyenne", value: d.avg_speed_kmh ? fmt.num(d.avg_speed_kmh, 1) + " km/h" : "—", icon: "📏", color: "blue" },
            { label: "Distance totale", value: fmt.km(d.total_distance_km), icon: "🛣️", color: "cyan" },
            { label: "Carburant total", value: fmt.num(d.total_fuel_liters, 0) + " L", icon: "⛽", color: "orange" },
            { label: "Rendement carburant", value: d.fuel_efficiency_km_l ? fmt.num(d.fuel_efficiency_km_l, 2) + " km/L" : "—", icon: "🌱", color: "green" },
        ];
        document.getElementById("transport-kpis").innerHTML = kpis.map(renderKpiCard).join("");
    } catch (e) {
        document.getElementById("transport-kpis").innerHTML = `<div class="card">${renderError(e.message)}</div>`;
    }
}

async function loadCharts() {
    try {
        const [pva, delays, routes, vehicles, transporters] = await Promise.all([
            API.get("/api/v1/transport/planned-vs-actual"),
            API.get("/api/v1/transport/delays"),
            API.get("/api/v1/transport/routes"),
            API.get("/api/v1/transport/vehicles"),
            API.get("/api/v1/transport/transporters"),
        ]);

        PLOT("chart-pva", [
            { x: pva.data.labels, y: pva.data.planned, type: "scatter", mode: "lines+markers", name: "Planifié (h)", line: { color: CHART_COLORS[0], width: 2 } },
            { x: pva.data.labels, y: pva.data.actual, type: "scatter", mode: "lines+markers", name: "Réel (h)", line: { color: CHART_COLORS[3], width: 2 } },
        ], { legend: { orientation: "h", y: -0.25 } });

        PLOT("chart-delays", [{
            x: delays.data.labels, y: delays.data.counts, type: "bar",
            marker: { color: [CHART_COLORS[1], CHART_COLORS[1], CHART_COLORS[0], CHART_COLORS[2], CHART_COLORS[2], CHART_COLORS[3]] },
        }]);

        const dimChart = (id, rows) => {
            const top = rows.slice(0, 6);
            PLOT(id, [{
                x: top.map(r => r.label), y: top.map(r => r.otd_rate), type: "bar",
                name: "Ponctualité (%)",
                marker: { color: top.map(r => r.otd_rate >= 75 ? CHART_COLORS[1] : r.otd_rate >= 60 ? CHART_COLORS[2] : CHART_COLORS[3]) },
                hovertemplate: "%{x}<br>Ponctualité: %{y}%<extra></extra>",
            }], { xaxis: { tickangle: -25, automargin: true } });
        };
        dimChart("chart-routes", routes.data);
        dimChart("chart-vehicles", vehicles.data);
        dimChart("chart-transporters", transporters.data);
    } catch (e) {
        ["chart-pva", "chart-delays", "chart-routes", "chart-vehicles", "chart-transporters"]
            .forEach(id => document.getElementById(id).innerHTML = renderError(e.message));
    }
}

async function loadTrips() {
    const el = document.getElementById("trips-table");
    try {
        const params = {
            start_date: document.getElementById("f-start").value,
            end_date: document.getElementById("f-end").value,
            page: tripPage, per_page: 10,
        };
        const res = await API.get("/api/v1/transport/trips", params);
        const rows = res.data;
        if (!rows.length) { el.innerHTML = renderEmpty("Aucune tournée pour ces filtres."); return; }
        const cols = [
            { key: "trip_id", label: "Tournée" },
            { key: "shipment_id", label: "Expédition", render: r => `<a href="/shipments/${r.shipment_id}">${r.shipment_id}</a>` },
            { label: "Véhicule", render: r => r.vehicle_registration || r.vehicle_id },
            { label: "Transporteur", render: r => r.transporter || "—" },
            { label: "Trajet", render: r => `${r.origin} → ${r.destination}` },
            { label: "Départ", render: r => fmt.date(r.departure_time) },
            { label: "Prévu", num: true, render: r => fmt.hours(r.planned_duration_hours) },
            { label: "Réel", num: true, render: r => r.actual_duration_hours ? fmt.hours(r.actual_duration_hours) : "—" },
            { label: "Distance", num: true, render: r => fmt.km(r.distance_km) },
            { label: "Statut", render: r => badge(...(TRIP_STATUS[r.trip_status] || [r.trip_status, "neutral"])) },
        ];
        el.innerHTML = renderTable(cols, rows);
        document.getElementById("trips-pagination").innerHTML = renderPagination(res.meta);
        document.querySelectorAll("#trips-pagination button[data-page]").forEach(b =>
            b.addEventListener("click", () => { tripPage = +b.dataset.page; loadTrips(); }));
    } catch (e) {
        el.innerHTML = renderError(e.message);
    }
}
