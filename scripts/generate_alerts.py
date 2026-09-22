"""Generate operational alerts from the current dataset.

Usage:
    python scripts/generate_alerts.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app  # noqa: E402
from app.analytics.alerts import generate_all_alerts  # noqa: E402


def main() -> None:
    app = create_app()
    with app.app_context():
        n = generate_all_alerts()
        print(f"Generated {n} operational alerts.")


if __name__ == "__main__":
    main()
