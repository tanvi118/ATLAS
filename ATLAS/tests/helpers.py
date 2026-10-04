import json
from datetime import date, timedelta

RESPONSE_KEYS = {"reply", "intent", "tasks_created", "sources", "session_id"}


def say(client, message, session="demo-session"):
    """POST /chat, check the stable response schema, return the JSON body."""
    r = client.post("/chat", json={"message": message, "session_id": session})
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) == RESPONSE_KEYS
    return body


def plan_json(n=3):
    d = (date.today() + timedelta(days=2)).isoformat()
    return json.dumps({"summary": "3-step NLP plan.", "tasks": [
        {"title": f"NLP step {i}", "subject": "NLP", "deadline": d, "priority": "high",
         "difficulty": "medium", "estimated_time_minutes": 45} for i in range(1, n + 1)]})
