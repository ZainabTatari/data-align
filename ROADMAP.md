# Roadmap

**Done in 0.9.0:** engine and all 24 categories (92 cases), suites (enable/disable, mandatory, dependencies, custom SQL cases),
JSON/CSV/HTML reports, PDF and Ollama hooks, checkpoint/resume, 67 automated tests. Details: [docs/STATUS.md](docs/STATUS.md).

**Next (0.10):** verify Ollama + PDF + Docker launcher on a real Windows machine; fix what breaks.
**Then (0.11-0.12):** PostgreSQL and SQL Server connectors (read-only), streamed/partitioned hashing for large tables.
**Then (1.0):** web dashboard (Langflow or small web app) with suite editor; CDC late-arrival and soft-delete checks; split/merge field detection;
LLM-assisted semantic mapping suggestions (always requiring human approval); DST/timezone tests; BigQuery/Snowflake connectors.

v1.0 is only declared when every category has a real connector-backed test on realistic data. We do not mark anything done without recorded evidence.
