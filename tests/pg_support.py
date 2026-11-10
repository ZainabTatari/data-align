"""Helpers to copy the SQLite fixtures into a real PostgreSQL server (for the differential test)."""
import os, sqlite3, urllib.parse as up

TYPE = {"INTEGER": "integer", "TEXT": "text", "REAL": "double precision"}

def pg_conn(dsn):
    import pg8000.dbapi as pg
    u = up.urlparse(dsn)
    return pg.connect(user=u.username, password=u.password, host=u.hostname, port=u.port, database=u.path.lstrip("/"))

def load(sqlite_path, dsn, schema, type_overrides=None):
    """Copy every table of a SQLite file into a fresh PG schema. type_overrides: {("table","col"): "numeric(10,2)"}."""
    type_overrides = type_overrides or {}
    src = sqlite3.connect(sqlite_path)
    pg = pg_conn(dsn); cur = pg.cursor()
    cur.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'); cur.execute(f'CREATE SCHEMA "{schema}"')
    for (t,) in src.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall():
        cols = src.execute(f'PRAGMA table_info("{t}")').fetchall()
        ddl = ", ".join(f'"{c[1]}" {type_overrides.get((t, c[1]), TYPE[(c[2] or "TEXT").split()[0].upper()])}' for c in cols)
        cur.execute(f'CREATE TABLE "{schema}"."{t}" ({ddl})')
        rows = src.execute(f'SELECT * FROM "{t}"').fetchall()
        if rows:
            marks = ",".join(["%s"] * len(cols))
            for r in rows:
                cur.execute(f'INSERT INTO "{schema}"."{t}" VALUES ({marks})', r)
    pg.commit(); pg.close(); src.close()
