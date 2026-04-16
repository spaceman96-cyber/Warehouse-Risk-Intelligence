import os
import time
import hashlib
import psycopg

MIGRATIONS_DIR = "/app/api/migrations"


def _psycopg_dsn() -> str:
    """
    psycopg wants a libpq DSN like:
      postgresql://user:pass@host:5432/db

    but SQLAlchemy often uses:
      postgresql+psycopg://...

    We'll support both by:
    - Prefer DATABASE_DSN if present (recommended)
    - Else transform DATABASE_URL to a psycopg DSN
    """
    dsn = os.getenv("DATABASE_DSN")
    if dsn:
        return dsn

    url = os.getenv("DATABASE_URL", "")
    if not url:
        raise RuntimeError("DATABASE_URL (or DATABASE_DSN) is not set")

    # transform SQLAlchemy URL -> psycopg DSN
    return url.replace("postgresql+psycopg://", "postgresql://")


def _file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _wait_for_db(dsn: str, *, timeout_s: int = 60) -> None:
    """Wait until Postgres accepts connections."""
    start = time.time()
    last_err = None
    while time.time() - start < timeout_s:
        try:
            with psycopg.connect(dsn) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1;")
            return
        except Exception as e:
            last_err = e
            print(f"DB not ready yet: {e}")
            time.sleep(1)

    raise RuntimeError(f"DB did not become ready in {timeout_s}s. Last error: {last_err}")


def _split_sql(sql: str) -> list[str]:
    """
    Very simple splitter: good enough for our migrations because we avoid semicolons inside
    dollar-quoted functions. If you later add complex SQL, consider a smarter parser.
    """
    parts = []
    for stmt in sql.split(";"):
        stmt = stmt.strip()
        if stmt:
            parts.append(stmt + ";")
    return parts


def run_migrations():
    dsn = _psycopg_dsn()
    _wait_for_db(dsn, timeout_s=60)

    if not os.path.exists(MIGRATIONS_DIR):
        print("No migrations folder found, skipping.")
        return

    files = sorted(f for f in os.listdir(MIGRATIONS_DIR) if f.endswith(".sql"))
    if not files:
        print("No migration files found.")
        return

    print(f"Running {len(files)} migrations (with tracking)...")

    with psycopg.connect(dsn, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    filename TEXT PRIMARY KEY,
                    checksum TEXT NOT NULL,
                    applied_at TIMESTAMP NOT NULL DEFAULT NOW()
                );
                """
            )

            for f in files:
                path = os.path.join(MIGRATIONS_DIR, f)
                checksum = _file_sha256(path)

                cur.execute(
                    "SELECT checksum FROM schema_migrations WHERE filename = %s",
                    (f,),
                )
                row = cur.fetchone()
                if row:
                    prev_checksum = row[0]
                    if prev_checksum != checksum:
                        raise RuntimeError(
                            f"Migration '{f}' was already applied but file changed!\n"
                            f"Prev checksum: {prev_checksum}\n"
                            f"New  checksum: {checksum}\n"
                            f"Fix: create a NEW migration file instead of editing old ones."
                        )
                    print(f"✅ Skipping already applied: {f}")
                    continue

                print(f"➡ Applying migration: {f}")
                with open(path, "r", encoding="utf-8") as sql_file:
                    sql = sql_file.read()

                try:
                    for stmt in _split_sql(sql):
                        cur.execute(stmt)
                except Exception:
                    print(f"❌ Migration failed: {f}")
                    raise

                cur.execute(
                    "INSERT INTO schema_migrations (filename, checksum) VALUES (%s, %s)",
                    (f, checksum),
                )

        conn.commit()

    print("✅ All migrations applied successfully.")


if __name__ == "__main__":
    run_migrations()