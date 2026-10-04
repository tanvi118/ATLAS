# Demo script (3–5 min) — use Swagger at http://127.0.0.1:8000/docs
Use `session_id: "demo"` in every chat call.

1. **Health (15 s)** `GET /health` → `{"status":"ok"}`. *"FastAPI backend is up; SQLite is the database."*
2. **Task via chat (45 s)** `POST /chat` `{"message":"Create a high priority NLP revision task for tomorrow, estimated 90 minutes.","session_id":"demo"}`
   → show `intent: create_task` and `tasks_created`. Then `GET /tasks`. *"A rule-based router handled this — no LLM needed — and the task is really in the database."*
3. **Update + complete (45 s)** "Change my NLP task priority to high." → "Mark my NLP revision task as completed." → `GET /tasks?status=completed`.
4. **Memory (45 s)** "Remember that I prefer studying in the evening." → "What are my preferences?". *"Stored in the memories table under this session id; restart the server and ask again — it's still there."*
5. **Study plan (60 s, needs API key)** "Make a revision plan for my AI exam in 3 days." → generated tasks in `tasks_created`. *"The LLM returns JSON; I validate it with Pydantic before saving, and it takes the evening preference into account."*
6. **Documents (45 s)** `POST /documents/upload` a PDF → show `indexed`. If Member 1's RAG is connected, `POST /documents/query` and show `sources` (document + page). If not: *"The PDF is saved, but indexing is not connected yet — the API says so honestly and returns no fake sources."*
7. **Architecture (30 s)** Frontend → FastAPI routes → agent (intent router) → task service / memory / LLM service / RAG adapter → SQLite → one standard response.

Backup if the API key or internet fails: do steps 1–4 only (no LLM needed).
