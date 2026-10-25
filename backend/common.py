"""Shared helpers for the validation module (used by validate.py and tests)."""
import re
from datetime import datetime

# Flag severities, used by Person 4 for scoring
LOW, MEDIUM, HIGH = "low", "medium", "high"

# Thresholds (0-100) for fuzzy name matching. Tune these on your sample set.
NAME_OK = 95        # at or above: treated as the same name
NAME_REVIEW = 80    # between NAME_REVIEW and NAME_OK: medium flag, below: high flag
LOW_CONFIDENCE = 0.60
PERCENT_TOLERANCE = 0.5    # form % vs marksheet %
PERCENT_CONSISTENCY = 1.0  # marks/total*100 vs printed %

try:
    from rapidfuzz import fuzz

    def name_similarity(a: str, b: str) -> float:
        """0-100 similarity that ignores word order ('Sharma Ananya' == 'Ananya Sharma')."""
        return float(fuzz.token_sort_ratio(a, b))
except ImportError:  # fallback so the code still runs without rapidfuzz installed
    from difflib import SequenceMatcher

    def name_similarity(a: str, b: str) -> float:
        a = " ".join(sorted(a.split()))
        b = " ".join(sorted(b.split()))
        return 100.0 * SequenceMatcher(None, a, b).ratio()


def make_flag(code: str, severity: str, reason: str) -> dict:
    """Flag in the shared team format: {"code", "severity", "reason"}."""
    return {"code": code, "severity": severity, "reason": reason, "source": "validation"}


def normalize_name(name) -> str:
    """Uppercase, strip titles and punctuation, collapse spaces."""
    if not name:
        return ""
    s = re.sub(r"[^A-Za-z\s]", " ", str(name)).upper()
    s = re.sub(r"\b(MR|MRS|MS|SHRI|SMT|KUMARI|DR)\b", " ", s)
    return " ".join(s.split())


_DATE_FORMATS = ["%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y", "%Y-%m-%d", "%d %m %Y", "%d-%b-%Y", "%d %b %Y"]


def normalize_date(value):
    """Return date as 'DD-MM-YYYY', or None if it cannot be parsed."""
    if not value:
        return None
    text = str(value).strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).strftime("%d-%m-%Y")
        except ValueError:
            continue
    return None


def parse_date(value):
    """Return a datetime.date, or None if the value cannot be parsed."""
    text = normalize_date(value)
    return datetime.strptime(text, "%d-%m-%Y").date() if text else None


def to_number(value):
    """Convert 86.4 / '86.4' / '4,20,000' to a float, or None."""
    if value is None or value == "":
        return None
    try:
        return float(str(value).replace(",", "").strip())
    except ValueError:
        return None


def only_digits(value) -> str:
    return re.sub(r"\D", "", str(value or ""))


def is_masked(value) -> bool:
    """True for numbers like 'XXXX XXXX 3456'."""
    return bool(re.search(r"[Xx*]", str(value or "")))


def normalize_id(value) -> str:
    """Uppercase, no spaces: ' abcps 1234d ' -> 'ABCPS1234D'."""
    return re.sub(r"\s+", "", str(value or "")).upper()
