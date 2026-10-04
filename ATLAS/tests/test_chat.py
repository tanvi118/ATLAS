import json
from datetime import date, timedelta

import httpx
import pytest

from app.config import settings
from app.services import agent_service, llm_service, rag_service

from helpers import plan_json, say


# ---------- intent detection ----------
@pytest.mark.parametrize("msg,intent", [
    ("Explain TF-IDF in simple words.", "chat"),
    ("Create a high priority DBMS revision task for tomorrow.", "create_task"),
    ("Show all my pending tasks.", "list_tasks"),
    ("Change my NLP task priority to high.", "update_task"),
    ("Mark my OS assignment as completed.", "complete_task"),
    ("Make a revision plan for my NLP exam tomorrow.", "study_plan"),
    ("From my uploaded notes, explain TF-IDF.", "document_qa"),
    ("Remember that I prefer studying in the evening.", "remember_preference"),
    ("Show my completed tasks", "list_tasks"),
])
def test_detect_intent(msg, intent):
    assert agent_service.detect_intent(msg) == intent


def test_field_parsers():
    today = date(2026, 10, 3)  # a Saturday
    assert agent_service.parse_deadline("due tomorrow", today)[0] == date(2026, 10, 4)
    assert agent_service.parse_deadline("by friday", today)[0] == date(2026, 10, 9)
    assert agent_service.parse_deadline("in 3 days", today)[0] == date(2026, 10, 6)
    assert agent_service.parse_deadline("on 2026-11-02", today)[0] == date(2026, 11, 2)
    assert agent_service.parse_minutes("estimated 90 minutes") == 90
    assert agent_service.parse_minutes("takes 1.5 hours") == 90
    assert agent_service.parse_priority("make it low priority") == "low"


# ---------- task actions through chat (no LLM involved) ----------
def test_create_task_via_chat(client):
    body = say(client, "Create a high priority NLP revision task for tomorrow, estimated 90 minutes.")
    assert body["intent"] == "create_task" and body["session_id"] == "demo-session"
    t = body["tasks_created"][0]
    assert t["title"] == "NLP revision" and t["priority"] == "high" and t["estimated_time_minutes"] == 90
    assert t["deadline"] == (date.today() + timedelta(days=1)).isoformat() + "T00:00:00"
    # it is really in the database
    assert client.get(f"/tasks/{t['id']}").json()["title"] == "NLP revision"


def test_create_task_needs_title(client):
    body = say(client, "Create a high priority task")
    assert body["intent"] == "create_task" and body["tasks_created"] == []
    assert client.get("/tasks").json()["tasks"] == []


def test_list_update_complete_flow(client):
    say(client, "Create a task to revise NLP")
    say(client, "Add a task: OS assignment")
    pending = say(client, "Show all my pending tasks")
    assert pending["intent"] == "list_tasks" and "NLP" in pending["reply"] and "OS assignment" in pending["reply"]

    upd = say(client, "Change my NLP task priority to high.")
    assert upd["intent"] == "update_task"
    nlp = next(t for t in client.get("/tasks").json()["tasks"] if "NLP" in t["title"])
    assert nlp["priority"] == "high"

    done = say(client, "Mark my OS assignment as completed.")
    assert done["intent"] == "complete_task"
    assert [t["status"] for t in client.get("/tasks", params={"status": "completed"}).json()["tasks"]] == ["completed"]
    assert "OS assignment" not in say(client, "Show all my pending tasks")["reply"]


def test_ambiguous_or_missing_target_asks_back(client):
    say(client, "Create a task to revise NLP unit 1")
    say(client, "Create a task to revise NLP unit 2")
    body = say(client, "Mark my NLP task as done")
    assert "which one" in body["reply"].lower()
    assert all(t["status"] == "pending" for t in client.get("/tasks").json()["tasks"])
    assert "couldn't find" in say(client, "Mark my chemistry lab as done")["reply"]
    assert "What should I change" in say(client, "Change my NLP task")["reply"]


# ---------- LLM-backed intents (mocked) ----------
def test_chat_uses_llm(client, monkeypatch):
    monkeypatch.setattr(llm_service, "generate_response", lambda m, s=None: "TF-IDF weighs rare words higher.")
    body = say(client, "Explain TF-IDF in simple words.")
    assert body["intent"] == "chat" and body["reply"] == "TF-IDF weighs rare words higher."
    assert body["tasks_created"] == [] and body["sources"] == []


def test_chat_without_api_key_is_controlled(client, monkeypatch):
    monkeypatch.undo()  # use the real generate_response
    monkeypatch.setattr(settings, "llm_api_key", "")
    body = say(client, "Explain TF-IDF in simple words.")
    assert body["intent"] == "chat" and "isn't configured" in body["reply"]
    # task features still work without a key
    assert say(client, "Create a task to revise DBMS")["tasks_created"]


def test_study_plan_creates_tasks(client, monkeypatch):
    monkeypatch.setattr(llm_service, "generate_response", lambda m, s=None: "```json\n" + plan_json() + "\n```")
    body = say(client, "Make a revision plan for my NLP exam tomorrow.")
    assert body["intent"] == "study_plan" and len(body["tasks_created"]) == 3
    assert len(client.get("/tasks").json()["tasks"]) == 3


