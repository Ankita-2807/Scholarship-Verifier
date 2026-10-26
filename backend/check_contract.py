# Checks that extract() gives exactly what the other team members' code expects.
# Run:  python check_contract.py 2>$null
import glob, os, re
from extract import extract

KEYS = {"type", "name", "dob", "id_number", "marks", "total",
        "percentage", "income", "issue_date", "path"}
DATE = re.compile(r"\d{2}/\d{2}/\d{4}")
problems = []

def check(label, ok, text):
    if not ok:
        problems.append(f"{label}: {text}")

for folder in sorted(glob.glob("sample_data/*/")):
    case = os.path.basename(folder.rstrip("/\\"))
    for doc_type in ("aadhaar", "marksheet", "income_certificate"):
        label = f"{case}/{doc_type}"
        d = extract(os.path.join(folder, doc_type + ".jpg"))
        check(label, set(d) == KEYS, f"keys are {sorted(d)}")
        check(label, d.get("type") == doc_type, f"type is {d.get('type')!r}")
        check(label, bool(d.get("name")), "name is missing")
        if doc_type == "aadhaar":
            check(label, re.fullmatch(r"\d{12}", d.get("id_number") or ""), f"id_number is {d.get('id_number')!r}")
            check(label, DATE.fullmatch(d.get("dob") or ""), f"dob is {d.get('dob')!r}")
        if doc_type == "marksheet":
            for k in ("marks", "total", "percentage"):
                check(label, isinstance(d.get(k), (int, float)), f"{k} is {d.get(k)!r}")
        if doc_type == "income_certificate":
            check(label, isinstance(d.get("income"), int) and d["income"] >= 10000, f"income is {d.get('income')!r}")
            check(label, DATE.fullmatch(d.get("issue_date") or ""), f"issue_date is {d.get('issue_date')!r}")

print("PROBLEMS:" if problems else "ALL OK: extract() output matches the team format")
for p in problems:
    print("  ", p)
