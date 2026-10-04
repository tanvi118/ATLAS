"""Persistent preferences (memories table) and recent chat history (conversations table)."""
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Conversation, Memory


def parse_preference(text: str) -> tuple[str, str] | None:
    """Turn a sentence into (key, value). Returns None if there is nothing to remember.

    'I prefer studying in the evening'        -> ('study_time', 'evening')
    'Remember that I prefer short explanations' -> ('explanation_style', 'short')
    anything else                              -> ('note_<slug>', the sentence)
    """
    body = re.sub(r"^\s*(please\s+)?remember(\s+that)?\s*", "", text.strip(), flags=re.I).rstrip(" .!")
    if not body:
        return None
    m = re.search(r"\b(morning|afternoon|evening|night)s?\b", body, re.I)
    if m and re.search(r"\b(prefer|study|studying|revise|revising|work|working)\b", body, re.I):
        return "study_time", m.group(1).lower()
    m = re.search(r"\b(short|brief|concise|detailed|simple|step[- ]by[- ]step)\s+(explanations?|answers?|responses?)\b", body, re.I)
    if m:
        return "explanation_style", m.group(1).lower()
    slug = re.sub(r"[^a-z0-9]+", "_", body.lower()).strip("_")[:40]
    return f"note_{slug}", body[:500]


def save_preference(db: Session, session_id: str, key: str, value: str) -> Memory:
    """Insert, or update in place if this key already exists for the session (no repeated copies)."""
    row = db.scalars(select(Memory).where(Memory.session_id == session_id, Memory.key == key)).first()
    if row:
        row.value = value
    else:
        row = Memory(session_id=session_id, key=key, value=value)
        db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_preferences(db: Session, session_id: str) -> dict[str, str]:
    rows = db.scalars(select(Memory).where(Memory.session_id == session_id).order_by(Memory.id))
    return {r.key: r.value for r in rows}


def preferences_as_text(prefs: dict[str, str]) -> str:
    return "; ".join(f"{k.replace('_', ' ')}: {v}" for k, v in prefs.items())


def add_message(db: Session, session_id: str, role: str, content: str) -> None:
    db.add(Conversation(session_id=session_id, role=role, content=content))
    db.commit()


def get_recent_messages(db: Session, session_id: str, limit: int = 6) -> list[dict]:
    rows = db.scalars(select(Conversation).where(Conversation.session_id == session_id)
                      .order_by(Conversation.id.desc()).limit(limit))
    return [{"role": r.role, "content": r.content} for r in reversed(list(rows))]
