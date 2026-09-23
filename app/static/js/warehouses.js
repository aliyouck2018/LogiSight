/**
 * LogiSight — Warehouses analytics page
 */

const PLOT = (el, data, layout = {}) =>
    Plotly.newPlot(prepPlotEl(el), data, {
        margin: { l: 48, r: 12, t: 8, b: 48 },
        font: { family: "Inter, sans-serif", size: 11, color: "#6b7a90" },
        paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)",
        ...layout,
    }, { displayModeBar: false, responsive: true });

const RISK_BADGE = {
    LOW: ["Faible", "success"], NORMAL: ["Normal", "info"],
    AT_RISK: ["À risque", "warning"], CRITICAL: ["Critique", "danger"],
};

document.addEventListener("DOMContentLoaded", refresh);

async function refresh() {
    try {
        const res = await API.get("/api/v1/warehouses/summary");
        const d = res.data;
        renderKpis(d);
        renderUtilization(d.warehouses);
        renderTableRows(d.warehouses);
        loadFlows();
        loadStorageDuration();
    } catch (e) {
        document.getElementById("wh-kpis").innerHTML = `<div class="card">${renderError(e.message)}</div>`;
    }
}

function renderKpis(d) {
    const kpis = [
        { label: "Capacité totale", value: fmt.num(d.total_capacity, 0) + " unités", icon: "🏭", color: "blue" },
        { label: "Occupation actuelle", value: fmt.num(d.total_occupied, 0) + " unités", icon: "📦", color: "cyan" },
        { label: "Taux d'occupation", value: fmt.pct(d.utilization), icon: "📊", color: d.utilization > 85 ? "red" : "green" },
        { label: "Durée moyenne stockage", value: d.avg_storage_days ? fmt.num(d.avg_storage_days, 1) + " j" : "—", icon: "🕒", color: "orange" },
        { label: "Coût stockage (12 mois)", value: fmt.xaf(d.total_storage_cost), icon: "💰", color: "cyan" },
        { label: "Entrepôts à risque", value: fmt.num(d.warehouses_at_risk), icon: "⚠️", color: d.warehouses_at_risk > 0 ? "red" : "green" },
    ];
    document.getElementById("wh-kpis").innerHTML = kpis.map(renderKpiCard).join("");
}

function renderUtilization(warehouses) {
    PLOT("chart-utilization", [{
        x: warehouses.map(w => w.warehouse_code),
        y: warehouses.map(w => w.utilization),
        type: "bar",
        marker: {
            color: warehouses.map(w =>
                w.utilization > 95 ? CHART_COLORS[3] : w.utilization > 85 ? CHART_COLORS[2]
                : w.utilization >= 70 ? CHART_COLORS[0] : CHART_COLORS[1]),
        },
        hovertemplate: "%{x}: %{y}%<extra></extra>",
    }], {
        shapes: warehouses.length ? [
            { type: "line", x0: -0.5, x1: warehouses.length - 0.5, y0: 85, y1: 85, line: { color: CHART_COLORS[2], dash: "dot", width: 1 } },
            { type: "line", x0: -0.5, x1: warehouses.length - 0.5, y0: 95, y1: 95, line: { color: CHART_COLORS[3], dash: "dot", width: 1 } },
        ] : [],
    });
}

async function loadFlows() {
    try {
        const res = await API.get("/api/v1/warehouses/trends");
        const t = res.data;
        PLOT("chart-flows", [
            { x: t.labels, y: t.in, type: "scatter", mode: "lines", name: "Entrées", line: { color: CHART_COLORS[0], width: 2 }, stackgroup: "one" },
            { x: t.labels, y: t.out, type: "scatter", mode: "lines", name: "Sorties", line: { color: CHART_COLORS[1], width: 2 }, stackgroup: "two" },
        ], { legend: { orientation: "h", y: -0.22 } });
    } catch (e) {
        document.getElementById("chart-flows").innerHTML = renderError(e.message);
    }
}

async function loadStorageDuration() {
    try {
        const res = await API.get("/api/v1/warehouses/storage-duration");
        PLOT("chart-storage", [{
            x: res.data.labels, y: res.data.counts, type: "bar",
            marker: { color: CHART_COLORS[5] },
        }]);
    } catch (e) {
        document.getElementById("chart-storage").innerHTML = renderError(e.message);
    }
}

function renderTableRows(warehouses) {
    const cols = [
        { key: "warehouse_code", label: "Code" },
        { key: "name", label: "Nom" },
        { key: "city", label: "Ville" },
        { key: "warehouse_type", label: "Type" },
        { label: "Capacité", num: true, render: r => fmt.num(r.capacity, 0) },
        { label: "Occupation", num: true, render: r => fmt.num(r.occupied, 0) },
        { label: "Taux", num: true, render: r => fmt.pct(r.utilization) },
        { label: "Risque", render: r => badge(...(RISK_BADGE[r.risk] || [r.risk, "neutral"])) },
    ];
    document.getElementById("warehouses-table").innerHTML = renderTable(cols, warehouses);
}
