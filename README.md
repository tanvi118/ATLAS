# ATLAS — Backend (Member 2)

ATLAS is an AI-powered academic assistant for students. This is the **backend**: a FastAPI service that manages tasks, talks to an LLM, routes chat messages to the right action, remembers preferences, and prepares PDF uploads for Member 1's RAG module. Member 3's frontend talks to it over HTTP.

## Features
* Task CRUD with search/filter, stored in SQLite (survives restarts)
* `/chat` with an intent router: chat, create/list/update/complete tasks, study plans, preferences, document Q&A
* Task commands work **without** an LLM key; general chat and study plans use the LLM (Groq by default)
* Persistent preferences and conversation history per `session_id`
* PDF upload (validated, safe filenames) and a RAG adapter — retrieval turns on once Member 1's code is added
* Automated tests with a mocked LLM and an in-memory database

## Tech stack
Python 3.11/3.12 · FastAPI · Uvicorn · Pydantic v2 · SQLAlchemy 2 · SQLite · httpx · python-dotenv · pytest

## Folder structure
```
backend/app/
  main.py  config.py  schemas.py
  api/       health.py  tasks.py  chat.py  documents.py     <- HTTP routes (thin)
  services/  task_service.py  llm_service.py  agent_service.py  memory_service.py  rag_service.py
  db/        database.py  models.py                         <- tasks, memories, conversations
backend/requirements.txt
tests/       conftest.py helpers.py test_tasks.py test_chat.py test_memory.py test_documents.py
docs/        API_CONTRACT.md  INTEGRATION_GUIDE.md  DEMO_SCRIPT.md
rag/ (Member 1)   frontend/ (Member 3)   uploads/ (created on first upload)
.env.example  .gitignore  pytest.ini
```

## Setup (Windows PowerShell, from the ATLAS folder in VS Code)
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r backend\requirements.txt
Copy-Item .env.example .env
```
Edit `.env` and set `LLM_API_KEY` (free key: https://console.groq.com/keys). Never commit `.env`.

**If PowerShell blocks activation** ("running scripts is disabled"), skip activation and call the venv's Python directly — no policy change needed:
```powershell
.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --app-dir backend
```
(Or for this window only: `Set-ExecutionPolicy -Scope Process Bypass`.)

## Run
```powershell
python -m uvicorn app.main:app --reload --app-dir backend
```
* API: http://127.0.0.1:8000 · Swagger: http://127.0.0.1:8000/docs · Health: http://127.0.0.1:8000/health
* VS Code: select the `.venv` interpreter, press F5 to debug ("ATLAS backend").
* `atlas.db` is created in the project root on first start. After changing the database models, delete `atlas.db` (dev data only).

## Test
```powershell
python -m pytest -q
```
No API key needed; the LLM is mocked and tests use a temporary in-memory database.

## Quick try (Swagger → POST /chat)
`{"message": "Create a high priority NLP revision task for tomorrow", "session_id": null}` → then `GET /tasks`.

## Current limitations
* **Document search needs Member 1's code.** Until then upload saves the PDF with `"indexed": false`, and questions get a "not connected yet" reply with no sources. See `docs/INTEGRATION_GUIDE.md`.
* The live Groq call is untested without your key; set `LLM_MODEL` if the default model isn't available to you.
* Intent detection is rule-based and English-only. Tasks created from chat get no subject.
* `session_id` is a plain label — there is no login or multi-user security.
* Changing database models needs a manual reset of `atlas.db` (no migrations).
