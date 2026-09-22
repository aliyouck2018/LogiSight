/**
 * LogiSight — Customs analytics page
 */

const PLOT = (el, data, layout = {}) =>
    Plotly.newPlot(el, data, {
        margin: { l: 48, r: 12, t: 8, b: 40 },
        font: { family: "Inter, sans-serif", size: 11, color: "#6b7a90" },
        paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)",
        ...layout,
    }, { displayModeBar: false, responsive: true });

document.addEventListener("DOMContentLoaded", () => {
    GlobalFilters.onChange(refresh);
    refresh();
});

async function refresh() {
    const params = GlobalFilters.apiParams(["origin", "destination", "customer_id", "cargo_type", "status"]);
    loadSummary(params);
    loadTrends();
    loadByDimensions();
    loadBreaches();
}

async function loadSummary(params) {
    try {
        const res = await API.get("/api/v1/customs/summary", params);
        const d = res.data;
        const breachDelta = d.sla_breach_rate_previous != null && d.sla_breach_rate != null
            ? Math.round((d.sla_breach_rate - d.sla_breach_rate_previous) * 10) / 10 : undefined;
        const kpis = [
            { label: "Déclarations totales", value: fmt.num(d.total_declarations), icon: "🛃", color: "blue", sub: "" },
            { label: "Dédouanées", value: fmt.num(d.cleared), icon: "✅", color: "green" },
            { label: "En attente", value: fmt.num(d.pending), icon: "⏳", color: "orange" },
            { label: "Délai moyen", value: d.avg_clearance_hours ? fmt.hours(d.avg_clearance_hours) : "—", icon: "🕒", color: "cyan" },
            { label: "Dépassement SLA", value: d.sla_breach_rate != null ? fmt.pct(d.sla_breach_rate) : "—", icon: "⚠️", color: "red", delta: breachDelta },
            { label: "Délai le plus long", value: d.longest_clearance_hours ? fmt.hours(d.longest_clearance_hours) : "—", icon: "📈", color: "orange" },
        ];
        document.getElementById("customs-kpis").innerHTML = kpis.map(k =>
            renderKpiCard(k)).join("");
    } catch (e) {
        document.getElementById("customs-kpis").innerHTML = `<div class="card">${renderError(e.message)}</div>`;
    }
}

async function loadTrends() {
    try {
        const res = await API.get("/api/v1/customs/trends");
        const t = res.data;
        PLOT("chart-clearance-trend", [{
            x: t.labels, y: t.avg_clearance_hours, type: "scatter", mode: "lines+markers",
            name: "Délai moyen (h)", line: { color: CHART_COLORS[0], width: 2.5, shape: "spline" },
            fill: "tozeroy", fillcolor: "rgba(30,94,255,0.08)",
        }]);
        PLOT("chart-breach-rate", [{
            x: t.labels, y: t.breach_rate, type: "bar", name: "Taux de dépassement (%)",
            marker: { color: t.breach_rate.map(v => v > 15 ? CHART_COLORS[3] : CHART_COLORS[2]) },
        }], { yaxis: { ticksuffix: "%", gridcolor: "#eef1f6" } });
    } catch (e) {
        ["chart-clearance-trend", "chart-breach-rate"].forEach(id =>
            document.getElementById(id).innerHTML = renderError(e.message));
    }
}

async function loadByDimensions() {
    try {
        const [cargo, dest] = await Promise.all([
            API.get("/api/v1/customs/by-cargo"),
            API.get("/api/v1/customs/by-destination"),
        ]);
        PLOT("chart-by-cargo", [{
            x: cargo.data.map(d => d.avg_clearance_hours),
            y: cargo.data.map(d => d.label), type: "bar", orientation: "h",
            marker: { color: CHART_COLORS[0] },
            hovertemplate: "%{y}: %{x} h<extra></extra>",
        }], { margin: { l: 110, r: 12, t: 8, b: 40 } });
        PLOT("chart-by-dest", [{
            x: dest.data.slice(0, 8).map(d => d.avg_clearance_hours),
            y: dest.data.slice(0, 8).map(d => d.label), type: "bar", orientation: "h",
            marker: { color: CHART_COLORS[5] },
            hovertemplate: "%{y}: %{x} h<extra></extra>",
        }], { margin: { l: 110, r: 12, t: 8, b: 40 } });
    } catch (e) {
        ["chart-by-cargo", "chart-by-dest"].forEach(id =>
            document.getElementById(id).innerHTML = renderError(e.message));
    }
}

let breachPage = 1;

async function loadBreaches() {
    const el = document.getElementById("breaches-table");
    try {
        const params = {
            start_date: document.getElementById("f-start").value,
            end_date: document.getElementById("f-end").value,
            page: breachPage, per_page: 10,
        };
        const res = await API.get("/api/v1/customs/breaches", params);
        const rows = res.data;
        if (!rows.length) { el.innerHTML = renderEmpty("Aucun dépassement de SLA sur la période."); return; }
        const cols = [
            { key: "declaration_id", label: "Déclaration" },
            { key: "shipment_id", label: "Expédition", render: r => `<a href="/shipments/${r.shipment_id}">${r.shipment_id}</a>` },
            { label: "Déclaration le", render: r => fmt.date(r.declaration_date) },
            { label: "Dédouané le", render: r => fmt.date(r.clearance_date) },
            { label: "Durée", num: true, render: r => fmt.hours(r.clearance_duration_hours) },
            { label: "SLA", num: true, render: r => fmt.hours(r.sla_hours) },
            { label: "Dépassement", num: true, render: r => fmt.hours(r.clearance_duration_hours - r.sla_hours) },
            { label: "Statut", render: () => badge("Dépassé", "danger") },
        ];
        el.innerHTML = renderTable(cols, rows);
        document.getElementById("breaches-pagination").innerHTML = renderPagination(res.meta);
        document.querySelectorAll("#breaches-pagination button[data-page]").forEach(b =>
            b.addEventListener("click", () => { breachPage = +b.dataset.page; loadBreaches(); }));
    } catch (e) {
        el.innerHTML = renderError(e.message);
    }
}
