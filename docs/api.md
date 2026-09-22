# API REST — /api/v1

Toutes les réponses sont JSON avec la forme :

```json
{ "success": true, "data": {}, "meta": {} }
```

Erreurs :

```json
{ "success": false, "error": { "code": "VALIDATION_ERROR", "message": "…" } }
```

## Filtres communs

`?start_date=&end_date=` (YYYY-MM-DD), `?origin=`, `?destination=`,
`?status=`, `?cargo_type=`, `?customer_id=`.
Listes paginées : `?page=1&per_page=25` (max 200).

## Tableau de bord

| Méthode | Route | Description |
|---|---|---|
| GET | `/api/v1/dashboard/summary` | 10 KPI exécutifs + deltas vs période précédente |
| GET | `/api/v1/dashboard/trends?months=12` | volume mensuel + courbe OTD |
| GET | `/api/v1/dashboard/status-distribution` | répartition par statut |
| GET | `/api/v1/dashboard/delay-causes` | causes de retard (partages %) |
| GET | `/api/v1/dashboard/routes` | performance par corridor (OTD, retard moyen) |
| GET | `/api/v1/dashboard/customs-trend` | délai moyen douane + taux de dépassement |
| GET | `/api/v1/dashboard/warehouses` | occupation par entrepôt |
| GET | `/api/v1/dashboard/recent-shipments` | dernières expéditions |

## Expéditions

| Méthode | Route | Description |
|---|---|---|
| GET | `/api/v1/shipments` | liste filtrable/triable/paginée (`?q=` recherche libre, `?sort=&order=`) |
| GET | `/api/v1/shipments/<shipment_id>` | détail complet (client, douane, tournées, entrepôt, timeline) |
| GET | `/api/v1/shipments/<shipment_id>/timeline` | chronologie Départ → Douane → Transport → Livraison |

## Douane

| Méthode | Route | Description |
|---|---|---|
| GET | `/api/v1/customs/summary` | KPI déclarations + SLA |
| GET | `/api/v1/customs/trends` | délai moyen + dépassements par mois |
| GET | `/api/v1/customs/breaches` | déclarations en dépassement (paginé) |
| GET | `/api/v1/customs/by-cargo` | délai moyen par type de marchandise |
| GET | `/api/v1/customs/by-destination` | délai moyen par destination |
| GET | `/api/v1/customs/declarations` | liste paginée (`?sla_status=`, `?customs_status=`) |

## Transport

| Méthode | Route | Description |
|---|---|---|
| GET | `/api/v1/transport/summary` | KPI tournées, vitesse, carburant |
| GET | `/api/v1/transport/routes` | performance par corridor |
| GET | `/api/v1/transport/vehicles` | performance par véhicule |
| GET | `/api/v1/transport/transporters` | performance par transporteur |
| GET | `/api/v1/transport/delays` | histogramme des retards |
| GET | `/api/v1/transport/planned-vs-actual` | durées planifiées vs réelles (12 mois) |
| GET | `/api/v1/transport/trips` | liste paginée des tournées |

## Entrepôts

| Méthode | Route | Description |
|---|---|---|
| GET | `/api/v1/warehouses/summary` | KPI capacité, occupation, coûts |
| GET | `/api/v1/warehouses/utilization` | détail par entrepôt |
| GET | `/api/v1/warehouses/trends` | flux entrées/sorties + coûts (12 mois) |
| GET | `/api/v1/warehouses/storage-duration` | distribution des durées de stockage |
| GET | `/api/v1/warehouses/transactions` | mouvements paginés |

## Alertes

| Méthode | Route | Description |
|---|---|---|
| GET | `/api/v1/alerts` | liste filtrable (`?status=`, `?severity=`, `?alert_type=`) |
| GET | `/api/v1/alerts/counts` | compteurs ouverts par sévérité/catégorie |
| PATCH | `/api/v1/alerts/<id>` | `{"status": "ACKNOWLEDGED" \| "RESOLVED" \| "OPEN"}` |

Transitions autorisées : `OPEN → ACKNOWLEDGED → RESOLVED` (retour OPEN possible
depuis ACKNOWLEDGED). Transition interdite → `409`.

## Insights

| Méthode | Route | Description |
|---|---|---|
| GET | `/api/v1/insights` | insights déterministes (métrique, valeur, seuil, action) |

## Rapports

| Méthode | Route | Description |
|---|---|---|
| POST | `/api/v1/reports/generate` | aperçu structuré (`report_type`, `start_date`, `end_date`) |
| POST | `/api/v1/reports/export` | binaire `format: csv \| xlsx \| pdf` |

Types : `executive`, `shipments`, `customs`, `transport`, `warehouse`.

## Divers

| Méthode | Route | Description |
|---|---|---|
| GET | `/api/v1/meta/filters` | options des filtres (origines, clients, statuts…) |
| GET | `/api/v1/map/routes` | corridors agrégés pour la carte Leaflet |
| GET | `/api/v1/data-quality` | contrôles de qualité de données |
| GET | `/health` | sonde de santé `{"status": "ok"}` |
