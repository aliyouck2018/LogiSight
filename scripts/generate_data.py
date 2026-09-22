"""LogiSight synthetic data generator.

Reproducible (SEED env var, default 42). Generates:
    customers, routes, vehicles, warehouses, shipments,
    customs_declarations, trips, warehouse_transactions

Business correlations baked in:
    - longer distance -> longer transit time
    - congested routes -> higher delay probability
    - certain cargo types -> longer customs clearance
    - high-value cargo -> longer customs processing
    - warehouses occupancy evolves over time
    - some vehicles are consistently less efficient
    - some customers have more delay incidents
    - weekends/holidays influence operations
    - random operational incidents create outliers

Intentional scenarios (visible through analytics):
    A: customs slowdown during months [7, 9] before end
    B: Douala -> Bertoua becomes a high-delay corridor (last 4 months)
    C: warehouse W-03 approaches capacity (last 3 months)
    D: a subset of vehicles consumes significantly more fuel
    E: two customers experience unusually high delivery delays
    F: a 3-week operational disruption creates a shipment backlog
"""
from __future__ import annotations

import os
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
from faker import Faker

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app, db
from app.analytics.risk import compute_risk_score, risk_level
from app.models import (Alert, CustomsDeclaration, Customer, Route, Shipment,
                        Trip, Vehicle, Warehouse, WarehouseTransaction)
from scripts.reference_data import (CARGO_TYPES, CARGO_WEIGHTS,
                                    CONTAINER_TYPES, COUNTRIES_DUTY,
                                    CUSTOMER_TYPES, CUSTOMER_TYPE_WEIGHTS,
                                    CUSTOMS_SLA_BY_CARGO, DELAY_CAUSES,
                                    DELAY_CAUSE_WEIGHTS,
                                    DOMESTIC_DISTANCES,
                                    INTERNATIONAL_CORRIDORS, INDUSTRIES,
                                    TRANSPORTERS, VEHICLE_TYPES, FUEL_TYPES,
                                    WAREHOUSE_TYPES, CAMEROON_CITIES,
                                    INTERNATIONAL_CITIES, CITIES)

fake = Faker("fr_FR")

# ---------------------------------------------------------------------------
# Scenarios parameters (months are counted backwards from END)
SCENARIO_CUSTOMS_SLOWDOWN_MONTHS = (7, 9)      # customs +80% clearance
SCENARIO_CORRIDOR_MONTHS_BACK = 4              # Douala->Bertoua degradation
SCENARIO_BACKLOG_START = 5.5                   # months back
SCENARIO_BACKLOG_WEEKS = 3
HIGH_RISK_CUSTOMER_COUNT = 2
BAD_VEHICLE_COUNT = 4

HOUR = timedelta(hours=1)
DAY = timedelta(days=1)


