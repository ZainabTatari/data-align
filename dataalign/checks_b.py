"""Categories 09-16."""
import re
from collections import Counter, defaultdict
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
from .core import case, ok, fail, review, not_tested, verdict, Result, PASS, FAIL, REVIEW, atomic_write, sanitize_error
from .checks_a import each, _matched, num
from .context import values_equal
from .db import q, DB
from .normalize import parse_decimal, quantize, hmac_hex, row_hash
from .rules import validate_record, check_rule
from . import pii as P

def spec_by_source(ctx, name):
    return next((s for s in ctx.specs if s["source"] == name), None)

def broken_fk_keys(ctx, sp, d):
    out = set()
    for fk in sp.get("fks", []):
        parent = spec_by_source(ctx, fk["ref_table"])
        pvals = {str(r.get(fk["ref_col"])) for r in ctx.load(parent)["srows"]}
        for k, r in d["s_by"].items():
            v = r.get(fk["col"])
            if v is not None and str(v) not in pvals: out.add(k)
    return out

def invalid_keys(ctx, sp, d):
    return {k for k, r in d["s_by"].items() if validate_record(sp.get("rules", {}), r)}

def expected_equal(ctx, sp, s, t):
    return all(values_equal(ctx.expected_value(sp, c, s.get(c)), t.get(c), num(sp, c)) for c in ctx.compare_cols(sp, True))

# ---- 09 Positive --------------------------------------------------------
@case("P01", 9, "Valid source records are accepted and migrated intact")
def p01(ctx):
    bad = []
    for sp, d in each(ctx):
        skip = invalid_keys(ctx, sp, d) | broken_fk_keys(ctx, sp, d) | d["excluded"]
        for k in sorted(set(d["s_by"]) - skip):
            t = d["t_by"].get(k)
            if t is None: bad.append((sp["source"], f"valid key {k} not migrated"))
            elif not expected_equal(ctx, sp, d["s_by"][k], t): bad.append((sp["source"], f"valid key {k} altered"))
    return verdict(bad, "All valid records migrated correctly", "Valid records lost or altered")

def _valid_example(r):
    k = r["kind"]
    if k == "not_null": return "x"
    if k == "range": return r.get("min", r.get("max", 0)) if r.get("min") is not None else r.get("max")
    if k == "in_set": return r["values"][0]
    if k == "date": return "2024-02-29"
    if k == "timestamp": return "2024-02-29 12:00:00"
    if k == "max_len": return "a" * r["n"]
    if k == "regex": return (r.get("examples", {}).get("valid") or [None])[0]

def _invalid_example(r):
    k = r["kind"]
    if k == "not_null": return None
    if k == "range":
        return str(parse_decimal(r["min"]) - 1) if r.get("min") is not None else str(parse_decimal(r["max"]) + 1)
    if k == "in_set": return "__BAD__"
    if k == "date": return "2023-02-30"
    if k == "timestamp": return "2023-13-01 00:00:00"
    if k == "max_len": return "a" * (r["n"] + 1)
    if k == "regex": return (r.get("examples", {}).get("invalid") or [None])[0]

def _all_rules(ctx):
    for sp in ctx.specs:
        for col, rs in list(sp.get("rules", {}).items()) + list(sp.get("target_rules", {}).items()):
            for r in rs: yield sp["source"], col, r

@case("P02", 9, "Rule-derived valid scenarios are accepted by the rule engine")
def p02(ctx):
    bad, n = [], 0
    for tbl, col, r in _all_rules(ctx):
        ex = _valid_example(r)
        if ex is None and r["kind"] != "not_null": continue
        n += 1
        if not check_rule(r, ex): bad.append((tbl, f"{col} {r['kind']}: valid example rejected"))
    if not n: return not_tested("No rules configured")
    return verdict(bad, f"{n} generated valid scenarios accepted", "Valid scenarios rejected")

