# Définitions des KPI

Tous les indicateurs sont calculés de manière déterministe et documentés ici.
Ils sont implémentés dans `app/analytics/kpis.py`, `app/analytics/dashboard.py`
et les modules du même dossier.

## Expéditions

### TOTAL SHIPMENTS — Total des expéditions
`COUNT(shipment_id)` sur la période sélectionnée (par défaut : historique complet).
Les expéditions dont le départ est prévu dans le futur (statut BOOKED) sont incluses
dans l'inventaire mais exclues des KPI de délai.

### ACTIVE SHIPMENTS — Expéditions en cours
Expéditions dont le statut n'est ni `DELIVERED` ni `CANCELLED`.

### ON-TIME DELIVERY RATE (OTD) — Taux de livraison à temps
```
expéditions livrées avec actual_arrival <= planned_arrival
─────────────────────────────────────────────────────────── × 100
             total des expéditions livrées
```
« Livrées » = statut `DELIVERED` ou `DELAYED` (arrivée constatée).

### AVERAGE DELIVERY TIME — Délai de livraison moyen
```
moyenne (actual_arrival − actual_departure)
```
pour les expéditions livrées. Affiché en jours.

### AVERAGE TRANSIT DELAY — Retard moyen
```
moyenne (actual_arrival − planned_arrival)
```
pour les expéditions complétées. Peut être négatif (avance).

## Douane

### CUSTOMS CLEARANCE TIME — Délai de dédouanement
```
clearance_date − declaration_date
```
Exprimé en heures.

### CUSTOMS SLA BREACH RATE — Taux de dépassement SLA
```
déclarations avec clearance_duration_hours > sla_hours
───────────────────────────────────────────────────── × 100
             déclarations dédouanées
```
Statut SLA par déclaration :
| Ratio durée/SLA | Statut |
|---|---|
| ≤ 0.85 | ON_TIME |
| 0.85 – 1.0 | AT_RISK |
| > 1.0 | BREACHED |

## Entrepôts

### WAREHOUSE UTILIZATION — Taux d'occupation
```
occupied_units / capacity_units × 100
```

### Niveau de risque entrepôt
| Occupation | Risque |
|---|---|
| < 70 % | LOW |
| 70 – 85 % | NORMAL |
| 85 – 95 % | AT_RISK |
| > 95 % | CRITICAL |

## Transport

### FUEL EFFICIENCY — Rendement carburant
```
distance_km / fuel_liters   (km/L)
```

### AVERAGE SPEED — Vitesse moyenne
```
distance_km / actual_duration_hours   (km/h)
```

### PONCTUALITÉ — Tournée à l'heure
Une tournée est à l'heure quand `actual_arrival <= planned_arrival`.

## Coût

### AVERAGE COST PER SHIPMENT — Coût moyen par expédition
Modèle dérivé transparent (données synthétiques) :
```
coût = transport terrestre      (distance × tarif au km, 280–420 XAF/km)
     + fret maritime            (800 000 – 2 400 000 XAF si import)
     + droits de douane         (valeur déclarée × taux selon pays d'origine)
     + coûts de stockage        (somme des mouvements d'entrepôt)
```

## Score de risque expédition (0–100)

Implémenté dans `app/analytics/risk.py` :

| Composante | Poids | Normalisation |
|---|---|---|
| Retard | 40 % | retard vs min(50 % du transit, 48 h) |
| Douane | 25 % | durée de dédouanement / SLA |
| Corridor | 20 % | historique de retard du corridor (0–1) |
| Opérationnel | 15 % | cause entrepôt (0.8), documentation/autres (0.5) |

| Score | Niveau |
|---|---|
| 0 – 24 | LOW |
| 25 – 49 | MEDIUM |
| 50 – 74 | HIGH |
| 75 – 100 | CRITICAL |

## Moteur d'insights (déterministe)

Règles principales (`app/analytics/insights.py`) :

| Condition | Insight |
|---|---|
| OTD < 80 % | Priorité haute — performance critique |
| OTD < 90 % | Avertissement — sous la cible |
| Baisse OTD > 2 pts vs période précédente | Dégradation |
| Taux de dépassement SLA douane > 10 % | La douane contribue fortement aux retards |
| Occupation entrepôt > 90 % | Capacité critique |
| Corridor avec OTD < 85 % (≥ 30 expéditions / 60 j) | Corridor sous-performant |
| Véhicule < 80 % du rendement moyen flotte | Surconsommation |
