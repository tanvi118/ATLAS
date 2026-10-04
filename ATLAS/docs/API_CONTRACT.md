# ATLAS API Contract (v0.2)

Base URL `http://127.0.0.1:8000` · Swagger `/docs` · JSON everywhere except file upload (multipart).
Owner: Member 2. Members 1 and 3: request changes, don't edit. This file matches the code in `backend/app/schemas.py`.

## Values
| Field | Allowed values |
|---|---|
| priority | `low`, `medium` (default), `high` |
| difficulty | `easy`, `medium` (default), `hard` |
| status | `pending` (default), `in_progress`, `completed` |
| intent | `chat`, `create_task`, `list_tasks`, `update_task`, `complete_task`, `study_plan`, `document_qa`, `remember_preference`, `use_memory` |

## Objects
**Task**
| field | type | notes |
|---|---|---|
| id | integer | assigned by server |
| title | string | required, 1–200 chars |
| subject | string \| null | max 100 |
| deadline | ISO datetime \| null | send `"2026-10-04"` or `"2026-10-04T14:30:00"`; returned as `"2026-10-04T00:00:00"` (no timezone) |
| priority, difficulty, status | see above | |
| estimated_time_minutes | integer \| null | 1–10080 |
| created_at | ISO datetime (UTC) | read-only |

Optional fields are always present in responses, as `null` — never omitted.
**Source**: `{"document": "NLP_Notes.pdf", "page": 4}` (`page` may be `null`).

## Health
`GET /health` → `200 {"status": "ok"}`

## Tasks
| Method | Path | Success |
|---|---|---|
| GET | `/tasks?status=&priority=&search=` | `200 {"tasks": [Task, ...]}` — soonest deadline first; `search` matches title or subject (case-insensitive) |
| POST | `/tasks` | `201 Task` |
| GET | `/tasks/{task_id}` | `200 Task` |
| PATCH | `/tasks/{task_id}` | `200 Task` — send any subset of fields (at least one); fields can't be `null` except subject, deadline, estimated_time_minutes |
| DELETE | `/tasks/{task_id}` | `200 {"id": 1, "deleted": true}` |

```json
POST /tasks
{"title": "Revise NLP", "subject": "Natural Language Processing", "deadline": "2026-10-04",
 "priority": "high", "difficulty": "medium", "estimated_time_minutes": 60}
```
Mark complete: `PATCH /tasks/1` `{"status": "completed"}`. Re-sending an identical task within 10 s returns the existing one (accidental double-click protection).

## Chat
`POST /chat`
```json
{"message": "Create a task to revise NLP", "session_id": null}
```
`message` 1–2000 chars. `session_id` optional/null: the server generates one and returns it. **Reuse the returned id** so history and preferences carry over.

Response — identical shape for every intent:
```json
{"reply": "Task created: #1 Revise NLP — due no deadline, medium priority, pending.",
 "intent": "create_task",
 "tasks_created": [ Task ],
 "sources": [ Source ],
 "session_id": "b1f0..."}
```
| intent | example | effect |
|---|---|---|
| chat | "Explain TF-IDF in simple words." | LLM answer (uses last 6 messages + saved preferences) |
| create_task | "Create a high priority DBMS revision task for tomorrow, estimated 90 minutes." | saved; returned in `tasks_created` |
| list_tasks | "Show all my pending tasks." | listed in `reply` (use `GET /tasks` for data) |
| update_task | "Change my NLP task priority to high." | DB updated; confirmed in `reply` |
| complete_task | "Mark my OS assignment as completed." | status → `completed` |
| study_plan | "Make a revision plan for my NLP exam tomorrow." | LLM JSON → validated → saved; all in `tasks_created`; uses saved preferences |
| remember_preference | "Remember that I prefer short explanations." / "I prefer studying in the evening." | saved per `session_id` |
| use_memory | "What are my preferences?" | lists saved preferences |
| document_qa | "From my uploaded notes, explain TF-IDF." | RAG + LLM, fills `sources`; if RAG isn't connected the reply says so, `sources` = `[]` |

Behaviour to rely on
* Task intents never need an LLM key.
* LLM problems (no key, bad key, rate limit, timeout, provider error) → still `200`, explanation in `reply`, nothing saved.
* Missing/ambiguous task reference → `reply` is a clarifying question; nothing changes. Users can say "task 3".
* Update/complete don't return the task object: refresh `GET /tasks` after each chat response.

## Documents
**`POST /documents/upload`** — `multipart/form-data`, field `file`; `.pdf` only, starts with `%PDF`, max 10 MB.
```json
201 {"document_id": "9f2c…(32 hex)", "filename": "NLP_Notes.pdf", "indexed": true, "chunks": 42, "message": "File saved and indexed."}
```
If RAG isn't connected the file is still saved but `"indexed": false`, `"chunks": null`, message `"File saved, but NOT indexed. …"`. Show `indexed` to the user; don't assume success.
Errors: `400` not a PDF / wrong type · `413` over 10 MB.

**`POST /documents/query`**
```json
{"question": "What is TF-IDF?", "document_id": "9f2c…", "session_id": "demo-session"}
```
`document_id`, `session_id` optional (no `document_id` = search everything).
```json
200 {"reply": "…", "intent": "document_qa", "sources": [{"document": "NLP_Notes.pdf", "page": 4}], "session_id": "demo-session"}
```
RAG not connected, nothing relevant found, or LLM failure → `200` with an explanatory `reply` and `"sources": []`. Unknown/invalid `document_id` → `404`. Sources come only from real retrieval.

## Errors
| status | when | body |
|---|---|---|
| 400 | bad upload (not PDF) | `{"detail": "Only PDF files are allowed."}` |
| 404 | task or document not found | `{"detail": "Task 99 not found"}` |
| 413 | upload too large | `{"detail": "File is too large (max 10 MB)."}` |
| 422 | invalid input | `{"detail": "Validation failed", "errors": [{"field": "priority", "message": "Input should be 'low', 'medium' or 'high'"}]}` |
| 500 | unexpected error in /chat | `{"detail": "Something went wrong while handling your message."}` |

## CORS
Allowed origins come from `CORS_ORIGINS` (default `http://localhost:5173,http://127.0.0.1:5173`). No wildcard.