# ---- 10 Negative --------------------------------------------------------
@case("N01", 10, "Invalid source records are rejected/quarantined, not silently loaded or dropped")
def n01(ctx):
    bad = []
    for sp, d in each(ctx):
        inv = invalid_keys(ctx, sp, d)
        for k in sorted(inv):
            if k in d["t_by"]: bad.append((sp["source"], f"invalid key {k} was loaded"))
            elif k not in d["rejected"] and k not in d["excluded"]: bad.append((sp["source"], f"invalid key {k} dropped without a reject record"))
        legit = inv | broken_fk_keys(ctx, sp, d)
        for k in sorted(d["rejected"] - legit):
            bad.append((sp["source"], f"valid key {k} was rejected"))
    return verdict(bad, "Invalid records handled correctly", "Invalid-record handling failures")

@case("N02", 10, "Records with broken relationships are not loaded")
def n02(ctx):
    bad = []
    for sp, d in each(ctx):
        for k in sorted(broken_fk_keys(ctx, sp, d)):
            if k in d["t_by"]: bad.append((sp["source"], f"orphan key {k} loaded"))
            elif k not in d["rejected"]: bad.append((sp["source"], f"orphan key {k} dropped without reject record"))
    return verdict(bad, "Broken relationships handled", "Broken-relationship handling failures")

@case("N03", 10, "Junk numeric/date input is handled safely (no crash, no false acceptance)")
def n03(ctx):
    bad = []
    for junk in ["abc", "", "NaN", "Infinity", "--1", "1.2.3", None, "1,2,3", "\x00"]:
        try:
            if parse_decimal(junk) is not None: bad.append(("parse_decimal", f"accepted junk {junk!r}"))
        except Exception as e: bad.append(("parse_decimal", f"raised {type(e).__name__}"))
    for junk in ["abc", None, "2023-02-30", "9999-99-99"]:
        try:
            if check_rule({"kind": "range", "min": 0, "max": 5}, junk) and junk is not None: bad.append(("range", "junk accepted"))
        except Exception as e: bad.append(("range", f"raised {type(e).__name__}"))
    return verdict(bad, "Junk input handled safely", "Unsafe junk handling")

@case("N04", 10, "Malicious identifiers and SQL are rejected")
def n04(ctx):
    from .custom import validate_select
    bad = []
    for ident in ["a;DROP TABLE x", "a b", "", "1abc", 'a"b', "a--b", "x" * 100]:
        try: q(ident); bad.append(("identifier", f"accepted {ident[:12]!r}"))
        except ValueError: pass
    for sql in ["DELETE FROM t", "SELECT 1; DROP TABLE t", "SELECT * FROM t -- x", "PRAGMA table_info(t)",
                "WITH x AS (SELECT 1) DELETE FROM t", "SELECT load_extension('x')"]:
        try: validate_select(sql); bad.append(("sql", f"accepted {sql[:20]!r}"))
        except ValueError: pass
    try: validate_select("SELECT COUNT(*) FROM t")
    except ValueError: bad.append(("sql", "rejected a valid SELECT"))
    return verdict(bad, "Unsafe identifiers/SQL rejected, valid SELECT accepted", "Injection defences failed")

@case("N05", 10, "Rule-derived invalid scenarios are rejected by the rule engine")
def n05(ctx):
    bad, n = [], 0
    for tbl, col, r in _all_rules(ctx):
        ex = _invalid_example(r)
        if ex is None and r["kind"] != "not_null": continue
        n += 1
        if check_rule(r, ex): bad.append((tbl, f"{col} {r['kind']}: invalid example accepted"))
    if not n: return not_tested("No rules configured")
    return verdict(bad, f"{n} generated invalid scenarios rejected", "Invalid scenarios accepted")

# ---- 11 Boundary --------------------------------------------------------
@case("B01", 11, "Numeric extremes (min, max, zero) preserved")
def b01(ctx):
    bad, n = [], 0
    for sp, d in each(ctx):
        for c in sp["decimals"]:
            vals = [(parse_decimal(d["s_by"][k].get(c)), k) for k in d["expected"] if parse_decimal(d["s_by"][k].get(c)) is not None]
            if not vals: continue
            picks = {min(vals)[1], max(vals)[1]} | {k for v, k in vals if v == 0}
            for k in picks:
                n += 1
                t = d["t_by"].get(k)
                if t is None or not values_equal(ctx.expected_value(sp, c, d["s_by"][k].get(c)), t.get(c), True):
                    bad.append((sp["source"], f"key {k} column {c} boundary value altered"))
    if not n: return not_tested("No numeric columns")
    return verdict(bad, f"{n} boundary values preserved", "Boundary values altered")

