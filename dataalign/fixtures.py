"""Synthetic insurance data: a clean source/target pair and a defective target with planted defects.
All data is fabricated (SSNs use the never-issued 9xx range, emails use example.com)."""
import os, random, sqlite3, unicodedata
from decimal import Decimal

FIRST = ["Alex", "Sam", "Priya", "Noor", "Wei", "Maria", "Ivan", "Fatima", "Chen", "Lena", "Omar", "Ana", "Kofi", "Yuki", "Tariq"]
LAST = ["Smith", "Patel", "Garcia", "Kim", "Okafor", "Novak", "Silva", "Haddad", "Ng", "Rossi", "Berg", "Cohen", "Reyes", "Sato"]
INVALID_POLICIES = [7, 77, 177]
TEST_CLAIMS, ORPHAN_CLAIMS, CDC_DELETED = list(range(601, 606)), [606, 607], [590, 591, 592]
CDC_UPDATED = list(range(10, 16))
N_POLICIES, AS_OF = 203, "2025-01-01 00:00:00"

def _ts(rng, y0=2023):
    return f"{rng.randint(y0, 2024)}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d} {rng.randint(0, 23):02d}:{rng.randint(0, 59):02d}:{rng.randint(0, 59):02d}"

def _money(rng, hi=25000):
    return f"{Decimal(rng.randint(100, hi * 100)) / 100:.2f}"

def source_rows():
    rng = random.Random(42)
    pol, valid_ids = [], []
    special = {10: {"premium": "0.00"}, 11: {"premium": "9999999.99"}, 20: {"start_date": "2024-02-29"},
               21: {"start_date": "2020-12-31"}, 22: {"start_date": "2016-01-01"},
               30: {"notes": 'Line1\r\nLine2, "quoted"; semi;colon'}, 31: {"notes": "Prefers e-mail • café"},
               32: {"notes": ""}, 40: {"notes": "Long note " * 20}, 60: {"holder_name": "Alex Kim"},
               63: {"premium": "1234.56"}, 64: {"premium": "1200.00"}, 65: {"holder_name": "José Álvarez"},
               66: {"holder_name": "René Müller"}, 67: {"start_date": "2023-02-28"}, 68: {"status": "A"},
               70: {"notes": "Standard"}, 71: {"notes": "Standard"}, 72: {"notes": "Standard"}}
    for i in range(1, N_POLICIES + 1):
        r = {"policy_id": i, "holder_name": f"{rng.choice(FIRST)} {rng.choice(LAST)}", "email": f"user{i}@example.com",
             "ssn": f"9{i % 100:02d}-{(i * 7) % 100:02d}-{1000 + i:04d}", "premium": _money(rng, 9999),
             "start_date": f"{rng.randint(2015, 2024)}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}",
             "status": rng.choice("AC"), "updated_at": _ts(rng),
             "notes": rng.choice([None, "Standard", "Renewal due", "Multi-policy discount"])}
        if i in INVALID_POLICIES: r["email"] = "not-an-email"
        r.update(special.get(i, {}))
        pol.append(r)
        if i not in INVALID_POLICIES: valid_ids.append(i)
    clm = []
    cspecial = {1: {"amount": "0.00"}, 2: {"amount": "9999999.99"}, 3: {"claim_date": "2024-02-29"}, 4: {"description": "Water damage in basement ... " * 9},
                5: {"description": ""}, 6: {"description": None}, 7: {"description": "Roof repair"}, 8: {"amount": "321.00"},
                15: {"amount": "777.77", "updated_at": "2024-12-30 23:59:59"}, 20: {"amount": "50.00"}, 21: {"amount": "0.30"},
                22: {"claim_date": "2024-06-15"}, 23: {"policy_id": 5}}
    for cid in list(range(1, 590)) + [593, 594, 595, 596, 597, 598, 599, 600] + CDC_DELETED + TEST_CLAIMS + ORPHAN_CLAIMS:
        r = {"claim_id": cid, "policy_id": rng.choice(valid_ids), "amount": _money(rng),
             "claim_date": f"{rng.randint(2022, 2024)}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}",
             "status": rng.choice(["OPEN", "PAID", "DENIED"]), "description": rng.choice(["Hail damage", "Collision", "Theft", "Fire", "Flood", "Windscreen"]),
             "updated_at": f"2024-{rng.randint(1, 11):02d}-{rng.randint(1, 28):02d} 10:00:00"}
        if cid in TEST_CLAIMS: r["status"] = "TEST"
        if cid in ORPHAN_CLAIMS: r["policy_id"] = 99000 + cid - 605
        r.update(cspecial.get(cid, {}))
        clm.append(r)
    clm = [c for c in clm if c["claim_id"] not in CDC_DELETED]       # deleted by CDC before the snapshot
    log, seq = [], 0
    def ev(op, key, minute):
        nonlocal seq; seq += 1
        log.append({"seq": seq, "event_id": f"E{seq:06d}", "table_name": "claims", "row_key": str(key), "op": op,
                    "ts": f"2024-12-{1 + minute // 1440:02d} {(minute // 60) % 24:02d}:{minute % 60:02d}:00"})
    m = 0
    for k in CDC_UPDATED + CDC_DELETED: m += 5; ev("I", k, m)
    for k in CDC_UPDATED: m += 5; ev("U", k, m)
    for k in CDC_DELETED: m += 5; ev("D", k, m)
    return pol, clm, log

