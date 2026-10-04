"""Lightweight intent router.

Flow:  message -> detect_intent() -> handler -> AgentResult
* Task commands use plain rules (reliable, no LLM needed).
* chat and study_plan call the LLM; the LLM output is only ever treated as data
  (validated with Pydantic) and never executed.
"""
import json
import re
from datetime import date, datetime, time, timedelta

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from app.schemas import AgentResult, Intent, SourceResponse, TaskCreate, TaskResponse, TaskUpdate
from app.services import llm_service, memory_service, rag_service, task_service
from app.services.llm_service import LLMError
from app.services.rag_service import RAGUnavailableError
from app.services.task_service import TaskNotFoundError

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

# ---------------------------------------------------------------- field parsers
_DEADLINE_RE = re.compile(
    r"\b(?:(?:for|by|on|due(?:\s+on)?|before|until|to)\s+)?"
    r"(day after tomorrow|tomorrow|today|next week|(?:next\s+)?(?:" + "|".join(WEEKDAYS) + r")"
    r"|in\s+\d+\s+days?|\d{4}-\d{2}-\d{2})\b",
    re.I,
)
_PRIORITY_RE = re.compile(
    r"\b(high|medium|low)[\s-]*priority\b|\bpriority\s*(?:to|is|=|:|of)?\s*(high|medium|low)\b|\b(urgent|asap)\b", re.I)
_DIFFICULTY_RE = re.compile(
    r"\b(easy|medium|hard)[\s-]*difficulty\b|\bdifficulty\s*(?:to|is|=|:|of)?\s*(easy|medium|hard)\b|\b(easy|hard)\s+task\b", re.I)
_TIME_RE = re.compile(
    r"\b(?:estimated?(?:\s+time)?(?:\s+(?:of|is|to|at))?\s*)?(\d+(?:\.\d+)?)\s*(hours?|hrs?|minutes?|mins?)\b", re.I)
_STATUS_RE = re.compile(
    r"\bstatus\s*(?:to|is|=|:)?\s*(pending|in[\s_-]progress|completed|done)\b", re.I)


def parse_deadline(text: str, today: date) -> tuple[date | None, re.Match | None]:
    m = _DEADLINE_RE.search(text)
    if not m:
        return None, None
    word = m.group(1).lower()
    if word == "today":
        d = today
    elif word == "tomorrow":
        d = today + timedelta(days=1)
    elif word == "day after tomorrow":
        d = today + timedelta(days=2)
    elif word == "next week":
        d = today + timedelta(days=7)
    elif word.startswith("in "):
        d = today + timedelta(days=int(re.search(r"\d+", word).group()))
    elif re.fullmatch(r"\d{4}-\d{2}-\d{2}", word):
        try:
            d = date.fromisoformat(word)
        except ValueError:
            return None, m
    else:  # weekday name -> next occurrence (never today)
        target = WEEKDAYS.index(word.replace("next", "").strip())
        d = today + timedelta(days=(target - today.weekday()) % 7 or 7)
    return d, m


def parse_priority(text: str) -> str | None:
    m = _PRIORITY_RE.search(text)
    if not m:
        return None
    return (m.group(1) or m.group(2) or "high").lower()


def parse_difficulty(text: str) -> str | None:
    m = _DIFFICULTY_RE.search(text)
    return (m.group(1) or m.group(2) or m.group(3)).lower() if m else None


def parse_minutes(text: str) -> int | None:
    m = _TIME_RE.search(text)
    if not m:
        return None
    value = float(m.group(1))
    return round(value * 60) if m.group(2).lower().startswith("h") else round(value)


