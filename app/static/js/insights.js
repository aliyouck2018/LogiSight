/**
 * LogiSight — Insights page
 */

const SEVERITY_STYLE = {
    HIGH: { icon: "🔴", label: "Priorité haute", color: "red" },
    WARNING: { icon: "🟠", label: "À surveiller", color: "orange" },
    INFO: { icon: "🟢", label: "Information", color: "green" },
};

document.addEventListener("DOMContentLoaded", loadInsights);

async function loadInsights() {
    const el = document.getElementById("insights-list");
    try {
        const res = await API.get("/api/v1/insights");
        const rows = res.data;
        if (!rows.length) { el.innerHTML = `<div class="card">${renderEmpty("Aucune insight disponible.")}</div>`; return; }

        el.innerHTML = rows.map(i => {
            const st = SEVERITY_STYLE[i.severity] || SEVERITY_STYLE.INFO;
            return `
            <div class="card insight-card">
                <div class="card-header">
                    <h3>${st.icon} ${i.title}</h3>
                    ${badge(st.label, st.color)}
                </div>
                <div class="card-body">
                    <div class="insight-desc">${i.description}</div>
                    <div class="insight-metrics">
                        <div><span class="kpi-label">Métrique</span><span>${i.metric}</span></div>
                        <div><span class="kpi-label">Valeur actuelle</span><span>${fmt.num(i.current_value, 1)}</span></div>
                        <div><span class="kpi-label">Seuil</span><span>${fmt.num(i.threshold, 1)}</span></div>
                    </div>
                    <div class="insight-action">→ ${i.recommended_action}</div>
                </div>
            </div>`;
        }).join("");
    } catch (e) {
        el.innerHTML = `<div class="card">${renderError(e.message)}</div>`;
    }
}
