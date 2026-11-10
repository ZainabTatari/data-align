# Data-Align in Langflow (optional visual front end)

Langflow is a drag-and-drop canvas. This folder lets you run Data-Align from a box on that canvas instead of the command line.
The checks themselves are still the same deterministic Python engine - Langflow only starts it and shows the summary.

**Tested (Langflow 1.13, Data-Align box -> Chat Output):** Demo data; **My data (easy mode)** with a `rules.csv` (same numbers as `run-mydata.bat`); and a missing folder, which shows a plain-words message.
**Not tested:** other Langflow versions, a PostgreSQL config from inside Langflow, the Langflow desktop app.

## Quick way (import the ready flow)
1. Install and start Langflow (`pip install langflow`, then `langflow run`), open it in your browser.
2. Projects -> Upload a flow -> choose `data_align_flow.json`.
3. Click the **Data-Align Audit** box. Set **Data-Align folder** to the folder on your computer that contains the `dataalign` folder.
4. Pick **What to audit**:
   - **Demo data** - the built-in example.
   - **My data (easy mode)** - put old data in `mydata/old`, new data in `mydata/new` and optionally `mydata/rules.csv` (see `mydata/README.txt`), then type the full path of your `mydata` folder in **mydata folder**.
   - **Config file** - advanced.
5. Open the Playground and press send. You get PASS/FAIL counts, failing case IDs, notes and the path of the HTML report.

## Build it yourself
New flow -> add **Custom Component** -> paste the whole of `data_align_component.py` -> Check & Save -> connect its output to a **Chat Output**.

Never put passwords in a config file (see docs/PILOT.md).
