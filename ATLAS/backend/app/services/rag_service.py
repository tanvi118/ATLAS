"""Adapter between the backend and Member 1's RAG code in rag/ (ingestion.py, retriever.py).

The backend only ever calls ingest_document() and retrieve_context() below. If Member 1's function
names/outputs differ, change ONLY this file. Nothing is faked: if rag/ isn't usable we raise
RAGUnavailableError and the callers say so.
"""
import importlib
import inspect
import logging
import sys
from pathlib import Path

from app.config import ROOT_DIR

logger = logging.getLogger("atlas.rag")
RAG_DIR = ROOT_DIR / "rag"

# Function names we look for in Member 1's modules (first match wins).
INGEST_NAMES = ("ingest_document", "ingest_pdf", "ingest")
RETRIEVE_NAMES = ("retrieve_context", "retrieve", "search", "query")


class RAGUnavailableError(Exception):
    def __init__(self, user_message: str = "Document search is not connected yet — the RAG module (Member 1's code in rag/) isn't available."):
        super().__init__(user_message)
        self.user_message = user_message


def _load(module_name: str, names: tuple[str, ...]):
    if str(RAG_DIR) not in sys.path:
        sys.path.insert(0, str(RAG_DIR))
    try:
        module = importlib.import_module(module_name)
    except Exception as e:  # missing file, missing dependency, bug in their code...
        logger.warning("Could not import rag/%s.py: %s", module_name, type(e).__name__)
        raise RAGUnavailableError()
    for name in names:
        fn = getattr(module, name, None)
        if callable(fn):
            return fn
    raise RAGUnavailableError(f"rag/{module_name}.py has none of the expected functions: {', '.join(names)}.")


def _call(fn, *args, **optional):
    """Pass optional keyword args only if the function accepts them."""
    accepted = inspect.signature(fn).parameters
    kwargs = {k: v for k, v in optional.items() if k in accepted and v is not None}
    return fn(*args, **kwargs)


def ingest_document(path: Path, document_id: str, filename: str) -> int | None:
    """Index a stored PDF. Returns the number of chunks if Member 1's code reports it."""
    fn = _load("ingestion", INGEST_NAMES)
    try:
        result = _call(fn, str(path), document_id=document_id, filename=filename)
    except Exception:
        logger.exception("RAG ingestion failed")
        raise RAGUnavailableError("The document couldn't be processed by the RAG module.")
    if isinstance(result, int):
        return result
    if isinstance(result, dict) and isinstance(result.get("chunks"), int):
        return result["chunks"]
    return None


def _normalize_sources(items) -> list[dict]:
    seen, out = set(), []
    for s in items or []:
        if not isinstance(s, dict):
            continue
        meta = s.get("metadata") if isinstance(s.get("metadata"), dict) else s
        doc = meta.get("document") or meta.get("source") or meta.get("filename")
        page = meta.get("page") if meta.get("page") is not None else meta.get("page_number")
        if not doc:
            continue
        page = page if isinstance(page, int) else None
        if (doc, page) not in seen:
            seen.add((doc, page))
            out.append({"document": str(doc), "page": page})
    return out


def retrieve_context(question: str, document_id: str | None = None) -> dict:
    """Return {"context": str, "sources": [{"document": str, "page": int | None}]}."""
    fn = _load("retriever", RETRIEVE_NAMES)
    try:
        raw = _call(fn, question, document_id=document_id)
    except Exception:
        logger.exception("RAG retrieval failed")
        raise RAGUnavailableError("Searching the documents failed.")

    if isinstance(raw, dict):  # {"answer_context"|"context": str, "sources": [...]}
        context = raw.get("context") or raw.get("answer_context") or ""
        return {"context": str(context), "sources": _normalize_sources(raw.get("sources"))}
    if isinstance(raw, list):  # list of chunk dicts
        texts = [c.get("text") or c.get("content") or "" for c in raw if isinstance(c, dict)]
        return {"context": "\n\n".join(t for t in texts if t), "sources": _normalize_sources(raw)}
    raise RAGUnavailableError("The RAG module returned an unexpected result.")