def _target_policies(pol):
    out = []
    for r in pol:
        if r["policy_id"] in INVALID_POLICIES: continue
        s = r["ssn"]
        out.append({"policy_id": r["policy_id"], "customer_name": r["holder_name"], "email": r["email"], "ssn": "***-**-" + s[-4:],
                    "premium": r["premium"], "start_date": r["start_date"], "status": {"A": "ACTIVE", "C": "CLOSED"}[r["status"]],
                    "updated_at": r["updated_at"], "notes": r["notes"]})
    return out

def _target_claims(clm):
    return [dict(c, claim_ref=f"CLM-{c['claim_id']}") for c in clm if c["status"] != "TEST" and c["claim_id"] not in ORPHAN_CLAIMS]

def _create(path, ddl, data, extra=None):
    if os.path.exists(path): os.remove(path)
    con = sqlite3.connect(path)
    for t, cols, rows in ddl:
        con.execute(f"CREATE TABLE {t} ({', '.join(cols)})")
        names = [c.split()[0] for c in cols]
        con.executemany(f"INSERT INTO {t} ({','.join(names)}) VALUES ({','.join('?' * len(names))})", [[r.get(n) for n in names] for r in rows])
    con.commit(); con.close()

POL_S = ["policy_id INTEGER PRIMARY KEY", "holder_name TEXT", "email TEXT", "ssn TEXT", "premium TEXT", "start_date TEXT", "status TEXT", "updated_at TEXT", "notes TEXT"]
CLM_S = ["claim_id INTEGER PRIMARY KEY", "policy_id INTEGER", "amount TEXT", "claim_date TEXT", "status TEXT", "description TEXT", "updated_at TEXT"]
LOG_S = ["seq INTEGER", "event_id TEXT", "table_name TEXT", "row_key TEXT", "op TEXT", "ts TEXT"]
POL_T = ["policy_id INTEGER", "customer_name TEXT", "email TEXT", "ssn TEXT", "premium TEXT", "start_date TEXT", "status TEXT", "updated_at TEXT", "notes TEXT"]
CLM_T = ["claim_id INTEGER", "policy_id INTEGER", "amount TEXT", "claim_date TEXT", "status TEXT", "description TEXT", "updated_at TEXT", "claim_ref TEXT"]

