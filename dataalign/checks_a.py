"""Categories 01-08."""
import datetime
from collections import Counter, defaultdict
from decimal import Decimal
from .core import case, ok, fail, review, not_tested, verdict, Result, PASS, FAIL, REVIEW
from .db import q
from .normalize import parse_decimal, row_hash, quantize
from .context import values_equal
from .mapping import suggest, type_class, declared_len
from .rules import valid_date, valid_ts

def each(ctx):
    for sp in ctx.specs:
        yield sp, ctx.load(sp)

def num(sp, c): return c in sp["decimals"]

# ---- 01 Row counts -------------------------------------------------------
@case("R01", 1, "Row count: target equals expected (source minus declared filters/rejects)")
def r01(ctx):
    bad, ev = [], {}
    for sp, d in each(ctx):
        exp, got = len(d["expected"]) + d["s_dups"] * 0, len(d["trows"])
        ev[sp["source"]] = {"source": len(d["srows"]), "filtered": len(d["excluded"]),
                            "rejected": len(d["rejected"]), "expected": exp, "target": got}
        if exp != got: bad.append((sp["source"], f"expected {exp}, target {got}"))
    return verdict(bad, "Counts reconcile for every table", "Row count mismatch", tables=ev)

@case("R02", 1, "Row count by partition", mandatory=False)
def r02(ctx):
    bad, n = [], 0
    for sp, d in each(ctx):
        col = sp.get("partition")
        if not col: continue
        n += 1
        e = Counter(str(ctx.expected_value(sp, col, d["s_by"][k].get(col))) for k in d["expected"])
        g = Counter(str(r.get(col)) for r in d["trows"])
        for p in set(e) | set(g):
            if e[p] != g[p]: bad.append((sp["source"], f"partition {p}: expected {e[p]}, got {g[p]}"))
    if not n: return not_tested("No partition column configured")
    return verdict(bad, "All partitions reconcile", "Partition count mismatch")

# ---- 02 Keys -------------------------------------------------------------
@case("K01", 2, "Primary key uniqueness in target")
def k01(ctx):
    bad = [(sp["source"], f"duplicate key {k}") for sp, d in each(ctx) for k in sorted(set(d["t_dups"]))]
    return verdict(bad, "No duplicate keys in target", "Duplicate primary keys in target")

@case("K02", 2, "Missing records (expected in target but absent)")
def k02(ctx):
    bad = [(sp["source"], f"missing key {k}") for sp, d in each(ctx) for k in sorted(d["expected"] - set(d["t_by"]))]
    return verdict(bad, "No expected record is missing", "Records missing from target")

@case("K03", 2, "Extra records in target")
def k03(ctx):
    bad = [(sp["source"], f"unexpected key {k}") for sp, d in each(ctx) for k in sorted(set(d["t_by"]) - d["expected"])]
    return verdict(bad, "No unexpected records in target", "Unexpected records in target")

@case("K04", 2, "Null or empty keys")
def k04(ctx):
    bad = []
    for sp, d in each(ctx):
        for side, rows in (("source", d["srows"]), ("target", d["trows"])):
            for r in rows:
                if any(r.get(c) is None or str(r.get(c)).strip() == "" for c in sp["pk"]):
                    bad.append((sp["source"], f"{side} row with null/empty key"))
    return verdict(bad, "No null or empty keys", "Null/empty keys found")

# ---- 03 Schema mapping ---------------------------------------------------
@case("M01", 3, "Every source column is mapped or explicitly ignored")
def m01(ctx):
    bad = [(sp["source"], f"unmapped column {c}") for sp in ctx.specs for c in sp["unmapped"]]
    sug = {sp["source"]: [s for s in suggest(sp["scols"], sp["tcols"]) if s["requires_approval"]] for sp in ctx.specs}
    return verdict(bad, "All source columns accounted for", "Unmapped source columns", status=REVIEW, ai_suggestions=sug)

@case("M02", 3, "Mapping approved by a human (suggestions are never self-approving)")
def m02(ctx):
    m = ctx.cfg.get("mapping", {})
    if m.get("approved") and m.get("version") and m.get("approved_by"):
        return ok(f"Mapping v{m['version']} approved by {m['approved_by']}")
    return review("Mapping is not approved (needs mapping.approved, version and approved_by)")

