"""Easy mode for non-technical testers: put the OLD data in mydata/old and the NEW data in mydata/new, then run.
Each side can be ONE database file (.db/.sqlite/.sqlite3) or several CSV files (one per table; file name = table name).
Nothing is ever written to your data. CSV files are copied into a temporary SQLite file inside the report folder."""
import csv, glob, json, os, re, secrets, sqlite3, sys
from .db import DB

DB_EXT = (".db", ".sqlite", ".sqlite3")
IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class EasyError(Exception):
    """A problem the tester can fix; the message is written in plain words."""


def _clean_name(s):
    s = re.sub(r"[^A-Za-z0-9_]", "_", s.strip())
    return ("c_" + s if not s or s[0].isdigit() else s)


def prepare_side(folder, label, work_dir):
    """Return a path to a SQLite file for this side."""
    if not os.path.isdir(folder):
        raise EasyError(f"The folder '{folder}' does not exist. Create it and put your {label} data inside.")
    files = [f for f in sorted(glob.glob(os.path.join(folder, "*"))) if os.path.isfile(f)]
    dbs = [f for f in files if f.lower().endswith(DB_EXT)]
    csvs = [f for f in files if f.lower().endswith(".csv")]
    if dbs and csvs:
        raise EasyError(f"The {label} folder has both database files and CSV files. Please use only one kind.")
    if len(dbs) > 1:
        raise EasyError(f"The {label} folder has {len(dbs)} database files. Please keep just one.")
    if dbs:
        return dbs[0]
    if not csvs:
        raise EasyError(f"The {label} folder '{folder}' is empty. Put one database file (.db) or your CSV files in it.")
    os.makedirs(work_dir, exist_ok=True)
    out = os.path.join(work_dir, f"{label}_from_csv.db")
    if os.path.exists(out): os.remove(out)
    con = sqlite3.connect(out)
    for f in csvs:
        table = _clean_name(os.path.splitext(os.path.basename(f))[0])
        with open(f, newline="", encoding="utf-8-sig") as fh:
            rd = csv.reader(fh)
            try: head = next(rd)
            except StopIteration: raise EasyError(f"The file '{os.path.basename(f)}' is empty.")
            cols = [_clean_name(c) for c in head]
            if len(set(cols)) != len(cols): raise EasyError(f"'{os.path.basename(f)}' has two columns with the same name.")
            con.execute(f'CREATE TABLE "{table}" (' + ", ".join(f'"{c}" TEXT' for c in cols) + ")")
            n = 0
            for row in rd:
                if not row: continue
                if len(row) != len(cols):
                    raise EasyError(f"'{os.path.basename(f)}' line {n + 2} has {len(row)} values but the header has {len(cols)}.")
                con.execute(f'INSERT INTO "{table}" VALUES ({",".join("?" * len(cols))})', row); n += 1
    con.commit(); con.close()
    return out


def _unique_col(db, table, cols):
    """Pick a column that identifies each row: prefer id-like names, and it must be unique and never empty."""
    pref = sorted(cols, key=lambda c: (0 if c.lower() == "id" else 1 if c.lower().endswith("_id") or c.lower().endswith("id") else 2, cols.index(c)))
    for c in pref:
        n, d, e = db.rows(f'SELECT COUNT(*), COUNT(DISTINCT "{c}"), SUM(CASE WHEN "{c}" IS NULL OR "{c}"=\'\' THEN 1 ELSE 0 END) FROM "{table}"')[0]
        if n and n == d and not e:
            return c
    return None


def build_config(src_path, tgt_path):
    s, t = DB(src_path), DB(tgt_path)
    notes, tables = [], []
    try:
        st, tt = s.tables(), t.tables()
        common = [x for x in st if x in tt]
        for x in st:
            if x not in tt: notes.append(f"Table '{x}' is in OLD but not in NEW (the audit will report this).")
        for x in tt:
            if x not in st: notes.append(f"Table '{x}' is in NEW but not in OLD.")
        for x in common:
            sc = [c for c, _ in s.columns(x)]; tc = [c for c, _ in t.columns(x)]
            same = [c for c in sc if c in tc]
            for c in sc:
                if c not in tc: notes.append(f"Table '{x}': column '{c}' is in OLD but not in NEW.")
            for c in tc:
                if c not in sc: notes.append(f"Table '{x}': column '{c}' is in NEW but not in OLD.")
            pk = _unique_col(s, x, sc)
            if not pk or pk not in tc:
                notes.append(f"Table '{x}' was skipped: no column in it uniquely identifies each row (like an ID).")
                continue
            tables.append({"source": x, "target": x, "pk": [pk], "columns": {c: c for c in same}, "required": [pk]})
    finally:
        s.close(); t.close()
    if not tables:
        raise EasyError("No table could be compared. The OLD and NEW data need at least one table with the same name and an ID column.")
    cfg = {"source": src_path, "target": tgt_path, "hmac_key_env": "DATAALIGN_HMAC_KEY", "query_timeout_s": 60,
           "source_system": "old", "target_system": "new", "tables": tables}
    return cfg, notes


