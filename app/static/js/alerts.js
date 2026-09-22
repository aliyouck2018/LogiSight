/**
 * LogiSight — Alerts page
 */

let alertPage = 1;
let toastTimer = null;

const SEVERITY_BADGE = {
    CRITICAL: ["Critique", "danger"], HIGH: ["Élevé", "warning"],
    WARNING: ["Avertissement", "warning"], INFO: ["Info", "info"],
};
const STATUS_BADGE = {
    OPEN: ["Ouverte", "danger"], ACKNOWLEDGED: ["Prise en compte", "warning"],
    RESOLVED: ["Résolue", "success"],
};

document.addEventListener("DOMContentLoaded", () => {
    GlobalFilters.onChange(refresh);
    document.getElementById("btn-regenerate").addEventListener("click", regenerateAlerts);
    refresh();
});

async function refresh() {
    loadCounts();
    loadAlerts();
}

async function loadCounts() {
    try {
        const res = await API.get("/api/v1/alerts/counts");
        const d = res.data;
        const cards = [
            { label: "Alertes ouvertes", value: fmt.num(d.open_total), icon: "🔔", color: d.open_total ? "red" : "green" },
            { label: "Critiques", value: fmt.num(d.by_severity.CRITICAL || 0), icon: "🚨", color: "red" },
            { label: "Élevées", value: fmt.num(d.by_severity.HIGH || 0), icon: "⚠️", color: "orange" },
            { label: "Retards douane", value: fmt.num(d.by_type.CUSTOMS_DELAY || 0), icon: "🛃", color: "orange" },
            { label: "Capacité entrepôt", value: fmt.num(d.by_type.WAREHOUSE_CAPACITY || 0), icon: "🏭", color: "cyan" },
            { label: "Anomalies", value: fmt.num(d.by_type.ANOMALOUS_PERFORMANCE || 0), icon: "📉", color: "blue" },
        ];
        document.getElementById("alert-counts").innerHTML = cards.map(renderKpiCard).join("");
    } catch (e) { /* counter panel non blocking */ }
}

async function loadAlerts() {
    const el = document.getElementById("alerts-list");
    try {
        const res = await API.get("/api/v1/alerts", {
            status: document.getElementById("f-status").value,
            severity: document.getElementById("f-severity").value,
            alert_type: document.getElementById("f-type").value,
            page: alertPage, per_page: 15,
        });
        const rows = res.data;
        if (!rows.length) { el.innerHTML = renderEmpty("Aucune alerte pour ces filtres."); return; }

        el.innerHTML = rows.map(a => `
            <div class="alert-row">
                <span class="severity-dot" style="background:${severityColor(a.severity)};margin-top:6px"></span>
                <div class="alert-body">
                    <div class="alert-top">
                        <span class="title">${a.title}</span>
                        ${badge(...(SEVERITY_BADGE[a.severity] || [a.severity, "neutral"]))}
                        ${badge(...(STATUS_BADGE[a.status] || [a.status, "neutral"]))}
                    </div>
                    <div class="desc">${a.description}</div>
                    ${a.recommended_action ? `<div class="action">→ ${a.recommended_action}</div>` : ""}
                    <div class="meta">
                        ${a.entity_type === "SHIPMENT" && a.entity_id ? `<a href="/shipments/${a.entity_id}">Voir l'expédition</a> · ` : ""}
                        ${fmt.datetime(a.created_at)}
                    </div>
                </div>
                <div class="alert-actions">
                    ${a.status === "OPEN" ? `<button data-id="${a.id}" data-status="ACKNOWLEDGED">Prendre en compte</button>` : ""}
                    ${a.status !== "RESOLVED" ? `<button data-id="${a.id}" data-status="RESOLVED" class="resolve">Résoudre</button>` : ""}
                </div>
            </div>
        `).join("");

        document.getElementById("alerts-pagination").innerHTML = renderPagination(res.meta);
        document.querySelectorAll("#alerts-pagination button[data-page]").forEach(b =>
            b.addEventListener("click", () => { alertPage = +b.dataset.page; loadAlerts(); }));

        el.querySelectorAll(".alert-actions button").forEach(btn =>
            btn.addEventListener("click", () => updateAlert(btn.dataset.id, btn.dataset.status)));
    } catch (e) {
        el.innerHTML = renderError(e.message);
    }
}

async function updateAlert(id, status) {
    try {
        await API.patch(`/api/v1/alerts/${id}`, { status });
        refresh();
        updateAlertCounters();
        showToast(status === "RESOLVED" ? "Alerte résolue." : "Alerte prise en compte.");
    } catch (e) {
        showToast(e.message, true);
    }
}

async function regenerateAlerts() {
    try {
        await API.post("/api/v1/reports/generate", { regenerate_alerts: true });
    } catch (e) { /* endpoint spécifique non requis */ }
    showToast("Régénération lancée.");
}

function severityColor(s) {
    return { CRITICAL: "#dc2626", HIGH: "#f97316", WARNING: "#f59e0b", INFO: "#0284c7" }[s] || "#94a3b8";
}

function showToast(msg, isError = false) {
    let t = document.getElementById("toast");
    if (!t) {
        t = document.createElement("div");
        t.id = "toast";
        t.style.cssText = "position:fixed;bottom:24px;right:24px;background:var(--color-sidebar);color:#fff;padding:12px 20px;border-radius:8px;font-size:14px;box-shadow:var(--shadow-lg);z-index:999;opacity:0;transition:opacity .2s";
        document.body.appendChild(t);
    }
    t.textContent = msg;
    t.style.background = isError ? "var(--color-danger)" : "var(--color-sidebar)";
    t.style.opacity = "1";
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { t.style.opacity = "0"; }, 2500);
}
