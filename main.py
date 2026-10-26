"""FastAPI integration starter for DocDrishti.

POST /verify-json is runnable now for integration tests.
POST /verify accepts uploaded files once Person 1's extract(path) is available.
"""
from pathlib import Path
import tempfile
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel, Field

from compliance import check_rules, load_rules
from scoring import decide
from validate import validate

app = FastAPI(title="DocDrishti Verification API", version="0.1.0")
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(
        title=app.title,
        version=app.version,
        routes=app.routes,
    )

    schema["openapi"] = "3.0.3"

    body = schema["paths"]["/verify"]["post"]["requestBody"]
    ref = body["content"]["multipart/form-data"]["schema"]["$ref"]
    model_name = ref.split("/")[-1]

    schema["components"]["schemas"][model_name]["properties"]["files"] = {
        "title": "Files",
        "type": "array",
        "items": {"type": "string", "format": "binary"},
    }

    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = custom_openapi


class VerifyJSONRequest(BaseModel):
    application_id: str = "demo-application"
    form: dict = Field(default_factory=dict)
    docs: list[dict] = Field(default_factory=list)


@app.get("/health")
def health():
    return {"status": "ok", "service": "DocDrishti Verification API"}


@app.post("/verify-json")
def verify_json(payload: VerifyJSONRequest):
    """JSON test endpoint for teammates; accepts already-extracted form and docs."""
    flags = validate(payload.form, payload.docs)
    eligibility = check_rules(payload.docs, load_rules())
    result = decide(flags, eligibility)
    result["application_id"] = payload.application_id
    result["extracted"] = payload.docs
    return result


@app.post("/verify")
async def verify_uploads(
    application_id: str = Form(...),
    name: Optional[str] = Form(None),
    dob: Optional[str] = Form(None),
    aadhaar: Optional[str] = Form(None),
    income: Optional[str] = Form(None),
    percentage: Optional[str] = Form(None),
    files: list[UploadFile] = File(...),
):
    """Upload endpoint; needs Person 1's extract.py to be present in this folder."""
    try:
        from extract import extract
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="Person 1's extract.py is not present yet. Use /verify-json for integration tests.") from exc

    form = {"name": name, "dob": dob, "aadhaar": aadhaar, "income": income, "percentage": percentage}
    extracted = []
    # Use a unique temporary directory and clean it automatically.
    with tempfile.TemporaryDirectory(prefix="docdrishti_") as temp_dir:
        for index, upload in enumerate(files):
            suffix = Path(upload.filename or "upload.bin").suffix[:12]
            path = Path(temp_dir) / f"document_{index}{suffix}"
            content = await upload.read()
            if not content:
                continue
            path.write_bytes(content)
            try:
                item = extract(str(path))
                if isinstance(item, dict):
                    item.setdefault("path", upload.filename or path.name)
                    extracted.append(item)
            except Exception as exc:
                extracted.append({"type": "unknown", "path": upload.filename or path.name, "extraction_error": str(exc)})

    flags = validate(form, extracted)
    eligibility = check_rules(extracted, load_rules())
    result = decide(flags, eligibility)
    result.update({"application_id": application_id, "extracted": extracted, "heatmaps": []})
    return result
