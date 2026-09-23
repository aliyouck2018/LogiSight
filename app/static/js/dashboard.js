/**
 * LogiSight — Dashboard page
 * Loads KPIs, trends, distributions, map, recent shipments, alerts, insights.
 * All data comes from the API; filters re-trigger every panel.
 */

const PLOT_DEFAULTS = {
    margin: { l: 44, r: 12, t: 8, b: 34 },
    font: { family: "Inter, Segoe UI, sans-serif", size: 11, color: "#6b7a90" },
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    xaxis: { gridcolor: "#eef1f6", tickfont: { size: 10 } },
    yaxis: { gridcolor: "#eef1f6", tickfont: { size: 10 } },
};

function plot(el, data, layout = {}, config = {}) {
    Plotly.newPlot(prepPlotEl(el), data, { ...PLOT_DEFAULTS, ...layout }, { displayModeBar: false, responsive: true, ...config });
}

/* ------------------------------------------------------------------ */
/* Filter options                                                      */
/* ------------------------------------------------------------------ */

async function loadFilterOptions() {
    const res = await API.get("/api/v1/meta/filters");
    const d = res.data;
    fillSelect("f-origin", d.origins);
    fillSelect("f-dest", d.destinations, "Toutes les destinations");
    fillSelect("f-customer", d.customers.map(c => c.name), "Tous les clients");
    fillSelect("f-cargo", d.cargo_types, "Tous les types");
    fillSelect("f-status", d.statuses, "Tous les statuts");

    // map customer select values to ids via index
    const sel = document.getElementById("f-customer");
    sel.dataset.ids = JSON.stringify(d.customers.map(c => c.id));
}

function customerIdFromName(name) {
    if (!name) return "";
    const sel = document.getElementById("f-customer");
    const ids = JSON.parse(sel.dataset.ids || "[]");
    const options = Array.from(sel.options).map(o => o.value);
    const idx = options.indexOf(name) - 1; // minus "all" option
    return idx >= 0 && ids[idx] !== undefined ? ids[idx] : "";
}

/* ------------------------------------------------------------------ */
/* KPI cards                                                           */
/* ------------------------------------------------------------------ */

const KPI_ICONS = {
    box: "📦", truck: "🚚", check: "✅", clock: "🕒",
    shield: "🛡️", alert: "⚠️", warehouse: "🏭", coins: "💰",
};

function renderKpis(kpis) {
    const grid = document.getElementById("kpi-grid");
    grid.innerHTML = kpis.map(k => {
        const isPct = k.unit === "%";
        const value =
            k.key === "avg_cost" ? fmt.xaf(k.value)
            : isPct ? fmt.pct(k.value)
            : k.unit === "jours" ? fmt.num(k.value, 1) + " jours"
            : k.unit === "h" ? fmt.hours(k.value)
            : fmt.num(k.value);
        return renderKpiCard({
            label: k.label,
            value,
            delta: k.delta,
            icon: KPI_ICONS[k.icon] || "📊",
            iconColor: iconColorFor(k.key),
        });
    }).join("");
}

function iconColorFor(key) {
    const map = {
        total_shipments: "blue", active_shipments: "cyan", delivered: "green",
        otd_rate: "green", avg_delivery_time: "blue", avg_customs_clearance: "cyan",
        avg_transit_delay: "orange", delayed_shipments: "red",
        warehouse_utilization: "orange", avg_cost: "cyan",
    };
    return map[key] || "blue";
}

/* ------------------------------------------------------------------ */
/* Charts                                                              */
/* ------------------------------------------------------------------ */

