# Paste into a Langflow "Custom Component". Import paths can differ between
# Langflow versions; if the import fails, check the built-in Custom Component
# template in your version and adapt the first imports.
import json, datetime
from jinja2 import Environment, FileSystemLoader, select_autoescape
from langflow.custom import Component
from langflow.io import MessageTextInput, Output
from langflow.schema import Message


class AuditReportRenderer(Component):
    display_name = "Audit Report Renderer"
    description = "Fills report.html with the auditor's JSON and returns HTML."
    inputs = [MessageTextInput(name="audit_json", display_name="Auditor JSON")]
    outputs = [Output(display_name="HTML", name="html", method="build_html")]

    def build_html(self) -> Message:
        raw = self.audit_json.strip().removeprefix("```json").removesuffix("```").strip()
        audit = json.loads(raw)
        env = Environment(loader=FileSystemLoader("/app/templates"),
                          autoescape=select_autoescape(["html"]))
        html = env.get_template("report.html").render(
            r=audit, date=datetime.date.today().isoformat())
        return Message(text=html)