class Generator:
    def __init__(self, n_shipments: int, months: int, seed: int):
        self.seed = seed
        self.rng = random.Random(seed)
        self.np_rng = np.random.default_rng(seed)
        Faker.seed(seed)
        fake.seed_instance(seed)

        self.n_shipments = n_shipments
        self.months = months
        self.end = datetime.now().replace(hour=12, minute=0, second=0, microsecond=0)
        self.start = self.end - timedelta(days=int(months * 30.44))

        # Scenario windows
        self.customs_slowdown = (
            self.end - timedelta(days=int(SCENARIO_CUSTOMS_SLOWDOWN_MONTHS[1] * 30.44)),
            self.end - timedelta(days=int(SCENARIO_CUSTOMS_SLOWDOWN_MONTHS[0] * 30.44)),
        )
        self.corridor_start = self.end - timedelta(days=int(SCENARIO_CORRIDOR_MONTHS_BACK * 30.44))
        self.backlog = (
            self.end - timedelta(days=int(SCENARIO_BACKLOG_START * 30.44)),
            self.end - timedelta(days=int(SCENARIO_BACKLOG_START * 30.44)) + timedelta(weeks=SCENARIO_BACKLOG_WEEKS),
        )

    # -- helpers ------------------------------------------------------------
    def rand_dt_in_month(self, month_start: datetime, month_end: datetime) -> datetime:
        """Random datetime inside month; weekends less likely (weekend effect)."""
        span = (month_end - month_start).days
        for _ in range(10):
            day = self.rng.randint(0, max(span - 1, 0))
            dt = month_start + timedelta(days=day, hours=self.rng.randint(6, 18))
            if dt.weekday() >= 5 and self.rng.random() < 0.6:
                continue  # skip weekends 60% of the time
            return dt
        return month_start + timedelta(days=self.rng.randint(0, max(span - 1, 0)), hours=10)

    def month_volume_weights(self) -> list[float]:
        """Growth ~ +0.8%/month + December seasonality + backlog spike.

        The final (partial) month is scaled by its elapsed share so the
        daily volume rate stays constant up to `end`.
        """
        weights = []
        for m in range(self.months):
            m_start = self.start + timedelta(days=int(m * 30.44))
            m_end = self.start + timedelta(days=int((m + 1) * 30.44))
            w = 1.0 * (1.008 ** m)
            if m_start.month == 12:
                w *= 1.25  # holiday season surge
            mid = m_start + timedelta(days=15)
            if self.backlog[0] <= mid <= self.backlog[1]:
                w *= 1.9  # backlog spike during disruption
            # partial-month scaling
            effective_end = min(m_end, self.end)
            if effective_end <= m_start:
                w = 0.0
            else:
                w *= (effective_end - m_start).total_seconds() / (m_end - m_start).total_seconds()
            weights.append(w)
        return weights

    def in_window(self, dt: datetime, window: tuple[datetime, datetime]) -> bool:
        return window[0] <= dt <= window[1]

    # -- master data ----------------------------------------------------------
    def gen_routes(self) -> list[dict]:
        routes = []
        cities = list(CAMEROON_CITIES)
        for a in cities:
            for b in cities:
                if a == b:
                    continue
                dist = DOMESTIC_DISTANCES.get((a, b)) or DOMESTIC_DISTANCES.get((b, a))
                if dist is None:
                    continue
                hours = round(dist / 45 * 1.35 + 4, 1)  # avg 45 km/h + pauses/buffer
                routes.append({
                    "origin": a, "destination": b, "distance_km": float(dist),
                    "expected_duration_hours": hours, "route_type": "DOMESTIC", "active": True,
                })
        for origin, (dest, sea_days) in INTERNATIONAL_CORRIDORS.items():
            port_hours = 12.0
            routes.append({
                "origin": origin, "destination": dest,
                "distance_km": round(sea_days * 24 * 18.5),  # notional maritime distance
                "expected_duration_hours": sea_days * 24.0,
                "route_type": "INTERNATIONAL", "active": True,
            })
        # a few Kribi-bound corridors
        for origin, sea_days in (("Shanghai", 26), ("Le Havre", 16)):
            routes.append({
                "origin": origin, "destination": "Kribi",
                "distance_km": round(sea_days * 24 * 18.5),
                "expected_duration_hours": sea_days * 24.0,
                "route_type": "INTERNATIONAL", "active": True,
            })
        return routes

    def gen_customers(self, n: int = 100) -> list[dict]:
        countries = ["Cameroun"] * 6 + ["Chine", "France", "Nigéria", "Émirats Arabes Unis", "Belgique"]
        customers = []
        for i in range(1, n + 1):
            ctype = self.rng.choices(CUSTOMER_TYPES, weights=CUSTOMER_TYPE_WEIGHTS)[0]
            country = self.rng.choice(countries) if ctype == "INTERNATIONAL" else "Cameroun"
            customers.append({
                "customer_code": f"CLI-{i:04d}",
                "name": fake.company()[:60],
                "customer_type": ctype,
                "industry": self.rng.choice(INDUSTRIES),
                "city": self.rng.choice(CAMEROON_CITIES) if country == "Cameroun" else self.rng.choice(INTERNATIONAL_CITIES),
                "country": country,
            })
        # Scenario E: designate 2 high-delay customers (indices 11, 67)
        self.high_risk_customers = {customers[11]["customer_code"], customers[67]["customer_code"]}
        return customers

    def gen_vehicles(self, n: int = 20) -> tuple[list[dict], set[str]]:
        vehicles = []
        for i in range(1, n + 1):
            vtype = self.rng.choice(VEHICLE_TYPES)
            vehicles.append({
                "vehicle_id": f"VEH-{i:03d}",
                "registration_number": f"CM-{self.rng.choice(['DL', 'YN', 'BU'])}-{1000 + i * 37}",
                "vehicle_type": vtype,
                "transporter": self.rng.choice(TRANSPORTERS),
                "capacity_kg": float(self.rng.choice([20000, 30000, 40000])),
                "fuel_type": self.rng.choice(FUEL_TYPES),
                "active": self.rng.random() > 0.05,
            })
        # Scenario D: first BAD_VEHICLE_COUNT vehicles are less efficient
        bad_vehicles = {v["vehicle_id"] for v in vehicles[:BAD_VEHICLE_COUNT]}
        return vehicles, bad_vehicles

    def gen_warehouses(self, n: int = 15) -> list[dict]:
        warehouses = []
        for i in range(1, n + 1):
            code = f"W-{i:02d}"
            city = self.rng.choices(["Douala", "Yaoundé", "Kribi", "Bafoussam", "Bamenda", "Bertoua", "Garoua"],
                                    weights=[0.35, 0.25, 0.10, 0.10, 0.08, 0.07, 0.05])[0]
            warehouses.append({
                "warehouse_code": code,
                "name": f"Entrepôt {code} {city}",
                "city": city,
                "capacity_units": float(self.rng.choice([4000, 6000, 8000, 10000])),
                "occupied_units": 0.0,  # recomputed from transactions
                "warehouse_type": self.rng.choice(WAREHOUSE_TYPES),
                "active": True,
            })
        return warehouses

    # -- shipments ------------------------------------------------------------
    def gen_shipments(self, routes: list[dict], customers: list[dict]) -> dict[str, list]:
        domestic = [r for r in routes if r["route_type"] == "DOMESTIC"]
        intl = [r for r in routes if r["route_type"] == "INTERNATIONAL"]
        month_weights = self.month_volume_weights()
        months_idx = list(range(self.months))

        shipments, customs, trips, wtrans = [], [], [], []
        cust_by_code = {c["customer_code"]: c for c in customers}
        cust_ids = [c["customer_code"] for c in customers]

        # Per-customer reliability multiplier (scenario E)
        for code, cust in cust_by_code.items():
            cust["_reliability"] = 3.0 if code in self.high_risk_customers else self.rng.uniform(0.7, 1.3)

        for i in range(1, self.n_shipments + 1):
            month_i = self.rng.choices(months_idx, weights=month_weights)[0]
            m_start = self.start + timedelta(days=int(month_i * 30.44))
            m_end = self.start + timedelta(days=int((month_i + 1) * 30.44))
            planned_departure = self.rand_dt_in_month(m_start, min(m_end, self.end))

            # ~3% of shipments are booked for the near future
            if self.rng.random() < 0.03:
                planned_departure = self.end + timedelta(
                    days=self.rng.randint(1, 12), hours=self.rng.randint(6, 18))

            cust_code = self.rng.choice(cust_ids)
            customer = cust_by_code[cust_code]

            is_international = self.rng.random() < 0.62
            cargo = self.rng.choices(CARGO_TYPES, weights=CARGO_WEIGHTS)[0]
            declared_value = round(float(self.np_rng.lognormal(mean=16.5, sigma=1.1)), 2)  # XAF ~ 15M avg
            weight = round(float(self.np_rng.gamma(shape=4, scale=3500)), 0)
            volume = round(max(weight / 260.0, 2), 1)

            if is_international:
                route = self.rng.choice(intl)
                origin = route["origin"]
                entry_port = route["destination"]
                if entry_port == "Douala" and self.rng.random() < 0.15:
                    entry_port = "Kribi"
                destination = entry_port if self.rng.random() < 0.2 else self.rng.choice(
                    [c for c in CAMEROON_CITIES if c != entry_port])
                sea_days = INTERNATIONAL_CORRIDORS.get(origin, ("Douala", 22))[1]
            else:
                route = self.rng.choice(domestic)
                # Scenario B: Douala -> Bertoua carries a much larger share recently
                if (planned_departure >= self.corridor_start
                        and self.rng.random() < 0.15):
                    route = next(r for r in domestic
                                 if r["origin"] == "Douala" and r["destination"] == "Bertoua")
                origin, destination = route["origin"], route["destination"]
                entry_port = None
                sea_days = 0

            cancelled = self.rng.random() < 0.02 and planned_departure < self.end - timedelta(days=30)

            # ---- delays ----
            reliability = customer["_reliability"]
            dep_delay_h = 0.0
            if self.rng.random() < 0.18 * min(reliability, 1.4):
                dep_delay_h = self.rng.uniform(2, 8)
            if self.in_window(planned_departure, self.backlog):
                dep_delay_h += self.rng.uniform(12, 72)  # backlog: departures pile up
            actual_departure = planned_departure + timedelta(hours=dep_delay_h) if not cancelled else None

            # ---- customs ----
            ports = ("Douala", "Kribi")
            requires_customs = is_international or origin in ports or destination in ports
            sla_hours = CUSTOMS_SLA_BY_CARGO[cargo]
            declaration_date = clearance_date = None
            clearance_hours = None
            customs_congestion = 1.0
            if requires_customs and not cancelled and actual_departure is not None:
                port_arrival = actual_departure + timedelta(days=sea_days) if is_international else \
                    actual_departure + timedelta(hours=self.rng.uniform(4, 20))
                declaration_date = port_arrival
                base_clear = self.rng.uniform(38, 64)
                if cargo in ("CHIMIQUE", "AGROALIMENTAIRE", "VIVRES"):
                    base_clear *= self.rng.uniform(1.3, 1.6)  # inspections
                if declared_value > 60_000_000:
                    base_clear *= 1.3  # high-value processing
                if declaration_date.weekday() >= 5:
                    base_clear *= 1.2  # weekend effect
                if self.in_window(declaration_date, self.customs_slowdown):
                    base_clear *= 1.35  # Scenario A: customs slowdown
                clearance_hours = round(base_clear * self.rng.uniform(0.85, 1.15), 1)

            # ---- land transport ----
            land_route = None
            if is_international and destination != entry_port:
                for r in domestic:
                    if r["origin"] == entry_port and r["destination"] == destination:
                        land_route = r
                        break
            elif not is_international:
                land_route = route

            if land_route:
                planned_trip_hours = land_route["expected_duration_hours"]
            elif is_international:
                planned_trip_hours = 6.0
            else:
                planned_trip_hours = 8.0

            # typical customs estimate used for ETA planning (SLA is only for breach analysis)
            CUSTOMS_ETA = {"CONTENEURISE": 51, "VIVRES": 74, "MATERIAUX": 51,
                           "CHIMIQUE": 74, "ELECTRONIQUE": 51, "TEXTILE": 51,
                           "AGROALIMENTAIRE": 74}
            customs_est = CUSTOMS_ETA[cargo]

            # planned arrival = departure + sea + typical clearance + trip + buffer (10% + 6h)
            planned_total = planned_trip_hours + (customs_est if requires_customs else 0) + sea_days * 24
            planned_buffer = max(16.0, min(planned_total * 0.08 + 6.0, 28.0))
            planned_arrival = planned_departure + timedelta(hours=planned_total + planned_buffer)

            # ---- compute actuals ----
            now = self.end
            if cancelled:
                actual_arrival = None
                delay_hours = None
                transit_hours = None
                status = "CANCELLED"
                delay_cause = None
            else:
                # actual duration = planned trip + deviation between actual clearance and ETA
                clearance_gap = (clearance_hours - customs_est) if (requires_customs and clearance_hours is not None) else 0.0
                actual_arrival = actual_departure + timedelta(hours=planned_total + clearance_gap)
                extra_delay = 0.0
                delay_cause = None

                route_delay_prob = 0.10
                if (origin, destination) == ("Douala", "Bertoua") and planned_departure >= self.corridor_start:
                    route_delay_prob = 0.55  # Scenario B
                if planned_departure >= self.end - timedelta(weeks=8):
                    route_delay_prob *= 1.7  # recent rainy-season congestion
                if planned_departure.weekday() >= 5:
                    route_delay_prob *= 1.1

                cause_roll = self.rng.random()
                if cause_roll < route_delay_prob * min(reliability, 1.4):
                    if self.rng.random() < 0.9:
                        delay_cause = self.rng.choices(DELAY_CAUSES, weights=DELAY_CAUSE_WEIGHTS)[0]
                        if delay_cause == "DOUANE" and not requires_customs:
                            delay_cause = "TRANSPORT"
                    if delay_cause == "ENTREPOT":
                        extra_delay = self.rng.uniform(12, 48)
                    else:
                        extra_delay = self.rng.uniform(12, 48)
                # random operational incidents -> outliers
                if self.rng.random() < 0.012:
                    extra_delay += self.rng.uniform(48, 120)
                    delay_cause = self.rng.choice(["TRANSPORT", "AUTRES"])

                # actual_arrival already includes departure delay via actual_departure
                actual_arrival += timedelta(hours=extra_delay)
                delay_hours = (actual_arrival - planned_arrival).total_seconds() / 3600
                transit_hours = (actual_arrival - actual_departure).total_seconds() / 3600

                # ---- status ----
                if actual_arrival <= now:
                    status = "DELAYED" if delay_hours > 12 else "DELIVERED"
                else:
                    elapsed = (now - actual_departure).total_seconds() / 3600
                    if elapsed < 0:
                        status = "BOOKED"
                    elif requires_customs and declaration_date and declaration_date > now:
                        status = "IN_TRANSIT"
                    elif requires_customs and clearance_date is None:
                        status = "AT_CUSTOMS"
                    elif requires_customs and declaration_date and \
                            now < declaration_date + timedelta(hours=clearance_hours or 0):
                        status = "AT_CUSTOMS"
                    elif requires_customs:
                        if now < actual_arrival - timedelta(hours=planned_trip_hours * 0.5):
                            status = "CUSTOMS_CLEARED"
                        else:
                            status = "OUT_FOR_DELIVERY"
                        if delay_hours > 12:
                            status = "DELAYED"
                    else:
                        if now < actual_arrival - timedelta(hours=planned_trip_hours * 0.5):
                            status = "IN_TRANSIT"
                        else:
                            status = "OUT_FOR_DELIVERY"
                        if delay_hours > 12:
                            status = "DELAYED"

                # shipments not yet arrived: arrival is unknown
                if actual_arrival > now:
                    transit_hours = None
                    if status != "DELAYED":
                        delay_hours = None
                    actual_arrival = None

            shipment = {
                "shipment_id": f"SHP-{i:06d}",
                "customer_code": cust_code,
                "origin": origin,
                "destination": destination,
                "country_of_origin": CITIES[origin][2],
                "country_of_destination": CITIES[destination][2],
                "cargo_type": cargo,
                "container_type": self.rng.choice(CONTAINER_TYPES),
                "declared_value": declared_value,
                "weight_kg": weight,
                "volume_m3": volume,
                "planned_departure": planned_departure,
                "actual_departure": actual_departure,
                "planned_arrival": planned_arrival,
                "actual_arrival": actual_arrival,
                "status": status,
                "delay_hours": round(delay_hours, 1) if delay_hours is not None else None,
                "transit_hours": round(transit_hours, 1) if transit_hours is not None else None,
                "delay_cause": delay_cause,
                "cost": None,
                "_requires_customs": requires_customs,
                "_sla_hours": sla_hours,
                "_clearance_hours": clearance_hours,
                "_declaration_date": declaration_date,
                "_clearance_date": None,
                "_land_route": land_route,
                "_entry_port": entry_port,
                "_is_international": is_international,
            }

            if requires_customs and not cancelled and declaration_date is not None:
                c_status = "PENDING"
                c_clearance_date = None
                if clearance_hours is not None:
                    c_clearance_date = declaration_date + timedelta(hours=clearance_hours)
                    if c_clearance_date <= now:
                        c_status = "CLEARED"
                        shipment["_clearance_date"] = c_clearance_date
                elif c_clearance_date is None and declaration_date < now:
                    c_status = "PENDING"
                customs.append({
                    "shipment": shipment,
                    "declaration_date": declaration_date,
                    "clearance_date": c_clearance_date,
                    "customs_status": c_status,
                    "clearance_duration_hours": clearance_hours,
                    "sla_hours": sla_hours,
                })

            shipments.append(shipment)

            # ---- trips (land leg) ----
            if not cancelled and status != "BOOKED" and actual_departure is not None:
                self._gen_trip(shipment, trips, vehicles_hint=None, i=i)

        return {"shipments": shipments, "customs": customs, "trips": trips,
                "wtrans": wtrans, "customers": customers}

    def _gen_trip(self, shipment: dict, trips: list, vehicles_hint, i: int):
        land = shipment["_land_route"]
        if land:
            origin, dest = land["origin"], land["destination"]
            distance, planned_h = land["distance_km"], land["expected_duration_hours"]
        elif shipment["_is_international"]:
            origin, dest = shipment["_entry_port"], shipment["destination"]
            distance, planned_h = self.rng.uniform(10, 35), 6.0
        else:
            return

        vehicle = self.rng.choice(self.vehicles) if vehicles_hint is None else vehicles_hint
        bad = vehicle["vehicle_id"] in self.bad_vehicles  # Scenario D

        dep = shipment["actual_departure"]
        if shipment["_requires_customs"]:
            # trip starts after customs clearance
            base = shipment["_declaration_date"] or dep
            if shipment["_clearance_hours"]:
                base = base + timedelta(hours=shipment["_clearance_hours"])
            dep = max(dep, base)

        speed = self.rng.uniform(38, 48) * (0.82 if bad else 1.0)
        actual_h = distance / max(speed, 10) + self.rng.uniform(2, 8)
        if shipment["delay_cause"] == "TRANSPORT":
            actual_h += self.rng.uniform(4, 20)
        actual_h = round(actual_h, 1)

        fuel_eff = self.rng.uniform(3.2, 4.6) * (0.72 if bad else 1.0)  # km/L
        fuel = round(distance / fuel_eff, 1) if distance > 50 else round(self.rng.uniform(15, 40), 1)

        planned_arrival = dep + timedelta(hours=planned_h)
        actual_arrival = dep + timedelta(hours=actual_h)

        if actual_arrival <= self.end:
            trip_status = "COMPLETED"
        elif dep > self.end:
            trip_status = "PLANNED"
        else:
            trip_status = "IN_PROGRESS"

        if trip_status != "COMPLETED":
            actual_arrival = None

        trips.append({
            "trip_id": f"TRP-{len(trips) + 1:06d}",
            "shipment_id": shipment["shipment_id"],
            "vehicle_id": vehicle["vehicle_id"],
            "driver_name": fake.name()[:60],
            "origin": origin,
            "destination": dest,
            "departure_time": dep,
            "planned_arrival": planned_arrival,
            "actual_arrival": actual_arrival,
            "planned_duration_hours": planned_h,
            "actual_duration_hours": actual_h if trip_status == "COMPLETED" else None,
            "distance_km": round(distance, 1),
            "fuel_liters": fuel if trip_status == "COMPLETED" else None,
            "trip_status": trip_status,
        })

    # -- warehouse transactions ----------------------------------------------
    def gen_warehouse_transactions(self, shipments: list[dict], warehouses: list[dict]) -> list[dict]:
        wh_by_city = {}
        for w in warehouses:
            wh_by_city.setdefault(w["city"], []).append(w)

        trans = []
        occupancy = {w["warehouse_code"]: 0.0 for w in warehouses}
        occupancy_history = {w["warehouse_code"]: [] for w in warehouses}

        for s in shipments:
            if s["status"] in ("BOOKED", "CANCELLED") or s["actual_arrival"] is None:
                continue
            city = s["destination"]
            candidates = wh_by_city.get(city)
            if not candidates:
                continue
            wh = self.rng.choice(candidates)
            qty = max(round(s["volume_m3"] * 1.5), 5)

            in_date = s["actual_arrival"]
            if in_date > self.end:
                continue
            storage_days = self.rng.uniform(8, 30)
            # Scenario C: W-03 congestion in last 3 months -> much longer storage
            if wh["warehouse_code"] == "W-03":
                if in_date >= self.end - timedelta(days=90):
                    storage_days = self.rng.uniform(30, 55)
                else:
                    storage_days = self.rng.uniform(10, 30)
            storage_days = round(storage_days, 1)
            out_date = in_date + timedelta(days=storage_days)
            rate = self.rng.uniform(1500, 4000)  # XAF / unit / day
            cost = round(qty * storage_days * rate, 2)

            trans.append({
                "warehouse_code": wh["warehouse_code"],
                "shipment_id": s["shipment_id"],
                "transaction_type": "IN",
                "quantity": qty,
                "transaction_date": in_date,
                "storage_duration_days": None,
                "storage_cost": None,
            })
            occupancy[wh["warehouse_code"]] += qty
            for w in warehouses:
                occupancy_history[w["warehouse_code"]].append(
                    (in_date, occupancy[w["warehouse_code"]]))

            if out_date <= self.end:
                trans.append({
                    "warehouse_code": wh["warehouse_code"],
                    "shipment_id": s["shipment_id"],
                    "transaction_type": "OUT",
                    "quantity": qty,
                    "transaction_date": out_date,
                    "storage_duration_days": storage_days,
                    "storage_cost": cost,
                })
                occupancy[wh["warehouse_code"]] -= qty
            else:
                # still in storage
                trans[-1]["storage_duration_days"] = None

        # final occupancy per warehouse (Scenario C: W-03 forced high)
        for w in warehouses:
            code = w["warehouse_code"]
            final = max(occupancy[code], 0.0)
            if code == "W-03":
                # Scenario C: keep W-03 at ~92.5% (AT_RISK band)
                final = 0.925 * w["capacity_units"]
            w["occupied_units"] = round(min(final, w["capacity_units"] * 0.995), 1)

        return trans

    # -- main entry -------------------------------------------------------------
    def run(self) -> dict:
        routes = self.gen_routes()
        customers = self.gen_customers()
        self.vehicles, self.bad_vehicles = self.gen_vehicles()
        warehouses = self.gen_warehouses()

        result = self.gen_shipments(routes, customers)
        shipments = result["shipments"]

        # customs SLA status + clearance dates
        now = self.end
        for c in result["customs"]:
            s = c["shipment"]
            if c["clearance_duration_hours"] is not None and c["declaration_date"] is not None:
                c["clearance_date"] = c["declaration_date"] + timedelta(hours=c["clearance_duration_hours"])
                c["customs_status"] = "CLEARED" if c["clearance_date"] <= now else "PENDING"
            if c["customs_status"] == "PENDING":
                c["sla_status"] = "AT_RISK" if c["declaration_date"] + timedelta(hours=c["sla_hours"]) < now else "ON_TIME"
            else:
                ratio = c["clearance_duration_hours"] / c["sla_hours"]
                c["sla_status"] = "BREACHED" if ratio > 1 else ("AT_RISK" if ratio > 0.85 else "ON_TIME")
            s["_clearance_date"] = c["clearance_date"]

        # warehouse transactions + occupancy
        wtrans = self.gen_warehouse_transactions(shipments, warehouses)

        # costs (transparent model): transport + maritime + duties + storage
        duties_map = {}
        for c in result["customs"]:
            s = c["shipment"]
            country = s["country_of_origin"]
            lo, hi = COUNTRIES_DUTY.get(country, (0.08, 0.18))
            duty = s["declared_value"] * self.rng.uniform(lo, hi)
            duties_map[s["shipment_id"]] = round(duty, 2)

        for s in shipments:
            if s["status"] == "CANCELLED":
                s["cost"] = 0.0
                continue
            land = s["_land_route"]
            land_cost = (land["distance_km"] * self.rng.uniform(280, 420)) if land else 50000
            sea_cost = self.rng.uniform(800_000, 2_400_000) if s["_is_international"] else 0
            duty = duties_map.get(s["shipment_id"], 0)
            wh_cost = sum(t["storage_cost"] or 0 for t in wtrans
                          if t["shipment_id"] == s["shipment_id"])
            s["cost"] = round(land_cost + sea_cost + duty + wh_cost, 2)

        # risk scores (import analytics — deterministic)
        route_badness = self._route_badness(shipments)
        for s in shipments:
            score = compute_risk_score(
                delay_hours=s["delay_hours"],
                transit_hours=s["transit_hours"],
                sla_hours=s["_sla_hours"] if s["_requires_customs"] else None,
                clearance_hours=s["_clearance_hours"],
                route_badness=route_badness.get((s["origin"], s["destination"]), 0.0),
                delay_cause=s["delay_cause"],
            )
            s["risk_score"] = score
            s["risk_level"] = risk_level(score)

        return {
            "routes": routes,
            "customers": customers,
            "vehicles": self.vehicles,
            "warehouses": warehouses,
            "shipments": shipments,
            "customs": result["customs"],
            "trips": result["trips"],
            "wtrans": wtrans,
        }

    def _route_badness(self, shipments: list[dict]) -> dict:
        """Normalized historical delay rate per route (0..1)."""
        from collections import defaultdict
        stats = defaultdict(lambda: [0, 0])
        for s in shipments:
            if s["delay_hours"] is None:
                continue
            key = (s["origin"], s["destination"])
            stats[key][0] += 1
            if s["delay_hours"] > 12:
                stats[key][1] += 1
        rates = {k: v[1] / v[0] for k, v in stats.items() if v[0] >= 20}
        if not rates:
            return {}
        lo, hi = min(rates.values()), max(rates.values())
        span = (hi - lo) or 1.0
        return {k: (v - lo) / span for k, v in rates.items()}