@case("B02", 11, "Longest strings preserved (no truncation at length limits)")
def b02(ctx):
    bad = []
    for sp, d in each(ctx):
        for c in ctx.compare_cols(sp):
            if c in sp["decimals"]: continue
            ranked = sorted(((len(str(d["s_by"][k].get(c))), k) for k in d["expected"] if isinstance(d["s_by"][k].get(c), str)), reverse=True)[:3]
            for _, k in ranked:
                t = d["t_by"].get(k)
                if t is not None and t.get(c) != d["s_by"][k].get(c): bad.append((sp["source"], f"key {k} column {c} longest value altered"))
    return verdict(bad, "Longest values preserved", "Long values altered")

@case("B03", 11, "Empty inputs handled; empty strings preserved")
def b03(ctx):
    bad = []
    try:
        row_hash({}, []); sum([], Decimal(0)); max([], default=None)
    except Exception as e: bad.append(("engine", sanitize_error(e)))
    for sp, d in each(ctx):
        for k, s, t in _matched(ctx, sp, d):
            for c in ctx.compare_cols(sp):
                if s.get(c) == "" and t.get(c) != "": bad.append((sp["source"], f"key {k} column {c} empty string changed"))
    return verdict(bad, "Empty inputs safe, empty strings preserved", "Empty-input handling failures")

@case("B04", 11, "Date boundaries preserved (leap days, year edges, min/max)")
def b04(ctx):
    bad, n = [], 0
    for sp, d in each(ctx):
        for c in sp.get("dates", []):
            vals = [(str(d["s_by"][k].get(c)), k) for k in d["expected"] if d["s_by"][k].get(c)]
            if not vals: continue
            picks = {min(vals)[1], max(vals)[1]} | {k for v, k in vals if v[5:10] in ("02-29", "12-31", "01-01")}
            for k in picks:
                n += 1
                t = d["t_by"].get(k)
                if t is None or str(t.get(c)) != str(d["s_by"][k].get(c)): bad.append((sp["source"], f"key {k} column {c} boundary date altered"))
    if not n: return not_tested("No date columns")
    return verdict(bad, f"{n} boundary dates preserved", "Boundary dates altered")

@case("B05", 11, "Precision overflow/underflow against declared DECIMAL(p,s)")
def b05(ctx):
    bad, n = [], 0
    for sp, d in each(ctx):
        for c, (p, s) in sp.get("precision", {}).items():
            n += 1
            for r in d["trows"]:
                v = parse_decimal(r.get(c))
                if v is None: continue
                if abs(v) >= Decimal(10) ** (p - s): bad.append((sp["source"], f"key {ctx.key_of(r, sp['pk'])} {c} overflow"))
                elif v != 0 and abs(v) < Decimal(10) ** -s: bad.append((sp["source"], f"key {ctx.key_of(r, sp['pk'])} {c} underflow"))
    if not n: return not_tested("No precision declared")
    return verdict(bad, "All values fit declared precision", "Precision overflow/underflow")

# ---- 12 Decimals --------------------------------------------------------
def _scale(d): return max(0, -d.as_tuple().exponent)

@case("D01", 12, "Exact decimal equality (no float drift)")
def d01(ctx):
    bad, n = [], 0
    for sp, d in each(ctx):
        for k, s, t in _matched(ctx, sp, d):
            for c in sp["decimals"]:
                n += 1
                if not values_equal(ctx.expected_value(sp, c, s.get(c)), t.get(c), True):
                    bad.append((sp["source"], f"key {k} column {c}"))
    if not n: return not_tested("No numeric columns")
    return verdict(bad, "All decimals exactly equal", "Decimal values differ")