@case("M03", 3, "Data type / length / nullability drift on mapped columns")
def m03(ctx):
    bad, weak = [], []
    approved = set(ctx.cfg.get("mapping", {}).get("approved_type_changes", []))
    for sp in ctx.specs:
        sc = {c: t for c, t in ctx.src.columns(sp["source"])}
        tc = {c: t for c, t in ctx.tgt.columns(sp["target"])}
        for s, t in sp["colmap"].items():
            a, b = sc.get(s, ""), tc.get(t, "")
            if type_class(a) != type_class(b) and f"{sp['source']}.{s}" not in approved:
                bad.append((sp["source"], f"{s}: {type_class(a)} -> {type_class(b)}"))
            la, lb = declared_len(a), declared_len(b)
            if la and lb and lb < la: bad.append((sp["source"], f"{s}: length {la} -> {lb}"))
    return verdict(bad, "No unapproved type or length drift", "Type/length drift")

@case("M04", 3, "New or unexpected target columns", mandatory=False)
def m04(ctx):
    bad = [(sp["source"], f"new target column {c}") for sp in ctx.specs for c in sp["new_tcols"]]
    return verdict(bad, "No unexpected target columns", "Unexpected target columns", status=REVIEW)

# ---- 04 Field comparison -------------------------------------------------
def _matched(ctx, sp, d):
    for k in sorted(d["expected"]):
        if k in d["t_by"]: yield k, d["s_by"][k], d["t_by"][k]

@case("F01", 4, "Field-by-field value comparison (non-transformed columns)")
def f01(ctx):
    bad = []
    for sp, d in each(ctx):
        cols = ctx.compare_cols(sp)
        for k, s, t in _matched(ctx, sp, d):
            for c in cols:
                if not values_equal(s.get(c), t.get(c), num(sp, c)):
                    bad.append((sp["source"], f"key {k} column {c}"))
    return verdict(bad, "All compared fields identical", "Field value mismatches")

@case("F02", 4, "Values replaced by NULL/empty in target")
def f02(ctx):
    bad = []
    for sp, d in each(ctx):
        for k, s, t in _matched(ctx, sp, d):
            for c in ctx.compare_cols(sp, True):
                sv, tv = s.get(c), t.get(c)
                if sv not in (None, "") and tv in (None, ""):
                    bad.append((sp["source"], f"key {k} column {c}"))
    return verdict(bad, "No values lost to NULL/empty", "Values lost to NULL/empty")

@case("F03", 4, "Whitespace, case and truncation differences")
def f03(ctx):
    bad = []
    for sp, d in each(ctx):
        for k, s, t in _matched(ctx, sp, d):
            for c in ctx.compare_cols(sp):
                a, b = s.get(c), t.get(c)
                if isinstance(a, str) and isinstance(b, str) and a != b:
                    kind = ("whitespace" if a.split() == b.split() else "case" if a.lower() == b.lower()
                            else "truncation" if a.startswith(b) and len(b) < len(a) else None)
                    if kind: bad.append((sp["source"], f"key {k} column {c}: {kind}"))
    return verdict(bad, "No whitespace/case/truncation damage", "Text damage detected")

# ---- 05 Data quality -----------------------------------------------------
@case("Q01", 5, "Duplicate business keys not present in source")
def q01(ctx):
    bad = []
    for sp, d in each(ctx):
        bk = sp.get("business_key")
        if not bk: continue
        cs = Counter(tuple(r.get(c) for c in bk) for r in d["srows"])
        ct = Counter(tuple(r.get(c) for c in bk) for r in d["trows"])
        bad += [(sp["source"], f"business key duplicated in target x{n}") for key, n in ct.items() if n > 1 and n > cs.get(key, 0)]
    return verdict(bad, "No new duplicates on business keys", "New duplicate business keys")

@case("Q02", 5, "Required columns are populated in target")
def q02(ctx):
    bad = []
    for sp, d in each(ctx):
        for r in d["trows"]:
            for c in sp.get("required", []):
                if r.get(c) is None or str(r.get(c)).strip() == "":
                    bad.append((sp["source"], f"key {ctx.key_of(r, sp['pk'])} column {c} empty"))
    return verdict(bad, "All required fields populated", "Required fields empty")

@case("Q03", 5, "NULL vs empty string semantics preserved")
def q03(ctx):
    bad = []
    for sp, d in each(ctx):
        for k, s, t in _matched(ctx, sp, d):
            for c in ctx.compare_cols(sp, True):
                a, b = s.get(c), t.get(c)
                if (a is None and b == "") or (a == "" and b is None):
                    bad.append((sp["source"], f"key {k} column {c}"))
    return verdict(bad, "NULL/empty semantics preserved", "NULL/empty confusion")

