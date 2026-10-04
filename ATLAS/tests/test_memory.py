import pytest
from helpers import plan_json, say

from app.services import llm_service, memory_service


@pytest.mark.parametrize("text,expected", [
    ("Remember that I prefer studying in the evening.", ("study_time", "evening")),
    ("I prefer studying in the morning", ("study_time", "morning")),
    ("Remember that I prefer short explanations", ("explanation_style", "short")),
])
def test_parse_preference(text, expected):
    assert memory_service.parse_preference(text) == expected


def test_preference_saved_updated_and_used_in_plan(client, monkeypatch):
    assert "evening" in say(client, "Remember that I prefer studying in the evening.")["reply"]
    say(client, "Remember that I prefer studying in the evening.")  # repeat -> no duplicate row
    say(client, "I prefer studying in the morning")                 # same key -> updated
    prefs = say(client, "What are my preferences?")
    assert prefs["intent"] == "use_memory" and prefs["reply"].count("study time") == 1 and "morning" in prefs["reply"]

    seen = {}
    def fake_llm(messages, system=None):
        seen["system"] = system
        return plan_json()
    monkeypatch.setattr(llm_service, "generate_response", fake_llm)
    say(client, "Make a study plan for tomorrow")
    assert "study time: morning" in seen["system"]


def test_preferences_reach_normal_chat_context(client, monkeypatch):
    say(client, "Remember that I prefer short explanations")
    seen = {}
    monkeypatch.setattr(llm_service, "generate_response", lambda m, s=None: (seen.update(system=s), "ok")[1])
    say(client, "Explain TF-IDF")
    assert "explanation style: short" in seen["system"]


def test_preferences_are_per_session(client):
    say(client, "Remember that I prefer studying at night", session="a")
    assert "I don't have any saved preferences" in say(client, "What do you remember about me?", session="b")["reply"]
    assert "night" in say(client, "What do you remember about me?", session="a")["reply"]


def test_nothing_to_remember_is_not_claimed_as_saved(client):
    reply = say(client, "Remember")["reply"]
    assert "What should I remember" in reply
    assert "don't have any saved" in say(client, "What are my preferences?")["reply"]


def test_memory_service_persists_in_database(db_session):
    memory_service.save_preference(db_session, "s1", "study_time", "evening")
    memory_service.add_message(db_session, "s1", "user", "hi")
    memory_service.add_message(db_session, "s1", "assistant", "hello")
    assert memory_service.get_preferences(db_session, "s1") == {"study_time": "evening"}
    assert [m["role"] for m in memory_service.get_recent_messages(db_session, "s1")] == ["user", "assistant"]
    assert memory_service.get_recent_messages(db_session, "other") == []


def test_chat_sends_recent_history_to_llm(client, monkeypatch):
    seen = []
    monkeypatch.setattr(llm_service, "generate_response", lambda m, s=None: (seen.append(m), "ok")[1])
    say(client, "Explain TF-IDF in simple words.")
    say(client, "Give an example of it.")
    assert [m["role"] for m in seen[1]] == ["user", "assistant", "user"]
    say(client, "Hello from another session", session="other")
    assert len(seen[2]) == 1  # other sessions don't see this history