@case("D02", 12, "Scale, rounding and truncation")
def d02(ctx):
    bad = []
    for sp, d in each(ctx):
        for k, s, t in _matched(ctx, sp, d):
            for c, places in sp["decimals"].items():
                a, b = parse_decimal(ctx.expected_value(sp, c, s.get(c))), parse_decimal(t.get(c))
                if a is None or b is None: continue
                if _scale(b) > places: bad.append((sp["source"], f"key {k} {c}: excess scale {_scale(b)}>{places}"))
                elif a != b:
                    kind = ("rounded-half-up" if quantize(a, places) == b else "truncated" if a.quantize(Decimal(1).scaleb(-places), rounding=ROUND_DOWN) == b else "other")
                    bad.append((sp["source"], f"key {k} {c}: {kind}"))
    return verdict(bad, "Scale and rounding preserved", "Scale/rounding defects")

_NUMFMT = re.compile(r"^-?\d+(\.\d+)?$")

@case("D03", 12, "Numeric text formatting compliance (no scientific notation, grouping or locale commas)")
def d03(ctx):
    bad = []
    for sp, d in each(ctx):
        for r in d["trows"]:
            for c, places in sp["decimals"].items():
                v = r.get(c)
                if isinstance(v, str) and (not _NUMFMT.match(v) or len(v.split(".")[-1]) != places and "." in v):
                    bad.append((sp["source"], f"key {ctx.key_of(r, sp['pk'])} column {c}: non-canonical format"))
    return verdict(bad, "All numeric text is canonically formatted", "Non-canonical numeric formatting")

@case("D04", 12, "Unit / currency / percentage conversion factors applied exactly", mandatory=False)
def d04(ctx):
    bad, n = [], 0
    for sp, d in each(ctx):
        for c, t in sp["transforms"].items():
            if t["kind"] != "factor": continue
            for k, s, tr in _matched(ctx, sp, d):
                n += 1
                if not values_equal(ctx.expected_value(sp, c, s.get(c)), tr.get(c), True): bad.append((sp["source"], f"key {k} column {c}"))
    if not n: return not_tested("No conversion factors configured")
    return verdict(bad, "Conversions exact", "Conversion errors")

# ---- 13 PII discovery ---------------------------------------------------
@case("PII01", 13, "Schema-based PII discovery (every PII-looking column is declared)")
def pii01(ctx):
    bad, found = [], []
    for sp in ctx.specs:
        inv = {v: s for s, v in sp["colmap"].items()}
        for side, cols in (("source", sp["scols"]), ("target", sp["tcols"])):
            for c in cols:
                cls = P.name_class(c)
                sc = c if side == "source" else inv.get(c, c)
                if cls:
                    found.append({"table": sp["source"], "column": c, "class": cls, "confidence": 0.7, "basis": "column name"})
                    if sc not in sp["pii"]: bad.append((sp["source"], f"{side} column {c} looks like {cls} but is not declared"))
    return verdict(bad, "All PII-looking columns are declared", "Undeclared PII columns", status=REVIEW, classification=found)

@case("PII02", 13, "Content-based PII/secret discovery in target text columns")
def pii02(ctx):
    sec, other = [], []
    for sp, d in each(ctx):
        declared_t = {sp["colmap"].get(c, c) for c in sp["pii"]}
        for r in d["trows_raw"][:5000]:
            for c, v in r.items():
                if c in declared_t or not isinstance(v, str): continue
                for cls in P.classify_text(v):
                    (sec if cls in P.SECRET_CLASSES else other).append((sp["source"], f"key {ctx.key_of(r, sp['pk']) if all(x in r for x in sp['tpk']) else '?'} column {c}: {cls}"))
    if sec: return verdict(sec, "", "Secrets/credentials found in target data", status=FAIL, other_pii_hits=len(other))
    return verdict(other, "No undeclared PII or secrets in target", "Undeclared PII found in target data", status=REVIEW)

