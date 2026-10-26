"""Rule-based eligibility checks. Demo thresholds must be replaced with official scheme rules."""
from datetime import date, datetime
import json
from pathlib import Path

DEFAULT_RULES_PATH = Path(__file__).with_name("rules.json")


def _parse_date(value):
    if not value:
        return None
    text = str(value).strip()
    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y", "%Y-%m-%d", "%d-%b-%Y", "%d %b %Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    return None


def age_of(dob, today=None):
    born = _parse_date(dob)
    if not born:
        return None
    today = today or date.today()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


def load_rules(path=DEFAULT_RULES_PATH):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def check_rules(docs, rules=None, today=None):
    """Return list of {rule, status, reason}; status is pass/fail/unknown."""
    rules = rules or load_rules()
    today = today or date.today()
    docs = docs or []
    result = []

    def add(rule, status, reason):
        result.append({"rule": rule, "status": status, "reason": reason})

    types = {str(d.get("type") or d.get("doc_type") or "").lower(): d for d in docs}
    for dtype in rules.get("required_docs", []):
        if dtype not in types:
            add("required_doc:" + dtype, "fail", f"Required document '{dtype}' is missing")
        else:
            add("required_doc:" + dtype, "pass", f"Required document '{dtype}' is present")

    aadhaar = types.get("aadhaar", {})
    dob = aadhaar.get("dob")
    age = age_of(dob, today)
    if age is None:
        add("age", "unknown", "Date of birth could not be read; manual check or re-upload needed")
    elif age < rules.get("min_age", 0) or age > rules.get("max_age", 200):
        add("age", "fail", f"Age {age} is outside the allowed range")
    else:
        add("age", "pass", f"Age {age} is within the allowed range")

    marksheet = types.get("marksheet", {})
    pct = marksheet.get("percentage")
    try:
        pct = float(pct) if pct not in (None, "") else None
    except (ValueError, TypeError):
        pct = None
    if pct is None and marksheet.get("marks") not in (None, "") and marksheet.get("total") not in (None, "", 0, "0"):
        try:
            marks, total = float(marksheet["marks"]), float(marksheet["total"])
            if total > 0 and marks <= total:
                pct = marks / total * 100
        except (ValueError, TypeError):
            pass
    if pct is None:
        add("minimum_percentage", "unknown", "Percentage could not be calculated from readable marks")
    elif pct < rules.get("min_percentage", 0):
        add("minimum_percentage", "fail", f"Percentage {pct:.1f}% is below the scheme minimum")
    else:
        add("minimum_percentage", "pass", f"Percentage {pct:.1f}% meets the scheme minimum")

    income_doc = types.get("income_certificate", {})
    income = income_doc.get("income")
    try:
        income = float(str(income).replace(",", "")) if income not in (None, "") else None
    except (ValueError, TypeError):
        income = None
    if income is None:
        add("family_income", "unknown", "Family income could not be read")
    elif income > rules.get("max_family_income", float("inf")):
        add("family_income", "fail", f"Family income {income:.0f} exceeds the scheme limit")
    else:
        add("family_income", "pass", f"Family income {income:.0f} is within the scheme limit")

    max_age_days = rules.get("income_certificate_max_age_days")
    issued = _parse_date(income_doc.get("issue_date"))
    if max_age_days is not None:
        if issued is None:
            add("income_certificate_freshness", "unknown", "Income certificate issue date could not be read")
        else:
            age_days = (today - issued).days
            if age_days < 0:
                add("income_certificate_freshness", "fail", "Income certificate issue date is in the future")
            elif age_days > max_age_days:
                add("income_certificate_freshness", "fail", "Income certificate is older than the allowed period")
            else:
                add("income_certificate_freshness", "pass", "Income certificate is within the allowed period")
    return result
