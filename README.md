# Data-Align

[![tests](https://github.com/YOUR-USERNAME/data-align/actions/workflows/tests.yml/badge.svg)](https://github.com/YOUR-USERNAME/data-align/actions)

**An open-source data-migration auditor. Deterministic checks prove; AI only explains.**

Data-Align compares a source database with a migrated target across **24 testing categories (92 test cases)**:
row counts, keys, schema mapping, field-by-field values, data quality, exact-decimal aggregates, SHA-256 row hashes,
timestamps, positive/negative/boundary cases, decimal precision, PII discovery, HMAC-based PII reconciliation,
security, referential integrity, ETL rules, CDC, schema evolution, encoding, lineage, performance, resilience and
compliance evidence. Every case ends as **PASS, FAIL, REVIEW or NOT_TESTED**, and the whole run as
**PASS / FAIL / REVIEW_REQUIRED / INCOMPLETE**. A disabled or unrun mandatory test can never produce a PASS.

> Version **0.9.0**. Honest status, including what is *not* built yet: [docs/STATUS.md](docs/STATUS.md).
> Reports never contain raw data values; PII is compared as HMAC-SHA-256 tokens; the AI only ever sees results, never rows.

## Try it in 2 minutes (nothing to install except Docker Desktop)

Windows: double-click **`run-demo.bat`**, or in PowerShell inside this folder:
```powershell
docker run --rm -v "${PWD}:/app" -w /app python:3.12-slim python -m dataalign demo --out dataalign_output
```
With Python 3.11+ already installed: `python -m dataalign demo`

It builds a synthetic insurance database, migrates it cleanly (**PASS**) and again with ~30 planted defects
(**FAIL**: missing rows, truncated text, float drift, mojibake, orphans, a leaked API key, a stale CDC watermark...).
Open `dataalign_output/defective/report.html`. A pre-made copy is in [docs/sample_report](docs/sample_report/).

## Use it on your own data
```bash
python -m dataalign init-suite my_suite.json     # choose which categories/cases are active, add custom SQL cases
python -m dataalign list-cases                   # see all 92 cases
export DATAALIGN_HMAC_KEY=$(python -c "import secrets;print(secrets.token_hex(32))")   # key stays in your environment
python -m dataalign run --config my_config.json --suite my_suite.json --out results [--resume] [--ai] [--pdf]
```
`suites/example_config.json` shows every setting. Exit code is 0 only when the overall result is PASS.

## Principles
- **AI interprets, code proves.** The optional local model (Ollama) writes a plain-English summary. It cannot change a status.
- **No silent passes.** Disabled, blocked, unconfigured or crashed checks are NOT_TESTED, and mandatory ones make the run INCOMPLETE.
- **Privacy by design.** Evidence holds keys and column names only. PII is hashed with a secret key. Prompts are scanned for PII.
- **Read-only.** Source and target are opened read-only; custom SQL must be a single SELECT.
- **Not legal advice.** Compliance checks verify technical evidence references only.

## Tests
`python -m unittest discover -s tests -v` (67 tests; passes on Python 3.11, 3.12, 3.13). See [docs/STATUS.md](docs/STATUS.md) for what they prove.

## Langflow visual flow
The original no-code flow (Langflow + Ollama + Gotenberg) is described in [docs/GUIDE.md](docs/GUIDE.md); it is
optional and **not yet verified end to end** against this engine.

License: MIT. Contributing: [CONTRIBUTING.md](CONTRIBUTING.md).