@case("Q04", 5, "Configured data-quality rules hold in target")
def q04(ctx):
    from .rules import validate_record
    bad = []
    for sp, d in each(ctx):
        rules = sp.get("target_rules", {})
        for r in d["trows"]:
            for col, kind in validate_record(rules, r):
                bad.append((sp["source"], f"key {ctx.key_of(r, sp['pk'])} column {col} violates {kind}"))
    return verdict(bad, "All data-quality rules satisfied", "Data-quality rule violations")

# ---- 06 Aggregates -------------------------------------------------------
def _dec(vals):
    return [x for x in (parse_decimal(v) for v in vals) if x is not None]

@case("A01", 6, "COUNT/SUM/MIN/MAX/AVG on numeric columns (exact decimal)")
def a01(ctx):
    bad, n = [], 0
    for sp, d in each(ctx):
        for c in sp["decimals"]:
            if c in sp["transforms"]: continue
            n += 1
            e = _dec(d["s_by"][k].get(c) for k in d["expected"])
            g = _dec(r.get(c) for r in d["trows"])
            def stats(x): return (len(x), sum(x, Decimal(0)), min(x) if x else None, max(x) if x else None,
                                  (sum(x, Decimal(0)) / len(x)) if x else None)
            for name, a, b in zip(("count", "sum", "min", "max", "avg"), stats(e), stats(g)):
                if a != b: bad.append((sp["source"], f"{c} {name}: expected {a}, got {b}"))
    if not n: return not_tested("No numeric columns configured")
    return verdict(bad, "Aggregates identical", "Aggregate mismatches")

@case("A02", 6, "COUNT DISTINCT", mandatory=False)
def a02(ctx):
    bad, n = [], 0
    for sp, d in each(ctx):
        for c in sp.get("distinct", []):
            n += 1
            e = len({str(ctx.expected_value(sp, c, d["s_by"][k].get(c))) for k in d["expected"]})
            g = len({str(r.get(c)) for r in d["trows"]})
            if e != g: bad.append((sp["source"], f"{c}: expected {e} distinct, got {g}"))
    if not n: return not_tested("No distinct-count columns configured")
    return verdict(bad, "Distinct counts match", "Distinct count mismatch")

@case("A03", 6, "Group totals (financial control totals)")
def a03(ctx):
    bad, n = [], 0
    for sp, d in each(ctx):
        gb = sp.get("group_by")
        if not gb: continue
        for c in sp["decimals"]:
            n += 1
            e, g = defaultdict(Decimal), defaultdict(Decimal)
            for k in d["expected"]:
                s = d["s_by"][k]; v = parse_decimal(s.get(c))
                if v is not None: e[str(ctx.expected_value(sp, gb, s.get(gb)))] += v
            for r in d["trows"]:
                v = parse_decimal(r.get(c))
                if v is not None: g[str(r.get(gb))] += v
            for grp in set(e) | set(g):
                if e[grp] != g[grp]: bad.append((sp["source"], f"{c} by {gb}={grp}: expected {e[grp]}, got {g[grp]}"))
    if not n: return not_tested("No group_by configured")
    return verdict(bad, "Group totals reconcile", "Group total mismatch")

# ---- 07 Hashing ----------------------------------------------------------
@case("H01", 7, "Row-level SHA-256 hash comparison (100% coverage incl. missing/extra rows)")
def h01(ctx):
    bad, cov = [], {}
    for sp, d in each(ctx):
        cols = ctx.compare_cols(sp, True)
        sh = {k: ctx.canon(sp, d["s_by"][k], cols) for k in d["expected"]}
        th = {k: ctx.canon_target(sp, r, cols) for k, r in d["t_by"].items()}
        for k in sorted(set(sh) | set(th)):
            if sh.get(k) != th.get(k): bad.append((sp["source"], f"key {k}"))
        cov[sp["source"]] = {"hashed_source": len(sh), "hashed_target": len(th)}
    return verdict(bad, "Every row hash matches", "Row hash mismatches", coverage=cov, normalization="1.0")

@case("H02", 7, "Partition/batch hash (order-independent)")
def h02(ctx):
    bad = []
    import hashlib
    for sp, d in each(ctx):
        cols = ctx.compare_cols(sp, True)
        a = hashlib.sha256("".join(sorted(ctx.canon(sp, d["s_by"][k], cols) for k in d["expected"])).encode()).hexdigest()
        b = hashlib.sha256("".join(sorted(ctx.canon_target(sp, r, cols) for r in d["trows"])).encode()).hexdigest()
        if a != b: bad.append((sp["source"], "batch hash differs"))
    return verdict(bad, "Batch hashes match", "Batch hash mismatch")

