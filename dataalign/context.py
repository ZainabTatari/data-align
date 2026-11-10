"""Run context: config, connections, table specs, cached row loading, transforms."""
import datetime, hashlib, json, os, time
from decimal import Decimal
from .db import DB, q, connect
from .normalize import parse_decimal, quantize, norm_text, row_hash
from . import __version__

def apply_transform(t, v):
    k = t["kind"]
    if v is None:
        return t.get("default") if k == "default" else None
    if k == "map":
        return t["values"].get(str(v), v if t.get("unmapped", "keep") == "keep" else None)
    if k == "upper": return str(v).upper()
    if k == "lower": return str(v).lower()
    if k == "trim": return str(v).strip()
    if k == "factor":
        d = parse_decimal(v)
        return None if d is None else quantize(d * parse_decimal(t["factor"]), t.get("places", 2))
    if k == "default": return v
    raise ValueError(f"unknown transform {k}")

def values_equal(a, b, numeric):
    if a is None or b is None:
        return a is None and b is None
    if numeric:
        da, db = parse_decimal(a), parse_decimal(b)
        return da is not None and db is not None and da == db
    return str(a) == str(b)

class Context:
    def __init__(self, cfg, hmac_key=None, out_dir=None):
        self.cfg = cfg
        self.src = connect(cfg["source"], cfg.get("query_timeout_s", 30))
        self.tgt = connect(cfg["target"], cfg.get("query_timeout_s", 30))
        self.hmac_key = hmac_key if hmac_key is not None else os.environ.get(cfg.get("hmac_key_env", "DATAALIGN_HMAC_KEY"))
        self.now = datetime.datetime.strptime(cfg["as_of"], "%Y-%m-%d %H:%M:%S") if cfg.get("as_of") else datetime.datetime.utcnow()
        self.run_id = "run-" + hashlib.sha256(f"{time.time_ns()}".encode()).hexdigest()[:12]
        self.timings, self.findings_so_far, self._cache = {}, [], {}
        self.out_dir, self.audit_path = out_dir, None
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
            self.audit_path = os.path.join(out_dir, "audit_log.jsonl")
        self.specs = [self._resolve(t) for t in cfg["tables"]]

    def cfg_public(self):
        c = {k: v for k, v in self.cfg.items() if k not in ("hmac_key",)}
        return c

    def audit(self, event, **kw):
        if self.audit_path:
            rec = {"ts": datetime.datetime.utcnow().isoformat() + "Z", "run_id": self.run_id, "event": event, **kw}
            with open(self.audit_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec) + "\n")

    def _resolve(self, t):
        s, tg = t["source"], t.get("target", t["source"])
        scols = [c for c, _ in self.src.columns(s)]
        tcols = [c for c, _ in self.tgt.columns(tg)] if self.tgt.has_table(tg) else []
        colmap = dict(t.get("columns") or {c: c for c in scols if c in tcols})
        sp = dict(t)
        sp.update(source=s, target=tg, scols=scols, tcols=tcols, colmap=colmap,
                  pk=t["pk"], tpk=[colmap.get(c, c) for c in t["pk"]],
                  unmapped=[c for c in scols if c not in colmap and c not in t.get("ignore", [])],
                  new_tcols=[c for c in tcols if c not in colmap.values() and c not in t.get("target_extra", []) and c not in t.get("derived", {})],
                  transforms=t.get("transforms", {}), decimals=t.get("decimals", {}), pii=t.get("pii", {}))
        return sp

    @staticmethod
    def key_of(row, pk):
        return "|".join(str(row.get(c)) for c in pk)

    def load(self, sp):
        k = ("load", sp["source"])
        if k in self._cache:
            return self._cache[k]
        srows = self.src.dicts(f"SELECT * FROM {q(sp['source'])}")
        trows_raw = self.tgt.dicts(f"SELECT * FROM {q(sp['target'])}") if sp["tcols"] else []
        inv = {v: s for s, v in sp["colmap"].items()}
        tview = [{inv[c]: r[c] for c in r if c in inv} for r in trows_raw]
        s_by, s_dups = {}, 0
        for r in srows:
            kk = self.key_of(r, sp["pk"])
            if kk in s_by: s_dups += 1
            s_by.setdefault(kk, r)
        t_by, t_dups = {}, []
        for r in tview:
            kk = self.key_of(r, sp["pk"])
            if kk in t_by: t_dups.append(kk)
            t_by.setdefault(kk, r)
        excluded = set()
        flt = sp.get("filter", {}).get("exclude")
        if flt:
            excluded = {kk for kk, r in s_by.items() if str(r.get(flt["column"])) in set(map(str, flt["in"]))}
        rejected = set()
        rj = sp.get("rejects")
        if rj and self.tgt.has_table(rj["table"]):
            rejected = {str(r[0]) for r in self.tgt.rows(
                f"SELECT {q(rj['key_col'])} FROM {q(rj['table'])} WHERE {q(rj['table_col'])} = ?", (sp["source"],))}
        d = dict(srows=srows, trows=tview, trows_raw=trows_raw, s_by=s_by, t_by=t_by, s_dups=s_dups,
                 t_dups=t_dups, excluded=excluded, rejected=rejected,
                 expected=set(s_by) - excluded - rejected)
        self._cache[k] = d
        return d

    def expected_value(self, sp, col, v):
        t = sp["transforms"].get(col)
        return apply_transform(t, v) if t else v

    def compare_cols(self, sp, include_transformed=False):
        """Mapped columns compared by plain equality (masked PII and transformed columns excluded)."""
        masked = {c for c, p in sp["pii"].items() if p.get("mode") == "masked"}
        return [c for c in sp["colmap"] if c not in masked and (include_transformed or c not in sp["transforms"])]

    def canon(self, sp, row, cols):
        r = {}
        for c in cols:
            v = self.expected_value(sp, c, row.get(c))
            if c in sp["decimals"] and v is not None:
                d = parse_decimal(v)
                v = d if d is not None else v
            r[c] = v
        return row_hash(r, cols)

    def canon_target(self, sp, row, cols):
        r = {}
        for c in cols:
            v = row.get(c)
            if c in sp["decimals"] and v is not None:
                d = parse_decimal(v)
                v = d if d is not None else v
            r[c] = v
        return row_hash(r, cols)
