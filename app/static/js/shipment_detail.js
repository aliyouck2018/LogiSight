/**
 * LogiSight — Shipment detail page
 */

const SHIPMENT_ID = window.location.pathname.split("/").pop();

document.addEventListener("DOMContentLoaded", loadDetail);

async function loadDetail() {
    try {
        const res = await API.get(`/api/v1/shipments/${SHIPMENT_ID}`);
        const s = res.data;
        document.getElementById("shipment-subtitle").textContent =
            `${s.origin} → ${s.destination} · ${s.customer_name || "—"}`;
        renderDetailKpis(s);
        renderTimeline(res);
        renderCustomsInfo(s);
        renderTransportInfo(s);
        renderWarehouseInfo(s);
    } catch (e) {
        document.getElementById("detail-error").innerHTML =
            `<div class="card">${renderError(e.message)}</div>`;
        ["detail-kpis", "timeline", "customs-info", "transport-info", "warehouse-info"]
            .forEach(id => document.getElementById(id).innerHTML = "");
    }
}

function renderDetailKpis(s) {
    const delay = s.delay_hours && s.delay_hours > 0 ? fmt.hours(s.delay_hours) : "À l'heure";
    const kpis = [
        { label: "Statut", value: (STATUS_LABELS[s.status] || [s.status])[0], icon: "🚚", color: "blue" },
        { label: "Retard", value: delay, icon: "🕒", color: s.delay_hours > 12 ? "red" : "green" },
        { label: "Transit réel", value: s.transit_hours ? fmt.hours(s.transit_hours) : "En cours", icon: "⏱️", color: "cyan" },
        { label: "Score de risque", value: s.risk_score != null ? `${s.risk_score} / 100` : "—", icon: "⚠️", color: riskColor(s.risk_level) },
        { label: "Valeur déclarée", value: fmt.xaf(s.declared_value), icon: "💰", color: "blue" },
        { label: "Coût total", value: fmt.xaf(s.cost), icon: "🧾", color: "cyan" },
        { label: "Poids", value: fmt.kg(s.weight_kg), icon: "⚖️", color: "blue" },
        { label: "Volume", value: fmt.num(s.volume_m3, 1) + " m³", icon: "📦", color: "orange" },
    ];
    document.getElementById("detail-kpis").innerHTML = kpis.map(k => `
        <div class="card kpi-card">
            <div class="kpi-icon ${k.color}">${k.icon}</div>
            <div>
                <div class="kpi-label">${k.label}</div>
                <div class="kpi-value" style="font-size:1.1rem">${k.value}</div>
            </div>
        </div>
    `).join("");
}

function riskColor(level) {
    return { LOW: "green", MEDIUM: "orange", HIGH: "red", CRITICAL: "red" }[level] || "blue";
}

function renderTimeline(res) {
    const steps = res.data.timeline || res.data;
    const el = document.getElementById("timeline");
    if (!Array.isArray(steps) || !steps.length) { el.innerHTML = renderEmpty(); return; }

    const items = steps.map(st => {
        const done = !!st.actual;
        const late = st.actual && st.planned && new Date(st.actual) > new Date(st.planned);
        return `
        <div class="timeline-step ${done ? "done" : ""}">
            <div class="timeline-dot" style="background:${done ? (late ? "var(--color-danger)" : "var(--color-success)") : "var(--color-border)"}"></div>
            <div class="timeline-content">
                <div class="tl-label">${st.label} <span class="tl-location">· ${st.location || ""}</span></div>
                <div class="tl-dates">
                    <span>Prévu : ${fmt.datetime(st.planned)}</span>
                    <span class="${late ? "late" : ""}">Réel : ${st.actual ? fmt.datetime(st.actual) : "—"}</span>
                    ${st.sla_status ? badge(...(SLA_LABELS[st.sla_status] || [st.sla_status, "neutral"])) : ""}
                    ${st.duration_hours ? `<span>${fmt.hours(st.duration_hours)}</span>` : ""}
                </div>
            </div>
        </div>`;
    }).join("");
    el.innerHTML = `<div class="timeline">${items}</div>`;
}