# ---------------------------------------------------------------- intent detection
def detect_intent(message: str) -> Intent:
    t = message.lower().strip()
    has_task_word = re.search(r"\btasks?\b", t) is not None

    if re.match(r"^(please\s+)?remember\b", t) or re.match(r"^(i\s+(really\s+)?prefer|my preference is)\b", t):
        return "remember_preference"
    if re.search(r"\b(plan|schedule|timetable|roadmap)\b", t) and not has_task_word:
        return "study_plan"
    if re.search(r"\b(what do you (remember|know)|(show|list|what are) my (saved )?preferences)\b", t):
        return "use_memory"
    if (re.search(r"\b(change|update|set|make|edit|move|push)\b", t)
            and re.search(r"\b(priority|difficulty|deadline|due date|status|estimated time)\b", t)) \
            or re.search(r"\b(reschedule|postpone)\b", t) \
            or (re.match(r"^(please\s+)?(change|update|edit)\b", t) and has_task_word):
        return "update_task"
    if (re.search(r"\b(create|add|new)\b", t) and re.search(r"\b(task|todo|to-do|reminder|assignment|homework)\b", t)) \
            or re.search(r"\bremind me\b", t):
        return "create_task"
    if re.search(r"\b(mark|set|tick|check off)\b.*\b(complete|completed|done|finished)\b", t) \
            or re.search(r"\b(finished|completed)\s+(my|the|with)\b", t) \
            or re.search(r"\bcomplete\s+(my|the)\b", t):
        return "complete_task"
    if (re.search(r"\b(show|list|view|display|see|what|which|get)\b", t)
            and re.search(r"\b(tasks?|todo|to-do|assignments|deadlines)\b", t)) \
            or re.search(r"\bmy (tasks|todo|to-do)\b", t):
        return "list_tasks"
    if re.search(r"\b(uploaded|my)\s+(notes|pdf|pdfs|document|documents|file|files|slides)\b", t) \
            or re.search(r"\b(from|according to) (the|my) (pdf|document|notes)\b", t):
        return "document_qa"
    return "chat"


# ---------------------------------------------------------------- helpers
def _result(intent: Intent, reply: str, tasks=()) -> AgentResult:
    return AgentResult(reply=reply, intent=intent, tasks_created=[TaskResponse.model_validate(t) for t in tasks])


def _fmt(t) -> str:
    return f"#{t.id} {t.title} — due {t.deadline.date() if t.deadline else 'no deadline'}, {t.priority} priority, {t.status}"


_STOP = set("""change update set make mark my the a an task tasks assignment as to priority high medium low
difficulty easy hard deadline due date completed complete done finished finish status please i have is of for on by
in pending progress tomorrow today next week mins min minutes hours hour hr hrs reschedule move postpone edit it this
that and with from me can you could would like want need push""".split() + WEEKDAYS)


