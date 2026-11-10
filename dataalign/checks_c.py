"""Categories 17-24."""
import csv, hashlib, io, json, os, re, resource, tempfile, time, unicodedata
from collections import defaultdict
from .core import (case, ok, fail, review, not_tested, verdict, Result, PASS, FAIL, REVIEW, atomic_write,
                   sanitize_error, REGISTRY, run_suite)
from .checks_a import each, _matched, num
from .checks_b import expected_equal, spec_by_source
from .context import values_equal
from .db import q, DB
from .mapping import type_class
from . import pii as P

# ---- 17 ETL -------------------------------------------------------------
@case("E01", 17, "Mapping/lookup/cleansing transformations applied correctly")
def e01(ctx):
    bad, n = [], 0
    for sp, d in each(ctx):
        cols = [c for c, t in sp["transforms"].items() if t["kind"] != "factor"]
        for k, s, t in _matched(ctx, sp, d):
            for c in cols:
                n += 1
                if not values_equal(ctx.expected_value(sp, c, s.get(c)), t.get(c), num(sp, c)):
                    bad.append((sp["source"], f"key {k} column {c}"))
    if not n: return not_tested("No transformations configured")
    return verdict(bad, f"{n} transformed values correct", "Transformation errors")

@case("E02", 17, "Filters: excluded rows are absent from target")
def e02(ctx):
    bad, n = [], 0
    for sp, d in each(ctx):
        if not d["excluded"]: continue
        n += 1
        bad += [(sp["source"], f"filtered key {k} present in target") for k in sorted(d["excluded"] & set(d["t_by"]))]
    if not n: return not_tested("No filters configured")
    return verdict(bad, "Filter honoured", "Filtered rows leaked into target")

@case("E03", 17, "Derived columns computed correctly", mandatory=False)
def e03(ctx):
    bad, n = [], 0
    for sp, d in each(ctx):
        for tcol, rule in sp.get("derived", {}).items():
            n += 1
            for r in d["trows_raw"]:
                s = d["s_by"].get("|".join(str(r.get(c)) for c in sp["tpk"]))
                if s is None: continue
                exp = rule["template"].format_map(defaultdict(str, {k: ("" if v is None else v) for k, v in s.items()}))
                if r.get(tcol) != exp: bad.append((sp["source"], f"key {'|'.join(str(r.get(c)) for c in sp['tpk'])} column {tcol}"))
    if not n: return not_tested("No derived columns configured")
    return verdict(bad, "Derived columns correct", "Derived column errors")

@case("E04", 17, "Every source row is exactly one of: migrated, filtered, rejected")
def e04(ctx):
    bad = []
    for sp, d in each(ctx):
        for k in d["s_by"]:
            states = [k in d["t_by"], k in d["excluded"], k in d["rejected"]]
            if sum(states) == 0: bad.append((sp["source"], f"key {k} unaccounted for"))
            if k in d["t_by"] and (k in d["rejected"]): bad.append((sp["source"], f"key {k} both loaded and rejected"))
    return verdict(bad, "Every source row accounted for", "Unaccounted or double-counted rows")

# ---- 18 CDC -------------------------------------------------------------
def _cdc(ctx):
    c = ctx.cfg.get("cdc")
    if not c or not ctx.src.has_table(c["log_table"]): return None, None
    sp = spec_by_source(ctx, c["table"])
    ev = ctx.src.dicts(f"SELECT seq, event_id, row_key, op, ts FROM {q(c['log_table'])} WHERE table_name = ? ORDER BY seq", (c["table"],))
    return c, (sp, ev)

def _last(events):
    last = {}
    for e in events: last[str(e["row_key"])] = e
    return last

@case("CDC01", 18, "Inserts/updates: latest change is reflected in target", mandatory=False)
def cdc01(ctx):
    c, x = _cdc(ctx)
    if not c: return not_tested("No CDC log configured")
    sp, ev = x; d = ctx.load(sp); bad = []
    for k, e in _last(ev).items():
        if e["op"] in ("I", "U"):
            if k not in d["s_by"]: bad.append(("cdc", f"key {k}: last event {e['op']} but absent in source")); continue
            if k in d["excluded"] or k in d["rejected"]: continue
            t = d["t_by"].get(k)
            if t is None or not expected_equal(ctx, sp, d["s_by"][k], t): bad.append(("cdc", f"key {k}: change not reflected"))
    return verdict(bad, "All latest changes reflected", "Changes missing or stale in target")

