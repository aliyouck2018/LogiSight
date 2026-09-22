/**
 * LogiSight — Reports page
 */

let currentReport = null;

document.addEventListener("DOMContentLoaded", () => {
    document.getElementById("report-form").addEventListener("submit", e => {
        e.preventDefault();
        generatePreview();
    });
    document.getElementById("btn-csv").addEventListener("click", () => exportReport("csv"));
    document.getElementById("btn-xlsx").addEventListener("click", () => exportReport("xlsx"));
    document.getElementById("btn-pdf").addEventListener("click", () => exportReport("pdf"));
});

async function generatePreview() {
    const payload = reportPayload();
    const status = document.getElementById("export-status");
    try {
        const res = await API.post("/api/v1/reports/generate", payload);
        currentReport = res.data;
        status.textContent = "Aperçu généré — export disponible.";
        renderPreview(currentReport);
    } catch (e) {
        status.textContent = "Erreur : " + e.message;
    }
}

async function exportReport(format) {
    const status = document.getElementById("export-status");
    try {
        status.textContent = "Export en cours…";
        const res = await fetch("/api/v1/reports/export", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ...reportPayload(), format }),
        });
        if (!res.ok) {
            const p = await res.json().catch(() => null);
            throw new Error(p?.error?.message || "Échec de l'export.");
        }
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `logisight_rapport.${format}`;
        a.click();
        URL.revokeObjectURL(url);
        status.textContent = `Export ${format.toUpperCase()} téléchargé.`;
    } catch (e) {
        status.textContent = "Erreur : " + e.message;
    }
}

function reportPayload() {
    return {
        report_type: document.getElementById("report-type").value,
        start_date: document.getElementById("f-start").value || null,
        end_date: document.getElementById("f-end").value || null,
    };
}

function renderPreview(report) {
    const card = document.getElementById("report-preview-card");
    card.style.display = "";
    const el = document.getElementById("report-preview");

    const kpiRows = (report.kpis || []).map(k => `
        <tr><td>${k.label}</td><td class="num">${k.value} ${k.unit || ""}</td></tr>
    `).join("");
    const findings = (report.findings || []).map(f => `<li>${f}</li>`).join("");
    const alerts = (report.alerts || []).map(a => `
        <div class="item-row">
            <span class="severity-dot" style="background:${severityColor(a.severity)}"></span>
            <div><div class="title">${a.title}</div><div class="desc">${a.description}</div></div>
        </div>`).join("");

    el.innerHTML = `
        <h2 style="font-size:1.2rem;margin-bottom:4px">${report.title}</h2>
        <div class="kpi-label" style="margin-bottom:16px">Période : ${report.period}</div>
        <div class="table-wrap" style="margin-bottom:16px">
            <table class="data-table"><thead><tr><th>Indicateur</th><th class="num">Valeur</th></tr></thead><tbody>${kpiRows}</tbody></table>
        </div>
        ${findings ? `<h3 style="font-size:1rem;margin-bottom:8px">Constats clés</h3><ul style="margin:0 0 16px 20px;font-size:0.875rem">${findings}</ul>` : ""}
        ${alerts ? `<h3 style="font-size:1rem;margin-bottom:8px">Alertes opérationnelles</h3><div class="item-list" style="border:1px solid var(--color-border);border-radius:8px">${alerts}</div>` : ""}
        <div class="kpi-label" style="margin-top:16px">Généré le ${new Date().toLocaleString("fr-FR")}</div>
    `;
}

function severityColor(s) {
    return { CRITICAL: "#dc2626", HIGH: "#f97316", WARNING: "#f59e0b", INFO: "#0284c7" }[s] || "#94a3b8";
}
