# Status matrix (v0.9.0), written honestly

**Evidence behind these claims** (all reproducible with `python -m unittest discover -s tests -v`):
- 92 test cases implemented across all 24 categories.
- Clean synthetic migration: 87 PASS, 0 FAIL, 0 REVIEW, 5 NOT_TESTED (optional cases with nothing configured). Overall **PASS**.
- Defective migration (about 30 planted defects): the engine's result was compared with a **hand-written expectation for every one of the 92 cases**
  (`tests/expected_manifest.py`). During the build this found one real engine bug (CDC02 trusted event order) which was fixed.
- 29 single-defect mutation tests on the clean target and 20+ configuration probes prove most checks can actually fire (no "always PASS" checks).
- Also tested: disabled mandatory case -> INCOMPLETE, dependency blocking, category switches, custom SQL safety, checkpoint/resume,
  source/target files byte-identical after a run, no raw PII/secrets/HMAC key in any output file, prompt-injection neutralised in the AI prompt,
  RFC 4231 HMAC vector, canonical-hash known answer. Run on Python 3.11, 3.12 and 3.13.

**Not independently verified yet** (code exists, could not be run in the build environment): Ollama AI commentary, Gotenberg PDF,
the Docker one-liner / `run-demo.bat`, and the Langflow flow import. Expect small fixes when you first run them.

| # | Category | Cases | State |
|---|----------|-------|-------|
| 01 | Row counts | R01 R02 | Working. Partition counts by one column. No parallel batch counts. |
| 02 | Keys | K01-K04 | Working (composite keys supported). |
| 03 | Schema mapping / drift | M01-M04 | Working. Suggestions come from name similarity and synonyms (deterministic); the LLM is not used for mapping yet. Split/merged-field detection is **not** built (only declared derived columns). Nullability drift not compared. |
| 04 | Field comparison | F01-F03 | Working. |
| 05 | Data quality | Q01-Q04 | Working (regex, range, set, date, length, not-null rules). |
| 06 | Aggregates | A01-A03 | Working, exact Decimal arithmetic. |
| 07 | SHA-256 hashing | H01-H03 | Working. Canonical form documented in `dataalign/normalize.py` (strings hashed exactly: no silent trimming or Unicode normalisation). |
| 08 | Timestamps | T01-T05 | Working for text timestamps. DST-transition tests not built. |
| 09 | Positive | P01 P02 | Working. |
| 10 | Negative | N01-N05 | Working. |
| 11 | Boundary | B01-B05 | Working. |
| 12 | Decimals | D01-D04 | Working (equality and formatting checked separately). |
| 13 | PII discovery | PII01 PII02 | Working: column-name and content patterns (email, SSN-shape, phone, Luhn-valid cards, AWS keys, JWT, secrets). Confidence is fixed (0.7 by name). Patterns are US-centric. |
| 14 | PII reconciliation | PR01-PR04 | Working: HMAC-SHA-256, masking check, key strength, AI-prompt scan. |
| 15 | Security | S01-S06 | Working. Encryption/retention are evidence references only (declared, not verified). |
| 16 | Referential integrity | RI01-RI03 | Working. |
| 17 | ETL | E01-E04 | Working: map/upper/lower/trim/factor/default transforms, filters, derived columns, reject accounting. No join/lookup-table validation. |
| 18 | CDC | CDC01-CDC05 | Working on a change-log table. Late-arrival and soft-delete detection **not built**. |
| 19 | Schema evolution | SE01-SE03 | Working against a baseline and a previous run. |
| 20 | Format / encoding | FE01-FE03 | Working (NFC, mojibake, special chars, CSV/JSON round-trip). Operates on database values, not on raw CSV/JSON files. |
| 21 | Lineage | L01-L03 | Working: run id, versions, file SHA-256s, audit log. |
| 22 | Performance | PF01-PF03 (+PF04) | Measures time, throughput, memory. Concurrency/CPU/cloud-cost (PF04) **not measurable** on SQLite; reported as NOT_TESTED. |
| 23 | Resilience | RS01-RS06 | Working self-tests: resume, missing/corrupt input, query timeout, atomic writes, idempotency. |
| 24 | Compliance evidence | CP01-CP05 | Working as **evidence-presence and clear-text-card checks only**. Never a legal determination. |

Cases verified only by their own self-test (no planted data defect makes them fail, by design): CP01 H03 L03 N03 N04 N05 P02 RS01-RS06 S06.

## Known gaps vs. the master prompt
- Only **SQLite files** are supported as source/target. SQL Server, PostgreSQL, BigQuery, Snowflake connectors are not written.
- All rows are loaded in memory: fine for tens of thousands of rows, **not** the million-row streaming/partitioned mode.
- No clickable web UI/dashboard. The "UI" is the command line plus the HTML/CSV/JSON report (PDF via Gotenberg, unverified).
- Test-case management (active/inactive, mandatory, dependencies, suites, custom SQL cases) is done through a JSON suite file, not a screen.
- Overall approval needs a human; the tool never approves a migration by itself.

## PostgreSQL connector (added in 0.9.x)
- **Verified:** the clean and defective test pairs were loaded into a real PostgreSQL 16 server; all 92 case results are identical to the SQLite run. Native NUMERIC/DATE/TIMESTAMP on both sides passes with no failures or review items. A text-to-native type change is reported (not silently passed).
- **Optional dependency:** `pip install pg8000` (pure Python). The engine itself is still standard-library only; SQLite needs nothing extra.
- **Safety:** connection URL only via an environment variable (`dsn_env`); session set to read-only with a statement timeout; write probe confirms the account cannot write.
- **Fingerprint:** PostgreSQL has no file to hash, so the report records a schema + row-count SHA-256 (kind shown in the report), not a content hash of the whole database.
- **Not verified:** other PostgreSQL versions, very large tables, SSL options, other databases (MySQL, SQL Server, Oracle).

## Langflow integration
- **Verified:** custom component builds and runs in Langflow 1.13; flow (Data-Align box -> Chat Output) returned the correct summary for the demo data, and for easy mode with rules.csv (identical numbers to the batch-file route).
- **Not verified:** other versions, own-database config run from Langflow. Langflow is optional; the engine does not need it.