def run_easy(folder="mydata", out="my_report", open_report=True, say=print):
    from .cli import execute
    from .core import default_suite
    os.environ.setdefault("DATAALIGN_HMAC_KEY", secrets.token_hex(24))
    work = os.path.join(out, "_work")
    say("Step 1 of 3: reading your OLD and NEW data (read-only)...")
    sp = prepare_side(os.path.join(folder, "old"), "old", work)
    tp = prepare_side(os.path.join(folder, "new"), "new", work)
    say("Step 2 of 3: matching tables and ID columns...")
    cfg, notes = build_config(sp, tp)
    for n in notes: say("  Note: " + n)
    say(f"  Comparing {len(cfg['tables'])} table(s): " + ", ".join(t["source"] for t in cfg["tables"]))
    rules_file = os.path.join(folder, "rules.csv")
    if os.path.exists(rules_file):
        n = apply_rules(cfg, rules_file)
        say(f"  Added {n} business rule(s) from {rules_file}")
    else:
        say("  No rules.csv found - business-rule checks will show as REVIEW (see mydata/rules_example.csv).")
    os.makedirs(out, exist_ok=True)
    json.dump(cfg, open(os.path.join(out, "config_used.json"), "w", encoding="utf-8"), indent=1)
    say("Step 3 of 3: running the checks (this can take a minute)...")
    rep = execute(cfg, default_suite(), out)
    s = rep["summary"]; html = os.path.abspath(os.path.join(out, "report.html"))
    say("")
    say(f"RESULT: {rep['overall']}   passed={s.get('PASS', 0)}  failed={s.get('FAIL', 0)}  needs review={s.get('REVIEW', 0)}  not tested={s.get('NOT_TESTED', 0)}")
    say("'Not tested' items are checks that need extra information (for example an approved mapping or evidence references).")
    say("They are listed honestly in the report - this quick mode never claims a pass it did not prove.")
    say(f"Report: {html}")
    if open_report:
        try:
            import webbrowser; webbrowser.open("file://" + html)
        except Exception:
            pass
    return rep, notes


# ---------------------------------------------------------------- business rules from a spreadsheet (rules.csv)
EMAIL = {"kind": "regex", "pattern": r"[^@\s]+@[^@\s]+\.[A-Za-z]{2,}", "examples": {"valid": ["a@b.co"], "invalid": ["not-an-email"]}}
RULE_HELP = ("required, allowed values, between, looks like email, is a date, matches pattern, old to new")


def _norm(s): return re.sub(r"\s+", " ", (s or "").strip().lower())


def apply_rules(cfg, path):
    """Read mydata/rules.csv (table, column, rule, value, applies_to) and add the rules to cfg. Returns how many rules were added.
    Raises EasyError with the line number for anything it cannot understand."""
    with open(path, newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.reader(fh))
    if not rows: raise EasyError("rules.csv is empty. Fill in the example rows (see rules_example.csv) or delete the file.")
    head = [_norm(h) for h in rows[0]]
    need = ["table", "column", "rule"]
    for n in need:
        if n not in head: raise EasyError(f"rules.csv needs a column called '{n}' in the first row (found: {', '.join(head) or 'nothing'}).")
    ix = {n: head.index(n) for n in head}
    by_table = {t["source"]: t for t in cfg["tables"]}
    added = 0
    for ln, r in enumerate(rows[1:], start=2):
        if not any(c.strip() for c in r): continue
        if r[0].strip().startswith("#"): continue
        get = lambda k: (r[ix[k]].strip() if k in ix and ix[k] < len(r) else "")
        table, col, rule, val, side = get("table"), get("column"), _norm(get("rule")), get("value"), _norm(get("applies_to")) or "new"
        where = f"rules.csv line {ln}"
        if table not in by_table:
            raise EasyError(f"{where}: table '{table}' is not one of the compared tables ({', '.join(by_table)}).")
        spec = by_table[table]
        if col not in spec["columns"]:
            raise EasyError(f"{where}: column '{col}' is not a column that exists in both OLD and NEW table '{table}'.")
        if side not in ("old", "new", "both"):
            raise EasyError(f"{where}: 'applies_to' must be old, new or both (you wrote '{side}').")
        if rule == "required":
            spec.setdefault("required", [])
            if col not in spec["required"]: spec["required"].append(col)
            added += 1; continue
        if rule == "old to new":
            pairs = {}
            for part in val.split(","):
                if "=" not in part: raise EasyError(f"{where}: 'old to new' needs pairs like A=ACTIVE, C=CLOSED (you wrote '{val}').")
                a, b = part.split("=", 1); pairs[a.strip()] = b.strip()
            spec.setdefault("transforms", {})[col] = {"kind": "map", "values": pairs}
            added += 1; continue
        if rule == "allowed values":
            vals = [v.strip() for v in val.split(",") if v.strip()]
            if not vals: raise EasyError(f"{where}: 'allowed values' needs a list like A,C.")
            new = {"kind": "in_set", "values": vals}
        elif rule == "between":
            m = re.fullmatch(r"\s*(-?[0-9.]*)\s*to\s*(-?[0-9.]*)\s*", val)
            if not m or not (m.group(1) or m.group(2)): raise EasyError(f"{where}: 'between' needs a value like 0 to 100 (you wrote '{val}').")
            new = {"kind": "range"}
            if m.group(1): new["min"] = m.group(1)
            if m.group(2): new["max"] = m.group(2)
        elif rule == "looks like email": new = dict(EMAIL)
        elif rule == "is a date": new = {"kind": "date"}
        elif rule == "matches pattern":
            try: re.compile(val)
            except re.error as e: raise EasyError(f"{where}: the pattern '{val}' is not valid ({e}).")
            new = {"kind": "regex", "pattern": val}
        else:
            raise EasyError(f"{where}: I do not know the rule '{get('rule')}'. Use one of: {RULE_HELP}.")
        if side in ("old", "both"): spec.setdefault("rules", {}).setdefault(col, []).append(new)
        if side in ("new", "both"): spec.setdefault("target_rules", {}).setdefault(col, []).append(new)
        added += 1
    return added
