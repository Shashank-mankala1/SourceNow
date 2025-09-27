from fastapi import APIRouter, UploadFile, File, HTTPException
import fitz # PyMuPDF
from api.core.store import STORE
from api.models.schemas import IngestResponse


router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("/pdf", response_model=IngestResponse)
def ingest_pdf(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files supported")

    try:
        data = file.file.read()
        doc = fitz.open(stream=data, filetype="pdf")
        text_parts = []
        for page in doc:
            text_parts.append(page.get_text("text"))
        text = "\n".join(text_parts).strip()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse PDF: {e}")

    if not text:
        raise HTTPException(status_code=400, detail="No extractable text found in PDF")

    ingest_id = STORE.new_ingest(text=text, source_type="pdf", meta={"filename": file.filename})
    return {"ingest_id": ingest_id}