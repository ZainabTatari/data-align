# Pilot guide - trying Data-Align safely

Thank you for testing. Data-Align compares a **source** and a **target** database after a migration and produces an evidence report.
The author is a tester, not a developer - feedback and corrections are very welcome.

## Ground rules (please read)
1. **Use non-sensitive or anonymised data only.** Reports contain keys and column names, never raw values, but do not take chances.
2. **Use a read-only database account.** Data-Align only reads, and also checks that it cannot write.
3. **Never put a password in a config file.** For PostgreSQL, put the connection URL in an environment variable.
4. A result of `PASS` means *the checks that ran passed*. `NOT_TESTED` items are listed honestly - read them.

## 1. Try the demo (5 minutes)
Windows: double-click `run-demo.bat`. Others: `python -m dataalign demo --out out`. Open the HTML report.

## 2. Point it at your own data
SQLite: use file paths in the config. PostgreSQL: `pip install pg8000`, then set
```
set DATAALIGN_SOURCE_DSN=postgresql://readonly_user:password@host:5432/dbname
set DATAALIGN_TARGET_DSN=postgresql://readonly_user:password@host:5432/dbname
```
and in your config:
```json
"source": {"type": "postgres", "dsn_env": "DATAALIGN_SOURCE_DSN", "schema": "public"},
"target": {"type": "postgres", "dsn_env": "DATAALIGN_TARGET_DSN", "schema": "public"}
```
See `suites/example_config.json` and `python -m dataalign list-cases`. You can disable tests that do not apply in the suite file.

## 3. What to send back
Open a **Pilot feedback** issue (Issues -> New issue). Useful: how far you got, what was confusing, any false alarm, whether the report could serve as sign-off evidence. Please do **not** attach the report if it names sensitive tables - describe it instead.
