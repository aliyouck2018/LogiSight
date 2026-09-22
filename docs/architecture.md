# Architecture

## Vue d'ensemble

```
┌──────────────────────────────────────────────────────────────┐
│                        Navigateur                            │
│   HTML (Jinja2) + CSS (design tokens) + Vanilla JS           │
│   Plotly.js (charts) · Leaflet.js (carte)                    │
└──────────────────────────┬───────────────────────────────────┘
                           │ JSON  /api/v1/*
┌──────────────────────────▼───────────────────────────────────┐
│                      Flask (run.py)                          │
│  ┌────────────┐  ┌─────────────────────────────────────┐     │
│  │ routes/    │  │  analytics/  (logique métier pure)  │     │
│  │  main.py   │  │   dashboard · customs · transport   │     │
│  │  api_*.py  │──▶   warehouses · risk · insights      │     │
│  │            │  │   alerts · stats · kpis             │     │
│  └────────────┘  └─────────────────────────────────────┘     │
│  ┌────────────┐  ┌─────────────────────────────────────┐     │
│  │ services/  │  │  models/ (SQLAlchemy + Alembic)     │     │
│  │ reports.py │  │   SQLite (data/logisight.db)        │     │
│  └────────────┘  └─────────────────────────────────────┘     │
└──────────────────────────────────────────────────────────────┘
```

## Principes

1. **Séparation des responsabilités** — les routes HTTP ne contiennent aucune
   logique métier ; les calculs vivent dans `app/analytics/` sous forme de
   fonctions (pures quand possible) testables indépendamment.
2. **Agrégation en SQL** — les tableaux de bord n'exposent jamais le dataset
   complet ; les moyennes, sommes et comptages sont calculés par SQLite via
   SQLAlchemy Core/ORM (`func.avg`, `func.count`, `case`).
3. **Aucune donnée en dur** — chaque KPI, graphique, tableau, alerte et insight
   provient de la base via l'API.
4. **Génération reproductible** — le générateur (`scripts/generate_data.py`)
   est déterministe (`SEED`) et introduit des scénarios métier volontaires.

## Modèle de données

| Table | Rôle | Relations |
|---|---|---|
| `customers` | Clients (CORPORATE, SME, GOVERNMENT, INTERNATIONAL) | 1-N `shipments` |
| `shipments` | Entité centrale : dates planifiées/réelles, statut, coût, retard, risque | FK `customers` |
| `customs_declarations` | Déclarations douanières, SLA, droits | 1-1 `shipments` (par `shipment_id`) |
| `vehicles` | Flotte (type, transporteur, capacité) | 1-N `trips` |
| `trips` | Tournées terrestres (planifié vs réel, carburant) | FK `shipments`, `vehicles` |
| `warehouses` | Sites d'entreposage (capacité, occupation) | 1-N `warehouse_transactions` |
| `warehouse_transactions` | Mouvements IN/OUT/ADJUSTMENT, coûts de stockage | FK `warehouses`, `shipments` |
| `routes` | Corridors (distance, durée attendue, type) | référentiel |
| `alerts` | Alertes opérationnelles générées par règles | référence d'entité |

### Index principaux
`shipments`: `shipment_id`, `customer_id`, `status`, `planned_departure`,
`planned_arrival`, `actual_arrival`, `origin`, `destination`, `(origin, destination)` ;
`customs_declarations`: `shipment_id`, `declaration_date`, `(status, date)` ;
`trips`: `vehicle_id`, `shipment_id`, `(vehicle_id, departure_time)`.

## Cycles de génération

```
python scripts/generate_data.py     # données synthétiques (seed=42)
python scripts/generate_alerts.py   # alertes par règles sur les données fraîches
```

Scénarios métier injectés (visibles dans les analytics) :
- **A** — ralentissement douanier (mois -9 à -7)
- **B** — corridor Douala → Bertoua dégradé (4 derniers mois, volume renforcé)
- **C** — entrepôt W-03 en approche de capacité (~92 %)
- **D** — 4 véhicules en surconsommation
- **E** — 2 clients à retard récurrents
- **F** — perturbation opérationnelle créant un backlog

## Frontend

- `static/css/tokens.css` — design tokens centralisés (couleurs, espacements,
  typographie, ombres, breakpoints).
- `static/css/base.css` — shell applicatif + composants réutilisables
  (cards KPI, badges, tables, pagination, états loading/empty/error, timeline).
- `static/js/app.js` — client API, formateurs fr-FR, mappings statuts/sévérité,
  composants partagés (KPI, table, pagination, filtres globaux).
- `static/js/<page>.js` — orchestration par page (dashboard, shipments, …).

## Sécurité

- Requêtes SQLAlchemy paramétrées (aucune concaténation SQL).
- Validation des entrées de pagination/filtres côté serveur.
- Gestion centralisée des erreurs 400/404/405/409/422/500 avec réponses JSON homogènes.
- Secrets via variables d'environnement (`.env`, non committé).