def build_pair(directory, defective=False):
    os.makedirs(directory, exist_ok=True)
    tag = "defective" if defective else "clean"
    spath, tpath = os.path.join(directory, f"source_{tag}.db"), os.path.join(directory, f"target_{tag}.db")
    pol, clm, log = source_rows()
    tpol, tclm = _target_policies(pol), _target_claims(clm)
    rejected = [{"table_name": "policies", "row_key": str(k), "reason": "invalid email"} for k in INVALID_POLICIES] + \
               [{"table_name": "claims", "row_key": str(k), "reason": "orphan policy_id"} for k in ORPHAN_CLAIMS]
    wm = {"table_name": "claims", "last_seq": max(e["seq"] for e in log)}
    clm_t_cols, pol_t_cols = list(CLM_T), list(POL_T)
    if defective:
        log = log + [{"seq": log[-1]["seq"] + 1, "event_id": "E000007", "table_name": "claims", "row_key": "590", "op": "I", "ts": "2024-12-01 00:35:00"}]
        clm_t_cols[2] = "amount REAL"; pol_t_cols.append("legacy_flag TEXT")
        wm["last_seq"] = wm["last_seq"] - 3
        P = {r["policy_id"]: r for r in tpol}; C = {r["claim_id"]: r for r in tclm}
        for k in (50, 51): tpol.remove(P[k])                                              # D1 missing rows
        tpol.append(dict(P[52], policy_id=9999, email="ghost@example.com"))                # D2 extra row
        tpol.append(dict(P[53]))                                                           # D3 duplicate row (same key + business key)
        P[60]["customer_name"] += " "                                                      # D4 trailing whitespace
        P[61]["email"] = P[61]["email"].upper()                                            # D6 case change
        P[62]["email"] = "other62@example.com"                                             # D19 wrong email
        P[63]["premium"] = "1234.5"                                                        # D7 precision loss
        P[64]["premium"] = "1.2E3"                                                         # D9 scientific notation (numerically equal)
        import unicodedata as u
        P[65]["customer_name"] = u.normalize("NFD", P[65]["customer_name"])               # D10 NFD
        P[66]["customer_name"] = "RenÃ© MÃ¼ller"                       # D11 mojibake
        P[67]["start_date"] = "2023-02-30"                                                 # D12 invalid date
        P[68]["status"] = "CLOSED"                                                         # D15 wrong mapping
        tpol.append(dict(next(r for r in pol_src_target(pol) if r["policy_id"] == 7)))     # D17 invalid row loaded
        P[70]["notes"] = "SSN 900-55-4444 on file"                                         # D18 PII in free text
        P[71]["notes"] = "api_key=ABCD1234EFGH5678"                                        # D18 secret in free text
        P[72]["notes"] = "card 4111111111111111"                                           # D18 / PCI
        P[73]["ssn"] = [r for r in pol if r["policy_id"] == 73][0]["ssn"]                  # D27 unmasked SSN
        C[20]["amount"] = -50.0                                                            # D16 negative amount
        C[21]["amount"] = 0.1 + 0.2                                                        # D8 float artefact
        C[22]["claim_date"] = "2099-01-01"                                                 # D13 future date
        C[23]["policy_id"] = 88888                                                         # D14 orphan
        C[15]["amount"], C[15]["updated_at"] = "700.00", "2024-12-10 09:00:00"             # D22 stale
        C[5]["description"] = None                                                         # D23 '' -> NULL
        C[7]["description"] = None                                                         # D28 value lost
        C[4]["description"] = C[4]["description"][:20]                                     # D5 truncation
        C[3]["claim_date"] = "2024-03-01"                                                  # D25 leap day
        C[2]["amount"] = "100000000.00"                                                    # D26 overflow
        C[8]["amount"] = None                                                              # D29 required null
        tclm.append(dict([c for c in clm if c["claim_id"] == 1][0], claim_id=590, claim_ref="CLM-590"))  # D20 deleted key resurrected
        for r in tpol: r.setdefault("legacy_flag", None)
    _create(spath, [("policies", POL_S, pol), ("claims", CLM_S, clm), ("change_log", LOG_S, log)], None)
    _create(tpath, [("policies", pol_t_cols, tpol), ("claims", clm_t_cols, tclm),
                    ("rejected_rows", ["table_name TEXT", "row_key TEXT", "reason TEXT"], rejected),
                    ("_watermark", ["table_name TEXT", "last_seq INTEGER"], [wm])], None)
    return spath, tpath

def pol_src_target(pol):                      # target-shaped copy of a source policy (used to plant an invalid row)
    return [{"policy_id": r["policy_id"], "customer_name": r["holder_name"], "email": r["email"], "ssn": "***-**-" + r["ssn"][-4:],
             "premium": r["premium"], "start_date": r["start_date"], "status": {"A": "ACTIVE", "C": "CLOSED"}[r["status"]],
             "updated_at": r["updated_at"], "notes": r["notes"]} for r in pol]

