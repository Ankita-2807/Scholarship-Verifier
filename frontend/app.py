import base64
import io

import requests
import streamlit as st
from PIL import Image, ImageDraw

# True  = show a made-up result (no API needed, good for building the page).
# False = call Person 4's real API.  Change this when the API is ready.
USE_DUMMY = True
API_URL = "http://localhost:8000/verify"


def dummy_heatmap():
    # A small fake "heatmap": blue picture with a red glowing patch
    img = Image.new("RGB", (320, 200), (30, 30, 160))
    ImageDraw.Draw(img).rectangle([60, 80, 260, 120], fill=(220, 40, 40))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return base64.b64encode(buf.getvalue()).decode()


def dummy_result():
    # Same shape as the real API result (section A5 of the guide)
    return {
        "score": 60,
        "decision": "REJECT (Fraud suspected)",
        "flags": [
            {"check": "Aadhaar checksum", "status": "pass", "reason": "Verhoeff check pass", "weight": 0},
            {"check": "Name match", "status": "pass", "reason": "Similarity 100%", "weight": 0},
            {"check": "Marks vs percentage", "status": "fail",
             "reason": "Calculated from marks 68.4%, printed on marksheet 88.4%", "weight": 25},
            {"check": "ELA tampering", "status": "fail", "reason": "ELA ratio 13.3 (limit 10.0)", "weight": 20},
            {"check": "Metadata editor", "status": "fail",
             "reason": "Editing software found: photoshop", "weight": 15},
        ],
        "eligibility": [
            {"rule": "Required documents", "status": "pass", "reason": "All documents present"},
            {"rule": "Age limit", "status": "pass", "reason": "Age 20, allowed 17 to 25"},
            {"rule": "Minimum percentage", "status": "fail", "reason": "Percentage 68.4%, minimum 75%"},
            {"rule": "Family income limit", "status": "pass", "reason": "Income Rs. 350,000, limit Rs. 800,000"},
        ],
        "heatmaps": {"marksheet": dummy_heatmap()},
    }


st.title("Scholarship Document Verification")

files = st.file_uploader("Upload Aadhaar, Marksheet and Income Certificate",
                         accept_multiple_files=True, type=["png", "jpg", "jpeg"])
app_id = st.text_input("Application ID", "app-1")

if st.button("Verify"):
    if USE_DUMMY:
        st.session_state["result"] = dummy_result()
        st.session_state["officer"] = None
    elif not files:
        st.warning("Please upload the documents first.")
    else:
        try:
            resp = requests.post(API_URL,
                                 files=[("files", (f.name, f.getvalue(), f.type)) for f in files],
                                 data={"application_id": app_id}, timeout=300)
            resp.raise_for_status()
            st.session_state["result"] = resp.json()
            st.session_state["officer"] = None
        except requests.exceptions.ConnectionError:
            st.error("Cannot reach the API. Is Person 4's server running? "
                     "(In the backend folder: uvicorn main:app --reload)")
        except Exception as e:
            st.error(f"Something went wrong: {e}")

# The result is kept in session_state, so it stays on screen when you click the officer buttons.
r = st.session_state.get("result")
if r:
    st.metric("Risk score", r["score"])
    colour = {"APPROVE": "green", "MANUAL REVIEW": "orange"}.get(r["decision"], "red")
    st.markdown(f"### :{colour}[{r['decision']}]")

    st.subheader("Document checks")
    for f in r["flags"]:
        st.write(f"[{f['status'].upper()}] {f['check']}: {f['reason']}")

    st.subheader("Scholarship eligibility")
    for e in r["eligibility"]:
        st.write(f"[{e['status'].upper()}] {e['rule']}: {e['reason']}")

    st.subheader("Tamper heatmap (ELA)")
    for doc_type, b64 in r.get("heatmaps", {}).items():
        st.caption(doc_type)
        st.image(base64.b64decode(b64))

    c1, c2 = st.columns(2)
    if c1.button("Approve (Officer)"):
        st.session_state["officer"] = "Application APPROVED by officer"
    if c2.button("Reject (Officer)"):
        st.session_state["officer"] = "Application REJECTED by officer"
    if st.session_state.get("officer"):
        st.info(st.session_state["officer"])