/**
 * LogiSight — Shipments list page
 */

let currentPage = 1;
let sortDir = "desc";

const SHIPMENT_COLUMNS = [
    { key: "shipment_id", label: "ID expédition", render: r => `<a href="/shipments/${r.shipment_id}">${r.shipment_id}</a>` },
    { key: "customer_name", label: "Client" },
    { label: "Origine → Destination", render: r => `${r.origin} → ${r.destination}` },
    { key: "cargo_type", label: "Marchandise" },
    { label: "Départ", render: r => fmt.date(r.planned_departure) },
    { label: "ETA", render: r => fmt.date(r.planned_arrival) },
    { label: "Livraison", render: r => fmt.date(r.actual_arrival) },
    { label: "Statut", render: r => badge(...(STATUS_LABELS[r.status] || [r.status, "neutral"])) },
    { label: "Retard", num: true, render: r => r.delay_hours ? fmt.hours(r.delay_hours) : "—" },
    { label: "Risque", render: r => badge(...(RISK_LABELS[r.risk_level] || [r.risk_level, "neutral"])) },
    { label: "Coût", num: true, render: r => fmt.xaf(r.cost) },
];

async function loadShipments() {
    const el = document.getElementById("shipments-table");
    const params = {
        ...GlobalFilters.apiParams(["status"]),
        status: document.getElementById("f-status").value,
        sort: document.getElementById("f-sort").value,
        order: sortDir,
        page: currentPage,
        per_page: 25,
    };
    if (params.sort && params.sort.startsWith("Tri :")) delete params.sort;

    try {
        const res = await API.get("/api/v1/shipments", params);
        const rows = res.data;
        if (!rows.length) {
            el.innerHTML = renderEmpty("Aucune expédition ne correspond aux filtres sélectionnés.");
            document.getElementById("shipments-pagination").innerHTML = "";
            return;
        }
        el.innerHTML = renderTable(SHIPMENT_COLUMNS, rows);
        document.getElementById("shipments-pagination").innerHTML = renderPagination(res.meta);
        bindPagination();
    } catch (e) {
        el.innerHTML = renderError(e.message);
    }
}

function bindPagination() {
    document.querySelectorAll("#shipments-pagination button[data-page]").forEach(btn => {
        btn.addEventListener("click", () => {
            currentPage = parseInt(btn.dataset.page, 10);
            loadShipments();
        });
    });
}

document.addEventListener("DOMContentLoaded", async () => {
    // prefill search from global-search redirect (?q=)
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get("q")) document.getElementById("f-q").value = urlParams.get("q");
    if (urlParams.get("origin")) setTimeout(() => {
        const sel = document.getElementById("f-origin");
        sel.value = urlParams.get("origin");
        loadShipments();
    }, 300);

    const res = await API.get("/api/v1/meta/filters");
    const d = res.data;
    fillSelect("f-origin", d.origins);
    fillSelect("f-dest", d.destinations, "Toutes les destinations");
    fillSelect("f-cargo", d.cargo_types, "Tous les types");
    fillSelect("f-status", d.statuses, "Tous les statuts");

    const debounced = debounce(loadShipments, 350);
    GlobalFilters.onChange(loadShipments);
    document.getElementById("f-q").addEventListener("input", () => { currentPage = 1; debounced(); });
    document.getElementById("f-sort").addEventListener("change", () => { currentPage = 1; loadShipments(); });

    loadShipments();
});
