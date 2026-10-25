import os, json, base64, hashlib, tempfile
import numpy as np
import cv2
from PIL import Image, ImageChops
from common import flag

# ELA limits per document type. These numbers come from our own sample documents,
# so every team must re-measure them on its own samples (see make_samples.py).
ELA_LIMITS = {"aadhaar": 14.0, "income_certificate": 14.0, "marksheet": 10.0}
DEFAULT_ELA_LIMIT = 12.0


def ela_score(path, quality=90, block=32):
    img = Image.open(path).convert("RGB")
    tmp = os.path.join(tempfile.gettempdir(), "ela_tmp.jpg")
    img.save(tmp, "JPEG", quality=quality)
    diff = np.array(ImageChops.difference(img, Image.open(tmp))).astype(float).mean(axis=2)
    gray = np.array(img.convert("L")).astype(float)
    h, w = diff.shape
    errs = [diff[i:i+block, j:j+block].mean()
            for i in range(0, h - block + 1, block) for j in range(0, w - block + 1, block)
            if gray[i:i+block, j:j+block].std() > 15]  # only blocks that contain text or edges
    ratio = max(errs) / (np.median(errs) + 1e-6) if errs else 0.0
    heat = cv2.applyColorMap((diff / (diff.max() + 1e-6) * 255).astype("uint8"),
                             cv2.COLORMAP_JET)
    return ratio, heat  # heat = heatmap image for the dashboard


def editor_found(path):
    img = Image.open(path)
    text = (str(img.info) + str(img.getexif().get(305, ""))).lower()  # 305 = Software tag
    return [s for s in ("photoshop", "gimp", "canva") if s in text]


def read_qr(path):
    # OpenCV's built-in QR reader, so no extra library is needed
    val, _, _ = cv2.QRCodeDetector().detectAndDecode(cv2.imread(path))
    if not val:
        return None
    try:
        return json.loads(val)
    except ValueError:
        return None


def heatmap_b64(path):
    # Turn the PNG into base64 text so the API can send it to the dashboard
    _, heat = ela_score(path)
    ok, png = cv2.imencode(".png", heat)
    return base64.b64encode(png.tobytes()).decode()


def duplicate_check(data, application_id, store="seen_docs.json"):
    # Has the same document content already been used in another application?
    # (An image hash does not work here: all documents of one type look alike.)
    keys = ("type", "name", "dob", "id_number", "marks", "total", "percentage", "income", "issue_date")
    fingerprint = hashlib.sha256(json.dumps([data.get(k) for k in keys]).encode()).hexdigest()
    seen = json.load(open(store)) if os.path.exists(store) else []
    for s in seen:
        if s["fingerprint"] == fingerprint and s["application_id"] != application_id:
            return flag("Duplicate document", "fail",
                        f"Same content was already used in application {s['application_id']}", 30)
    seen.append({"fingerprint": fingerprint, "application_id": application_id})
    json.dump(seen, open(store, "w"))
    return flag("Duplicate document", "pass", "No duplicate found")


def authenticate(path, data):
    out = []
    ratio, _ = ela_score(path)
    limit = ELA_LIMITS.get(data["type"], DEFAULT_ELA_LIMIT)
    out.append(flag("ELA tampering", "fail" if ratio > limit else "pass",
                    f"ELA ratio {ratio:.1f} (limit {limit})", 20))
    tools = editor_found(path)
    out.append(flag("Metadata editor", "fail" if tools else "pass",
                    ("Editing software found: " + ", ".join(tools)) if tools
                    else "No editing software found", 15))
    if data["type"] == "aadhaar":
        qr = read_qr(path)
        if qr is None:
            out.append(flag("Aadhaar QR", "warn", "QR code could not be read", 10))
        else:
            ok = (qr.get("name", "").lower() == (data.get("name") or "").lower()
                  and qr.get("dob") == data.get("dob"))
            out.append(flag("Aadhaar QR match", "pass" if ok else "fail",
                            "QR data and OCR data " + ("match" if ok else "do not match"), 25))
    return out