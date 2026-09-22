/**
 * LogiSight — Frontend core
 * API client, shared UI component renderers, state helpers.
 */

/* ==========================================================================
   API client
   ========================================================================== */

const API = {
    async request(path, options = {}) {
        let response;
        try {
            response = await fetch(path, {
                headers: { "Content-Type": "application/json", ...options.headers },
                ...options,
            });
        } catch (networkErr) {
            throw { code: "NETWORK_ERROR", message: "Impossible de contacter le serveur." };
        }
        let payload = null;
        try { payload = await response.json(); } catch (_) { /* no body */ }

        if (!response.ok || (payload && payload.success === false)) {
            throw {
                code: payload?.error?.code || "HTTP_" + response.status,
                message: payload?.error?.message || "Une erreur est survenue.",
                status: response.status,
            };
        }
        return payload;
    },

    get(path, params) {
        if (params) {
            const qs = new URLSearchParams(
                Object.entries(params).filter(([, v]) => v !== "" && v !== null && v !== undefined)
            ).toString();
            if (qs) path += (path.includes("?") ? "&" : "?") + qs;
        }
        return this.request(path);
    },

    post(path, body) { return this.request(path, { method: "POST", body: JSON.stringify(body || {}) }); },
    patch(path, body) { return this.request(path, { method: "PATCH", body: JSON.stringify(body || {}) }); },
};

/* ==========================================================================
   Formatting helpers (fr-FR)
   ========================================================================== */

