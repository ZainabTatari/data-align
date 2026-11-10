# Data-Align

[![tests](https://github.com/ZainabTatari/data-align/actions/workflows/tests.yml/badge.svg)](https://github.com/ZainabTatari/data-align/actions)

**An open-source data-migration auditor. Deterministic checks prove; AI only explains.**

Data-Align compares an old database with a migrated one across **24 testing categories (92 test cases)**: row counts, keys, schema mapping, field-by-field values, data quality, exact-decimal aggregates, SHA-256 row hashes, timestamps, positive/negative/boundary cases, decimal precision, PII discovery, HMAC-based PII reconciliation, security, referential integrity, ETL rules, CDC, schema evolution, encoding, lineage, performance, resilience and compliance evidence.

Every case ends as **PASS, FAIL, REVIEW or NOT_TESTED**, and the whole run as **PASS / FAIL / REVIEW_REQUIRED / INCOMPLETE**. A disabled or unrun mandatory test can never produce a PASS.

> Version **0.9.0**. Honest status, including what is *not* built yet: [docs/STATUS.md](docs/STATUS.md).
> Reports never contain raw data values; PII is compared as HMAC-SHA-256 tokens; the AI only ever sees results, never rows.

## Who is this for?
Teams that must **prove** a data migration was correct - for example insurance, utilities and healthcare - and need repeatable sign-off evidence, not just "it looked fine". Works with SQLite, CSV files and PostgreSQL.

## Three ways to use it

| | Best for | Start here |
|---|---|---|
| **1. Demo** | See what it does in 2 minutes | double-click `run-demo.bat` |
| **2. Easy mode (no coding)** | Audit your own data | put data in `mydata/old` and `mydata/new`, double-click `run-mydata.bat` |
| **3. Command line / Langflow** | Advanced settings, PostgreSQL, automation | see below |

### 1. Try the demo (needs Python 3.11+ or Docker Desktop)
Windows: double-click **`run-demo.bat`** (it uses Python if installed, otherwise Docker Desktop). Or in a terminal:
```
python -m dataalign demo --out dataalign_output
```
It builds a synthetic insurance database, migrates it cleanly (**PASS**) and again with about 30 planted defects (**FAIL**: missing rows, truncated text, float drift, mojibake, orphans, a leaked API key, a stale CDC watermark...). Open `dataalign_output/defective/report.html`. A pre-made copy is in [docs/sample_report](docs/sample_report/).

### 2. Audit your own data (no coding)
1. Put your **old** data in `mydata/old` and your **new** data in `mydata/new`. Each can be one database file (`.db`) or CSV files, one per table.
2. Optional: copy `mydata/rules_example.csv` to `mydata/rules.csv` and edit it in Excel to add your own business rules.
3. Double-click **`run-mydata.bat`**. Your report opens in the browser.

Details: [docs/EASY_MODE.md](docs/EASY_MODE.md). Advanced rules: [docs/BUSINESS_RULES.md](docs/BUSINESS_RULES.md).
Without rules and evidence documents, easy mode reports **INCOMPLETE** rather than PASS for identical data - it never claims a pass it did not prove.

### 3. Command line, PostgreSQL and Langflow
```
python -m dataalign init-suite my_suite.json     # choose which categories/cases are active, add custom SQL cases
python -m dataalign list-cases                   # see all 92 cases
python -m dataalign run --config my_config.json --suite my_suite.json --out results [--resume]
```
`suites/example_config.json` shows every setting. Exit code is 0 only when the overall result is PASS.

- **PostgreSQL:** `pip install pg8000`, put the connection URL in an environment variable (never in the config file). See [docs/PILOT.md](docs/PILOT.md).
- **Langflow (optional visual front end):** import the flow from [integrations/langflow](integrations/langflow/README.md). It can run the demo, your `mydata` folder (with `rules.csv`) or a config file. Tested on Langflow 1.13.

## Principles
- **AI interprets, code proves.** The optional local model (Ollama) writes a plain-English summary. It cannot change a status.
- **No silent passes.** Disabled, blocked, unconfigured or crashed checks are NOT_TESTED, and mandatory ones make the run INCOMPLETE.
- **Privacy by design.** Evidence holds keys and column names only. PII is hashed with a secret key. Prompts are scanned for PII.
- **Read-only.** Source and target are opened read-only; custom SQL must be a single SELECT.
- **Not legal advice.** Compliance checks verify technical evidence references only.

## Tests
`python -m unittest discover -s tests -v` (80 tests; 6 of them need a PostgreSQL server and skip otherwise; passes on Python 3.11, 3.12, 3.13). See [docs/STATUS.md](docs/STATUS.md) for what they prove.

## What is not verified yet
The optional Ollama AI summary and the Gotenberg PDF export are built but not verified end to end. The original Langflow + Ollama + Gotenberg flow in [docs/GUIDE.md](docs/GUIDE.md) is not connected to this engine; use the Langflow box above instead. Full list: [docs/STATUS.md](docs/STATUS.md).

## Feedback welcome
Data-Align was built by a **tester, not a developer**, with AI assistance. The checks are deterministic and tested. Corrections, bug reports and pilot feedback are very welcome - open an issue or see [docs/PILOT.md](docs/PILOT.md).

License: MIT. Contributing: [CONTRIBUTING.md](CONTRIBUTING.md).