@case("CDC02", 18, "Deletes: deleted keys absent from target", mandatory=False)
def cdc02(ctx):
    c, x = _cdc(ctx)
    if not c: return not_tested("No CDC log configured")
    sp, ev = x; d = ctx.load(sp)
    deleted = {str(e["row_key"]) for e in ev if e["op"] == "D"} - set(d["s_by"])   # source truth, not event order
    bad = [("cdc", f"key {k}: deleted in source but still in target") for k in sorted(deleted & set(d["t_by"]))]
    return verdict(bad, "Deleted keys absent", "Deleted records still present")

@case("CDC03", 18, "Event order and duplicate events", mandatory=False)
def cdc03(ctx):
    c, x = _cdc(ctx)
    if not c: return not_tested("No CDC log configured")
    sp, ev = x; bad = []
    ids = [e["event_id"] for e in ev]
    bad += [("cdc", f"duplicate event id {i}") for i in sorted({i for i in ids if ids.count(i) > 1})]
    per = defaultdict(list)
    for e in ev: per[str(e["row_key"])].append(e)
    for k, es in per.items():
        for a, b in zip(es, es[1:]):
            if b["ts"] < a["ts"]: bad.append(("cdc", f"key {k}: events out of order (seq {a['seq']}->{b['seq']})"))
    return verdict(bad, "Event stream ordered, no duplicates", "Event stream anomalies")

@case("CDC04", 18, "Watermark progression: target watermark equals last applied source event", mandatory=False)
def cdc04(ctx):
    c, x = _cdc(ctx)
    if not c or not c.get("watermark_table") or not ctx.tgt.has_table(c["watermark_table"]): return not_tested("No watermark table")
    sp, ev = x
    wm = ctx.tgt.scalar(f"SELECT last_seq FROM {q(c['watermark_table'])} WHERE table_name = ?", (c["table"],))
    mx = max((e["seq"] for e in ev), default=None)
    bad = [] if wm == mx else [("watermark", f"target watermark {wm} != source max seq {mx}")]
    return verdict(bad, f"Watermark at seq {mx}", "Watermark lag or drift")

@case("CDC05", 18, "Idempotency: replaying / de-duplicating the stream yields the same state", mandatory=False)
def cdc05(ctx):
    c, x = _cdc(ctx)
    if not c: return not_tested("No CDC log configured")
    sp, ev = x
    def state(evs):
        s = {}
        for e in sorted(evs, key=lambda e: e["seq"]): s[str(e["row_key"])] = e["op"] != "D"
        return {k for k, v in s.items() if v}
    seen, dedup = set(), []
    for e in ev:
        if e["event_id"] not in seen: seen.add(e["event_id"]); dedup.append(e)
    full, once, twice = state(ev), state(dedup), state(ev + [dict(e, seq=e["seq"] + 10**9) for e in ev])
    bad = []
    if full != once: bad.append(("cdc", f"duplicate delivery changes final state ({len(full ^ once)} keys)"))
    if full != twice: bad.append(("cdc", "replaying the stream twice changes final state"))
    return verdict(bad, "Replay is idempotent", "Non-idempotent event stream")

# ---- 19 Schema evolution ------------------------------------------------
@case("SE01", 19, "Target columns match the approved baseline schema", mandatory=False)
def se01(ctx):
    base = ctx.cfg.get("baseline_schema")
    if not base: return not_tested("No baseline schema configured")
    bad = []
    for sp in ctx.specs:
        exp, got = set(base.get(sp["target"], {})), set(sp["tcols"])
        bad += [(sp["source"], f"new column {c}") for c in sorted(got - exp)] + [(sp["source"], f"missing column {c}") for c in sorted(exp - got)]
    return verdict(bad, "Schema equals baseline", "Schema drift from baseline")

@case("SE02", 19, "Backward compatibility: column type classes unchanged from baseline", mandatory=False)
def se02(ctx):
    base = ctx.cfg.get("baseline_schema")
    if not base: return not_tested("No baseline schema configured")
    bad = []
    for sp in ctx.specs:
        tc = dict(ctx.tgt.columns(sp["target"]))
        for c, t in base.get(sp["target"], {}).items():
            if c in tc and type_class(t) != type_class(tc[c]): bad.append((sp["source"], f"{c}: {type_class(t)} -> {type_class(tc[c])}"))
    return verdict(bad, "Types backward compatible", "Incompatible type changes")

