import re

def detect_type(text):
    t = text.lower()
    if "aadhaar" in t or "uidai" in t:
        return "aadhaar"
    if re.search(r"[il1]ncome", t) and "certificate" in t:
        return "income_certificate"
    if "marks" in t or "board" in t:
        return "marksheet"
    return "unknown"

def after_label(lines, label):
    # Gets the value from a line like "Name: Rahul Sharma"
    for ln in lines:
        m = re.match(r"^\s*" + label + r"\s*[:\-]?\s*(.+)", ln, re.I)
        if m:
            return m.group(1).strip()
    return None

def to_num(s):
    m = re.search(r"\d[\d,]*(?:\.\d+)?", s or "")
    if not m:
        return None
    n = m.group(0).replace(",", "")
    return float(n) if "." in n else int(n)

def find_aadhaar(lines):
    # Look at each line separately so DOB digits do not get mixed in
    for ln in lines:
        m = re.search(r"(?<![\d/])(\d{4})\s?(\d{4})\s?(\d{4})(?![\d/])", ln)
        if m:
            return "".join(m.groups())
    return None

def find_date(lines):
    # Finds a date like 14/03/2005 anywhere (also 14-03-2005, 14.03.2005, or 14/O3/2005)
    for ln in lines:
        m = re.search(r"(?<![\d/])([\dOoIl]{2})[/\-.]([\dOoIl]{2})[/\-.]([\dOoIl]{4})(?![\d/])", ln)
        if m:
            fix = {"O": "0", "o": "0", "I": "1", "l": "1"}      # letters OCR confuses with digits
            return "/".join("".join(fix.get(c, c) for c in g) for g in m.groups())
    return None

def money(token):
    # "4,20,000"  "4.20.000"  "420000.00"  ->  420000
    token = re.sub(r"\.0{1,2}$", "", token.strip(".,"))
    digits = re.sub(r"[.,]", "", token)
    return int(digits) if digits.isdigit() else None

AMOUNT = r"(\d[\d,.]*)"

def find_income(lines):
    # 1) normal label: "Annual Income: Rs. 4,20,000"
    val = after_label(lines, r"annual\s+income")
    m = re.search(AMOUNT, val) if val else None
    if m and money(m.group(1)):
        return money(m.group(1))
    # 2) any line with Rs / INR / rupee sign followed by an amount
    for ln in lines:
        m = re.search(r"(?:rs|inr|\u20b9)\.?\s*[:\-]?\s*" + AMOUNT, ln, re.I)
        if m and money(m.group(1)):
            return money(m.group(1))
    # 3) a line that mentions income / annual (even if misread) and has a number,
    #    or the number is on the next line
    for i, ln in enumerate(lines):
        if re.search(r"[il1]nc[o0]me|annual|annuol", ln, re.I):
            for cand in (ln, lines[i + 1] if i + 1 < len(lines) else ""):
                if "/" in cand:
                    continue                 # skip dates
                m = re.search(r"(?<![\d,.])(\d[\d,.]{3,})", cand)
                if m and money(m.group(1)):
                    return money(m.group(1))
    return None

def clean_lines(lines):
    # The Hindi model sometimes reads ":" as the Devanagari sign "\u0903" - turn it back into ":"
    return [ln.replace("\u0903", ":").replace("\uff1a", ":") for ln in lines]

def parse(lines):
    lines = clean_lines(lines)
    text = " ".join(lines)
    doc_type = detect_type(text)
    dob = after_label(lines, r"(?:dob|date of birth)")
    clean = find_date([dob]) if dob else None
    if clean:
        dob = clean                     # tidy form: 14/03/2005
    elif doc_type == "aadhaar":
        dob = find_date(lines)          # label missed? take the date from the card
    percentage = to_num(after_label(lines, r"percentage"))
    if percentage is None:                      # label missed? use the number that has a % sign
        m = re.search(r"(\d{2,3}(?:\.\d+)?)\s*%", text)
        percentage = to_num(m.group(1)) if m else None
    issue_date = after_label(lines, r"(?:issue date|date of issue)")
    if doc_type == "income_certificate":        # label missed? take the date from the certificate
        issue_date = find_date([issue_date]) if issue_date and find_date([issue_date]) else find_date(lines)
    return {
        "type": doc_type,
        "name": after_label(lines, r"(?:student\s+)?name"),
        "dob": dob,
        "id_number": find_aadhaar(lines),
        "marks": to_num(after_label(lines, r"marks obtained")),
        "total": to_num(after_label(lines, r"total marks")),
        "percentage": percentage,
        "income": find_income(lines) if doc_type == "income_certificate" else None,
        "issue_date": issue_date,
    }

_reader = None
def extract(path):
    global _reader
    if _reader is None:
        import easyocr
        _reader = easyocr.Reader(["en", "hi"])
    lines = _reader.readtext(path, detail=0)
    data = parse(lines)
    data["path"] = path
    return data
