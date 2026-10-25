"""Validation module (Person 2) for the scholarship verifier.

validate(form, docs) -> list of flags, each {"code", "severity", "reason", "source"}.

`docs` is a list of what Person 1's extract(path) returns, for example:
  {"type": "aadhaar", "name": "...", "dob": "14/03/2005", "id_number": "234567890124", "path": "aadhaar.jpg", ...}
  {"type": "income_certificate", "name": "...", "income": 420000, "issue_date": "10/06/2026", ...}
  {"type": "marksheet", "name": "...", "marks": 432, "total": 500, "percentage": 86.4, ...}
The older nested format {"doc_type", "fields": {...}} is also accepted.

`form` is the applicant's form, for example:
  {"name": "Ananya Sharma", "dob": "14/03/2005", "aadhaar": "234567890123",
   "income": 420000, "percentage": 86.4}
"""
from datetime import date

import verhoeff
from common import (HIGH, LOW, MEDIUM, NAME_OK, NAME_REVIEW, PERCENT_CONSISTENCY, PERCENT_TOLERANCE,
                    is_masked, make_flag, name_similarity, normalize_date, normalize_name,
                    only_digits, parse_date, to_number)

REQUIRED_DOCS = ["aadhaar", "income_certificate", "marksheet"]
REQUIRED_FORM_FIELDS = ["name", "dob", "aadhaar"]
FIELDS = ("name", "dob", "id_number", "marks", "total", "percentage", "income", "issue_date")


def adapt(doc):
    """Turn extract() output into {"doc_type", "fields", "path"} (nested input passes through)."""
    if "fields" in doc:
        return {"doc_type": doc.get("doc_type"), "fields": doc["fields"], "path": doc.get("path", "")}
    return {"doc_type": doc.get("type") or doc.get("doc_type"),
            "fields": {k: doc.get(k) for k in FIELDS}, "path": doc.get("path", "")}


# ---------- completeness ----------
def check_completeness(form, docs, required_docs):
    flags = []
    for field in REQUIRED_FORM_FIELDS:
        if not form.get(field):
            flags.append(make_flag("MISSING_FIELD", HIGH, f"Form field '{field}' is empty"))
    present = {d["doc_type"] for d in docs}
    for doc_type in required_docs:
        if doc_type not in present:
            flags.append(make_flag("MISSING_DOC", HIGH, f"Required document '{doc_type}' was not uploaded"))
    return flags


# ---------- single-field comparisons ----------
def compare_names(a, b, label):
    na, nb = normalize_name(a), normalize_name(b)
    if not na or not nb:
        return []
    score = name_similarity(na, nb)
    if score >= NAME_OK:
        return []
    if score >= NAME_REVIEW:
        return [make_flag("NAME_FUZZY_MISMATCH", MEDIUM, f"{label}: names are similar but not identical ({score:.0f}% match)")]
    return [make_flag("NAME_MISMATCH", HIGH, f"{label}: names differ ({score:.0f}% match)")]


def compare_dates(a, b, label):
    da, db = normalize_date(a), normalize_date(b)
    if da and db and da != db:
        return [make_flag("DOB_MISMATCH", HIGH, f"{label}: date of birth {da} vs {db}")]
    return []


def check_aadhaar_number(number):
    """Format and Verhoeff checksum. Masked numbers cannot be checked."""
    if is_masked(number):
        return []
    digits = only_digits(number)
    if len(digits) != 12 or digits[0] in "01":
        return [make_flag("AADHAAR_FORMAT", HIGH, "Aadhaar must have 12 digits and cannot start with 0 or 1")]
    if not verhoeff.validate(digits):
        return [make_flag("CHECKSUM_FAIL", HIGH, "Aadhaar check digit is invalid (number may be altered)")]
    return []


def compare_aadhaar(form_value, doc_value, label):
    a, b = only_digits(form_value), only_digits(doc_value)
    if not a or not b:
        return []
    if is_masked(form_value) or is_masked(doc_value):
        return [] if a[-4:] == b[-4:] else [make_flag("ID_MISMATCH", HIGH, f"{label}: last 4 digits differ")]
    return [] if a == b else [make_flag("ID_MISMATCH", HIGH, f"{label}: Aadhaar number differs from the form")]


