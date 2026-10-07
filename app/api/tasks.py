"""«Дела»: agreements from the calls and tasks added by hand; their calendar events and map points."""
import asyncio
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from .. import db, tasks
from ..events import hub

router = APIRouter(tags=["tasks"])
_backfill = asyncio.Lock()


class TaskEvent(BaseModel):
    title: str
    start: str = Field(..., description="YYYY-MM-DDTHH:MM, местное время")
    end: str = Field(..., description="YYYY-MM-DDTHH:MM")
    all_day: bool = False
    notes: str = ""


class TaskGeo(BaseModel):
    address: str = ""
    lat: float
    lon: float


class TaskIn(BaseModel):
    title: str | None = None
    details: str | None = None
    number: str | None = Field(None, description="Номер человека, с которым связано дело")
    assignee: str | None = None
    due_at: str | None = Field(None, description="YYYY-MM-DD или YYYY-MM-DDTHH:MM; пусто — без срока")
    place: str | None = None
    status: Literal["open", "done"] | None = None
    event: TaskEvent | None = Field(None, description="Событие в календаре (подтверждённое пользователем)")
    geo: TaskGeo | None = Field(None, description="Точка на карте (подтверждённая пользователем)")


def _one(task_id: int) -> dict:
    t = db.get("tasks", task_id)
    if not t:
        raise HTTPException(404, "дело не найдено")
    return db.attach_contacts([t])[0]


def _changed(task: dict, action: str = "updated"):
    hub.publish("tasks.updated", {"id": task["id"], "action": action})
    return task


@router.get("/tasks")
def list_tasks(status: Literal["open", "done", "all"] = Query("all", description="open — в работе, done — выполненные"),
               overdue: bool | None = Query(None, description="true — только просроченные (срок прошёл, дело открыто)"),
               number: str = Query("", description="Номер человека в любом виде"),
               contact_id: int | None = Query(None, description="Контакт (дела с его номером)"),
               call_id: int | None = Query(None, description="Дела из этого звонка"),
               due_from: str = Query("", description="Срок не раньше, YYYY-MM-DD"),
               due_to: str = Query("", description="Срок не позже, YYYY-MM-DD (включительно)"),
               tag: str = Query("", description="Тег контакта"),
               q: str = Query("", description="Слова в названии, подробностях, месте, имени")):
    """Дела, новые сверху. Без параметров — все; фильтры совпадают с папками раздела «Дела»."""
    return tasks.query(status, overdue, number, contact_id, call_id, due_from, due_to, q, tag)


@router.get("/tasks/{task_id}")
def get_task(task_id: int):
    """Одно дело: с событием (event), местом (geo) и контактом."""
    return _one(task_id)


@router.get("/events")
def list_events(start: str = Query(..., alias="from", description="Первый день, YYYY-MM-DD"),
                end: str = Query(..., alias="to", description="Последний день, YYYY-MM-DD (включительно)")):
    """Что запланировано на период, по времени: события календаря (kind=event) и сроки открытых дел, для
    которых события ещё нет (kind=deadline). У каждого — дело (task)."""
    return tasks.agenda(start, end)


@router.get("/places")
def list_places(status: Literal["open", "done", "all"] = "open"):
    """Дела с местом на карте (geo: address, lat, lon)."""
    return [t for t in tasks.query(status) if t.get("geo")]


@router.put("/tasks/{task_id}/event")
def set_event(task_id: int, body: TaskEvent):
    """Создать или изменить событие дела в календаре."""
    _one(task_id)
    db.update("tasks", task_id, {"event": body.model_dump(), "updated_at": db.now()})
    return _changed(_one(task_id))


@router.put("/tasks/{task_id}/geo")
def set_geo(task_id: int, body: TaskGeo):
    """Поставить или передвинуть место дела на карте (координаты и адрес)."""
    _one(task_id)
    db.update("tasks", task_id, {"geo": body.model_dump(), "updated_at": db.now()})
    return _changed(_one(task_id))


@router.post("/tasks/{task_id}/done")
def complete_task(task_id: int):
    """Отметить дело выполненным."""
    _one(task_id)
    db.update("tasks", task_id, {"status": "done", "updated_at": db.now()})
    return _changed(_one(task_id))


@router.post("/tasks/{task_id}/reopen")
def reopen_task(task_id: int):
    """Вернуть выполненное дело в работу."""
    _one(task_id)
    db.update("tasks", task_id, {"status": "open", "updated_at": db.now()})
    return _changed(_one(task_id))


@router.post("/tasks", status_code=201)
def create_task(body: TaskIn):
    """Добавить дело вручную."""
    data = body.model_dump(exclude_none=True)
    if not (data.get("title") or "").strip():
        raise HTTPException(422, "укажите, что нужно сделать")
    if data.get("number"):
        data["number"] = db.normalize_phone(data["number"])
    ts = db.now()
    t = db.insert("tasks", {**data, "source": "manual", "created_at": ts, "updated_at": ts})
    return _changed(_one(t["id"]), "created")


@router.put("/tasks/{task_id}")
def update_task(task_id: int, body: TaskIn):
    """Изменить дело: любые поля, в том числе status, event, geo."""
    _one(task_id)
    data = body.model_dump(exclude_unset=True)
    if data.get("number"):
        data["number"] = db.normalize_phone(data["number"])
    db.update("tasks", task_id, {**data, "updated_at": db.now()})
    return _changed(_one(task_id))


@router.delete("/tasks/{task_id}/event")
def delete_event(task_id: int):
    """Удалить событие из календаря (дело остаётся)."""
    _one(task_id)
    db.execute("UPDATE tasks SET event=NULL, updated_at=? WHERE id=?", (db.now(), task_id))
    return _changed(_one(task_id))


@router.delete("/tasks/{task_id}/geo")
def delete_geo(task_id: int):
    """Убрать место с карты (дело остаётся)."""
    _one(task_id)
    db.execute("UPDATE tasks SET geo=NULL, updated_at=? WHERE id=?", (db.now(), task_id))
    return _changed(_one(task_id))


@router.delete("/tasks/{task_id}")
def delete_task(task_id: int):
    """Удалить дело вместе с его событием и местом."""
    deleted = db.delete("tasks", task_id)
    hub.publish("tasks.updated", {"id": task_id, "action": "deleted"})
    return {"deleted": deleted}


@router.post("/calls/{call_id}/tasks")
async def extract_tasks(call_id: int):
    """Look for the call's agreements again (the AI's untouched tasks of this call are replaced)."""
    try:
        added = await tasks.extract(call_id, replace=True)
    except tasks.TaskError as e:
        raise HTTPException(422, str(e))
    return {"added": len(added), "items": db.attach_contacts(added)}


@router.post("/tasks/backfill")
async def backfill():
    """Look for agreements in the past calls the AI hasn't read yet (those with a transcript), oldest first."""
    if _backfill.locked():
        raise HTTPException(409, "прошлые звонки уже разбираются")
    async with _backfill:
        ids = [r["id"] for r in db.fetch_all("calls", "SELECT c.id FROM calls c WHERE COALESCE(c.tasks_done,0)=0 AND "
                                                     "EXISTS(SELECT 1 FROM call_messages m WHERE m.call_id=c.id AND "
                                                     "m.role IN ('user','assistant','operator')) ORDER BY c.id")]
        added = failed = 0
        for call_id in ids:
            try:
                added += len(await tasks.extract(call_id))
            except tasks.TaskError:
                failed += 1
        return {"calls": len(ids), "added": added, "failed": failed}
