# Integration Guide

## Status
| Part | State |
|---|---|
| Tasks CRUD, chat router, memory, history, PDF upload | **Implemented and tested** (mocked LLM) |
| Real LLM calls (Groq) | Implemented, **needs your `LLM_API_KEY`**; not tested against the live API |
| Document indexing + retrieval | **Placeholder**: adapter ready, waits for Member 1's code |
| Frontend | Member 3 |

## Member 1 (RAG): what to provide
Put these in `rag/` (no backend imports in your code, so nothing circular):

1. `rag/ingestion.py` with a function named `ingest_document` (or `ingest_pdf` / `ingest`):
   `ingest_document(pdf_path: str, document_id: str = None, filename: str = None) -> int | dict`
   Index the PDF at `pdf_path`; tag every chunk with `document_id`, the display `filename` and the page number. Return the chunk count (or `{"chunks": n}`). Raise an exception on failure. Extra parameters are optional — the adapter only passes the ones your function declares.
2. `rag/retriever.py` with `retrieve_context` (or `retrieve` / `search` / `query`):
   `retrieve_context(question: str, document_id: str = None)` returning either
   `{"context": "joined chunk text", "sources": [{"document": "NLP_Notes.pdf", "page": 4}]}`
   (key `answer_context` is accepted instead of `context`), or a list of chunk dicts with `text` and `document`/`source`/`filename` + `page`/`page_number` (also inside a `metadata` dict).
3. Persist the vector store on disk (e.g. `rag/vector_store/`) so it survives restarts. Dependencies go in a requirements file the backend venv can install.

Backend files PDFs are saved to: `uploads/<document_id>.pdf` (the path is passed to your ingest function).
Where the connection happens: `backend/app/services/rag_service.py` (`INGEST_NAMES`, `RETRIEVE_NAMES`, `_normalize_sources`). If your names/outputs differ, tell Member 2 — only that file changes.

Test the connection: start the backend → Swagger → `POST /documents/upload` (expect `"indexed": true`) → `POST /documents/query` (expect real `sources`). Or `python -m pytest tests/test_documents.py`.

## Member 3 (frontend): what to know
* Read `docs/API_CONTRACT.md`; field names are fixed: task `id` is an integer, `GET /tasks` → `{"tasks": [...]}`, chat uses `tasks_created`.
* Backend URL from one env variable (e.g. `VITE_API_URL=http://127.0.0.1:8000`). Dev origin must be `http://localhost:5173` or `http://127.0.0.1:5173` (other ports: add to `CORS_ORIGINS` in `.env`).
* Keep the `session_id` from the first `/chat` response and send it afterwards.
* After every `/chat` response, re-fetch `GET /tasks`.
* Show `message`/`indexed` from upload; show `sources` (document + page) under document answers.
* 422 bodies carry `errors[].field/message` for form errors.

## Quick end-to-end check
1. `GET /health` → ok. 2. Chat "Create a task to revise NLP" → appears in `GET /tasks`.
3. Chat "Remember that I prefer short explanations" then "What are my preferences?".
4. (Needs key) "Explain TF-IDF" and "Make a study plan for my NLP exam tomorrow".
5. (Needs Member 1) upload + query a PDF.