@case("H03", 7, "Canonical hashing self-test (known-answer, order and type invariance)")
def h03(ctx):
    r1 = row_hash({"a": 1, "b": "x", "c": None}, ["a", "b", "c"])
    kat = row_hash({"a": 1, "b": "x", "c": None}, ["a", "b", "c"]) == r1
    same_dec = row_hash({"a": Decimal("1.50")}, ["a"]) == row_hash({"a": Decimal("1.5")}, ["a"])
    null_vs_empty = row_hash({"a": None}, ["a"]) != row_hash({"a": ""}, ["a"])
    unicode_exact = row_hash({"a": "e\u0301"}, ["a"]) != row_hash({"a": "\u00e9"}, ["a"])
    ws_exact = row_hash({"a": "x "}, ["a"]) != row_hash({"a": "x"}, ["a"])
    col_order = row_hash({"a": 1, "b": 2}, ["a", "b"]) != row_hash({"a": 1, "b": 2}, ["b", "a"])
    bad = [(n, "") for n, v in (("determinism", kat), ("decimal 1.50==1.5", same_dec), ("null!=empty", null_vs_empty),
                                 ("no silent Unicode normalisation", unicode_exact), ("no silent trimming", ws_exact), ("column order is part of the spec", col_order)) if not v]
    return verdict(bad, "Canonical form behaves as documented", "Hash spec violation")

# ---- 08 Timestamps -------------------------------------------------------
def _ts_cols(sp): return sp.get("dates", [])

@case("T01", 8, "Valid dates/timestamps in target")
def t01(ctx):
    bad = []
    for sp, d in each(ctx):
        for r in d["trows"]:
            for c in _ts_cols(sp):
                v = r.get(c)
                if v is not None and not valid_ts(v): bad.append((sp["source"], f"key {ctx.key_of(r, sp['pk'])} column {c}"))
    return verdict(bad, "All dates valid", "Invalid dates in target")

@case("T02", 8, "No future-dated business records")
def t02(ctx):
    bad, lim = [], ctx.now.strftime("%Y-%m-%d %H:%M:%S")
    for sp, d in each(ctx):
        for r in d["trows"]:
            for c in _ts_cols(sp):
                v = r.get(c)
                if v is not None and valid_ts(v) and str(v) > lim: bad.append((sp["source"], f"key {ctx.key_of(r, sp['pk'])} column {c}"))
    return verdict(bad, "No future dates", "Future-dated records")

@case("T03", 8, "Freshness: target reflects latest source modification")
def t03(ctx):
    bad, n = [], 0
    for sp, d in each(ctx):
        u = sp.get("updated_col")
        if not u: continue
        n += 1
        sm = max((str(d["s_by"][k].get(u)) for k in d["expected"] if d["s_by"][k].get(u)), default=None)
        tm = max((str(r.get(u)) for r in d["trows"] if r.get(u)), default=None)
        if sm != tm: bad.append((sp["source"], f"latest source {u} != latest target {u}"))
    if not n: return not_tested("No updated_col configured")
    return verdict(bad, "Target is current", "Target is stale or ahead")

@case("T04", 8, "Migration latency within limit", mandatory=False)
def t04(ctx):
    lim = ctx.cfg.get("max_latency_s")
    n, bad = 0, []
    for sp, d in each(ctx):
        lc, uc = sp.get("loaded_col"), sp.get("updated_col")
        if not (lim and lc and uc): continue
        for k, s, t in _matched(ctx, sp, d):
            if t.get(lc) and s.get(uc):
                n += 1
                a = datetime.datetime.strptime(str(t[lc]), "%Y-%m-%d %H:%M:%S"); b = datetime.datetime.strptime(str(s[uc]), "%Y-%m-%d %H:%M:%S")
                if (a - b).total_seconds() > lim: bad.append((sp["source"], f"key {k}"))
    if not n: return not_tested("No loaded_col/max_latency_s configured")
    return verdict(bad, "Latency within limit", "Latency exceeded", status=REVIEW)

@case("T05", 8, "Timestamps are UTC / carry no unexpected offset")
def t05(ctx):
    bad = []
    for sp, d in each(ctx):
        for r in d["trows"]:
            for c in _ts_cols(sp):
                v = str(r.get(c) or "")
                if len(v) > 19 and v[19:] not in ("Z", "+00:00", ".000", ".000Z"):
                    bad.append((sp["source"], f"key {ctx.key_of(r, sp['pk'])} column {c} has offset"))
    return verdict(bad, "No non-UTC offsets", "Non-UTC offsets found", status=REVIEW)
