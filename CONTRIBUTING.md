# Contributing

Thanks for helping! Good first contributions:
- SQL profile queries for MySQL, SQL Server or BigQuery (see sql/)
- New planted defects for test-data/
- Prompt improvements (prompts/auditor_system_prompt.txt) with before/after results
- Report template improvements (templates/report.html)

How: open an Issue to discuss, or click "Fork", make your change, and open a Pull Request.
Please use synthetic data only. Never include real data or credentials.

## Adding or changing a test case
1. Add a function in `dataalign/checks_a.py`, `checks_b.py` or `checks_c.py` decorated with `@case("ID", category, "title")`.
   Return `ok()/fail()/review()/not_tested()` or use `verdict(bad, ...)`. Put only keys and column names in evidence, never values.
2. Plant a defect that should trigger it (`fixtures.py`) or add a mutation in `tests/test_dataalign.py`.
3. Write the expected result in `tests/expected_manifest.py` **by reasoning, before looking at engine output**.
4. Run `python -m unittest discover -s tests -v`. A check that can never fail is a bug.