const fmt = {
    num(v, decimals = 0) {
        if (v === null || v === undefined || isNaN(v)) return "—";
        return Number(v).toLocaleString("fr-FR", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
    },
    pct(v, decimals = 1) {
        if (v === null || v === undefined || isNaN(v)) return "—";
        return this.num(v, decimals) + " %";
    },
    xaf(v) {
        if (v === null || v === undefined || isNaN(v)) return "—";
        return this.num(Math.round(v)) + " XAF";
    },
    hours(v) {
        if (v === null || v === undefined || isNaN(v)) return "—";
        if (v >= 48) return this.num(v / 24, 1) + " jours";
        return this.num(v, 1) + " h";
    },
    date(v) {
        if (!v) return "—";
        const d = new Date(v);
        if (isNaN(d)) return v;
        return d.toLocaleDateString("fr-FR", { day: "2-digit", month: "short", year: "numeric" });
    },
    datetime(v) {
        if (!v) return "—";
        const d = new Date(v);
        if (isNaN(d)) return v;
        return d.toLocaleString("fr-FR", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
    },
    km(v) { return v == null ? "—" : this.num(v) + " km"; },
    kg(v) { return v == null ? "—" : this.num(v) + " kg"; },
    delta(v, suffix = "%") {
        if (v === null || v === undefined || isNaN(v)) return `<span class="kpi-delta flat">— <span class="vs">vs période précédente</span></span>`;
        const cls = v > 0.05 ? "up" : v < -0.05 ? "down" : "flat";
        const arrow = v > 0 ? "↑" : v < 0 ? "↓" : "→";
        return `<span class="kpi-delta ${cls}">${arrow} ${Math.abs(v).toLocaleString("fr-FR", { maximumFractionDigits: 1 })}${suffix} <span class="vs">vs période précédente</span></span>`;
    },
};

const CHART_COLORS = ["#1e5eff", "#16a34a", "#f59e0b", "#dc2626", "#7c3aed", "#0284c7", "#64748b"];

/* ==========================================================================
   Status / severity mapping (FR labels)
   ========================================================================== */

const STATUS_LABELS = {
    BOOKED: ["Réservée", "neutral"],
    IN_TRANSIT: ["En transit", "info"],
    AT_CUSTOMS: ["À la douane", "warning"],
    CUSTOMS_CLEARED: ["Dédouanée", "primary"],
    OUT_FOR_DELIVERY: ["En livraison", "info"],
    DELIVERED: ["Livrée", "success"],
    DELAYED: ["Retardée", "danger"],
    CANCELLED: ["Annulée", "neutral"],
};

const SEVERITY_LABELS = {
    INFO: ["Info", "info"],
    WARNING: ["Élevé", "warning"],
    HIGH: ["Élevé", "warning"],
    CRITICAL: ["Critique", "danger"],
};

const SLA_LABELS = {
    ON_TIME: ["À l'heure", "success"],
    AT_RISK: ["À risque", "warning"],
    BREACHED: ["Dépassé", "danger"],
};

const RISK_LABELS = {
    LOW: ["Faible", "success"],
    MEDIUM: ["Moyen", "warning"],
    HIGH: ["Élevé", "danger"],
    CRITICAL: ["Critique", "danger"],
};

const ALERT_STATUS_LABELS = {
    OPEN: ["Ouverte", "danger"],
    ACKNOWLEDGED: ["Prise en compte", "warning"],
    RESOLVED: ["Résolue", "success"],
};

function badge(label, color) {
    return `<span class="badge ${color}">${label}</span>`;
}

/* Fill a <select> with option values (keeps the "all" placeholder). */
function fillSelect(id, values, allLabel = "Toutes les origines") {
    const sel = document.getElementById(id);
    if (!sel) return;
    (values || []).forEach(v => {
        const opt = document.createElement("option");
        opt.value = v;
        opt.textContent = v;
        sel.appendChild(opt);
    });
}

function debounce(fn, ms) {
    let t;
    return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
}

/* ==========================================================================
   State renderers: loading / error / empty
   ========================================================================== */

function renderLoading(msg = "Chargement des données logistiques…") {
    return `<div class="state"><div class="spinner"></div>${msg}</div>`;
}

function renderError(msg = "Impossible de charger les données opérationnelles.") {
    return `<div class="state error">${msg}<br><button class="btn-retry" style="margin-top:12px">Réessayer</button></div>`;
}

function renderEmpty(msg = "Aucune donnée ne correspond aux filtres sélectionnés.") {
    return `<div class="state">${msg}</div>`;
}

/* ==========================================================================
   KPI cards
   ========================================================================== */

function renderKpiCard({ label, value, delta, icon, iconColor = "blue", sub }) {
    const deltaHtml = delta !== undefined ? `<div>${fmt.delta(delta)}</div>` : (sub ? `<div class="kpi-delta flat">${sub}</div>` : "");
    return `
    <div class="card kpi-card">
        <div class="kpi-icon ${iconColor}">${icon}</div>
        <div>
            <div class="kpi-label">${label}</div>
            <div class="kpi-value">${value}</div>
            ${deltaHtml}
        </div>
    </div>`;
}

/* ==========================================================================
   Simple table + pagination
   ========================================================================== */

function renderTable(columns, rows) {
    const head = columns.map(c => `<th class="${c.num ? "num" : ""}" ${c.sortable ? `data-key="${c.key}"` : ""}>${c.label}</th>`).join("");
    const body = rows.map(r => `<tr>${columns.map(c => `<td class="${c.num ? "num" : ""}">${c.render ? c.render(r) : (r[c.key] ?? "—")}</td>`).join("")}</tr>`).join("");
    return `<div class="table-wrap"><table class="data-table"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
}

function renderPagination(meta) {
    if (!meta || meta.pages <= 1) return "";
    const p = meta.page, total = meta.pages;
    const btn = (label, page, disabled, current) =>
        `<button ${disabled ? "disabled" : ""} data-page="${page}" class="${current ? "current" : ""}">${label}</button>`;
    let buttons = btn("‹", p - 1, p <= 1);
    const start = Math.max(1, p - 2), end = Math.min(total, p + 2);
    if (start > 1) buttons += btn("1", 1, false, false) + (start > 2 ? `<span style="padding:0 4px">…</span>` : "");
    for (let i = start; i <= end; i++) buttons += btn(i, i, false, i === p);
    if (end < total) { if (end < total - 1) buttons += `<span style="padding:0 4px">…</span>`; buttons += btn(total, total, false, false); }
    buttons += btn("›", p + 1, p >= total);
    return `<div class="pagination">
        <span>${fmt.num(meta.total)} résultat(s) — page ${p} / ${total}</span>
        <div class="pages">${buttons}</div>
    </div>`;
}

/* ==========================================================================
   Global filters (date range + entity filters)
   ========================================================================== */

const GlobalFilters = {
    values() {
        return {
            start_date: document.getElementById("f-start")?.value || "",
            end_date: document.getElementById("f-end")?.value || "",
            origin: document.getElementById("f-origin")?.value || "",
            destination: document.getElementById("f-dest")?.value || "",
            customer_id: document.getElementById("f-customer")?.value || "",
            cargo_type: document.getElementById("f-cargo")?.value || "",
            status: document.getElementById("f-status")?.value || "",
        };
    },
    onChange(cb) {
        document.querySelectorAll(".filter-bar select, .filter-bar input").forEach(el => {
            el.addEventListener("change", () => cb(this.values()));
        });
    },
    apiParams(exclude = []) {
        const v = this.values();
        exclude.forEach(k => delete v[k]);
        return v;
    },
};

/* ==========================================================================
   Alert counter in nav
   ========================================================================== */

async function updateAlertCounters() {
    try {
        const res = await API.get("/api/v1/alerts", { status: "OPEN", per_page: 1 });
        const total = res.meta?.total || 0;
        const nav = document.getElementById("nav-alert-count");
        const notif = document.getElementById("notif-count");
        if (nav && total > 0) { nav.textContent = total; nav.style.display = ""; }
        if (notif && total > 0) { notif.textContent = total > 99 ? "99+" : total; notif.style.display = ""; }
    } catch (_) { /* silent */ }
}

/* ==========================================================================
   Global search — redirect to shipments page
   ========================================================================== */

document.addEventListener("DOMContentLoaded", () => {
    const search = document.getElementById("global-search");
    if (search) {
        search.addEventListener("keydown", (e) => {
            if (e.key === "Enter" && search.value.trim()) {
                window.location = "/shipments?q=" + encodeURIComponent(search.value.trim());
            }
        });
    }
    updateAlertCounters();
});
