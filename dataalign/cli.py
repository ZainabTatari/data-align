import argparse, json, os, secrets, sys
from . import __version__
from .core import REGISTRY, CATEGORIES, default_suite, run_suite, atomic_write
from .context import Context

def execute(cfg, suite, out_dir, resume=False, ai=False, pdf=False, ai_model="qwen2.5:7b"):
    from . import checks  # noqa
    from .report import build_report, write_json, write_csv, write_html, render_html
    os.makedirs(out_dir, exist_ok=True)
    ctx = Context(cfg, out_dir=out_dir)
    try:
        findings, ov = run_suite(ctx, suite, out_dir, resume=resume)
        rep = build_report(ctx, suite, findings, ov)
    finally:
        ctx.src.close(); ctx.tgt.close()
    if ai:
        from .ai import ask
        rep["ai_commentary"] = ask(rep, model=ai_model)
    write_json(rep, os.path.join(out_dir, "report.json"))
    write_csv(rep, os.path.join(out_dir, "report.csv"))
    write_html(rep, os.path.join(out_dir, "report.html"))
    if pdf:
        from .pdf import html_to_pdf
        try: html_to_pdf(render_html(rep), os.path.join(out_dir, "report.pdf"))
        except Exception as e: print(f"PDF not created (is the Gotenberg container running?): {type(e).__name__}")
    return rep

def _print(rep, name):
    s = rep["summary"]
    print(f"{name}: {rep['overall']}  " + "  ".join(f"{k}={s.get(k, 0)}" for k in ("PASS", "FAIL", "REVIEW", "NOT_TESTED")))

def demo(out, ai=False, pdf=False):
    from .fixtures import build_pair, demo_config
    os.environ.setdefault("DATAALIGN_HMAC_KEY", secrets.token_hex(24))   # demo-only key, never written to disk
    data = os.path.join(out, "demo_data")
    cs, ct = build_pair(data, False); ds, dt = build_pair(data, True)
    suite = default_suite()
    rc = execute(demo_config(cs, ct), suite, os.path.join(out, "clean"), ai=ai, pdf=pdf)
    _print(rc, "clean migration    ")
    rd = execute(demo_config(ds, dt, previous_results=os.path.join(out, "clean", "report.json")), suite, os.path.join(out, "defective"), ai=ai, pdf=pdf)
    _print(rd, "defective migration")
    print(f"\nOpen {os.path.join(out, 'defective', 'report.html')} in your browser.")
    return rc, rd

def main(argv=None):
    p = argparse.ArgumentParser(prog="dataalign", description="Data-Align migration auditor")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd")
    d = sub.add_parser("demo", help="run on built-in synthetic data (clean and defective)"); d.add_argument("--out", default="dataalign_output"); d.add_argument("--ai", action="store_true"); d.add_argument("--pdf", action="store_true")
    r = sub.add_parser("run", help="audit your own databases"); r.add_argument("--config", required=True); r.add_argument("--suite"); r.add_argument("--out", default="dataalign_output")
    r.add_argument("--resume", action="store_true"); r.add_argument("--ai", action="store_true"); r.add_argument("--pdf", action="store_true"); r.add_argument("--model", default="qwen2.5:7b")
    e = sub.add_parser("easy", help="beginner mode: audit the data in mydata/old and mydata/new"); e.add_argument("--folder", default="mydata"); e.add_argument("--out", default="my_report"); e.add_argument("--no-open", action="store_true")
    sub.add_parser("list-cases", help="show all test cases")
    i = sub.add_parser("init-suite", help="write a suite file you can edit"); i.add_argument("path")
    a = p.parse_args(argv)
    if a.cmd == "demo": demo(a.out, a.ai, a.pdf); return 0
    if a.cmd == "easy":
        from .easy import run_easy, EasyError
        try: rep, _ = run_easy(a.folder, a.out, open_report=not a.no_open)
        except EasyError as ex: print("\nCannot start: " + str(ex)); return 2
        return 0 if rep["overall"] == "PASS" else 1
    if a.cmd == "run":
        cfg = json.load(open(a.config, encoding="utf-8"))
        suite = json.load(open(a.suite, encoding="utf-8")) if a.suite else default_suite()
        rep = execute(cfg, suite, a.out, a.resume, a.ai, a.pdf, a.model); _print(rep, "result"); return 0 if rep["overall"] == "PASS" else 1
    if a.cmd == "list-cases":
        from . import checks  # noqa
        for c in sorted(REGISTRY.values(), key=lambda c: (c.category, c.id)):
            print(f"{c.category:02d} {CATEGORIES[c.category][:38]:38} {c.id:6} {'mandatory' if c.mandatory else 'optional ':9} {c.title}")
        print(f"\n{len(REGISTRY)} built-in cases in {len(CATEGORIES)} categories"); return 0
    if a.cmd == "init-suite":
        from . import checks  # noqa
        s = default_suite(); s["categories"] = {str(n): True for n in CATEGORIES}
        s["cases"] = {c.id: {"enabled": True, "mandatory": c.mandatory} for c in REGISTRY.values()}
        s["custom"] = [{"id": "X-001", "category": 5, "title": "Example: no negative claim amounts", "type": "sql_zero", "side": "target",
                        "sql": "SELECT claim_id FROM claims WHERE CAST(amount AS REAL) < 0", "mandatory": False}]
        atomic_write(a.path, json.dumps(s, indent=2)); print("wrote", a.path); return 0
    p.print_help(); return 0
