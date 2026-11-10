"""Declarative custom test cases with a SELECT-only SQL validator."""
import re
from .core import Case, Result, PASS, FAIL, REVIEW, not_tested
from .normalize import parse_decimal

_FORBIDDEN = re.compile(r"\b(insert|update|delete|drop|alter|create|attach|detach|pragma|replace|vacuum|reindex|truncate|grant|exec|load_extension)\b", re.I)

def validate_select(sql):
    s = sql.strip().rstrip(";").strip()
    if ";" in s:
        raise ValueError("multiple statements are not allowed")
    if not re.match(r"^(select|with)\b", s, re.I):
        raise ValueError("only SELECT queries are allowed")
    if _FORBIDDEN.search(re.sub(r"'[^']*'", "''", s)):
        raise ValueError("forbidden keyword in query")
    if "--" in s or "/*" in s:
        raise ValueError("comments are not allowed")
    return s

def _eq(a, b):
    da, db = parse_decimal(a), parse_decimal(b)
    if da is not None and db is not None:
        return da == db
    return a == b

def build_custom_cases(defs):
    out = {}
    for d in defs:
        cid, typ = d["id"], d["type"]
        def fn(ctx, d=d, typ=typ):
            try:
                if typ == "sql_equal":
                    a = ctx.src.rows(validate_select(d["source_sql"]))
                    b = ctx.tgt.rows(validate_select(d["target_sql"]))
                    good = len(a) == len(b) and all(len(x) == len(y) and all(_eq(i, j) for i, j in zip(x, y)) for x, y in zip(a, b))
                    return Result(PASS if good else FAIL, "Source and target query results " + ("match" if good else "differ"),
                                  source_rows=len(a), target_rows=len(b))
                if typ == "sql_zero":
                    db = ctx.tgt if d.get("side", "target") == "target" else ctx.src
                    n = len(db.rows(validate_select(d["sql"])))
                    return Result(PASS if n == 0 else FAIL, f"{n} offending rows", offending_rows=n)
                if typ == "sql_expect":
                    db = ctx.tgt if d.get("side", "target") == "target" else ctx.src
                    v = db.scalar(validate_select(d["sql"]))
                    good = _eq(v, d["expected"])
                    return Result(PASS if good else FAIL, "Result " + ("matches" if good else "does not match") + " expectation")
                return not_tested(f"Unknown custom case type {typ}")
            except ValueError as e:
                return Result(FAIL, f"Rejected unsafe or invalid custom query: {e}")
        out[cid] = Case(cid, int(d.get("category", 5)), d.get("title", cid), fn, d.get("mandatory", False), d.get("depends", ()))
    return out