async function loadCharts(params) {
    // volume + OTD trends
    const trends = await API.get("/api/v1/dashboard/trends", params);
    const t = trends.data;

    plot("chart-volume", [{
        x: t.labels, y: t.volume, type: "scatter", mode: "lines+markers",
        name: "Volume", line: { color: CHART_COLORS[0], width: 2.5, shape: "spline" },
        fill: "tozeroy", fillcolor: "rgba(30,94,255,0.08)",
    }], { yaxis: { gridcolor: "#eef1f6", title: "Expéditions" } });

    plot("chart-otd", [{
        x: t.labels, y: t.otd, type: "scatter", mode: "lines+markers",
        name: "OTD", line: { color: CHART_COLORS[1], width: 2.5, shape: "spline" },
    }], {
        yaxis: { gridcolor: "#eef1f6", ticksuffix: "%", range: [Math.max(0, Math.min(...t.otd.filter(v => v !== null)) - 10), 100] },
    });

    // status donut
    const status = await API.get("/api/v1/dashboard/status-distribution", params);
    const sData = status.data;
    const sLabels = Object.keys(sData);
    const statusFr = sLabels.map(s => (STATUS_LABELS[s] || [s])[0]);
    const sColors = sLabels.map(s => colorForStatus(s));
    plot("chart-status", [{
        labels: statusFr, values: sLabels.map(s => sData[s]), type: "pie",
        hole: 0.62, marker: { colors: sColors }, textinfo: "percent",
        hovertemplate: "%{label}: %{value}<extra></extra>",
    }], { showlegend: true, legend: { orientation: "v", x: 1, y: 0.5 }, margin: { l: 8, r: 8, t: 8, b: 8 } });

    // delay causes
    const causes = await API.get("/api/v1/dashboard/delay-causes", params);
    const c = causes.data;
    plot("chart-causes", [{
        type: "bar", orientation: "h",
        y: c.labels.map(l => labelForCause(l)).reverse(),
        x: c.shares.slice().reverse(),
        marker: { color: c.shares.map(v => v > 30 ? CHART_COLORS[3] : v > 15 ? CHART_COLORS[2] : CHART_COLORS[0]).reverse() },
        hovertemplate: "%{y}: %{x}%<extra></extra>",
    }], { xaxis: { gridcolor: "#eef1f6", ticksuffix: "%" }, yaxis: { automargin: true } });

    // routes performance
    const routes = await API.get("/api/v1/dashboard/routes", params);
    const r = routes.data.slice(0, 6);
    if (r.length) {
        plot("chart-routes", [
            {
                x: r.map(x => x.route), y: r.map(x => x.otd), type: "bar", name: "OTD (%)",
                marker: { color: CHART_COLORS[0] }, yaxis: "y",
            },
            {
                x: r.map(x => x.route), y: r.map(x => x.avg_delay), type: "scatter",
                mode: "lines+markers", name: "Retard moyen (h)", yaxis: "y2",
                line: { color: CHART_COLORS[2], width: 2 },
            },
        ], {
            yaxis: { gridcolor: "#eef1f6", ticksuffix: "%" },
            yaxis2: { overlaying: "y", side: "right", title: "h", showgrid: false },
            legend: { orientation: "h", y: -0.28 },
            xaxis: { tickangle: -18, automargin: true },
        });
    } else {
        document.getElementById("chart-routes").innerHTML = renderEmpty();
    }
}

function colorForStatus(s) {
    const map = {
        DELIVERED: "#16a34a", IN_TRANSIT: "#1e5eff", AT_CUSTOMS: "#f59e0b",
        CUSTOMS_CLEARED: "#0284c7", OUT_FOR_DELIVERY: "#7c3aed",
        DELAYED: "#dc2626", CANCELLED: "#94a3b8", BOOKED: "#64748b",
    };
    return map[s] || "#94a3b8";
}

function labelForCause(c) {
    const map = {
        DOUANE: "Douane", TRANSPORT: "Transport", DOCUMENTATION: "Documentation",
        ENTREPOT: "Entrepôt", AUTRES: "Autres",
    };
    return map[c] || c;
}

/* ------------------------------------------------------------------ */
/* Map                                                                 */
/* ------------------------------------------------------------------ */

let mapObj = null;
let mapLayers = null;

async function loadMap() {
    const res = await API.get("/api/v1/map/routes");
    const { cities, routes } = res.data;

    const mapEl = prepPlotEl("map-network");
    if (!mapObj) {
        mapObj = L.map(mapEl, { zoomControl: false, attributionControl: false });
        L.control.zoom({ position: "bottomright" }).addTo(mapObj);
        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            attribution: "© OpenStreetMap",
        }).addTo(mapObj);
        mapLayers = L.layerGroup().addTo(mapObj);
        Object.entries(cities).forEach(([name, coords]) => {
            if (coords[0] > 15) return; // skip far international origins on the base view
            L.circleMarker(coords, {
                radius: 5, color: "#0d1b3e", weight: 2, fillColor: "#ffffff", fillOpacity: 1,
            }).addTo(mapLayers).bindTooltip(name, { permanent: false });
        });
        mapObj.fitBounds([[1.8, 8.2], [11.5, 15.2]]);
    } else {
        mapLayers.clearLayers();
    }

    routes.forEach(r => {
        // Domestic corridors only — international legs would clutter the view
        if (cities[r.origin][0] > 15 || cities[r.destination][0] > 15) return;
        const width = Math.min(1 + r.volume / 60, 6);
        const color = r.otd === null ? "#94a3b8" : r.otd >= 80 ? "#16a34a" : r.otd >= 65 ? "#f59e0b" : "#dc2626";
        L.polyline([r.from, r.to], {
            color, weight: width, opacity: 0.75,
        }).addTo(mapLayers).on("click", () => {
            window.location = `/shipments?origin=${encodeURIComponent(r.origin)}&destination=${encodeURIComponent(r.destination)}`;
        }).bindPopup(`
            <strong>${r.origin} → ${r.destination}</strong><br>
            Expéditions : ${fmt.num(r.volume)}<br>
            OTD : ${fmt.pct(r.otd)}<br>
            Retard moyen : ${fmt.hours(r.avg_delay)}
        `);
    });
}

