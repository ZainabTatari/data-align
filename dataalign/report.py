"""Report building and JSON / CSV / HTML writers. Reports never contain raw data values."""
import csv, hashlib, html, io, json, os
from collections import Counter
from . import __version__
from .core import CATEGORIES, DECISION, atomic_write, FAIL, PASS, REVIEW, NOT_TESTED
from .normalize import NORMALIZATION_VERSION

DISCLAIMER = ("Automated technical evidence only. This report is not legal advice and does not establish compliance "
              "with GDPR, CCPA/CPRA, HIPAA, PCI DSS or any contract. AI commentary, if present, interprets results and "
              "never overrides deterministic checks. A human must approve the migration.")
LIMITATIONS = [
 "Connectors: SQLite files only in 0.9.0 (SQL Server, PostgreSQL, BigQuery, Snowflake not implemented).",
 "Rows are loaded in memory; million-row streaming/partitioned mode is not implemented.",
 "Compliance and encryption items check that evidence references are declared; they do not verify them.",
 "CDC late-arrival detection, split/merged-field detection and cloud cost/concurrency measurement are not implemented.",
]

def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()

def build_report(ctx, suite, findings, overall, interim=False):
    cfg_sha = hashlib.sha256(json.dumps(ctx.cfg_public(), sort_keys=True, default=str).encode()).hexdigest()
    by = Counter(f["status"] for f in findings)
    cats = []
    for n, name in CATEGORIES.items():
        fs = [f for f in findings if f["category"] == n]
        cats.append({"number": n, "name": name, "cases": len(fs), **{s: sum(1 for f in fs if f["status"] == s) for s in (PASS, FAIL, REVIEW, NOT_TESTED)}})
    return {"run_id": ctx.run_id, "tool_version": __version__, "normalization_version": NORMALIZATION_VERSION,
            "suite": {"name": suite.get("name"), "version": suite.get("version")}, "as_of": ctx.now.strftime("%Y-%m-%d %H:%M:%S"),
            "config_sha256": cfg_sha, "source_sha256": ctx.src.fingerprint()[0], "target_sha256": ctx.tgt.fingerprint()[0],
            "source_fingerprint_kind": ctx.src.fingerprint()[1], "target_fingerprint_kind": ctx.tgt.fingerprint()[1],
            "overall": overall, "decision": DECISION.get(overall, "Interim snapshot"), "interim": interim,
            "summary": dict(by), "categories": cats, "findings": findings,
            "disclaimer": DISCLAIMER, "limitations": LIMITATIONS, "ai_commentary": None}

def write_json(rep, path): atomic_write(path, json.dumps(rep, indent=2, default=str, ensure_ascii=False))

def write_csv(rep, path):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["id", "category", "title", "status", "mandatory", "message", "duration_ms"])
    for f in rep["findings"]:
        w.writerow([f["id"], f["category_name"], f["title"], f["status"], f["mandatory"], f["message"], f["duration_ms"]])
    atomic_write(path, buf.getvalue())

_COL = {"PASS": "#1a7f37", "FAIL": "#cf222e", "REVIEW": "#9a6700", "NOT_TESTED": "#6e7781"}

def render_html(rep):
    e = html.escape
    rows = []
    for f in rep["findings"]:
        ev = ""
        if f["evidence"].get("samples"):
            ev = "<br><small>" + e("; ".join(f["evidence"]["samples"])) + "</small>"
        rows.append(f"<tr><td>{e(f['id'])}</td><td>{e(f['category_name'])}</td><td>{e(f['title'])}{' <i>(optional)</i>' if not f['mandatory'] else ''}</td>"
                    f"<td style='color:{_COL[f['status']]};font-weight:700'>{e(f['status'])}</td><td>{e(f['message'])}{ev}</td></tr>")
    cats = "".join(f"<tr><td>{c['number']:02d}</td><td>{e(c['name'])}</td><td>{c['cases']}</td><td>{c['PASS']}</td><td>{c['FAIL']}</td><td>{c['REVIEW']}</td><td>{c['NOT_TESTED']}</td></tr>" for c in rep["categories"])
    ai = f"<h2>AI commentary (interpretation only)</h2><pre>{e(rep['ai_commentary'])}</pre>" if rep.get("ai_commentary") else ""
    lim = "".join(f"<li>{e(x)}</li>" for x in rep["limitations"])
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Data-Align report {e(rep['run_id'])}</title>
<style>body{{font-family:system-ui,sans-serif;margin:2rem;color:#1f2328}}table{{border-collapse:collapse;width:100%;margin:1rem 0}}
td,th{{border:1px solid #d0d7de;padding:.35rem .5rem;text-align:left;vertical-align:top;font-size:.85rem}}th{{background:#f6f8fa}}
.big{{font-size:1.6rem;font-weight:700;color:{_COL.get(rep['overall'], '#1f2328') if rep['overall'] in _COL else ('#9a6700' if rep['overall'] != 'PASS' else '#1a7f37')}}}</style></head><body>
<h1>Data-Align audit report</h1><p class="big">{e(rep['overall'])}</p><p>{e(rep['decision'])}</p>
<p><small>Run {e(rep['run_id'])} · tool {e(rep['tool_version'])} · suite {e(str(rep['suite']['name']))} · as of {e(rep['as_of'])}<br>
source SHA-256 {e(rep['source_sha256'])}<br>target SHA-256 {e(rep['target_sha256'])}</small></p>
<h2>Summary: {e(json.dumps(rep['summary']))}</h2>
<table><tr><th>#</th><th>Category</th><th>Cases</th><th>PASS</th><th>FAIL</th><th>REVIEW</th><th>NOT_TESTED</th></tr>{cats}</table>
<h2>All test cases</h2><table><tr><th>ID</th><th>Category</th><th>Test</th><th>Status</th><th>Detail (keys and column names only, never raw values)</th></tr>{''.join(rows)}</table>
{ai}<h2>Known limitations of this version</h2><ul>{lim}</ul><p><small>{e(rep['disclaimer'])}</small></p></body></html>"""

def write_html(rep, path): atomic_write(path, render_html(rep))