# ---- 14 Privacy-preserving reconciliation -------------------------------
@case("PR01", 14, "HMAC-SHA-256 PII reconciliation (compare tokens, not raw values)")
def pr01(ctx):
    if not ctx.hmac_key: return not_tested("No HMAC key available (set DATAALIGN_HMAC_KEY)")
    bad, n = [], 0
    for sp, d in each(ctx):
        for c, p in sp["pii"].items():
            if p.get("mode") == "masked": continue
            for k, s, t in _matched(ctx, sp, d):
                if s.get(c) is None and t.get(c) is None: continue
                n += 1
                if s.get(c) is None or t.get(c) is None or hmac_hex(ctx.hmac_key, s[c]) != hmac_hex(ctx.hmac_key, t[c]):
                    bad.append((sp["source"], f"key {k} column {c}: token mismatch"))
    if not n: return not_tested("No HMAC-mode PII columns configured")
    return verdict(bad, f"{n} PII tokens match", "PII token mismatches")

@case("PR02", 14, "HMAC key management (strength, sourced from environment, not stored)")
def pr02(ctx):
    k = ctx.hmac_key
    if not k: return not_tested("No HMAC key available")
    ks = k if isinstance(k, str) else k.decode()
    weak = {"changeme", "secret", "password", "test", "key", "dataalign"}
    bad = []
    if len(ks) < 32: bad.append(("key", "shorter than 32 characters"))
    if ks.lower() in weak: bad.append(("key", "well-known weak value"))
    if "hmac_key" in ctx.cfg or ks in str(ctx.cfg_public()): bad.append(("config", "key stored in configuration"))
    return verdict(bad, "Key is strong and sourced from the environment", "Key management weakness", status=REVIEW)

@case("PR03", 14, "Masked columns are masked in target and never equal the raw value")
def pr03(ctx):
    bad, n = [], 0
    for sp, d in each(ctx):
        for c, p in sp["pii"].items():
            if p.get("mode") != "masked": continue
            n += 1
            rx, keep = re.compile(p["mask_regex"]), p.get("keep_last", 0)
            for k, s, t in _matched(ctx, sp, d):
                sv, tv = s.get(c), t.get(c)
                if sv is None: continue
                if tv is None or tv == sv or not rx.fullmatch(str(tv)) or (keep and str(tv)[-keep:] != str(sv)[-keep:]):
                    bad.append((sp["source"], f"key {k} column {c}: not correctly masked"))
    if not n: return not_tested("No masked columns configured")
    return verdict(bad, "Masking correct", "Masking failures")

@case("PR04", 14, "Data minimisation: AI prompt contains no PII")
def pr04(ctx):
    from .ai import build_prompt
    from .report import build_report
    rep = build_report(ctx, {"name": "interim"}, ctx.findings_so_far, "INTERIM", interim=True)
    leaks = P.leak_scan(build_prompt(rep), ctx)
    return verdict([("prompt", l) for l in leaks], "AI prompt is PII-free", "PII/secret in AI prompt")

# ---- 15 Security --------------------------------------------------------
@case("S01", 15, "Source and target connections are read-only")
def s01(ctx):
    import sqlite3
    bad = []
    for name, db in (("source", ctx.src), ("target", ctx.tgt)):
        try:
            db.conn.execute("CREATE TABLE _dataalign_write_probe(x)")
            bad.append((name, "WRITE SUCCEEDED"))
            db.conn.execute("DROP TABLE _dataalign_write_probe")
        except sqlite3.OperationalError: pass
    return verdict(bad, "Both connections reject writes", "Connection is writable")

@case("S02", 15, "Reports/evidence contain no raw PII or secrets")
def s02(ctx):
    from .report import build_report, render_html
    import json
    rep = build_report(ctx, {"name": "interim"}, ctx.findings_so_far, "INTERIM", interim=True)
    text = json.dumps(rep, default=str) + render_html(rep)
    return verdict([("report", l) for l in P.leak_scan(text, ctx)], "No PII or secrets in report output", "PII/secrets leaked into report")

@case("S03", 15, "No secrets stored in configuration")
def s03(ctx):
    import json
    txt = json.dumps(ctx.cfg_public(), default=str)
    bad = [("config", f"secret pattern {c}") for c in P.classify_text(txt) if c in P.SECRET_CLASSES]
    for key in ctx.cfg:
        if re.search(r"pass|secret|token|api_?key|hmac_key", key, re.I) and key != "hmac_key_env": bad.append(("config", f"key '{key}' present"))
    return verdict(bad, "Configuration holds no secrets", "Secrets in configuration")

