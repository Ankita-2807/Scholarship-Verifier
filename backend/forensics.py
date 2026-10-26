import os, json, base64, hashlib, tempfile
import numpy as np
import cv2
from PIL import Image, ImageChops
from common import make_flag, HIGH, MEDIUM, LOW

# ELA limits per document type. Re-measure on the team's final sample documents.
ELA_LIMITS = {"aadhaar": 14.0, "income_certificate": 14.0, "marksheet": 10.0}
DEFAULT_ELA_LIMIT = 12.0


def _flag(code, severity, reason):
    f = make_flag(code, severity, reason)
    f["source"] = "authentication"
    return f


def ela_score(path, quality=90, block=32):
    img = Image.open(path).convert("RGB")
    tmp = os.path.join(tempfile.gettempdir(), "ela_tmp.jpg")
    img.save(tmp, "JPEG", quality=quality)
    diff = np.array(ImageChops.difference(img, Image.open(tmp))).astype(float).mean(axis=2)
    gray = np.array(img.convert("L")).astype(float)
    h, w = diff.shape
    errs = [diff[i:i+block, j:j+block].mean()
            for i in range(0, h - block + 1, block) for j in range(0, w - block + 1, block)
            if gray[i:i+block, j:j+block].std() > 15]  # only blocks with text or edges
    ratio = max(errs) / (np.median(errs) + 1e-6) if errs else 0.0
    heat = cv2.applyColorMap((diff / (diff.max() + 1e-6) * 255).astype("uint8"),
                             cv2.COLORMAP_JET)
    return ratio, heat


def editor_found(path):
    img = Image.open(path)
    text = (str(img.info) + str(img.getexif().get(305, ""))).lower()  # 305 = Software tag
    return [s for s in ("photoshop", "gimp", "canva") if s in text]


def read_qr(path):
    val, _, _ = cv2.QRCodeDetector().detectAndDecode(cv2.imread(path))
    if not val:
        return None
    try:
        return json.loads(val)
    except ValueError:
        return None


def heatmap_b64(path):
    _, heat = ela_score(path)
    ok, png = cv2.imencode(".png", heat)
    return base64.b64encode(png.tobytes()).decode()


def duplicate_check(data, application_id, store="seen_docs.json"):
    """Returns a list: one flag if a duplicate is found, else an empty list."""
    keys = ("type", "name", "dob", "id_number", "marks", "total", "percentage", "income", "issue_date")
    fingerprint = hashlib.sha256(json.dumps([data.get(k) for k in keys]).encode()).hexdigest()
    seen = json.load(open(store)) if os.path.exists(store) else []
    for s in seen:
        if s["fingerprint"] == fingerprint and s["application_id"] != application_id:
            return [_flag("DUPLICATE_DOC", HIGH,
                          f"Same content was already used in application {s['application_id']}")]
    seen.append({"fingerprint": fingerprint, "application_id": application_id})
    json.dump(seen, open(store, "w"))
    return []


def authenticate(path, data):
    """Returns a list of flags (only problems). Empty list means all checks passed."""
    out = []
    ratio, _ = ela_score(path)
    limit = ELA_LIMITS.get(data["type"], DEFAULT_ELA_LIMIT)
    if ratio > limit:
        out.append(_flag("ELA_TAMPERING", MEDIUM,
                         f"Possible edited region: ELA ratio {ratio:.1f} (limit {limit})"))
    tools = editor_found(path)
    if tools:
        out.append(_flag("EDITOR_METADATA", MEDIUM,
                         "Editing software found in file: " + ", ".join(tools)))
    if data["type"] == "aadhaar":
        qr = read_qr(path)
        if qr is None:
            out.append(_flag("QR_UNREADABLE", LOW, "Aadhaar QR code could not be read"))
        else:
            ok = (qr.get("name", "").lower() == (data.get("name") or "").lower()
                  and qr.get("dob") == data.get("dob"))
            if not ok:
                out.append(_flag("QR_MISMATCH", HIGH, "QR data and printed data do not match"))
    return out