"""Declarative data-quality rules."""
import re
from datetime import datetime, date
from .normalize import parse_decimal

def valid_date(v):
    try:
        datetime.strptime(str(v)[:10], "%Y-%m-%d"); return True
    except Exception:
        return False

def valid_ts(v):
    for f in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            datetime.strptime(str(v), f); return True
        except Exception:
            pass
    return False

BUILTIN_SPEC = {}

def check_rule(rule, value, record=None):
    """Return True if value satisfies rule. rule: dict with kind + params."""
    k = rule["kind"]
    if k == "not_null":
        return value is not None and str(value).strip() != ""
    if value is None:
        return True  # other rules ignore NULLs; use not_null to forbid
    if k == "regex":
        return re.fullmatch(rule["pattern"], str(value)) is not None
    if k == "range":
        d = parse_decimal(value)
        if d is None: return False
        lo, hi = rule.get("min"), rule.get("max")
        return (lo is None or d >= parse_decimal(lo)) and (hi is None or d <= parse_decimal(hi))
    if k == "in_set":
        return str(value) in set(map(str, rule["values"]))
    if k == "date":
        return valid_date(value)
    if k == "timestamp":
        return valid_ts(value)
    if k == "max_len":
        return len(str(value)) <= rule["n"]
    raise ValueError(f"unknown rule kind {k}")

def validate_record(rules_by_col, record):
    bad = []
    for col, rules in rules_by_col.items():
        for r in rules:
            if not check_rule(r, record.get(col), record):
                bad.append((col, r["kind"]))
    return bad