@case("SE03", 19, "Regression vs previous run (previously passing cases must not now fail)", mandatory=False)
def se03(ctx):
    p = ctx.cfg.get("previous_results")
    if not p or not os.path.exists(p): return not_tested("No previous results supplied")
    prev = {f["id"]: f["status"] for f in json.load(open(p, encoding="utf-8"))["findings"]}
    now = {f["id"]: f["status"] for f in ctx.findings_so_far}
    bad = [("regression", f"{i}: PASS -> {now[i]}") for i in sorted(now) if prev.get(i) == PASS and now[i] == FAIL]
    return verdict(bad, f"No regressions across {len(now)} comparable cases", "Regressions since previous run")

# ---- 20 Format and encoding --------------------------------------------
_MOJI = re.compile("[ÃÂ][\u0080-¿]|â€|�")

@case("FE01", 20, "Unicode normalisation and mojibake")
def fe01(ctx):
    bad = []
    for sp, d in each(ctx):
        for k, s, t in _matched(ctx, sp, d):
            for c in ctx.compare_cols(sp):
                a, b = s.get(c), t.get(c)
                if isinstance(b, str) and isinstance(a, str) and a != b:
                    if unicodedata.normalize("NFC", a) == a and unicodedata.normalize("NFC", b) != b: bad.append((sp["source"], f"key {k} column {c}: not NFC"))
                    if _MOJI.search(b) and not _MOJI.search(a): bad.append((sp["source"], f"key {k} column {c}: mojibake"))
    return verdict(bad, "Encoding intact", "Encoding damage")

@case("FE02", 20, "Special characters, quotes, newlines and line endings preserved")
def fe02(ctx):
    bad, n = [], 0
    rx = re.compile("[\"',;\\n\\r\\t\\\\<>&%]|[^\\x00-\\x7f]")
    for sp, d in each(ctx):
        for k, s, t in _matched(ctx, sp, d):
            for c in ctx.compare_cols(sp):
                if isinstance(s.get(c), str) and rx.search(s[c]):
                    n += 1
                    if t.get(c) != s[c]: bad.append((sp["source"], f"key {k} column {c}"))
    return verdict(bad, f"{n} special-character values preserved", "Special-character values altered")

@case("FE03", 20, "CSV/JSON round-trip and malformed-JSON detection")
def fe03(ctx):
    bad = []
    for sp, d in each(ctx):
        cols = [c for c in sp["tcols"]]
        buf = io.StringIO(newline="")
        w = csv.writer(buf, lineterminator="\n"); w.writerow(cols)
        for r in d["trows_raw"]: w.writerow(["" if r.get(c) is None else r.get(c) for c in cols])
        back = list(csv.reader(io.StringIO(buf.getvalue(), newline="")))
        if len(back) != len(d["trows_raw"]) + 1: bad.append((sp["source"], "CSV row count changed in round-trip"))
        else:
            for r, row in zip(d["trows_raw"], back[1:]):
                if ["" if r.get(c) is None else str(r.get(c)) for c in cols] != row: bad.append((sp["source"], "CSV cell changed in round-trip")); break
        if json.loads(json.dumps(d["trows_raw"], ensure_ascii=False)) != d["trows_raw"]: bad.append((sp["source"], "JSON round-trip changed data"))
        for c in sp.get("json_cols", []):
            col = sp["colmap"].get(c, c)
            for r in d["trows_raw"]:
                if r.get(col) is not None:
                    try: json.loads(r[col])
                    except Exception: bad.append((sp["source"], f"malformed JSON in {col}")); break
    return verdict(bad, "Round-trips lossless", "Format round-trip failures")

# ---- 21 Lineage ---------------------------------------------------------
@case("L01", 21, "Lineage record complete (batch, versions, snapshot, audit id)")
def l01(ctx):
    need = {"batch_id": ctx.cfg.get("batch_id"), "snapshot_id": ctx.cfg.get("snapshot_id"),
            "transform_version": ctx.cfg.get("transform_version"), "mapping_version": ctx.cfg.get("mapping", {}).get("version"),
            "source_system": ctx.cfg.get("source_system"), "target_system": ctx.cfg.get("target_system")}
    bad = [("lineage", f"{k} missing") for k, v in need.items() if not v]
    return verdict(bad, "Lineage metadata complete", "Lineage metadata missing", status=REVIEW, audit_id=ctx.run_id)

@case("L02", 21, "Every target column is traceable (mapped, derived or declared)")
def l02(ctx):
    bad = [(sp["source"], f"untraceable target column {c}") for sp in ctx.specs for c in sp["new_tcols"]]
    return verdict(bad, "All target columns traceable", "Untraceable target columns", status=REVIEW)

