"""Render an auditor JSON file to HTML, and to PDF if Gotenberg is running.
Usage: pip install jinja2 requests && python scripts/render_report.py test-data/sample_audit.json
"""
import json, sys, datetime, pathlib
from jinja2 import Environment, FileSystemLoader, select_autoescape

def render_html(audit: dict, template_dir="templates") -> str:
    # autoescape ON: AI output is untrusted and must not inject HTML
    env = Environment(loader=FileSystemLoader(template_dir),
                      autoescape=select_autoescape(["html"]))
    return env.get_template("report.html").render(
        r=audit, date=datetime.date.today().isoformat())

def html_to_pdf(html: str, url="http://localhost:3000/forms/chromium/convert/html") -> bytes:
    import requests
    resp = requests.post(url, files={"files": ("index.html", html, "text/html")}, timeout=60)
    resp.raise_for_status()
    return resp.content

if __name__ == "__main__":
    audit = json.loads(pathlib.Path(sys.argv[1]).read_text())
    out = pathlib.Path("output"); out.mkdir(exist_ok=True)
    html = render_html(audit)
    (out / "report.html").write_text(html)
    print("Wrote output/report.html")
    try:
        (out / "report.pdf").write_bytes(html_to_pdf(html))
        print("Wrote output/report.pdf")
    except Exception as e:
        print("PDF step skipped (is Gotenberg running on port 3000?):", e)
