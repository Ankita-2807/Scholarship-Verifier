"""Creates dummy (SAMPLE) documents + truth.json for 4 test cases.
Run: python make_samples.py -> creates the sample_data/ folder
"""
import os, json, cv2
from datetime import date, timedelta
from PIL import Image, ImageDraw, ImageFont
from verhoeff import generate

OUT = "sample_data"
FONT_FILES = ["arial.ttf", "DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
              "/System/Library/Fonts/Supplemental/Arial.ttf"]


def font(size):
    for f in FONT_FILES:
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            pass
    return ImageFont.load_default()


def qr_image(text, scale=5):
    enc = cv2.QRCodeEncoder.create()
    img = cv2.resize(enc.encode(text), None, fx=scale, fy=scale,
                     interpolation=cv2.INTER_NEAREST)
    img = cv2.copyMakeBorder(img, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=255)
    return Image.fromarray(img).convert("RGB")


def draw_doc(lines, path, qr=None, quality=95):
    """Every field goes on its own line as 'Label: value', so OCR + regex works well."""
    img = Image.new("RGB", (900, 640), "white")
    d = ImageDraw.Draw(img)
    d.rectangle([10, 10, 890, 630], outline="black", width=3)
    y = 40
    for i, ln in enumerate(lines):
        d.text((50, y), ln, fill="black", font=font(34 if i == 0 else 30))
        y += 62
    if qr is not None:
        img.paste(qr, (640, 360))
    d.text((50, 590), "SAMPLE DOCUMENT - NOT REAL", fill="red", font=font(22))
    img.save(path, "JPEG", quality=quality)


def tamper(path, box, new_text, out_path):
    """Simulates an edit: covers a region, writes new text, re-saves with a Photoshop tag."""
    img = Image.open(path).convert("RGB")
    d = ImageDraw.Draw(img)
    d.rectangle(box, fill="white")
    d.text((box[0] + 2, box[1]), new_text, fill="black", font=font(30))
    exif = img.getexif()
    exif[305] = "Adobe Photoshop 25.0"
    img.save(out_path, "JPEG", quality=90, exif=exif)


def dstr(d):
    return d.strftime("%d/%m/%Y")


def make_case(folder, name, marksheet_name, age, first11,
              marks, total, printed_pct, income, cert_days_old):
    os.makedirs(os.path.join(OUT, folder), exist_ok=True)
    today = date.today()
    dob = dstr(today.replace(year=today.year - age) - timedelta(days=30))
    number = generate(first11)
    spaced = f"{number[:4]} {number[4:8]} {number[8:]}"
    issue = dstr(today - timedelta(days=cert_days_old))
    docs = {
        "aadhaar": ["Government of India - Aadhaar", f"Name: {name}", f"DOB: {dob}", spaced],
        "marksheet": ["State Board of Education", "Class 12 Marksheet", f"Student Name: {marksheet_name}",
                      f"Marks Obtained: {marks}", f"Total Marks: {total}", f"Percentage: {printed_pct}%"],
        "income_certificate": ["Income Certificate", f"Name: {name}",
                               f"Annual Income: Rs. {income:,}", f"Issue Date: {issue}",
                               "Issuing Authority: Tehsildar"],
    }
    paths = {}
    for t, lines in docs.items():
        p = os.path.join(OUT, folder, f"{t}.jpg")
        qr = qr_image(json.dumps({"name": name, "dob": dob})) if t == "aadhaar" else None
        draw_doc(lines, p, qr)
        paths[t] = p
    json.dump(docs, open(os.path.join(OUT, folder, "truth.json"), "w"), indent=2)
    return paths


if __name__ == "__main__":
    make_case("case1_genuine", "Rahul Sharma", "Rahul Sharma", 21, "23456789012",
              430, 500, 86.0, 420000, 120)

    # Case 2: marksheet is edited. The real percentage is 68.4, the edit makes it 88.4.
    p = make_case("case2_tampered", "Neha Gupta", "Neha Gupta", 20, "34567890123",
                  342, 500, 68.4, 350000, 90)
    tamper(p["marksheet"], (50, 355, 600, 405), "Percentage: 88.4%", p["marksheet"])
    # truth.json must describe what is visible on the edited image
    tf = os.path.join(OUT, "case2_tampered", "truth.json")
    truth = json.load(open(tf))
    truth["marksheet"][-1] = "Percentage: 88.4%"
    json.dump(truth, open(tf, "w"), indent=2)

    make_case("case3_review", "Mohd Arif Khan", "Mohammad Arif Khan", 21, "45678901234",
              400, 500, 80.0, 500000, 430)
    make_case("case4_not_eligible", "Simran Kaur", "Simran Kaur", 20, "56789012345",
              450, 500, 90.0, 950000, 60)
    print("Done. Check the sample_data/ folder.")
