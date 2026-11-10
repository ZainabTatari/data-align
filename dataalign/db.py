"""Read-only SQLite access with identifier validation."""
import re, sqlite3, time

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")

def q(name):
    """Validate and quote an SQL identifier. Raises ValueError on anything suspicious."""
    if not isinstance(name, str) or not _IDENT.match(name):
        raise ValueError(f"unsafe identifier: {name!r}")
    return '"' + name + '"'

class DB:
    def __init__(self, path, timeout_s=30):
        self.path = path
        self.timeout_s = timeout_s
        self.conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        self.conn.row_factory = sqlite3.Row

    def _guard(self):
        t0 = time.time()
        self.conn.set_progress_handler(lambda: 1 if time.time() - t0 > self.timeout_s else 0, 10000)

    def query(self, sql, params=()):
        self._guard()
        return self.conn.execute(sql, params)

    def rows(self, sql, params=()):
        return [tuple(r) for r in self.query(sql, params).fetchall()]

    def dicts(self, sql, params=()):
        return [dict(r) for r in self.query(sql, params).fetchall()]

    def scalar(self, sql, params=()):
        r = self.query(sql, params).fetchone()
        return None if r is None else r[0]

    def tables(self):
        return [r[0] for r in self.rows("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]

    def has_table(self, t):
        return t in self.tables()

    def columns(self, t):
        return [(r[1], (r[2] or "").upper()) for r in self.rows(f"PRAGMA table_info({q(t)})")]

    def close(self):
        self.conn.close()

    dialect = "sqlite"
    runaway_sql = ("WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM c WHERE x<500000000) SELECT count(*) FROM c")

    def fingerprint(self):
        import hashlib
        h = hashlib.sha256()
        with open(self.path, "rb") as f:
            for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
        return h.hexdigest(), "file-sha256"

    def write_probe(self):
        """True if a write SUCCEEDED (which is a security failure)."""
        try:
            self.conn.execute("CREATE TABLE _dataalign_write_probe(x)")
        except sqlite3.OperationalError:
            return False
        self.conn.execute("DROP TABLE _dataalign_write_probe")
        return True

def safe_open(path):
    return DB(path)

class PGDB:
    """Read-only PostgreSQL access via pg8000 (pure Python; `pip install pg8000`).
    The connection string comes from an environment variable, never from the config file."""
    dialect = "postgres"
    runaway_sql = "SELECT count(*) FROM generate_series(1, 500000000)"

    def __init__(self, spec, timeout_s=30):
        try:
            import pg8000.dbapi as pg
        except ImportError as e:
            raise RuntimeError("PostgreSQL support needs the pg8000 package: pip install pg8000") from e
        import os, urllib.parse as up
        env = spec.get("dsn_env")
        dsn = os.environ.get(env or "")
        if not dsn:
            raise RuntimeError(f"Environment variable {env!r} with the PostgreSQL connection URL is not set")
        u = up.urlparse(dsn)
        if u.scheme not in ("postgres", "postgresql"):
            raise ValueError("connection URL must start with postgresql://")
        qs = up.parse_qs(u.query)
        ssl = qs.get("sslmode", [""])[0] in ("require", "verify-ca", "verify-full")
        self.schema = spec.get("schema", "public")
        self.timeout_s = timeout_s
        self.conn = pg.connect(user=up.unquote(u.username or ""), password=up.unquote(u.password or ""), host=u.hostname or "localhost",
                               port=u.port or 5432, database=(u.path or "/").lstrip("/"), timeout=15, ssl_context=True if ssl else None)
        self.conn.autocommit = True
        cur = self.conn.cursor()
        cur.execute("SET default_transaction_read_only = on")
        cur.execute(f"SET statement_timeout = {max(1, int(timeout_s * 1000))}")
        cur.execute(f"SET search_path TO {q(self.schema)}")
        self.conn.autocommit = False   # every statement now runs in a READ ONLY transaction
        self.conn.rollback()

    def _exec(self, sql, params=()):
        cur = self.conn.cursor()
        try:
            cur.execute(sql.replace("?", "%s") if params else sql, tuple(params) if params else ())
            rows = cur.fetchall() if cur.description else []
            cols = [d[0] for d in cur.description] if cur.description else []
        finally:
            self.conn.rollback()
        return cols, rows

    def rows(self, sql, params=()): return [tuple(r) for r in self._exec(sql, params)[1]]
    def dicts(self, sql, params=()):
        cols, rows = self._exec(sql, params)
        return [dict(zip(cols, r)) for r in rows]
    def scalar(self, sql, params=()):
        r = self._exec(sql, params)[1]
        return None if not r else r[0][0]

    def tables(self):
        return [r[0] for r in self.rows("SELECT table_name FROM information_schema.tables WHERE table_schema = ? AND table_type = 'BASE TABLE' ORDER BY 1", (self.schema,))]

    def has_table(self, t): return t in self.tables()

    def columns(self, t):
        out = []
        for name, typ, clen, prec, scale in self.rows(
                "SELECT column_name, data_type, character_maximum_length, numeric_precision, numeric_scale FROM information_schema.columns "
                "WHERE table_schema = ? AND table_name = ? ORDER BY ordinal_position", (self.schema, t)):
            if clen: typ = f"{typ}({clen})"
            elif typ == "numeric" and prec: typ = f"numeric({prec},{scale or 0})"
            out.append((name, typ))
        return out

    def fingerprint(self):
        import hashlib, json
        meta = []
        for t in self.tables():
            meta.append([t, self.columns(t), self.scalar(f"SELECT COUNT(*) FROM {q(t)}")])
        return hashlib.sha256(json.dumps(meta, sort_keys=True, default=str).encode()).hexdigest(), "schema+rowcount-sha256"

    def write_probe(self):
        try:
            cur = self.conn.cursor(); cur.execute("CREATE TABLE _dataalign_write_probe(x int)")
        except Exception:
            return False
        finally:
            self.conn.rollback()
        return True

    def close(self):
        try: self.conn.close()
        except Exception: pass

def connect(spec, timeout_s=30):
    """spec: a SQLite file path, {"type":"sqlite","path":...} or {"type":"postgres","dsn_env":...,"schema":...}"""
    if isinstance(spec, str): return DB(spec, timeout_s)
    t = spec.get("type", "sqlite")
    if t == "sqlite": return DB(spec["path"], timeout_s)
    if t == "postgres": return PGDB(spec, timeout_s)
    raise ValueError(f"unknown database type {t!r}")