def insert_data(app, data: dict):
    """Bulk insert generated data into SQLite."""
    with app.app_context():
        # wipe in FK order
        for model in (WarehouseTransaction, CustomsDeclaration, Trip, Alert,
                      Shipment, Customer, Vehicle, Warehouse, Route):
            model.__table__.drop(db.engine, checkfirst=True)
            model.__table__.create(db.engine)

        db.session.execute(Route.__table__.insert(), data["routes"])
        db.session.execute(Customer.__table__.insert(), data["customers"])
        db.session.execute(Vehicle.__table__.insert(), data["vehicles"])
        db.session.execute(Warehouse.__table__.insert(), data["warehouses"])

        # map codes -> surrogate ids
        cust_rows = db.session.execute(db.select(Customer.id, Customer.customer_code)).all()
        cust_map = {code: cid for cid, code in cust_rows}
        veh_rows = db.session.execute(db.select(Vehicle.id, Vehicle.vehicle_id)).all()
        veh_map = {vid: vid for vid, _ in veh_rows}
        wh_rows = db.session.execute(db.select(Warehouse.id, Warehouse.warehouse_code)).all()
        wh_map = {code: wid for wid, code in wh_rows}

        shipment_rows = []
        for s in data["shipments"]:
            shipment_rows.append({
                "shipment_id": s["shipment_id"],
                "customer_id": cust_map[s["customer_code"]],
                "origin": s["origin"],
                "destination": s["destination"],
                "country_of_origin": s["country_of_origin"],
                "country_of_destination": s["country_of_destination"],
                "cargo_type": s["cargo_type"],
                "container_type": s["container_type"],
                "declared_value": s["declared_value"],
                "weight_kg": s["weight_kg"],
                "volume_m3": s["volume_m3"],
                "planned_departure": s["planned_departure"],
                "actual_departure": s["actual_departure"],
                "planned_arrival": s["planned_arrival"],
                "actual_arrival": s["actual_arrival"],
                "status": s["status"],
                "cost": s["cost"],
                "delay_hours": s["delay_hours"],
                "transit_hours": s["transit_hours"],
                "risk_score": s["risk_score"],
                "risk_level": s["risk_level"],
                "delay_cause": s["delay_cause"],
            })
        _bulk_insert(Shipment, shipment_rows)

        customs_rows = []
        for c in data["customs"]:
            s = c["shipment"]
            value = s["declared_value"]
            country = s["country_of_origin"]
            customs_rows.append({
                "declaration_id": f"CUS-{len(customs_rows) + 1:06d}",
                "shipment_id": s["shipment_id"],
                "declaration_date": c["declaration_date"],
                "clearance_date": c["clearance_date"],
                "customs_status": c["customs_status"],
                "declared_value": value,
                "duties_amount": round(value * 0.2, 2),
                "clearance_duration_hours": c["clearance_duration_hours"],
                "sla_hours": c["sla_hours"],
                "sla_status": c["sla_status"],
            })
        _bulk_insert(CustomsDeclaration, customs_rows)

        trip_rows = []
        for t in data["trips"]:
            t = dict(t)
            t.pop("vehicle_pk", None)
            trip_rows.append(t)
        _bulk_insert(Trip, trip_rows)

        wtrans_rows = []
        for t in data["wtrans"]:
            wtrans_rows.append({
                "warehouse_id": wh_map[t["warehouse_code"]],
                "shipment_id": t["shipment_id"],
                "transaction_type": t["transaction_type"],
                "quantity": t["quantity"],
                "transaction_date": t["transaction_date"],
                "storage_duration_days": t["storage_duration_days"],
                "storage_cost": t["storage_cost"],
            })
        _bulk_insert(WarehouseTransaction, wtrans_rows)

        db.session.commit()
        return {
            "customers": len(data["customers"]),
            "routes": len(data["routes"]),
            "vehicles": len(data["vehicles"]),
            "warehouses": len(data["warehouses"]),
            "shipments": len(shipment_rows),
            "customs": len(customs_rows),
            "trips": len(trip_rows),
            "wtrans": len(wtrans_rows),
        }


def _bulk_insert(model, rows, batch=2000):
    for i in range(0, len(rows), batch):
        db.session.execute(model.__table__.insert(), rows[i:i + batch])


def main():
    seed = int(os.environ.get("SEED", 42))
    n = int(os.environ.get("N_SHIPMENTS", 20000))
    months = int(os.environ.get("N_MONTHS", 24))

    print(f"Generating synthetic data (seed={seed}, shipments={n}, months={months})…")
    app = create_app()
    gen = Generator(n_shipments=n, months=months, seed=seed)
    data = gen.run()

    counts = insert_data(app, data)
    print("Done.")
    for k, v in counts.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
