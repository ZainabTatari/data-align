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

def safe_open(path):
    return DB(path)
