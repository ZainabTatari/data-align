# Adding your company's business rules (step by step)

**Non-technical way:** use `mydata/rules.csv` (see `mydata/README.txt`). The rest of this page is the advanced settings-file way.

Easy mode (`run-mydata.bat`) does not know your rules. To add them, use a settings file.

## Step 1 - get a starting file
Run easy mode once. It saves the settings it used in `my_report\config_used.json`.
Copy that file to `my_config.json` (same folder as `run-mydata.bat`) and open it in Notepad.

## Step 2 - add rules to a table
Find your table inside `"tables"` and add lines like these (mind the commas). Rules in `"rules"` describe the OLD data; `"target_rules"` describe the NEW data.
```json
"required": ["policy_id", "email"],
"rules": {
  "status":     [{"kind": "in_set", "values": ["A", "C"]}],
  "premium":    [{"kind": "range", "min": "0", "max": "99999999.99"}],
  "email":      [{"kind": "regex", "pattern": "[^@\\s]+@[^@\\s]+\\.[A-Za-z]{2,}"}],
  "start_date": [{"kind": "date"}]
},
"target_rules": {
  "status": [{"kind": "in_set", "values": ["ACTIVE", "CLOSED"]}]
},
"transforms": {"status": {"kind": "map", "values": {"A": "ACTIVE", "C": "CLOSED"}}}
```
| Rule | Meaning |
|---|---|
| `in_set` | value must be one of the listed values |
| `range` | number between `min` and/or `max` |
| `regex` | text must match a pattern (e.g. email shape) |
| `date` | must be a real date/time |
| `required` | must never be empty |
| `transforms` / `map` | an expected, approved change (old A becomes new ACTIVE), so it is not reported as a defect |

## Step 3 - run it
Open a command window in the folder and run:
`python -m dataalign run --config my_config.json --out my_report`
(or with Docker running: `docker run --rm -v "%cd%:/app" -w /app python:3.12-slim python -m dataalign run --config my_config.json --out my_report`)

Rule breaks appear under case **Q04** ("Configured data-quality rules hold in target") and required-column problems under **Q02**.
If the file has a typing mistake (a missing comma, say), the tool says it cannot read the file - fix and rerun.

Tested: these exact rules, applied to the demo data, were run and the planted rule violation was reported as Q04 FAIL.
Still advanced and untested by non-technical users - please report anything confusing.
