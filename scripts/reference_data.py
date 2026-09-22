"""Reference data for the synthetic generator: cities, coordinates, business constants.

All data is synthetic and inspired by (but not representative of) the
Cameroon / CEMAC region.
"""

# name -> (lat, lon, country)
CITIES = {
    # Cameroon
    "Douala": (4.0483, 9.7043, "Cameroun"),
    "Yaoundé": (3.8480, 11.5021, "Cameroun"),
    "Kribi": (2.9400, 9.9100, "Cameroun"),
    "Bafoussam": (5.4781, 10.4176, "Cameroun"),
    "Bamenda": (5.9597, 10.1459, "Cameroun"),
    "Bertoua": (4.5772, 13.6846, "Cameroun"),
    "Garoua": (9.3016, 13.3921, "Cameroun"),
    "Ngaoundéré": (7.3167, 13.5833, "Cameroun"),
    # International origins
    "Shanghai": (31.2304, 121.4737, "Chine"),
    "Dubaï": (25.2048, 55.2708, "Émirats Arabes Unis"),
    "Lagos": (6.5244, 3.3792, "Nigéria"),
    "Abidjan": (5.3599, -4.0083, "Côte d'Ivoire"),
    "Le Havre": (49.4938, 0.1077, "France"),
    "Anvers": (51.2194, 4.4025, "Belgique"),
}

CAMEROON_CITIES = [c for c, v in CITIES.items() if v[2] == "Cameroun"]
INTERNATIONAL_CITIES = [c for c, v in CITIES.items() if v[2] != "Cameroun"]

# Approx road distance (km) between Cameroon cities — synthetic estimates
DOMESTIC_DISTANCES = {
    ("Douala", "Yaoundé"): 240, ("Douala", "Kribi"): 160, ("Douala", "Bafoussam"): 280,
    ("Douala", "Bamenda"): 370, ("Douala", "Bertoua"): 750, ("Douala", "Garoua"): 1150,
    ("Douala", "Ngaoundéré"): 950,
    ("Yaoundé", "Kribi"): 400, ("Yaoundé", "Bafoussam"): 320, ("Yaoundé", "Bamenda"): 400,
    ("Yaoundé", "Bertoua"): 520, ("Yaoundé", "Garoua"): 920, ("Yaoundé", "Ngaoundéré"): 730,
    ("Bafoussam", "Bamenda"): 90, ("Bafoussam", "Bertoua"): 630, ("Bafoussam", "Garoua"): 1030,
    ("Bafoussam", "Ngaoundéré"): 830,
    ("Bamenda", "Bertoua"): 700, ("Bamenda", "Garoua"): 1100, ("Bamenda", "Ngaoundéré"): 900,
    ("Bertoua", "Garoua"): 680, ("Bertoua", "Ngaoundéré"): 480,
    ("Kribi", "Bafoussam"): 420, ("Kribi", "Yaoundé"): 400, ("Kribi", "Douala"): 160,
}

# International corridors: origin -> (destination, sea_days)
INTERNATIONAL_CORRIDORS = {
    "Shanghai": ("Douala", 28), "Dubaï": ("Douala", 22), "Lagos": ("Douala", 4),
    "Abidjan": ("Douala", 8), "Le Havre": ("Douala", 18), "Anvers": ("Douala", 19),
}

CARGO_TYPES = [
    "CONTENEURISE", "VIVRES", "MATERIAUX", "CHIMIQUE",
    "ELECTRONIQUE", "TEXTILE", "AGROALIMENTAIRE",
]
CARGO_WEIGHTS = [0.34, 0.12, 0.14, 0.08, 0.12, 0.10, 0.10]

CONTAINER_TYPES = ["20_PIEDS", "40_PIEDS", "40_HC", "FRIGORIFIQUE", "CITERNE", "VRAC"]

CUSTOMER_TYPES = ["CORPORATE", "SME", "GOVERNMENT", "INTERNATIONAL"]
CUSTOMER_TYPE_WEIGHTS = [0.30, 0.35, 0.10, 0.25]

INDUSTRIES = [
    "Agroalimentaire", "BTP", "Distribution", "Énergie", "Télécommunications",
    "Textile", "Santé", "Industrie", "Transport", "Commerce international",
]

VEHICLE_TYPES = ["TRACTEUR_40T", "CAMION_30T", "CAMION_20T", "PORTE_CONTENEURS", "FRIGORIFIQUE"]
FUEL_TYPES = ["DIESEL", "DIESEL", "DIESEL", "GAZ"]

TRANSPORTERS = [
    "TransCam Express", "Sahel Logistics", "Gulf Transport CM", "Rapid CEMAC",
    "Ocean Bridge Freight", "Kadei Logistics", "Wouri Transit", "Nord-Sud Cargo",
]

WAREHOUSE_TYPES = ["PORTUAIRE", "SECH", "FRIGORIFIQUE", "TRANSIT"]

# Delay causes — weights define the global distribution of causes
DELAY_CAUSES = ["DOUANE", "TRANSPORT", "DOCUMENTATION", "ENTREPOT", "AUTRES"]
DELAY_CAUSE_WEIGHTS = [0.35, 0.26, 0.17, 0.12, 0.10]

# SLA (hours) by cargo type for customs clearance
CUSTOMS_SLA_BY_CARGO = {
    "CONTENEURISE": 72, "VIVRES": 72, "MATERIAUX": 96, "CHIMIQUE": 120,
    "ELECTRONIQUE": 96, "TEXTILE": 96, "AGROALIMENTAIRE": 72,
}

# Countries -> customs duty rate ranges (synthetic)
COUNTRIES_DUTY = {
    "Chine": (0.18, 0.32), "Émirats Arabes Unis": (0.12, 0.22),
    "Nigéria": (0.10, 0.18), "Côte d'Ivoire": (0.08, 0.15),
    "France": (0.10, 0.20), "Belgique": (0.10, 0.20), "Cameroun": (0.05, 0.12),
}