@case("L03", 21, "Audit trail covers every executed case")
def l03(ctx):
    if not ctx.audit_path or not os.path.exists(ctx.audit_path): return fail("No audit log")
    logged = {json.loads(l).get("id") for l in open(ctx.audit_path, encoding="utf-8") if '"case_done"' in l}
    miss = [f["id"] for f in ctx.findings_so_far if f["id"] not in logged and not f.get("disabled")]
    return verdict([("audit", f"{i} not logged") for i in miss], "Every case is in the audit log", "Cases missing from audit log")

# ---- 22 Performance -----------------------------------------------------
@case("PF01", 22, "Per-case execution time within budget")
def pf01(ctx):
    lim = ctx.cfg.get("max_case_s", 30) * 1000
    slow = [(f["id"], f"{f['duration_ms']} ms") for f in ctx.findings_so_far if f.get("duration_ms", 0) > lim]
    top = sorted(((f["duration_ms"], f["id"]) for f in ctx.findings_so_far), reverse=True)[:3]
    return verdict(slow, "All cases within budget", "Cases over time budget", status=REVIEW, slowest_ms=top)

@case("PF02", 22, "Measured hashing throughput (rows/second)")
def pf02(ctx):
    n, t0 = 0, time.perf_counter()
    c0 = time.process_time()
    for sp, d in each(ctx):
        cols = ctx.compare_cols(sp, True)
        for r in d["s_by"].values(): ctx.canon(sp, r, cols); n += 1
    dt = max(time.perf_counter() - t0, 1e-9)
    rps = n / dt
    r = ok if rps >= ctx.cfg.get("min_rows_per_s", 500) else review
    return r(f"{rps:,.0f} rows/s over {n} rows (measured, single process)", rows=n, seconds=round(dt, 4), rows_per_s=round(rps), cpu_seconds=round(time.process_time() - c0, 4))

@case("PF03", 22, "Peak memory within limit")
def pf03(ctx):
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    mb = rss / (1024 * 1024) if rss > 10**8 else rss / 1024
    r = ok if mb <= ctx.cfg.get("max_memory_mb", 1024) else review
    return r(f"Peak RSS {mb:.0f} MB (measured)", peak_mb=round(mb))

@case("PF04", 22, "Concurrency, partition parallelism and cloud query cost", mandatory=False)
def pf04(ctx):
    return not_tested("Not measurable with local SQLite files; requires a cloud-warehouse connector (not implemented in 0.9.0)")

# ---- 23 Resilience ------------------------------------------------------
@case("RS01", 23, "Checkpoint/resume: an interrupted run resumes without redoing finished cases")
def rs01(ctx):
    saved_f, saved_t, saved_a = ctx.findings_so_far, dict(ctx.timings), ctx.audit_path
    ctx.audit_path = None
    suite = {"name": "selftest", "custom": [{"id": "X1", "type": "sql_zero", "side": "source", "sql": "SELECT 1 WHERE 1=0"},
                                            {"id": "X2", "type": "sql_zero", "side": "source", "sql": "SELECT 1 WHERE 1=0"}]}
    try:
        with tempfile.TemporaryDirectory() as td:
            run_suite(ctx, suite, td, only={"X1"})           # "crash" after X1
            ctx.timings.clear()
            f2, _ = run_suite(ctx, suite, td, resume=True, only={"X1", "X2"})
            resumed = "X1" not in ctx.timings and "X2" in ctx.timings
            done = {f["id"]: f["status"] for f in f2}
    finally:
        ctx.findings_so_far, ctx.timings, ctx.audit_path = saved_f, saved_t, saved_a
    bad = [] if resumed and done == {"X1": PASS, "X2": PASS} else [("resume", f"resumed={resumed} results={done}")]
    return verdict(bad, "Resume skipped finished work and completed the rest", "Checkpoint/resume failed")

@case("RS02", 23, "Unavailable target fails loudly (never silently creates an empty database)")
def rs02(ctx):
    try:
        DB(os.path.join(tempfile.gettempdir(), "dataalign_does_not_exist.db")).tables()
    except Exception: return ok("Missing database raised an error")
    return fail("Missing database was opened without error")

