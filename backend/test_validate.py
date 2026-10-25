"""Run with:  python test_validate.py   (no pytest needed)"""
from datetime import date

import verhoeff
from common import normalize_date, normalize_name, parse_date, to_number
from validate import adapt, validate

AADHAAR = "23456789012" + verhoeff.generate("23456789012")      # valid dummy number
BAD_AADHAAR = AADHAAR[:-1] + str((int(AADHAAR[-1]) + 1) % 10)    # wrong check digit
TODAY = date(2026, 10, 25)


def codes(flags):
    return {f["code"] for f in flags}


def form():
    return {"name": "Ananya Sharma", "dob": "14/03/2005", "aadhaar": AADHAAR, "income": 420000, "percentage": 86.4}


def docs():
    """Same shape as Person 1's extract() output."""
    return [
        {"type": "aadhaar", "name": "Ananya Sharma", "dob": "14/03/2005", "id_number": AADHAAR, "marks": None,
         "total": None, "percentage": None, "income": None, "issue_date": None, "path": "aadhaar.jpg"},
        {"type": "income_certificate", "name": "Ananya Sharma", "dob": None, "id_number": None, "marks": None,
         "total": None, "percentage": None, "income": 420000, "issue_date": "10/06/2026", "path": "income.jpg"},
        {"type": "marksheet", "name": "Ananya Sharma", "dob": "14/03/2005", "id_number": None, "marks": 432,
         "total": 500, "percentage": 86.4, "income": None, "issue_date": None, "path": "marksheet.jpg"},
    ]


def run(f=None, d=None):
    return validate(f or form(), d or docs(), today=TODAY)


def test_verhoeff_known_values():
    assert verhoeff.validate("2363") and not verhoeff.validate("2364")
    assert verhoeff.generate("236") == "3"
    assert verhoeff.validate(AADHAAR) and not verhoeff.validate(BAD_AADHAAR)


def test_helpers():
    assert normalize_date("14/03/2005") == "14-03-2005"
    assert normalize_date("2005-03-14") == "14-03-2005"
    assert normalize_date("garbage") is None
    assert parse_date("14/03/2005") == date(2005, 3, 14)
    assert to_number("4,20,000") == 420000 and to_number(None) is None
    assert normalize_name("Mr. ananya  sharma") == "ANANYA SHARMA"


def test_clean_application_has_no_flags():
    assert run() == []


def test_nested_format_still_accepted():
    nested = adapt({"doc_type": "aadhaar", "fields": {"name": "A"}})
    assert nested["fields"]["name"] == "A"


def test_bad_aadhaar_checksum():
    d = docs(); d[0]["id_number"] = BAD_AADHAAR
    f = form(); f["aadhaar"] = BAD_AADHAAR
    assert "CHECKSUM_FAIL" in codes(run(f, d))


def test_aadhaar_on_form_differs_from_card():
    f = form(); f["aadhaar"] = BAD_AADHAAR
    assert "ID_MISMATCH" in codes(run(f))


def test_unreadable_aadhaar_number():
    d = docs(); d[0]["id_number"] = None
    assert "UNREADABLE_FIELD" in codes(run(None, d))


def test_income_mismatch():
    d = docs(); d[1]["income"] = 380000
    assert "INCOME_MISMATCH" in codes(run(None, d))


def test_percentage_mismatch_with_form():
    f = form(); f["percentage"] = 92.0
    assert "PERCENTAGE_MISMATCH" in codes(run(f))


def test_marks_inconsistent_with_percentage():
    d = docs(); d[2]["marks"] = 300           # 300/500 = 60%, but percentage says 86.4
    assert "MARKS_INCONSISTENT" in codes(run(None, d))


def test_marks_greater_than_total():
    d = docs(); d[2]["marks"] = 600
    assert "MARKS_INCONSISTENT" in codes(run(None, d))


def test_missing_marksheet():
    assert "MISSING_DOC" in codes(run(None, docs()[:2]))


def test_dob_mismatch_between_card_and_marksheet():
    d = docs(); d[2]["dob"] = "14/03/1999"
    assert "DOB_MISMATCH" in codes(run(None, d))


def test_name_order_variation_is_not_high():
    d = docs(); d[1]["name"] = "SHARMA ANANYA"
    assert not any(x["severity"] == "high" for x in run(None, d))


def test_different_name_is_high():
    d = docs(); d[1]["name"] = "Rohan Verma"
    assert "NAME_MISMATCH" in codes(run(None, d))


def test_unknown_document():
    d = docs() + [{"type": "unknown", "path": "mystery.jpg"}]
    assert "UNKNOWN_DOC" in codes(run(None, d))


def test_future_issue_date():
    d = docs(); d[1]["issue_date"] = "10/06/2027"
    assert "ISSUE_DATE_FUTURE" in codes(run(None, d))


def test_masked_aadhaar_skips_checksum():
    d = docs(); d[0]["id_number"] = "XXXX XXXX " + AADHAAR[-4:]
    assert "CHECKSUM_FAIL" not in codes(run(None, d))


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print("PASS", t.__name__)
    print(f"\nAll {len(tests)} tests passed")