def demo_config(spath, tpath, previous_results=None):
    email = {"kind": "regex", "pattern": r"[^@\s]+@[^@\s]+\.[A-Za-z]{2,}", "examples": {"valid": ["a@b.co"], "invalid": ["not-an-email"]}}
    pol_rules = {"email": [email], "status": [{"kind": "in_set", "values": ["A", "C"]}], "premium": [{"kind": "range", "min": "0", "max": "99999999.99"}],
                 "start_date": [{"kind": "date"}]}
    cfg = {
        "source": spath, "target": tpath, "as_of": AS_OF, "hmac_key_env": "DATAALIGN_HMAC_KEY", "query_timeout_s": 30,
        "source_system": "demo-legacy-sqlite", "target_system": "demo-cloud-sqlite", "batch_id": "BATCH-2025-01-01",
        "snapshot_id": "SNAP-001", "transform_version": "T-1.0", "retention_days": 365,
        "mapping": {"approved": True, "version": "1.0", "approved_by": "qa.lead", "approved_type_changes": []},
        "evidence": {"encryption_at_rest": "DOC-ENC-001", "encryption_in_transit": "DOC-TLS-002"},
        "compliance": {"gdpr": {"lawful_basis_ref": "LB-12", "retention_days": 365, "dsar_process_ref": "DSAR-3"},
                       "ccpa": {"opt_out_ref": "OPT-1", "deletion_ref": "DEL-2"}},
        "cdc": {"table": "claims", "log_table": "change_log", "watermark_table": "_watermark"},
        "baseline_schema": {"policies": {c.split()[0]: c.split()[1] for c in POL_T}, "claims": {c.split()[0]: c.split()[1] for c in CLM_T}},
        "tables": [
         {"source": "policies", "target": "policies", "pk": ["policy_id"], "business_key": ["email"],
          "columns": {"policy_id": "policy_id", "holder_name": "customer_name", "email": "email", "ssn": "ssn", "premium": "premium",
                      "start_date": "start_date", "status": "status", "updated_at": "updated_at", "notes": "notes"},
          "transforms": {"status": {"kind": "map", "values": {"A": "ACTIVE", "C": "CLOSED"}}},
          "decimals": {"premium": 2}, "precision": {"premium": [10, 2]}, "dates": ["start_date", "updated_at"], "updated_col": "updated_at",
          "partition": "status", "distinct": ["status"], "required": ["policy_id", "email", "start_date"], "rules": pol_rules,
          "target_rules": {"email": [email], "status": [{"kind": "in_set", "values": ["ACTIVE", "CLOSED"]}],
                           "premium": [{"kind": "range", "min": "0", "max": "99999999.99"}], "start_date": [{"kind": "date"}]},
          "pii": {"holder_name": {"class": "person_name", "mode": "clear"}, "email": {"class": "email", "mode": "hmac"},
                  "ssn": {"class": "government_id", "mode": "masked", "mask_regex": r"\*{3}-\*{2}-\d{4}", "keep_last": 4}},
          "rejects": {"table": "rejected_rows", "key_col": "row_key", "table_col": "table_name"}},
         {"source": "claims", "target": "claims", "pk": ["claim_id"],
          "derived": {"claim_ref": {"template": "CLM-{claim_id}"}},
          "decimals": {"amount": 2}, "precision": {"amount": [10, 2]}, "dates": ["claim_date", "updated_at"], "updated_col": "updated_at",
          "partition": "status", "distinct": ["status", "policy_id"], "group_by": "status", "required": ["claim_id", "policy_id", "amount"],
          "filter": {"exclude": {"column": "status", "in": ["TEST"]}},
          "rules": {"amount": [{"kind": "range", "min": "0"}], "claim_date": [{"kind": "date"}]},
          "target_rules": {"amount": [{"kind": "range", "min": "0"}], "claim_date": [{"kind": "date"}],
                           "status": [{"kind": "in_set", "values": ["OPEN", "PAID", "DENIED"]}]},
          "fks": [{"col": "policy_id", "ref_table": "policies", "ref_col": "policy_id", "sum_col": "amount"}],
          "rejects": {"table": "rejected_rows", "key_col": "row_key", "table_col": "table_name"}},
        ]}
    if previous_results: cfg["previous_results"] = previous_results
    return cfg
