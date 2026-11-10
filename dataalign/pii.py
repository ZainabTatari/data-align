"""PII detection patterns and leak scanning."""
import re

NAME_PATTERNS = [
 ("email", r"e[-_]?mail"), ("government_id", r"ssn|social|passport|national_id|tax_id|licen[sc]e"),
 ("phone", r"phone|mobile|tel(?:ephone)?\b"), ("date_of_birth", r"dob|birth"),
 ("person_name", r"(^|_)(first|last|full|holder|customer|client|patient)?_?name($|_)"),
 ("address", r"address|street|postcode|zip"), ("financial", r"card|\bpan\b|iban|account_?(no|num)|routing"),
 ("health", r"diagnos|mrn|patient|icd|medical|prescri"), ("credential", r"passw|secret|token|api_?key"),
 ("employee", r"salary|employee|payroll"),
]

def luhn(num):
    ds = [int(c) for c in num][::-1]
    t = sum(ds[0::2]) + sum(sum(divmod(2 * d, 10)) for d in ds[1::2])
    return t % 10 == 0

CONTENT = {
 "email": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
 "us_ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
 "phone": re.compile(r"\b\(?\d{3}\)?[-. ]\d{3}[-. ]\d{4}\b"),
 "card_number": re.compile(r"\b\d{13,19}\b"),
 "aws_access_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
 "jwt": re.compile(r"\beyJ[\w-]{5,}\.[\w-]{5,}\.[\w-]{5,}\b"),
 "secret_assignment": re.compile(r"(?i)\b(api[_-]?key|secret|token|password|passwd)\s*[:=]\s*\S{8,}"),
}
SECRET_CLASSES = {"aws_access_key", "jwt", "secret_assignment"}

def classify_text(s):
    """Return set of PII/secret classes found in a string."""
    out = set()
    for name, rx in CONTENT.items():
        for m in rx.finditer(s):
            if name == "card_number" and not luhn(m.group(0)):
                continue
            out.add(name)
    return out

def name_class(col):
    for cls, pat in NAME_PATTERNS:
        if re.search(pat, col, re.I):
            return cls
    return None

def pii_values(ctx):
    vals = set()
    for sp in ctx.specs:
        d = ctx.load(sp)
        for col in sp["pii"]:
            for r in d["srows"]:
                v = r.get(col)
                if isinstance(v, str) and len(v) >= 5: vals.add(v)
            for r in d["trows"]:
                v = r.get(col)
                if isinstance(v, str) and len(v) >= 5: vals.add(v)
    return vals

def leak_scan(text, ctx):
    """Return list of leak descriptions (never the leaked value)."""
    leaks = []
    for v in pii_values(ctx):
        if v in text: leaks.append("declared-PII value present")
    for cls in classify_text(text):
        leaks.append(f"pattern:{cls}")
    if ctx.hmac_key:
        k = ctx.hmac_key if isinstance(ctx.hmac_key, str) else ctx.hmac_key.decode("utf-8", "ignore")
        if k and k in text: leaks.append("HMAC key present")
    return leaks