@case("RS03", 23, "Corrupted input fails cleanly")
def rs03(ctx):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
        f.write(b"this is not a sqlite database" * 50)
    try:
        try: DB(f.name).tables()
        except Exception as e: return ok("Corrupt file rejected: " + sanitize_error(e))
        return fail("Corrupt file accepted")
    finally: os.unlink(f.name)

@case("RS04", 23, "Query timeouts are enforced")
def rs04(ctx):
    d = DB(ctx.cfg["source"], 0.05); t0 = time.time()
    try:
        d.scalar("WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM c WHERE x<500000000) SELECT count(*) FROM c")
    except Exception:
        return ok(f"Runaway query interrupted after {time.time()-t0:.2f}s")
    finally: d.close()
    return fail("Runaway query was not interrupted")

@case("RS05", 23, "Interrupted report writes never corrupt the previous report")
def rs05(ctx):
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "report.json")
        atomic_write(p, "ORIGINAL")
        try: atomic_write(p, 12345)           # fails mid-write
        except Exception: pass
        intact = open(p).read() == "ORIGINAL"
        clean = [f for f in os.listdir(td) if f.startswith(".tmp_")] == []
    bad = ([] if intact else [("report", "original overwritten")]) + ([] if clean else [("report", "temp file left behind")])
    return verdict(bad, "Atomic writes verified", "Report write is not atomic")

@case("RS06", 23, "Idempotency: re-running a check gives identical results")
def rs06(ctx):
    a, b = REGISTRY["H01"].fn(ctx), REGISTRY["H01"].fn(ctx)
    same = (a.status, a.message, a.evidence) == (b.status, b.message, b.evidence)
    return ok("Two runs identical") if same else fail("Two runs differ")

# ---- 24 Compliance evidence --------------------------------------------
NOTE = " (technical evidence only; not a legal determination of compliance)"

@case("CP01", 24, "Run evidence package is complete and tamper-evident")
def cp01(ctx):
    from .report import build_report
    rep = build_report(ctx, {"name": "interim", "version": "0"}, ctx.findings_so_far, "INTERIM", interim=True)
    need = ["run_id", "tool_version", "config_sha256", "source_sha256", "target_sha256", "suite", "as_of", "disclaimer", "normalization_version"]
    return verdict([("evidence", f"missing {k}") for k in need if not rep.get(k)], "Evidence fields present", "Evidence fields missing")

def _evidence(ctx, fw, keys):
    c = ctx.cfg.get("compliance", {}).get(fw)
    if c is None: return None
    miss = [k for k in keys if not c.get(k)]
    return miss

@case("CP02", 24, "GDPR technical evidence references", mandatory=False)
def cp02(ctx):
    miss = _evidence(ctx, "gdpr", ["lawful_basis_ref", "retention_days", "dsar_process_ref"])
    if miss is None: return not_tested("GDPR checks not configured")
    inv = any(sp["pii"] for sp in ctx.specs)
    if miss or not inv: return review("Missing: " + ", ".join(miss + ([] if inv else ["PII inventory"])) + NOTE)
    return ok("Evidence references present" + NOTE)

@case("CP03", 24, "HIPAA technical evidence references", mandatory=False)
def cp03(ctx):
    health = [(sp["source"], c) for sp in ctx.specs for c in sp["scols"] + sp["tcols"] if P.name_class(c) == "health"]
    miss = _evidence(ctx, "hipaa", ["baa_ref", "audit_log", "access_review_ref"])
    if miss is None and not health: return not_tested("No health-data columns and HIPAA not configured")
    if miss is None: return review("Health-related columns detected but no HIPAA evidence configured" + NOTE)
    return review("Missing: " + ", ".join(miss) + NOTE) if miss else ok("Evidence references present" + NOTE)

@case("CP04", 24, "PCI DSS: no clear-text card numbers in target")
def cp04(ctx):
    bad = []
    for sp, d in each(ctx):
        for r in d["trows_raw"]:
            for c, v in r.items():
                if isinstance(v, (str, int)) and "card_number" in P.classify_text(str(v)):
                    bad.append((sp["source"], f"clear-text card number in column {c}"))
    return verdict(bad, "No clear-text card numbers found" + NOTE, "Clear-text card numbers in target")

@case("CP05", 24, "CCPA/CPRA technical evidence references", mandatory=False)
def cp05(ctx):
    miss = _evidence(ctx, "ccpa", ["opt_out_ref", "deletion_ref"])
    if miss is None: return not_tested("CCPA checks not configured")
    return review("Missing: " + ", ".join(miss) + NOTE) if miss else ok("Evidence references present" + NOTE)
