# Prints the ELA ratio, editing software and QR status of every sample document.
# Use it to choose ELA_LIMITS in forensics.py
import glob
from forensics import ela_score, editor_found, read_qr

for f in sorted(glob.glob("sample_data/*/*.jpg")):
    ratio, _ = ela_score(f)
    qr = "QR ok" if ("aadhaar" in f and read_qr(f)) else ""
    print(f"{f.replace('sample_data/', ''):45s} ELA {ratio:6.2f} {editor_found(f)} {qr}")