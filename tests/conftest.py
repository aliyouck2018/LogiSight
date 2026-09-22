"""Pytest fixtures: test app with an in-memory seeded database."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app, db  # noqa: E402
from app.config import TestingConfig  # noqa: E402


@pytest.fixture(scope="session")
def app():
    """Session app with a small seeded dataset (fast)."""
    app = create_app(TestingConfig())
    with app.app_context():
        db.create_all()
        from scripts.generate_data import Generator, insert_data

        gen = Generator(n_shipments=60, months=6, seed=42)
        data = gen.run()
        insert_data(app, data)

        from app.analytics.alerts import generate_all_alerts
        generate_all_alerts()
        yield app


@pytest.fixture()
def client(app):
    return app.test_client()
