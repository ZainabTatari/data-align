"""Data-Align custom component for Langflow.

How to use: in Langflow, add a "Custom Component" to the canvas, paste this whole file into it, and click Check & Save.
Set the 'Data-Align folder' input to the folder that contains `dataalign/` (the unzipped repo).
"""
import sys

from langflow.custom import Component
from langflow.io import DropdownInput, MessageTextInput, Output
from langflow.schema.message import Message

DEMO, EASY, CONFIG = "Demo data", "My data (easy mode)", "Config file"


class DataAlignAudit(Component):
    display_name = "Data-Align Audit"
    description = "Runs the Data-Align migration checks (deterministic) and returns a PASS/FAIL summary."
    icon = "shield-check"
    name = "DataAlignAudit"

    inputs = [
        MessageTextInput(name="engine_path", display_name="Data-Align folder",
                         info="Folder that contains the 'dataalign' package (the unzipped repo folder).", value=""),
        DropdownInput(name="mode", display_name="What to audit", options=[DEMO, EASY, CONFIG], value=DEMO,
                      info="Demo = built-in example. My data = the 'mydata' folder (old/new + optional rules.csv). Config file = advanced."),
        MessageTextInput(name="data_folder", display_name="mydata folder", value="mydata",
                         info="Used by 'My data (easy mode)'. Contains the folders old and new, and optionally rules.csv."),
        MessageTextInput(name="config_path", display_name="Config file (JSON)", value="",
                         info="Only used by 'Config file'. Same file you would use with 'dataalign run'."),
        MessageTextInput(name="disabled_categories", display_name="Categories to switch off",
                         info="Config-file mode only. Optional, numbers 1-24 separated by commas, e.g. 11,12", value=""),
        MessageTextInput(name="out_dir", display_name="Output folder", value="dataalign_langflow_output"),
    ]
    outputs = [Output(display_name="Audit summary", name="summary", method="run_audit")]

    def run_audit(self) -> Message:
        if self.engine_path:
            sys.path.insert(0, self.engine_path)
        from dataalign.api import audit, demo_audit, easy_audit
        from dataalign.easy import EasyError
        notes = []
        try:
            if self.mode == EASY:
                res = easy_audit(self.data_folder, self.out_dir); notes = res.get("notes", [])
            elif self.mode == CONFIG:
                off = [int(x) for x in str(self.disabled_categories or "").replace(" ", "").split(",") if x]
                res = audit(self.config_path, self.out_dir, disabled_categories=off)
            else:
                res = demo_audit(self.out_dir)
        except EasyError as e:                       # plain-words problem the tester can fix
            self.status = "Cannot start"
            return Message(text="Cannot start: " + str(e))
        c = res["counts"]
        text = (f"Overall: {res['overall']}\n"
                f"PASS={c['PASS']}  FAIL={c['FAIL']}  REVIEW={c['REVIEW']}  NOT_TESTED={c['NOT_TESTED']}\n"
                f"Failing cases: {', '.join(res['failing_cases']) or 'none'}\n"
                f"Report: {res['report_html']}")
        if notes:
            text += "\nNotes:\n- " + "\n- ".join(notes)
        self.status = res["overall"]
        return Message(text=text)
