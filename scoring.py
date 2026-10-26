"""Transparent prototype risk scoring. Scores are rule penalties, NOT fraud probabilities."""

# Configure these weights with the team before presenting as final policy.
FLAG_WEIGHTS = {
    "CHECKSUM_FAIL": 40,
    "AADHAAR_FORMAT": 40,
    "ID_MISMATCH": 25,
    "NAME_MISMATCH": 25,
    "NAME_FUZZY_MISMATCH": 10,
    "DOB_MISMATCH": 20,
    "MARKS_INCONSISTENT": 25,
    "PERCENTAGE_MISMATCH": 25,
    "INCOME_MISMATCH": 25,
    "MISSING_DOC": 10,
    "MISSING_FIELD": 10,
    "UNREADABLE_FIELD": 10,
    "UNKNOWN_DOC": 10,
    "ISSUE_DATE_FUTURE": 15,
    "DUPLICATE_DOCUMENT": 30,
    "TAMPERING_SUSPECTED": 20,
    "ELA_TAMPERING_SUSPECTED": 20,
    "EDITOR_METADATA": 10,
    "QR_MISMATCH": 25,
}
SEVERITY_DEFAULTS = {"high": 20, "medium": 10, "low": 5}


def score_flags(flags):
    """Sum flag penalties with a 100-point cap. Unknown codes use severity defaults."""
    total = 0
    scored = []
    for flag in flags or []:
        code = str(flag.get("code", "UNKNOWN"))
        severity = str(flag.get("severity", "medium")).lower()
        weight = FLAG_WEIGHTS.get(code, SEVERITY_DEFAULTS.get(severity, 10))
        total += weight
        scored.append({**flag, "weight": weight})
    return min(total, 100), scored


def decide(flags, eligibility):
    score, scored_flags = score_flags(flags)
    failures = [item for item in (eligibility or []) if item.get("status") == "fail"]
    unknowns = [item for item in (eligibility or []) if item.get("status") == "unknown"]
    if score >= 60:
        decision = "MANUAL REVIEW - HIGH RISK"
    elif failures:
        decision = "NOT ELIGIBLE"
    elif unknowns:
        decision = "MANUAL REVIEW - INCOMPLETE DATA"
    elif score >= 30:
        decision = "MANUAL REVIEW"
    else:
        decision = "ELIGIBILITY CHECK PASSED - HUMAN REVIEW REQUIRED"
    return {
        "score": score,
        "decision": decision,
        "flags": scored_flags,
        "eligibility": eligibility or [],
        "score_is_probability": False,
    }
