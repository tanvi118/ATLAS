"""Document endpoints. Three separate jobs:
  1. upload   -> validate + save the PDF (this file)
  2. indexing -> rag_service.ingest_document()  (Member 1's code, via the adapter)
  3. retrieval -> agent_service.answer_document_question() -> rag_service.retrieve_context()
"""
import logging
import re
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from app import schemas
from app.config import settings
from app.services import agent_service, rag_service
from app.services.llm_service import LLMError
from app.services.rag_service import RAGUnavailableError

logger = logging.getLogger("atlas.documents")
router = APIRouter(prefix="/documents", tags=["documents"])

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB
_ID_RE = re.compile(r"^[0-9a-f]{32}$")


def _safe_name(name: str | None) -> str:
    """Keep only the file's base name; strip any path and odd characters."""
    base = Path((name or "document.pdf").replace("\\", "/")).name
    return re.sub(r"[^\w.\- ]", "_", base)[:100] or "document.pdf"


@router.post("/upload", response_model=schemas.DocumentUploadResponse, status_code=201)
def upload_document(file: UploadFile = File(...)):
    display_name = _safe_name(file.filename)
    if not display_name.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are allowed.")
    data = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File is too large (max 10 MB).")
    if not data.startswith(b"%PDF"):
        raise HTTPException(400, "That file isn't a valid PDF.")

    # Step 1: save under a name WE generate (never the user's filename).
    document_id = uuid.uuid4().hex
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    path = settings.upload_dir / f"{document_id}.pdf"
    path.write_bytes(data)

    # Step 2: try to index it. We only say "indexed" if this really succeeded.
    try:
        chunks = rag_service.ingest_document(path, document_id, display_name)
    except RAGUnavailableError as e:
        return {"document_id": document_id, "filename": display_name, "indexed": False, "chunks": None,
                "message": f"File saved, but NOT indexed. {e.user_message}"}
    return {"document_id": document_id, "filename": display_name, "indexed": True, "chunks": chunks,
            "message": "File saved and indexed."}


@router.post("/query", response_model=schemas.DocumentQueryResponse)
def query_document(body: schemas.DocumentQueryRequest):
    session_id = body.session_id or str(uuid.uuid4())
    if body.document_id is not None and not (
            _ID_RE.match(body.document_id) and (settings.upload_dir / f"{body.document_id}.pdf").is_file()):
        raise HTTPException(404, f"Document {body.document_id} not found")
    try:
        reply, sources = agent_service.answer_document_question(body.question, body.document_id)
    except RAGUnavailableError as e:  # retriever not connected -> clear message, empty sources
        reply, sources = e.user_message, []
    except LLMError as e:
        reply, sources = e.user_message, []
    return {"reply": reply, "intent": "document_qa", "sources": sources, "session_id": session_id}