# ---------- per-document checks ----------
def check_marksheet(f, form):
    flags = []
    marks, total, pct = to_number(f.get("marks")), to_number(f.get("total")), to_number(f.get("percentage"))
    if marks is None and pct is None:
        return [make_flag("UNREADABLE_FIELD", MEDIUM, "Marksheet: marks and percentage could not be read")]
    if marks is not None and total:
        if marks > total:
            flags.append(make_flag("MARKS_INCONSISTENT", HIGH, f"Marksheet: marks obtained ({marks:g}) exceed total ({total:g})"))
        elif pct is not None and abs(marks / total * 100 - pct) > PERCENT_CONSISTENCY:
            flags.append(make_flag("MARKS_INCONSISTENT", HIGH,
                                   f"Marksheet: {marks:g}/{total:g} is {marks / total * 100:.1f}% but percentage shows {pct:g}%"))
    form_pct = to_number(form.get("percentage"))
    if form_pct is not None and pct is not None and abs(form_pct - pct) > PERCENT_TOLERANCE:
        flags.append(make_flag("PERCENTAGE_MISMATCH", HIGH, f"Marksheet shows {pct:g}% but the form says {form_pct:g}%"))
    return flags


def check_income_certificate(f, form, today):
    flags = []
    income = to_number(f.get("income"))
    if income is None:
        flags.append(make_flag("UNREADABLE_FIELD", MEDIUM, "Income certificate: income amount could not be read"))
    else:
        form_income = to_number(form.get("income", form.get("annual_income")))
        if form_income is not None and form_income != income:
            flags.append(make_flag("INCOME_MISMATCH", HIGH,
                                   f"Income certificate shows {income:,.0f} but the form says {form_income:,.0f}"))
    issued = parse_date(f.get("issue_date"))
    if issued and issued > today:
        flags.append(make_flag("ISSUE_DATE_FUTURE", MEDIUM, f"Income certificate issue date {issued:%d-%m-%Y} is in the future"))
    return flags


# ---------- main entry ----------
def validate(form, docs, required_docs=None, today=None):
    form = form or {}
    docs = [adapt(d) for d in (docs or [])]
    today = today or date.today()
    flags = check_completeness(form, docs, required_docs or REQUIRED_DOCS)

    for d in docs:
        dtype, f, label = d["doc_type"], d["fields"], (d["doc_type"] or "document").replace("_", " ").capitalize()
        if dtype in (None, "unknown"):
            flags.append(make_flag("UNKNOWN_DOC", MEDIUM, f"Could not identify the document type of {d['path'] or 'an upload'}"))
            continue
        flags += compare_names(form.get("name"), f.get("name"), f"{label} vs form")
        flags += compare_dates(form.get("dob"), f.get("dob"), f"{label} vs form")
        if dtype == "aadhaar":
            if not f.get("id_number"):
                flags.append(make_flag("UNREADABLE_FIELD", MEDIUM, "Aadhaar: number could not be read"))
            else:
                flags += check_aadhaar_number(f["id_number"])
        elif dtype == "marksheet":
            flags += check_marksheet(f, form)
        elif dtype == "income_certificate":
            flags += check_income_certificate(f, form, today)
        if f.get("id_number"):
            flags += compare_aadhaar(form.get("aadhaar"), f["id_number"], f"{label} vs form")

    # document vs document: Aadhaar against the others
    aadhaar = next((d["fields"] for d in docs if d["doc_type"] == "aadhaar"), None)
    if aadhaar:
        for d in docs:
            if d["doc_type"] in ("income_certificate", "marksheet"):
                label = d["doc_type"].replace("_", " ").capitalize()
                flags += compare_names(aadhaar.get("name"), d["fields"].get("name"), f"Aadhaar vs {label.lower()}")
                flags += compare_dates(aadhaar.get("dob"), d["fields"].get("dob"), f"Aadhaar vs {label.lower()}")
    return flags


if __name__ == "__main__":
    import json
    form = {"name": "Ananya Sharma", "dob": "14/03/2005", "aadhaar": "234567890124", "income": 420000, "percentage": 86.4}
    docs = [{"type": "income_certificate", "name": "ANANYA SHARMA", "income": 380000, "issue_date": "10/06/2026", "path": "income.jpg"}]
    print(json.dumps(validate(form, docs), indent=2))
