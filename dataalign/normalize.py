"""Canonical normalisation, hashing and exact decimal handling."""
import hashlib, hmac, json, re, unicodedata
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

NORMALIZATION_VERSION = "1.0"

def parse_decimal(v):
    if v is None:
        return None
    if isinstance(v, Decimal):
        return v
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return Decimal(v)
    if isinstance(v, float):
        return Decimal(repr(v))
    s = str(v).strip().replace(" ", "").replace(" ", "")
    if s == "":
        return None
    if re.fullmatch(r"-?\d{1,3}(\.\d{3})+,\d+", s):      # 1.234,56
        s = s.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"-?\d{1,3}(,\d{3})+(\.\d+)?", s):  # 1,234.56
        s = s.replace(",", "")
    elif re.fullmatch(r"-?\d+,\d+", s):                   # 12,5
        s = s.replace(",", ".")
    try:
        d = Decimal(s)
    except InvalidOperation:
        return None
    return d if d.is_finite() else None

def quantize(d, places=2):
    return d.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)

def canon_decimal(d):
    s = format(d.normalize(), "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s

def norm_text(v):
    if v is None:
        return None
    s = unicodedata.normalize("NFC", str(v)).strip()
    return re.sub(r"\s+", " ", s)

def _tag(v):
    if v is None:
        return "N", None
    d = parse_decimal(v) if not isinstance(v, str) else None
    if isinstance(v, (int, float, Decimal)) and not isinstance(v, bool) and d is not None:
        return "D", canon_decimal(d)
    return "S", str(v)   # exact text: no trimming or Unicode normalisation (those are detected, never hidden)

def canonical_bytes(row, cols):
    arr = []
    for c in cols:
        t, val = _tag(row.get(c))
        arr.append([c, t, val])
    return json.dumps(arr, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

def row_hash(row, cols):
    return hashlib.sha256(canonical_bytes(row, cols)).hexdigest()

def hmac_hex(key, value):
    if isinstance(key, str):
        key = key.encode()
    return hmac.new(key, norm_text(value).encode("utf-8"), hashlib.sha256).hexdigest()
