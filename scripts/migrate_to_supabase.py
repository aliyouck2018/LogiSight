"""Migrate the local SQLite database to Supabase (PostgreSQL).

Usage: .venv/bin/python scripts/migrate_to_supabase.py
Requires DATABASE_URL to point at the target PostgreSQL/Supabase instance.
"""
import io
import os
import sqlite3
import sys

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text

SQLITE_PATH = "data/logisight.db"
ALEMBIC_REVISION = "2fb2985193f2"

TABLE_ORDER = [
    "customers",
    "vehicles",
    "routes",
    "warehouses",
    "shipments",
    "alerts",
    "trips",
    "customs_declarations",
    "warehouse_transactions",
]


def _esc(v: object) -> str:
    if v is None:
        return r"\N"
    if isinstance(v, bool):
        return "t" if v else "f"
    s = str(v)
    for a, b in (("\\", "\\\\"), ("\t", "\\t"), ("\n", "\\n"), ("\r", "\\r")):
        s = s.replace(a, b)
    return s


def main() -> int:
    dst_url = os.environ["DATABASE_URL"]
    dst = create_engine(
        dst_url,
        connect_args={"connect_timeout": 15, "sslmode": "require"},
    )

    from app import create_app, db

    app = create_app()
    with app.app_context():
        db.create_all()
    print("Schema created on destination.", flush=True)

    sqlite_cur = sqlite3.connect(SQLITE_PATH)
    raw_conn = dst.raw_connection()
    cur = raw_conn.cursor()

    try:
        total = 0
        for table in TABLE_ORDER:
            sql_cur = sqlite_cur.execute(f'SELECT * FROM "{table}"')
            cols = [d[0] for d in sql_cur.description]
            pbool = {}
            for row in sqlite_cur.execute(f'PRAGMA table_info("{table}")'):
                pbool[row[1]] = (row[2] or "").upper() in ("BOOLEAN", "BOOL")
            rows = sql_cur.fetchall()
            if not rows:
                print(f"{table}: 0 rows (skipped)", flush=True)
                continue
            buf = io.StringIO()
            for r in rows:
                vals = []
                for cname, v in zip(cols, r):
                    if pbool.get(cname) and v is not None:
                        v = bool(v)
                    vals.append(_esc(v))
                buf.write("\t".join(vals))
                buf.write("\n")
            buf.seek(0)
            cur.copy_expert(
                'COPY "{}" ({}) FROM STDIN WITH (FORMAT text)'.format(table, ", ".join(cols)),
                buf,
            )
            total += len(rows)
            print(f"{table}: {len(rows)} rows copied", flush=True)

        cur.execute(
            "CREATE TABLE IF NOT EXISTS alembic_version"
            " (version_num VARCHAR(32) NOT NULL, CONSTRAINT alembic_version_pkc"
            " PRIMARY KEY (version_num))"
        )
        cur.execute("DELETE FROM alembic_version")
        cur.execute("INSERT INTO alembic_version (version_num) VALUES (%s)", (ALEMBIC_REVISION,))
        raw_conn.commit()
        print(f"Done. {total} rows migrated; alembic_version={ALEMBIC_REVISION}", flush=True)
    except Exception:
        raw_conn.rollback()
        raise
    finally:
        raw_conn.close()
        sqlite_cur.close()
    return 0


if __name__ == "__main__":
    if "DATABASE_URL" not in os.environ or not os.environ["DATABASE_URL"].startswith("postgresql"):
        print("DATABASE_URL must be set to a postgres:// URL", file=sys.stderr)
        sys.exit(1)
    sys.exit(main())