/* ------------------------------------------------------------------ */
/* Tables & panels                                                     */
/* ------------------------------------------------------------------ */

async function loadRecentShipments(params) {
    const el = document.getElementById("recent-shipments");
    try {
        const res = await API.get("/api/v1/dashboard/recent-shipments", { ...params, limit: 8 });
        const rows = res.data;
        if (!rows.length) { el.innerHTML = renderEmpty("Aucune expédition pour ces filtres."); return; }
        const columns = [
            { key: "shipment_id", label: "ID expédition", render: r => `<a href="/shipments/${r.shipment_id}">${r.shipment_id}</a>` },
            { key: "customer_name", label: "Client" },
            { label: "Origine → Destination", render: r => `${r.origin} → ${r.destination}` },
            { label: "Statut", render: r => badge(...(STATUS_LABELS[r.status] || [r.status, "neutral"])) },
            { label: "ETA", render: r => fmt.date(r.planned_arrival) },
            { label: "Retard", num: true, render: r => r.delay_hours ? fmt.hours(r.delay_hours) : "—" },
            { label: "Risque", render: r => badge(...(RISK_LABELS[r.risk_level] || [r.risk_level, "neutral"])) },
        ];
        el.innerHTML = renderTable(columns, rows);
    } catch (e) {
        el.innerHTML = renderError(e.message);
        bindRetry(el, () => loadRecentShipments(params));
    }
}

async function loadCriticalAlerts() {
    const el = document.getElementById("critical-alerts");
    try {
        const res = await API.get("/api/v1/alerts", { status: "OPEN", per_page: 5 });
        const rows = res.data;
        if (!rows.length) { el.innerHTML = renderEmpty("Aucune alerte ouverte."); return; }
        el.innerHTML = rows.map(a => `
            <div class="item-row">
                <span class="severity-dot" style="background:${severityColor(a.severity)}"></span>
                <div>
                    <div class="title">${a.title}</div>
                    <div class="desc">${a.description}</div>
                </div>
                <span class="when">${fmt.datetime(a.created_at)}</span>
            </div>
        `).join("");
    } catch (e) {
        el.innerHTML = renderError(e.message);
    }
}

function severityColor(s) {
    return { CRITICAL: "#dc2626", HIGH: "#f97316", WARNING: "#f59e0b", INFO: "#0284c7" }[s] || "#94a3b8";
}

async function loadInsights() {
    const el = document.getElementById("management-insights");
    try {
        const res = await API.get("/api/v1/insights");
        const rows = res.data.slice(0, 5);
        if (!rows.length) { el.innerHTML = renderEmpty("Aucune insight disponible."); return; }
        const icon = { HIGH: "🔴", WARNING: "🟠", INFO: "🟢" };
        el.innerHTML = rows.map(i => `
            <div class="item-row">
                <span style="font-size:16px">${icon[i.severity] || "🔵"}</span>
                <div>
                    <div class="title">${i.title}</div>
                    <div class="desc">${i.description}</div>
                </div>
            </div>
        `).join("");
    } catch (e) {
        el.innerHTML = renderError(e.message);
    }
}

function bindRetry(el, fn) {
    const btn = el.querySelector(".btn-retry");
    if (btn) btn.addEventListener("click", fn);
}

/* ------------------------------------------------------------------ */
/* Main                                                                */
/* ------------------------------------------------------------------ */

async function refreshDashboard() {
    const raw = GlobalFilters.apiParams(["customer_id"]);
    // customer filter uses name in the select — resolve to id
    const params = { ...raw, customer_id: customerIdFromName(raw.customer_id) };

    try {
        const res = await API.get("/api/v1/dashboard/summary", params);
        renderKpis(res.data.kpis);
        document.getElementById("last-updated").textContent =
            "Dernière mise à jour : " + new Date().toLocaleString("fr-FR", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
    } catch (e) {
        document.getElementById("kpi-grid").innerHTML = `<div class="card">${renderError(e.message)}</div>`;
    }
    loadCharts(params).catch(console.error);
    loadMap().catch(console.error);
    loadRecentShipments(params);
    loadCriticalAlerts();
    loadInsights();
}

document.addEventListener("DOMContentLoaded", async () => {
    await loadFilterOptions();
    GlobalFilters.onChange(refreshDashboard);
    refreshDashboard();
});
