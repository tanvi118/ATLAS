"""Task CRUD logic. Independent of the LLM."""
import re
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Task, utcnow
from app.schemas import TaskCreate, TaskUpdate

DUPLICATE_WINDOW_SECONDS = 10


class TaskNotFoundError(Exception):
    def __init__(self, task_id: int):
        super().__init__(f"Task {task_id} not found")
        self.task_id = task_id


def _eq(column, value):
    return column.is_(None) if value is None else column == value


def _find_recent_duplicate(db: Session, data: TaskCreate) -> Task | None:
    """Same task submitted again within a few seconds = accidental repeat."""
    cutoff = utcnow() - timedelta(seconds=DUPLICATE_WINDOW_SECONDS)
    stmt = select(Task).where(
        func.lower(Task.title) == data.title.lower(),
        _eq(Task.subject, data.subject),
        _eq(Task.deadline, data.deadline),
        Task.priority == data.priority,
        Task.created_at >= cutoff,
    )
    return db.scalars(stmt).first()


def create_task(db: Session, data: TaskCreate) -> Task:
    existing = _find_recent_duplicate(db, data)
    if existing:
        return existing
    task = Task(**data.model_dump())
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def get_tasks(db: Session, status: str | None = None, priority: str | None = None,
              search: str | None = None) -> list[Task]:
    stmt = select(Task)
    if status:
        stmt = stmt.where(Task.status == status)
    if priority:
        stmt = stmt.where(Task.priority == priority)
    if search:
        like = f"%{search.strip().lower()}%"
        stmt = stmt.where(func.lower(Task.title).like(like) | func.lower(func.coalesce(Task.subject, "")).like(like))
    # soonest deadline first, tasks without a deadline last
    stmt = stmt.order_by(Task.deadline.is_(None), Task.deadline, Task.id)
    return list(db.scalars(stmt))


def get_task(db: Session, task_id: int) -> Task:
    task = db.get(Task, task_id)
    if task is None:
        raise TaskNotFoundError(task_id)
    return task


def update_task(db: Session, task_id: int, data: TaskUpdate) -> Task:
    task = get_task(db, task_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(task, field, value)
    db.commit()
    db.refresh(task)
    return task


def complete_task(db: Session, task_id: int) -> Task:
    return update_task(db, task_id, TaskUpdate(status="completed"))


def delete_task(db: Session, task_id: int) -> None:
    task = get_task(db, task_id)
    db.delete(task)
    db.commit()


def _stem(word: str) -> str:
    return word[:5]


def search_tasks(db: Session, keywords: list[str], include_completed: bool = True) -> list[tuple[int, Task]]:
    """Rank tasks by how many keywords appear in title/subject (best first)."""
    wanted = {_stem(k) for k in keywords}
    ranked = []
    for task in get_tasks(db):
        if not include_completed and task.status == "completed":
            continue
        words = {_stem(w) for w in re.findall(r"[a-z0-9]+", f"{task.title} {task.subject or ''}".lower())}
        score = len(wanted & words)
        if score:
            ranked.append((score, task))
    ranked.sort(key=lambda pair: (-pair[0], pair[1].id))
    return ranked