def test_study_plan_retries_then_gives_up_on_bad_json(client, monkeypatch):
    calls = []
    def bad(m, s=None):
        calls.append(1)
        return "Sure! Here's a plan: study hard."
    monkeypatch.setattr(llm_service, "generate_response", bad)
    body = say(client, "Make a study plan for my AI exam")
    assert len(calls) == 2 and body["tasks_created"] == []
    assert "didn't create any tasks" in body["reply"]
    assert client.get("/tasks").json()["tasks"] == []


def test_study_plan_rejects_invalid_task_fields(client, monkeypatch):
    bad = json.dumps({"summary": "x", "tasks": [{"title": "A", "priority": "urgent"}]})
    monkeypatch.setattr(llm_service, "generate_response", lambda m, s=None: bad)
    assert say(client, "Make a study plan for my AI exam")["tasks_created"] == []


def test_study_plan_without_key(client, monkeypatch):
    monkeypatch.undo()
    monkeypatch.setattr(settings, "llm_api_key", "put_your_key_here")
    body = say(client, "Make a study plan for my AI exam")
    assert body["intent"] == "study_plan" and "isn't configured" in body["reply"] and body["tasks_created"] == []


def test_document_qa_via_chat_when_rag_unavailable(client, monkeypatch):
    def unavailable(q, document_id=None):
        raise rag_service.RAGUnavailableError()
    monkeypatch.setattr(rag_service, "retrieve_context", unavailable)
    body = say(client, "From my uploaded notes, explain TF-IDF.")
    assert body["intent"] == "document_qa" and "not connected" in body["reply"] and body["sources"] == []


def test_document_qa_via_chat_with_mocked_rag(client, monkeypatch):
    monkeypatch.setattr(rag_service, "retrieve_context", lambda q, document_id=None: {
        "context": "TF-IDF = term frequency x inverse document frequency.",
        "sources": [{"document": "NLP_Notes.pdf", "page": 4}]})
    seen = {}
    def fake_llm(messages, system=None):
        seen["prompt"] = messages[0]["content"]
        return "TF-IDF weighs terms by rarity."
    monkeypatch.setattr(llm_service, "generate_response", fake_llm)
    body = say(client, "From my uploaded notes, explain TF-IDF.")
    assert body["sources"] == [{"document": "NLP_Notes.pdf", "page": 4}]
    assert "inverse document frequency" in seen["prompt"]


# ---------- request validation / session ----------
def test_chat_validation_and_session(client):
    assert client.post("/chat", json={"message": ""}).status_code == 422
    assert client.post("/chat", json={}).status_code == 422
    body = client.post("/chat", json={"message": "Show my tasks"}).json()
    assert len(body["session_id"]) > 10  # generated when not supplied


# ---------- llm_service error mapping (httpx mocked, no network) ----------
class FakeResp:
    def __init__(self, status, data=None):
        self.status_code, self._data = status, data
    def json(self):
        if self._data is None:
            raise ValueError
        return self._data


@pytest.fixture()
def keyed(monkeypatch):
    monkeypatch.undo()
    monkeypatch.setattr(settings, "llm_api_key", "real-looking-key")
    monkeypatch.setattr(settings, "llm_base_url", "https://example.invalid/v1")


def test_llm_success(keyed, monkeypatch):
    seen = {}
    def fake_post(url, headers, json, timeout):
        seen.update(url=url, json=json)
        return FakeResp(200, {"choices": [{"message": {"content": " hi "}}]})
    monkeypatch.setattr(httpx, "post", fake_post)
    assert llm_service.generate_response([{"role": "user", "content": "yo"}], "sys") == "hi"
    assert seen["url"].endswith("/chat/completions") and seen["json"]["messages"][0]["role"] == "system"


@pytest.mark.parametrize("status,fragment", [(401, "rejected the API key"), (429, "rate limit"),
                                              (400, "LLM_MODEL"), (500, "had a problem")])
def test_llm_http_errors(keyed, monkeypatch, status, fragment):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: FakeResp(status))
    with pytest.raises(llm_service.LLMError) as e:
        llm_service.generate_response([{"role": "user", "content": "x"}])
    assert fragment in e.value.user_message and "real-looking-key" not in e.value.user_message


def test_llm_timeout_and_network(keyed, monkeypatch):
    for exc, fragment in ((httpx.ReadTimeout("t"), "too long"), (httpx.ConnectError("c"), "Couldn't reach")):
        def raiser(*a, _e=exc, **k):
            raise _e
        monkeypatch.setattr(httpx, "post", raiser)
        with pytest.raises(llm_service.LLMError) as e:
            llm_service.generate_response([{"role": "user", "content": "x"}])
        assert fragment in e.value.user_message


def test_llm_malformed_body(keyed, monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: FakeResp(200, {"oops": 1}))
    with pytest.raises(llm_service.LLMError):
        llm_service.generate_response([{"role": "user", "content": "x"}])