function renderCustomsInfo(s) {
    const el = document.getElementById("customs-info");
    if (!s.customs) { el.innerHTML = renderEmpty("Aucune déclaration douanière pour cette expédition."); return; }
    const c = s.customs;
    const rows = [
        ["N° déclaration", c.declaration_id],
        ["Date de déclaration", fmt.datetime(c.declaration_date)],
        ["Date de dédouanement", fmt.datetime(c.clearance_date)],
        ["Durée de dédouanement", c.clearance_duration_hours ? fmt.hours(c.clearance_duration_hours) : "En attente"],
        ["SLA", fmt.hours(c.sla_hours)],
        ["Statut SLA", badge(...(SLA_LABELS[c.sla_status] || [c.sla_status, "neutral"]))],
        ["Valeur déclarée", fmt.xaf(c.declared_value)],
        ["Droits et taxes", fmt.xaf(c.duties_amount)],
    ];
    el.innerHTML = `<div class="table-wrap"><table class="data-table"><tbody>${
        rows.map(([k, v]) => `<tr><td style="color:var(--color-muted);width:45%">${k}</td><td>${v ?? "—"}</td></tr>`).join("")
    }</tbody></table></div>`;
}

function renderTransportInfo(s) {
    const el = document.getElementById("transport-info");
    if (!s.trips || !s.trips.length) { el.innerHTML = renderEmpty("Aucune tournée enregistrée."); return; }
    const cols = [
        { key: "trip_id", label: "Tournée" },
        { label: "Véhicule", render: r => r.vehicle_registration || r.vehicle_id },
        { label: "Transporteur", render: r => r.transporter || "—" },
        { label: "Conducteur", render: r => r.driver_name || "—" },
        { label: "Trajet", render: r => `${r.origin} → ${r.destination}` },
        { label: "Prévu", num: true, render: r => fmt.hours(r.planned_duration_hours) },
        { label: "Réel", num: true, render: r => r.actual_duration_hours ? fmt.hours(r.actual_duration_hours) : "—" },
        { label: "Distance", num: true, render: r => fmt.km(r.distance_km) },
        { label: "Carburant", num: true, render: r => r.fuel_liters ? fmt.num(r.fuel_liters, 0) + " L" : "—" },
        { label: "Statut", render: r => badge(...(TRIP_STATUS[r.trip_status] || [r.trip_status, "neutral"])) },
    ];
    el.innerHTML = renderTable(cols, s.trips);
}

const TRIP_STATUS = {
    PLANNED: ["Planifiée", "neutral"], IN_PROGRESS: ["En cours", "info"],
    COMPLETED: ["Terminée", "success"], CANCELLED: ["Annulée", "neutral"],
};

function renderWarehouseInfo(s) {
    const el = document.getElementById("warehouse-info");
    if (!s.warehouse_transactions || !s.warehouse_transactions.length) {
        el.innerHTML = renderEmpty("Aucun mouvement d'entrepôt.");
        return;
    }
    const cols = [
        { label: "Date", render: r => fmt.date(r.transaction_date) },
        { label: "Type", render: r => badge(...({ IN: ["Entrée", "primary"], OUT: ["Sortie", "success"], ADJUSTMENT: ["Ajustement", "warning"] }[r.transaction_type] || [r.transaction_type, "neutral"])) },
        { label: "Quantité", num: true, render: r => fmt.num(r.quantity, 0) },
        { label: "Durée stockage", render: r => r.storage_duration_days ? fmt.num(r.storage_duration_days, 1) + " j" : "—" },
        { label: "Coût stockage", render: r => r.storage_cost ? fmt.xaf(r.storage_cost) : "—" },
    ];
    el.innerHTML = renderTable(cols, s.warehouse_transactions);
}
