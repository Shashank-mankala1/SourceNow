from fastapi import APIRouter, HTTPException
from fastapi import UploadFile, File
from api.models.schemas import IngestRequest, IngestResponse
from api.core.store import STORE

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("", response_model=IngestResponse)
def ingest(req: IngestRequest):
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required for this milestone")
    ingest_id = STORE.new_ingest(text=text, source_type=req.source_type, meta=req.meta)
    return {"ingest_id": ingest_id}


@router.post("/pdf", response_model=IngestResponse)
async def ingest_pdf(file: UploadFile = File(...)):
    # basic validation
    if (file.content_type or "").lower() not in {"application/pdf", "application/octet-stream"}:
        # some browsers send octet-stream; we'll accept it
        pass

    # read file bytes
    data = await file.read()

    # extract text with PyMuPDF
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not open PDF: {e}")

    pages = []
    for page in doc:
        try:
            # plain text extraction; returns "" for image-only pages
            pages.append(page.get_text("text"))
        except Exception:
            pages.append("")

    text = "\n".join(p.strip() for p in pages if p is not None).strip()

    if not text:
        # We’ll add OCR support later; for now return a helpful message
        raise HTTPException(
            status_code=422,
            detail="No selectable text found (PDF may be image-only). OCR support is coming next."
        )

    ingest_id = STORE.new_ingest(text=text, source_type="pdf", meta={"filename": file.filename})
    return {"ingest_id": ingest_id}