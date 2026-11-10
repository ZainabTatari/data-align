"""Case registry, runner, checkpoint/resume, overall decision logic."""
import datetime, hashlib, json, os, re, tempfile, time, traceback

PASS, FAIL, REVIEW, NOT_TESTED = "PASS", "FAIL", "REVIEW", "NOT_TESTED"

CATEGORIES = {
 1: "Row Count Reconciliation", 2: "Primary Key and Record Integrity",
 3: "AI Schema Mapping and Drift Detection", 4: "Field-Level Data Comparison",
 5: "Duplicate, Null and Data Quality", 6: "Aggregate Reconciliation",
 7: "SHA-256 Hash Integrity", 8: "Timestamp and Data Freshness",
 9: "Positive Testing", 10: "Negative Testing", 11: "Boundary Value Testing",
 12: "Numeric Precision and Decimal Conversion", 13: "PII Discovery and Classification",
 14: "Privacy-Preserving PII Reconciliation", 15: "Security and Access Control",
 16: "Referential Integrity", 17: "ETL/ELT Transformation Validation",
 18: "CDC and Incremental Migration", 19: "Schema Evolution and Regression",
 20: "Data Format and Encoding", 21: "Data Lineage and Traceability",
 22: "Performance and Scalability", 23: "Resilience and Recovery",
 24: "Privacy and Compliance Evidence",
}

class Result:
    def __init__(self, status, message="", **evidence):
        self.status, self.message, self.evidence = status, message, evidence

def ok(msg="", **ev): return Result(PASS, msg, **ev)
def fail(msg, **ev): return Result(FAIL, msg, **ev)
def review(msg, **ev): return Result(REVIEW, msg, **ev)
def not_tested(msg, **ev): return Result(NOT_TESTED, msg, **ev)

def verdict(bad, ok_msg, fail_msg, status=FAIL, **ev):
    """bad: list of (label, detail) problems. Evidence is limited to labels/counts (never raw values)."""
    if not bad:
        return Result(PASS, ok_msg, **ev)
    ev = dict(ev, problem_count=len(bad), samples=[str(b) for b in bad[:5]])
    return Result(status, f"{fail_msg} ({len(bad)})", **ev)

class Case:
    def __init__(self, cid, cat, title, fn, mandatory, depends):
        self.id, self.category, self.title, self.fn = cid, cat, title, fn
        self.mandatory, self.depends = mandatory, tuple(depends)

REGISTRY = {}

def case(cid, cat, title, mandatory=True, depends=()):
    def deco(fn):
        REGISTRY[cid] = Case(cid, cat, title, fn, mandatory, depends)
        return fn
    return deco

def sanitize_error(e):
    s = f"{type(e).__name__}: {e}"
    s = re.sub(r"(?:[A-Za-z]:)?[\\/][^\s'\"]+", "<path>", s)
    return s[:300]

def atomic_write(path, data):
    mode = "wb" if isinstance(data, bytes) else "w"
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".tmp_")
    try:
        with os.fdopen(fd, mode, **({} if mode == "wb" else {"encoding": "utf-8", "newline": ""})) as f:
            f.write(data)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise

def default_suite(name="enterprise_24"):
    return {"name": name, "version": "1.0", "cases": {}, "categories": {}, "custom": [],
            "policy": {"disabled_mandatory_blocks_approval": True}}

def overall(findings):
    st = [f["status"] for f in findings]
    mand_nt = [f for f in findings if f["status"] == NOT_TESTED and f["mandatory"]]
    if FAIL in st:
        return "FAIL"
    if mand_nt:
        return "INCOMPLETE"
    if REVIEW in st:
        return "REVIEW_REQUIRED"
    return "PASS"

DECISION = {
 "PASS": "Automated evidence supports approval, subject to human sign-off.",
 "FAIL": "Do not approve: one or more checks failed.",
 "INCOMPLETE": "Cannot approve: mandatory checks were not run (disabled, blocked or not configured).",
 "REVIEW_REQUIRED": "No failures, but items need human review before approval.",
}

def run_suite(ctx, suite, out_dir=None, resume=False, only=None):
    from . import checks  # noqa: registers cases
    from .custom import build_custom_cases
    cases = dict(REGISTRY)
    cases.update(build_custom_cases(suite.get("custom", [])))
    cfg_digest = hashlib.sha256(json.dumps([ctx.cfg_public(), suite], sort_keys=True, default=str).encode()).hexdigest()
    ck_path = os.path.join(out_dir, "checkpoint.json") if out_dir else None
    done = {}
    if resume and ck_path and os.path.exists(ck_path):
        try:
            ck = json.load(open(ck_path, encoding="utf-8"))
            if ck.get("digest") == cfg_digest:
                done = ck["findings"]
        except Exception:
            done = {}
    ctx.audit("run_start", suite=suite.get("name"), resumed=bool(done))
    findings, by_id = [], {}
    order = sorted(cases.values(), key=lambda c: (c.category, c.id))
    for c in order:
        if only and c.id not in only:
            continue
        over = suite.get("cases", {}).get(c.id, {})
        enabled = over.get("enabled", True) and suite.get("categories", {}).get(str(c.category), True)
        mandatory = over.get("mandatory", c.mandatory)
        if c.id in done:
            f = done[c.id]
        else:
            t0 = time.perf_counter()
            if not enabled:
                r = not_tested("Disabled by suite configuration (a disabled test is NOT a pass).")
                disabled = True
            else:
                disabled = False
                blocked = [d for d in c.depends + tuple(over.get("depends", ()))
                           if by_id.get(d, {}).get("status") in (FAIL, NOT_TESTED, None)]
                if blocked:
                    r = not_tested("Blocked: dependency not passed: " + ", ".join(blocked))
                else:
                    try:
                        ctx.findings_so_far = list(findings)
                        r = c.fn(ctx)
                    except Exception as e:  # a crashing check is never a pass
                        r = not_tested("Check could not run: " + sanitize_error(e))
            dur = round((time.perf_counter() - t0) * 1000, 2)
            ctx.timings[c.id] = dur
            f = {"id": c.id, "category": c.category, "category_name": CATEGORIES.get(c.category, "Custom"),
                 "title": c.title, "status": r.status, "mandatory": mandatory, "disabled": disabled,
                 "message": r.message, "evidence": r.evidence, "duration_ms": dur}
            ctx.audit("case_done", id=c.id, status=r.status)
            if ck_path:
                done[c.id] = f
                atomic_write(ck_path, json.dumps({"digest": cfg_digest, "findings": done}, default=str))
        f["mandatory"] = mandatory
        findings.append(f)
        by_id[c.id] = f
    ov = overall(findings)
    ctx.audit("run_end", overall=ov)
    return findings, ov
