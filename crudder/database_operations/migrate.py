import os
import psycopg

# CONFIG
DATABASE_URL = os.getenv(
    "CRUDDER_DB_URL",
    "postgresql://civicpatch:development_password@crudder_db:5432/development_db",
)
MIGRATIONS_DIR = "database_operations/migrations"


def ensure_migrations_table(conn):
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ DEFAULT now()
            )
        """)
    conn.commit()


def get_applied_migrations(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT version FROM schema_migrations ORDER BY version")
        return {row[0] for row in cur.fetchall()}


def apply_migration(conn, version, filepath):
    print(f"Applying {version}...")
    with open(filepath, "r", encoding="utf-8") as f:
        sql = f.read()
    with conn.cursor() as cur:
        cur.execute(sql)
        cur.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (version,))
    conn.commit()


def rollback_last_migration(conn):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT version FROM schema_migrations ORDER BY applied_at DESC LIMIT 1"
        )
        row = cur.fetchone()
        if not row:
            print("No migrations to rollback.")
            return
        version = row["version"]
        down_path = os.path.join(MIGRATIONS_DIR, f"{version}.down.sql")
        if not os.path.exists(down_path):
            print(f"No rollback file found for {version}")
            return
        print(f"Rolling back {version}...")
        with open(down_path, "r", encoding="utf-8") as f:
            sql = f.read()
        cur.execute(sql)
        cur.execute("DELETE FROM schema_migrations WHERE version = %s", (version,))
    conn.commit()


def migrate_up(conn):
    ensure_migrations_table(conn)
    applied = get_applied_migrations(conn)
    files = sorted(f for f in os.listdir(MIGRATIONS_DIR) if f.endswith(".up.sql"))
    for f in files:
        version = f.replace(".up.sql", "")
        if version not in applied:
            apply_migration(conn, version, os.path.join(MIGRATIONS_DIR, f))
    print("✅ All migrations applied.")


def main():
    import sys

    cmd = sys.argv[1] if len(sys.argv) > 1 else "up"

    with psycopg.connect(DATABASE_URL) as conn:
        if cmd == "up":
            migrate_up(conn)
        elif cmd == "down":
            rollback_last_migration(conn)
        else:
            print("Usage: python migrate.py [up|down]")


if __name__ == "__main__":
    main()
