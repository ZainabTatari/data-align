"""Column-mapping suggestions. Deterministic scoring; an AI model may add semantic hints but never approves."""
import difflib, re

SYNONYMS = [{"name", "fullname", "customer_name", "holder_name", "client_name"},
            {"dob", "birth_date", "date_of_birth"}, {"phone", "mobile", "telephone", "tel"},
            {"email", "email_address", "mail"}, {"amount", "amt", "total", "value"},
            {"created_at", "created", "create_date"}, {"updated_at", "modified_at", "last_modified"}]

def _n(s): return re.sub(r"[^a-z0-9]", "", s.lower())

def suggest(src_cols, tgt_cols):
    out, used = [], set()
    for s in src_cols:
        if s in tgt_cols:
            out.append({"source": s, "target": s, "confidence": 1.0, "evidence": "identical name",
                        "requires_approval": False})
            used.add(s); continue
        best, score, why = None, 0.0, ""
        for t in tgt_cols:
            if t in used or t in src_cols:
                continue
            r = difflib.SequenceMatcher(None, _n(s), _n(t)).ratio()
            syn = any(s.lower() in g and t.lower() in g for g in SYNONYMS)
            sc = max(r, 0.85 if syn else 0)
            if sc > score:
                best, score, why = t, sc, ("synonym group" if syn else f"name similarity {r:.2f}")
        if best and score >= 0.6:
            used.add(best)
            out.append({"source": s, "target": best, "confidence": round(score, 2), "evidence": why,
                        "requires_approval": True})
        else:
            out.append({"source": s, "target": None, "confidence": 0.0, "evidence": "no candidate",
                        "requires_approval": True})
    return out

def type_class(decl):
    d = (decl or "").upper()
    if "INT" in d: return "integer"
    if any(x in d for x in ("CHAR", "CLOB", "TEXT")): return "text"
    if any(x in d for x in ("REAL", "FLOA", "DOUB")): return "float"
    if any(x in d for x in ("DEC", "NUM")): return "decimal"
    if "BLOB" in d: return "blob"
    if any(x in d for x in ("DATE", "TIME")): return "datetime"
    return "other"

def declared_len(decl):
    m = re.search(r"\((\d+)", decl or "")
    return int(m.group(1)) if m else None
