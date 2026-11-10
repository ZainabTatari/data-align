# Easy mode - audit your own data without coding

See `mydata/README.txt`. Short version: put OLD data in `mydata/old`, NEW data in `mydata/new` (one .db file, or CSV files - one per table), then double-click `run-mydata.bat`.

**What it does:** matches tables with the same name, picks an ID-like column that is unique and never empty, compares columns with the same name, and runs all 92 checks.
**Business rules without coding:** copy `mydata/rules_example.csv` to `mydata/rules.csv`, edit it in Excel (save as CSV) - one rule per row: required, allowed values, between, looks like email, is a date, matches pattern, old to new. Mistakes are reported with the line number. Tested on the demo data.
**What it does not do:** it cannot know other things like approved mapping, evidence documents or PII classes, so those checks show REVIEW or NOT_TESTED. Identical data therefore gives INCOMPLETE (not PASS) in easy mode - that is deliberate and honest. Differences in rows or values give FAIL.
**Limits:** tables or columns with different names are reported as notes, not matched; CSV values are all treated as text; no Excel files directly (save as CSV); PostgreSQL needs the advanced config (docs/PILOT.md).
