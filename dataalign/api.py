"""Simple function interface so other tools (e.g. a Langflow component) can run an audit without the command line."""
import os, json, secrets
from .core import default_suite
from .cli import execute


def audit(config, out_dir, disabled_categories=None, suite=None):
    """Run the audit. `config` is a dict or a path to a JSON config. Returns a small, safe summary dict
    (counts, overall result, report paths, failing case ids) - never raw data values."""
    if isinstance(config, (str, os.PathLike)):
        config = json.load(open(config, encoding="utf-8"))
    suite = suite or default_suite()
    for cat in (disabled_categories or []):                    # category numbers 1-24, e.g. [11, 12]
        suite.setdefault("categories", {})[str(int(cat))] = False
    os.environ.setdefault("DATAALIGN_HMAC_KEY", secrets.token_hex(24))
    rep = execute(config, suite, out_dir)
    s = rep["summary"]
    return {
        "overall": rep["overall"],
        "counts": {k: s.get(k, 0) for k in ("PASS", "FAIL", "REVIEW", "NOT_TESTED")},
        "failing_cases": sorted(f["id"] for f in rep["findings"] if f["status"] == "FAIL"),
        "report_html": os.path.join(out_dir, "report.html"),
        "report_json": os.path.join(out_dir, "report.json"),
    }


def demo_audit(out_dir, defective=True):
    """Audit the built-in synthetic insurance data (no real data needed)."""
    from .fixtures import build_pair, demo_config
    s, t = build_pair(os.path.join(out_dir, "demo_data"), defective)
    return audit(demo_config(s, t), os.path.join(out_dir, "defective" if defective else "clean"))


def easy_audit(folder, out_dir):
    """Audit the data in <folder>/old and <folder>/new (plus <folder>/rules.csv if present). Same summary as audit()."""
    from .easy import run_easy
    rep, notes = run_easy(folder, out_dir, open_report=False, say=lambda *a: None)
    s = rep["summary"]
    return {
        "overall": rep["overall"],
        "counts": {k: s.get(k, 0) for k in ("PASS", "FAIL", "REVIEW", "NOT_TESTED")},
        "failing_cases": sorted(f["id"] for f in rep["findings"] if f["status"] == "FAIL"),
        "report_html": os.path.abspath(os.path.join(out_dir, "report.html")),
        "report_json": os.path.abspath(os.path.join(out_dir, "report.json")),
        "notes": notes,
    }
