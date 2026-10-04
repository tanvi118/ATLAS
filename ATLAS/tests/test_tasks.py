from sqlalchemy.orm import sessionmaker

from app.db.database import Base, make_engine
from app.schemas import TaskCreate
from app.services import task_service

NEW = {"title": "Revise NLP", "subject": "Natural Language Processing", "deadline": "2026-10-04",
       "priority": "high", "difficulty": "medium", "estimated_time_minutes": 60}


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


def test_create_and_list(client):
    r = client.post("/tasks", json=NEW)
    assert r.status_code == 201
    body = r.json()
    assert body["id"] == 1 and body["status"] == "pending" and body["created_at"]
    assert body["title"] == "Revise NLP" and body["deadline"] == "2026-10-04T00:00:00"
    tasks = client.get("/tasks").json()["tasks"]
    assert len(tasks) == 1 and tasks[0]["id"] == body["id"]


def test_defaults_applied(client):
    t = client.post("/tasks", json={"title": "Read chapter 3"}).json()
    assert t["priority"] == "medium" and t["difficulty"] == "medium" and t["deadline"] is None


def test_deadline_accepts_datetime_too(client):
    t = client.post("/tasks", json={"title": "Viva", "deadline": "2026-10-05T14:30:00"}).json()
    assert t["deadline"] == "2026-10-05T14:30:00"


def test_search_and_filter(client):
    client.post("/tasks", json={"title": "Revise NLP", "subject": "Language", "priority": "high"})
    client.post("/tasks", json={"title": "OS assignment", "subject": "Operating Systems"})
    titles = lambda **p: [t["title"] for t in client.get("/tasks", params=p).json()["tasks"]]
    assert titles(search="nlp") == ["Revise NLP"]
    assert titles(search="operating") == ["OS assignment"]   # matches subject
    assert titles(search="zzz") == []
    assert titles(priority="high") == ["Revise NLP"]
    assert titles(search="os", status="pending") == ["OS assignment"]
    assert client.get("/tasks", params={"status": "bogus"}).status_code == 422


def test_get_one(client):
    tid = client.post("/tasks", json=NEW).json()["id"]
    assert client.get(f"/tasks/{tid}").json()["title"] == "Revise NLP"


def test_update_priority_and_complete(client):
    tid = client.post("/tasks", json={**NEW, "priority": "low"}).json()["id"]
    r = client.patch(f"/tasks/{tid}", json={"priority": "high"})
    assert r.status_code == 200 and r.json()["priority"] == "high"
    r = client.patch(f"/tasks/{tid}", json={"status": "completed"})
    assert r.json()["status"] == "completed"
    assert client.get("/tasks", params={"status": "completed"}).json()["tasks"][0]["id"] == tid
    assert client.get("/tasks", params={"status": "pending"}).json()["tasks"] == []


def test_delete(client):
    tid = client.post("/tasks", json=NEW).json()["id"]
    assert client.delete(f"/tasks/{tid}").json() == {"id": tid, "deleted": True}
    assert client.get(f"/tasks/{tid}").status_code == 404


def test_invalid_task_id_404(client):
    for r in (client.get("/tasks/999"), client.patch("/tasks/999", json={"priority": "low"}), client.delete("/tasks/999")):
        assert r.status_code == 404 and "999" in r.json()["detail"]


def test_non_numeric_id_422(client):
    assert client.get("/tasks/abc").status_code == 422


def test_validation_errors_are_readable(client):
    r = client.post("/tasks", json={**NEW, "priority": "urgent"})
    assert r.status_code == 422
    err = r.json()
    assert err["detail"] == "Validation failed" and err["errors"][0]["field"] == "priority"
    assert client.post("/tasks", json={"subject": "x"}).status_code == 422          # missing title
    assert client.post("/tasks", json={"title": "  "}).status_code == 422           # blank title
    assert client.post("/tasks", json={"title": "x", "deadline": "not-a-date"}).status_code == 422
    assert client.post("/tasks", json={"title": "x", "estimated_time_minutes": -5}).status_code == 422


def test_patch_validation(client):
    tid = client.post("/tasks", json=NEW).json()["id"]
    assert client.patch(f"/tasks/{tid}", json={}).status_code == 422
    assert client.patch(f"/tasks/{tid}", json={"status": "done"}).status_code == 422
    assert client.patch(f"/tasks/{tid}", json={"priority": None}).status_code == 422


def test_accidental_duplicate_is_not_created_twice(client):
    a = client.post("/tasks", json=NEW).json()
    b = client.post("/tasks", json=NEW).json()
    assert a["id"] == b["id"] and len(client.get("/tasks").json()["tasks"]) == 1


def test_tasks_persist_after_restart(tmp_path):
    url = f"sqlite:///{tmp_path / 'persist.db'}"
    engine = make_engine(url)
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as s:
        task_service.create_task(s, TaskCreate(title="Survives restart", priority="high"))
    engine.dispose()  # "stop the backend"
    engine2 = make_engine(url)  # "start it again"
    with sessionmaker(bind=engine2)() as s:
        tasks = task_service.get_tasks(s)
    assert [t.title for t in tasks] == ["Survives restart"]
    engine2.dispose()