def _keywords(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return [w for w in words if not w.isdigit() and len(w) >= 2 and w not in _STOP]


def _resolve_target(db: Session, message: str, include_completed: bool):
    """Find the one task the user means. Returns (task, None) or (None, clarifying reply)."""
    m = re.search(r"(?:\btask|\bid|#)\s*#?(\d+)\b", message.lower())
    if m:
        try:
            return task_service.get_task(db, int(m.group(1))), None
        except TaskNotFoundError:
            return None, f"I couldn't find task #{m.group(1)}."
    keywords = _keywords(message)
    if not keywords:
        return None, "Which task do you mean? Tell me part of its title, or its id (e.g. 'task 3')."
    ranked = task_service.search_tasks(db, keywords, include_completed)
    if not ranked:
        return None, "I couldn't find a matching task. Say 'show my tasks' to see what you have."
    best = [t for score, t in ranked if score == ranked[0][0]]
    if len(best) > 1:
        options = "\n".join(_fmt(t) for t in best[:5])
        return None, f"Several tasks match — which one? Use its id (e.g. 'task {best[0].id}'):\n{options}"
    return best[0], None


# ---------------------------------------------------------------- task handlers
_LEAD_RE = re.compile(
    r"^\s*(?:please\s+)?(?:(?:can|could) you\s+)?(?:create|add|make|set up|remind me)\s+(?:me\s+)?(?:a|an|the|my|new)?\s*(?:new\s+)?", re.I)


def _extract_title(message: str) -> str:
    text = message
    for rx in (_PRIORITY_RE, _DIFFICULTY_RE, _TIME_RE, _DEADLINE_RE):
        text = rx.sub(" ", text)
    text = _LEAD_RE.sub("", text)
    text = re.sub(r"\b(?:task|reminder|to-?do)\b", " ", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip(" ,.;:-")
    text = re.sub(r"^(?:called|named|titled|to|for|about)\s+", "", text, flags=re.I)
    text = re.sub(r"\s+(?:for|by|on|due|to|and)$", "", text, flags=re.I).strip(" ,.;:-")
    return text[:1].upper() + text[1:]


def _handle_create(db: Session, message: str, today: date, session_id: str = "") -> AgentResult:
    title = _extract_title(message)
    if not title:
        return _result("create_task", "What should the task be called? For example: 'Create a task to revise DBMS tomorrow'.")
    deadline, _ = parse_deadline(message, today)
    fields = {"title": title, "deadline": datetime.combine(deadline, time.min) if deadline else None}
    for key, value in (("priority", parse_priority(message)), ("difficulty", parse_difficulty(message)),
                       ("estimated_time_minutes", parse_minutes(message))):
        if value is not None:
            fields[key] = value
    try:
        data = TaskCreate(**fields)
    except ValidationError:
        return _result("create_task", "I couldn't read the task details. Try: 'Create a high priority NLP revision task for tomorrow'.")
    task = task_service.create_task(db, data)  # raises on DB failure -> never claims success falsely
    return _result("create_task", f"Task created: {_fmt(task)}.", [task])


def _handle_list(db: Session, message: str, today: date, session_id: str = "") -> AgentResult:
    t = message.lower()
    status = ("in_progress" if re.search(r"\bin[\s-]progress\b", t)
              else "completed" if re.search(r"\b(completed|done|finished)\b", t)
              else "pending" if re.search(r"\bpending\b", t) else None)
    pm = re.search(r"\b(high|medium|low)[\s-]*priority\b", t)
    tasks = task_service.get_tasks(db, status=status, priority=pm.group(1) if pm else None)
    if not tasks:
        return _result("list_tasks", "You have no matching tasks.")
    shown = tasks[:20]
    more = f"\n…and {len(tasks) - 20} more." if len(tasks) > 20 else ""
    return _result("list_tasks", f"You have {len(tasks)} task(s):\n" + "\n".join(_fmt(x) for x in shown) + more)


def _handle_update(db: Session, message: str, today: date, session_id: str = "") -> AgentResult:
    changes: dict = {}
    if (p := parse_priority(message)):
        changes["priority"] = p
    if (d := parse_difficulty(message)):
        changes["difficulty"] = d
    if (mins := parse_minutes(message)) is not None:
        changes["estimated_time_minutes"] = mins
    if (sm := _STATUS_RE.search(message)):
        s = sm.group(1).lower().replace(" ", "_").replace("-", "_")
        changes["status"] = "completed" if s == "done" else s
    if re.search(r"\b(deadline|due|reschedule|postpone|move|push)\b", message.lower()):
        deadline, _ = parse_deadline(message, today)
        if deadline:
            changes["deadline"] = datetime.combine(deadline, time.min)
    if not changes:
        return _result("update_task", "What should I change — priority, deadline, difficulty, estimated time or status?")
    task, ask = _resolve_target(db, message, include_completed=True)
    if ask:
        return _result("update_task", ask)
    try:
        updated = task_service.update_task(db, task.id, TaskUpdate(**changes))
    except ValidationError:
        return _result("update_task", "I couldn't apply that change. Try e.g. 'Change my NLP task priority to high'.")
    summary = ", ".join(f"{k.replace('_', ' ')} → {v}" for k, v in changes.items())
    return _result("update_task", f"Updated #{updated.id} {updated.title}: {summary}.", [])


def _handle_complete(db: Session, message: str, today: date, session_id: str = "") -> AgentResult:
    task, ask = _resolve_target(db, message, include_completed=False)
    if ask:
        return _result("complete_task", ask)
    done = task_service.complete_task(db, task.id)
    return _result("complete_task", f"Marked as completed: #{done.id} {done.title}.")


# ---------------------------------------------------------------- LLM handlers
CHAT_SYSTEM_PROMPT = (
    "You are ATLAS, a friendly academic assistant for students. Explain clearly and concisely. "
    "You cannot see the student's tasks or documents in this reply, so never claim to have saved, "
    "changed or searched anything. If they want to manage tasks, tell them to say e.g. "
    "'Create a high priority DBMS revision task for tomorrow'."
)


def _handle_chat(db: Session, message: str, today: date, session_id: str = "") -> AgentResult:
    history = memory_service.get_recent_messages(db, session_id)
    system = CHAT_SYSTEM_PROMPT
    prefs = memory_service.get_preferences(db, session_id)
    if prefs:  # saved preferences become part of the LLM context
        system += "\nStudent preferences (follow them): " + memory_service.preferences_as_text(prefs)
    reply = llm_service.generate_response(history + [{"role": "user", "content": message}], system)
    return _result("chat", reply)


class StudyPlan(BaseModel):
    summary: str = ""
    tasks: list[TaskCreate] = Field(min_length=1, max_length=10)


def _plan_system_prompt(today: date) -> str:
    return (
        f"You are ATLAS, an academic planner. Today is {today.isoformat()}. Reply with ONLY valid JSON, no markdown:\n"
        '{"summary": "1-2 sentence overview", "tasks": [{"title": "specific study step", "subject": "string or null", '
        '"deadline": "YYYY-MM-DD", "priority": "low|medium|high", "difficulty": "easy|medium|hard", '
        '"estimated_time_minutes": 60}]}\n'
        "Make 3 to 8 small, concrete tasks that finish before the student's exam/deadline. "
        "Do not repeat tasks the student already has."
    )


def _parse_plan(raw: str) -> StudyPlan:
    text = re.sub(r"```(?:json)?", "", raw)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object found")
    return StudyPlan.model_validate(json.loads(text[start:end + 1]))


def _handle_study_plan(db: Session, message: str, today: date, session_id: str = "") -> AgentResult:
    existing = [t for t in task_service.get_tasks(db) if t.status != "completed"][:15]
    context = "\n".join(f"- {t.title} (due {t.deadline or 'n/a'})" for t in existing) or "(none)"
    messages = [{"role": "user", "content": f"{message}\n\nStudent's current open tasks:\n{context}"}]
    system = _plan_system_prompt(today)
    prefs = memory_service.get_preferences(db, session_id)
    if prefs:
        system += "\nStudent preferences (respect them when choosing deadlines/sessions): " + memory_service.preferences_as_text(prefs)

    plan = None
    for attempt in range(2):  # one retry if the model returns bad JSON
        raw = llm_service.generate_response(messages, system)
        try:
            plan = _parse_plan(raw)
            break
        except (ValueError, ValidationError):
            messages = messages + [{"role": "assistant", "content": raw},
                                   {"role": "user", "content": "That was not valid JSON in the required format. Reply with ONLY the JSON object."}]
    if plan is None:
        return _result("study_plan", "I couldn't generate a valid study plan this time, so I didn't create any tasks. Please try again.")

    created = []
    for item in plan.tasks:
        if item.deadline and item.deadline.date() < today:
            item = item.model_copy(update={"deadline": datetime.combine(today, time.min)})
        created.append(task_service.create_task(db, item))
    lines = "\n".join(_fmt(t) for t in created)
    return _result("study_plan", f"{plan.summary or 'Here is your study plan.'}\nI created {len(created)} task(s):\n{lines}", created)


# ---------------------------------------------------------------- documents & memory
DOC_SYSTEM_PROMPT = (
    "Answer the student's question using ONLY the document excerpts provided. If the answer is not in the "
    "excerpts, say you couldn't find it in the document. Never invent citations, quotes or page numbers."
)


def answer_document_question(question: str, document_id: str | None = None) -> tuple[str, list[dict]]:
    """RAG: retrieve excerpts, then ask the LLM to answer from them. May raise RAGUnavailableError / LLMError."""
    data = rag_service.retrieve_context(question, document_id)
    if not data["context"].strip():
        return "I couldn't find anything relevant to that in the document(s).", []
    prompt = f"Document excerpts:\n{data['context']}\n\nQuestion: {question}"
    reply = llm_service.generate_response([{"role": "user", "content": prompt}], DOC_SYSTEM_PROMPT)
    return reply, data["sources"]


def _handle_document_qa(db, message, today, session_id="") -> AgentResult:
    try:
        reply, sources = answer_document_question(message)
    except RAGUnavailableError as e:  # not connected yet -> honest message, no sources
        return _result("document_qa", e.user_message)
    return AgentResult(reply=reply, intent="document_qa", sources=[SourceResponse(**s) for s in sources])


def _handle_remember(db, message, today, session_id="") -> AgentResult:
    pref = memory_service.parse_preference(message)
    if pref is None:
        return _result("remember_preference", "What should I remember? For example: 'Remember that I prefer studying in the evening.'")
    key, value = pref
    memory_service.save_preference(db, session_id, key, value)  # raises if the DB write fails
    return _result("remember_preference", f"Saved: {key.replace('_', ' ')} = {value}.")


def _handle_use_memory(db, message, today, session_id="") -> AgentResult:
    prefs = memory_service.get_preferences(db, session_id)
    if not prefs:
        return _result("use_memory", "I don't have any saved preferences for this session yet.")
    return _result("use_memory", "Your saved preferences:\n" + "\n".join(f"- {k.replace('_', ' ')}: {v}" for k, v in prefs.items()))


HANDLERS = {
    "chat": _handle_chat, "create_task": _handle_create, "list_tasks": _handle_list,
    "update_task": _handle_update, "complete_task": _handle_complete, "study_plan": _handle_study_plan,
    "document_qa": _handle_document_qa, "remember_preference": _handle_remember,
    "use_memory": _handle_use_memory,
}


def handle_message(db: Session, message: str, session_id: str = "", today: date | None = None) -> AgentResult:
    today = today or date.today()
    intent = detect_intent(message)
    try:
        return HANDLERS[intent](db, message, today, session_id)
    except LLMError as e:  # missing key, timeout, rate limit... -> controlled reply
        return AgentResult(reply=e.user_message, intent=intent)
