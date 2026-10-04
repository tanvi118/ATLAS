from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import schemas
from app.db.database import get_db
from app.services import task_service
from app.services.task_service import TaskNotFoundError

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _not_found(e: TaskNotFoundError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(e))


@router.get("", response_model=schemas.TaskListResponse)
def list_tasks(
    status: schemas.Status | None = Query(default=None),
    priority: schemas.Priority | None = Query(default=None),
    search: str | None = Query(default=None, max_length=100),
    db: Session = Depends(get_db),
):
    return {"tasks": task_service.get_tasks(db, status=status, priority=priority, search=search)}


@router.post("", response_model=schemas.TaskResponse, status_code=201)
def create_task(body: schemas.TaskCreate, db: Session = Depends(get_db)):
    return task_service.create_task(db, body)


@router.get("/{task_id}", response_model=schemas.TaskResponse)
def get_task(task_id: int, db: Session = Depends(get_db)):
    try:
        return task_service.get_task(db, task_id)
    except TaskNotFoundError as e:
        raise _not_found(e)


@router.patch("/{task_id}", response_model=schemas.TaskResponse)
def update_task(task_id: int, body: schemas.TaskUpdate, db: Session = Depends(get_db)):
    try:
        return task_service.update_task(db, task_id, body)
    except TaskNotFoundError as e:
        raise _not_found(e)


@router.delete("/{task_id}", response_model=schemas.TaskDeleteResponse)
def delete_task(task_id: int, db: Session = Depends(get_db)):
    try:
        task_service.delete_task(db, task_id)
    except TaskNotFoundError as e:
        raise _not_found(e)
    return {"id": task_id, "deleted": True}
