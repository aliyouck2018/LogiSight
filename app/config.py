"""Application configuration via environment variables."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


class Config:
    """Base configuration shared by all environments."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{BASE_DIR / 'data' / 'logisight.db'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    JSON_SORT_KEYS = False
    JSONIFY_PRETTYPRINT_REGULAR = False

    # Pagination defaults
    DEFAULT_PAGE_SIZE = 25
    MAX_PAGE_SIZE = 200

    # Synthetic data generation
    DATA_SEED = _int_env("SEED", 42)
    N_SHIPMENTS = _int_env("N_SHIPMENTS", 20000)
    N_MONTHS_HISTORY = _int_env("N_MONTHS", 24)

    # Currency / units
    CURRENCY = "XAF"


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


class ProductionConfig(Config):
    DEBUG = False


def get_config() -> Config:
    env = os.environ.get("FLASK_ENV", "development")
    return {
        "development": DevelopmentConfig,
        "testing": TestingConfig,
        "production": ProductionConfig,
    }.get(env, DevelopmentConfig)