@case("S04", 15, "Audit log written and retention declared")
def s04(ctx):
    import os
    bad = []
    if not ctx.audit_path or not os.path.exists(ctx.audit_path) or os.path.getsize(ctx.audit_path) == 0:
        bad.append(("audit", "audit log missing or empty"))
    if bad: return verdict(bad, "", "Audit logging failed")
    if not ctx.cfg.get("retention_days"): return review("Audit log present but retention_days not declared")
    return ok(f"Audit log present; retention {ctx.cfg['retention_days']} days declared")

@case("S05", 15, "Encryption configuration evidence declared (declared, not verified)", mandatory=False)
def s05(ctx):
    ev = ctx.cfg.get("evidence", {})
    miss = [k for k in ("encryption_at_rest", "encryption_in_transit") if not ev.get(k)]
    if miss: return review("Missing evidence references: " + ", ".join(miss))
    return ok("Evidence references declared (document references only; encryption itself not verified by this tool)")

@case("S06", 15, "Errors are sanitised (no paths or stack traces)")
def s06(ctx):
    try: DB("/nonexistent/secret/dir/x.db")
    except Exception as e: msg = sanitize_error(e)
    else: return fail("Opening a missing database did not fail")
    bad = [("error", "path leaked")] if "/nonexistent" in msg or "secret/dir" in msg or "Traceback" in msg else []
    return verdict(bad, "Error text is sanitised", "Error text leaks internals")

# ---- 16 Referential integrity -------------------------------------------
@case("RI01", 16, "No orphaned child records in target")
def ri01(ctx):
    bad, n = [], 0
    for sp in ctx.specs:
        for fk in sp.get("fks", []):
            n += 1
            p = spec_by_source(ctx, fk["ref_table"])
            c_col, p_col = sp["colmap"][fk["col"]], p["colmap"][fk["ref_col"]]
            cnt = ctx.tgt.scalar(f"SELECT COUNT(*) FROM {q(sp['target'])} c LEFT JOIN {q(p['target'])} p ON c.{q(c_col)} = p.{q(p_col)} "
                                 f"WHERE c.{q(c_col)} IS NOT NULL AND p.{q(p_col)} IS NULL")
            if cnt: bad.append((sp["source"], f"{cnt} orphaned rows on {fk['col']}"))
    if not n: return not_tested("No foreign keys configured")
    return verdict(bad, "No orphans in target", "Orphaned records in target")

@case("RI02", 16, "Parent-child cardinality preserved")
def ri02(ctx):
    bad, n = [], 0
    for sp, d in each(ctx):
        for fk in sp.get("fks", []):
            n += 1
            e = Counter(str(d["s_by"][k].get(fk["col"])) for k in d["expected"])
            g = Counter(str(r.get(fk["col"])) for r in d["trows"])
            diff = [p for p in set(e) | set(g) if e[p] != g[p]]
            bad += [(sp["source"], f"parent {p}: child count {e[p]} -> {g[p]}") for p in diff]
    if not n: return not_tested("No foreign keys configured")
    return verdict(bad, "Child counts per parent preserved", "Cardinality changed")

@case("RI03", 16, "Cross-table consistency: child totals per parent preserved", mandatory=False)
def ri03(ctx):
    bad, n = [], 0
    for sp, d in each(ctx):
        for fk in sp.get("fks", []):
            sc = fk.get("sum_col")
            if not sc: continue
            n += 1
            e, g = defaultdict(Decimal), defaultdict(Decimal)
            for k in d["expected"]:
                v = parse_decimal(d["s_by"][k].get(sc))
                if v is not None: e[str(d["s_by"][k].get(fk["col"]))] += v
            for r in d["trows"]:
                v = parse_decimal(r.get(sc))
                if v is not None: g[str(r.get(fk["col"]))] += v
            bad += [(sp["source"], f"parent {p}: total differs") for p in set(e) | set(g) if e[p] != g[p]]
    if not n: return not_tested("No sum_col configured")
    return verdict(bad, "Parent totals preserved", "Parent totals differ")
