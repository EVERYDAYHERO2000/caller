"""Calls and SMS endpoints."""
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .. import ambience, config, db, history_chat, summary, transcribe, waveform
from ..calls import AgentNotReady, LineBusy, calls
from ..modem.manager import modem

router = APIRouter()

CALL_SELECT = """
SELECT c.*, a.name AS agent_name, s.name AS script_name,
       cs.text AS ai_summary
FROM calls c
LEFT JOIN call_summaries cs ON cs.call_id = c.id
LEFT JOIN agents a ON a.id = c.agent_id
LEFT JOIN scripts s ON s.id = c.script_id
"""


# ---------------------------------------------------------------- calls

class DialIn(BaseModel):
    number: str = Field(..., description="Номер телефона, например +79161234567")
    agent_id: int | None = Field(None, description="Агент; по умолчанию агент сценария или первый")
    no_agent: bool = Field(False, description="Позвонить без голосового агента (только набор номера)")
    browser: bool = Field(False, description="Говорить через браузер (WS /api/calls/audio)")
    script_id: int | None = None
    variables: dict[str, Any] = Field(default_factory=dict, description="Значения {{переменных}} сценария")
    queue: bool = Field(False, description="Поставить в очередь, если линия занята")
    scheduled_at: str | None = Field(None, description="ISO-время отложенного звонка (ставится в очередь)")
    history: bool | None = Field(None, description="Агент знает про предыдущие звонки и SMS с этим номером "
                                                   "(не задано — как в сценарии)")
    prompt: str = Field("", description="Особое задание агенту на этот звонок (дополняет сценарий): "
                                        "«узнай, когда он свободен на этой неделе»")


class AnswerIn(BaseModel):
    agent_id: int | None = None
    script_id: int | None = None
    browser: bool = Field(False, description="Ответить самому через браузер")


class DtmfIn(BaseModel):
    digits: str


def _normalize_time(value: str | None) -> str | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        raise HTTPException(422, "scheduled_at must be ISO 8601")
    return dt.astimezone().isoformat(timespec="seconds")


@router.get("/calls", tags=["calls"])
def list_calls(direction: str | None = Query(None, pattern="^(in|out)$"),
               status: str | None = None, number: str | None = None,
               thread: str | None = Query(None, description="Звонки одного абонента: его номер или hidden (скрытый)"),
               limit: int = Query(50, le=500), offset: int = 0):
    where, params = [], []
    if thread == "hidden":
        where.append("c.number=''")
    elif thread:
        tail = db.normalize_phone(thread)[-10:] or thread
        where.append("c.number LIKE ?")
        params.append(f"%{tail}")
    if direction:
        where.append("c.direction=?")
        params.append(direction)
    if status:
        where.append("c.status=?")
        params.append(status)
    if number:
        where.append("c.number LIKE ?")
        params.append(f"%{number}%")
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    total = db.scalar(f"SELECT COUNT(*) FROM calls c{clause}", params)
    items = db.fetch_all("calls", f"{CALL_SELECT}{clause} ORDER BY c.id DESC LIMIT ? OFFSET ?",
                         (*params, limit, offset))
    return {"items": db.attach_contacts(items), "total": total}


@router.get("/calls/threads", tags=["calls"])
def call_threads():
    """Calls grouped by the other person's number (newest first): the last call, how many, the contact."""
    threads: dict[str, dict] = {}
    spam = db.spam_keys()
    for r in db.fetch_all("calls", "SELECT c.id, c.direction, c.number, c.status, c.started_at, c.created_at, "
                                   "c.ended_at, c.duration, c.seen, c.summary, cs.text AS ai_summary FROM calls c "
                                   "LEFT JOIN call_summaries cs ON cs.call_id=c.id ORDER BY c.id DESC"):
        key = db.normalize_phone(r["number"])[-10:] if r["number"] else ""
        if key not in threads:
            threads[key] = {"number": r["number"] or "", "thread": r["number"] or "hidden", "last": r, "count": 0,
                            "unseen": 0, "spam": bool(key) and key in spam}
        threads[key]["count"] += 1
        threads[key]["unseen"] += int(not r["seen"] and bool(r["ended_at"]))
    return db.attach_contacts(list(threads.values()))


@router.get("/calls/active", tags=["calls"])
def active_call():
    return {"active": calls.active()}


@router.post("/calls", tags=["calls"], status_code=201)
async def make_call(body: DialIn):
    """Start an outbound call handled by a voice agent (or queue it)."""
    try:
        return await calls.dial(body.number, body.agent_id, body.script_id, body.variables,
                                queue=body.queue, scheduled_at=_normalize_time(body.scheduled_at),
                                no_agent=body.no_agent, browser=body.browser, history=body.history,
                                prompt=body.prompt)
    except LineBusy as e:
        raise HTTPException(409, str(e))
    except AgentNotReady as e:
        raise HTTPException(503, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))


@router.post("/calls/active/answer", tags=["calls"])
async def answer_call(body: AnswerIn):
    try:
        await calls.answer(body.agent_id, body.script_id, browser=body.browser)
    except ValueError as e:
        raise HTTPException(409, str(e))
    return {"ok": True}


@router.post("/calls/active/hangup", tags=["calls"])
async def hangup_call():
    if not calls.current:
        raise HTTPException(409, "нет активного звонка")
    await calls.hangup("api")
    return {"ok": True}


@router.post("/calls/active/dtmf", tags=["calls"])
async def send_dtmf(body: DtmfIn):
    if not calls.current:
        raise HTTPException(409, "нет активного звонка")
    await calls.send_dtmf(body.digits)
    return {"ok": True}


@router.get("/calls/{call_id}", tags=["calls"])
def get_call(call_id: int):
    row = db.fetch_one("calls", f"{CALL_SELECT} WHERE c.id=?", (call_id,))
    if not row:
        raise HTTPException(404, "not found")
    db.attach_contacts([row])
    row["messages"] = db.fetch_all("call_messages", "SELECT * FROM call_messages WHERE call_id=? ORDER BY id",
                                   (call_id,))
    row["summary_record"] = summary.get(call_id)
    row["can_summarize"] = row["summary_record"] is None and summary.can_summarize(call_id)
    row["can_transcribe"] = row["status"] in ("completed",) and transcribe.can_transcribe(row)
    return row


@router.post("/calls/{call_id}/transcribe", tags=["calls"])
async def transcribe_call(call_id: int):
    """Recognize the call's recording with SpeechKit (calls without an agent), then summarize it."""
    if not db.get("calls", call_id):
        raise HTTPException(404, "not found")
    try:
        n = await transcribe.transcribe(call_id)
    except transcribe.TranscribeError as e:
        raise HTTPException(422, str(e))
    try:
        await summary.create(call_id)
    except summary.SummaryError:
        pass
    return {"phrases": n}


@router.get("/calls/{call_id}/summary", tags=["calls"])
def get_call_summary(call_id: int):
    """The post-call summary (read-only)."""
    row = summary.get(call_id)
    if not row:
        raise HTTPException(404, "суммаризации нет")
    return row


@router.post("/calls/{call_id}/summary", tags=["calls"], status_code=201)
async def create_call_summary(call_id: int):
    """Generate the summary if the call doesn't have one yet (e.g. automatic run failed).
    An existing summary is never regenerated or changed."""
    if not db.get("calls", call_id):
        raise HTTPException(404, "not found")
    if summary.get(call_id):
        raise HTTPException(409, "суммаризация уже есть и не может быть изменена")
    if calls.current and calls.current.id == call_id:
        raise HTTPException(409, "звонок ещё идёт")
    try:
        return await summary.create(call_id)
    except summary.SummaryError as e:
        raise HTTPException(422 if "расшифровки" in str(e) else 502, str(e))


@router.get("/calls/{call_id}/waveform", tags=["calls"])
def get_waveform(call_id: int, n: int = Query(waveform.BUCKETS, description="Сколько столбиков")):
    """Peaks of the recording for the player (channels: [left = собеседник, right = агент / вы])."""
    row = db.get("calls", call_id) or {}
    path = config.RECORDINGS_DIR / row["recording"] if row.get("recording") else None
    if not path or not path.exists():
        raise HTTPException(404, "no recording")
    return waveform.peaks(path, n)


@router.get("/ambience/{sound_id}/waveform", tags=["calls"])
def get_ambience_waveform(sound_id: str, n: int = Query(waveform.BUCKETS)):
    path = ambience.path(sound_id)
    if not path:
        raise HTTPException(404, "нет такого звука")
    return waveform.peaks(path, n)


@router.get("/ambience", tags=["calls"])
def list_ambience():
    """Background sounds for agent calls (the `ambience` of a script)."""
    return {"items": ambience.sounds(), "volume": db.setting("ambience.volume", 0.3)}


@router.get("/ambience/{sound_id}.wav", tags=["calls"])
def get_ambience(sound_id: str):
    path = ambience.path(sound_id)
    if not path:
        raise HTTPException(404, "нет такого звука")
    return FileResponse(path, media_type="audio/wav")


@router.get("/calls/{call_id}/recording", tags=["calls"])
def get_recording(call_id: int):
    row = db.get("calls", call_id)
    if not row or not row.get("recording"):
        raise HTTPException(404, "no recording")
    path = config.RECORDINGS_DIR / row["recording"]
    if not path.exists():
        raise HTTPException(404, "file missing")
    return FileResponse(path, media_type="audio/wav")  # no attachment name: the UI names the download


@router.delete("/calls/{call_id}", tags=["calls"])
def delete_call(call_id: int):
    """Cancel a queued call or delete a finished call record."""
    row = db.get("calls", call_id)
    if not row:
        raise HTTPException(404, "not found")
    if calls.current and calls.current.id == call_id:
        raise HTTPException(409, "звонок активен — сначала завершите его")
    return {"deleted": _delete_call(row)}


def _delete_call(row: dict) -> bool:
    """The call with its recording, transcript and summary («Дела» from it stay, without the link)."""
    call_id = row["id"]
    if row.get("recording"):
        (config.RECORDINGS_DIR / row["recording"]).unlink(missing_ok=True)
    db.execute("DELETE FROM call_messages WHERE call_id=?", (call_id,))
    db.execute("UPDATE tasks SET call_id=NULL WHERE call_id=?", (call_id,))
    deleted = db.delete("calls", call_id)
    # the summary is protected while its call exists, so it is removed after the call
    db.execute("DELETE FROM call_summaries WHERE call_id=?", (call_id,))
    return deleted


class NumberIn(BaseModel):
    number: str = Field(..., description="Номер абонента (любая запись)")


def _person(number: str) -> tuple[str, dict | None]:
    key = db.normalize_phone(number)[-10:]
    if not key:
        raise HTTPException(422, "нужен номер")
    return number, db.find_contact(number)


@router.post("/history/forget", tags=["calls"])
def forget_history(body: NumberIn):
    """«Очистить историю агента» абонента: агенты забывают все его звонки и SMS (они остаются в журнале),
    чат ИИ-ассистента контакта стирается. Новые звонки и SMS агент снова будет знать. Необратимо."""
    number, contact = _person(body.number)
    return history_chat.forget(number, contact["id"] if contact else None)


@router.delete("/history/calls", tags=["calls"])
def delete_person_calls(number: str = Query(..., description="Номер абонента")):
    """«Удалить все звонки» абонента: звонки с записями, расшифровками и резюме, и чат ИИ-ассистента контакта.
    SMS остаются. Активный звонок и звонки в очереди не трогаются. Необратимо."""
    number, contact = _person(number)
    rows = [c for c in history_chat._calls({"phone": number}) if c["status"] != "queued"
            and not (calls.current and calls.current.id == c["id"])]
    n = sum(1 for c in rows if _delete_call(c))
    chat_n = db.execute("DELETE FROM contact_chat WHERE contact_id=?", (contact["id"],)).rowcount if contact else 0
    return {"calls": n, "chat": chat_n}


class ForgetIn(BaseModel):
    forgotten: bool = Field(True, description="true — агенты не знают этот звонок; false — снова знают")


@router.put("/calls/{call_id}/forgotten", tags=["calls"])
def forget_call(call_id: int, body: ForgetIn):
    """Убрать звонок из истории агента (он остаётся в журнале) или вернуть его туда."""
    if not db.get("calls", call_id):
        raise HTTPException(404, "not found")
    return db.update("calls", call_id, {"forgotten": int(body.forgotten)})


def _calls_new(user: dict | None = None) -> int:
    """Finished calls the user hasn't opened yet (the menu badge); spam doesn't count."""
    spam = db.spam_keys()
    return sum(1 for (n,) in db.rows("SELECT number FROM calls WHERE seen=0 AND ended_at IS NOT NULL")
               if not (n and db.normalize_phone(n)[-10:] in spam))


class SpamIn(BaseModel):
    number: str


@router.post("/spam", tags=["calls"])
def mark_spam(body: SpamIn):
    """Mark a number as spam: its calls go to the «Спам» folder only."""
    key = db.normalize_phone(body.number)[-10:]
    if not key:
        raise HTTPException(422, "нужен номер")
    db.execute("INSERT OR REPLACE INTO spam_numbers(key, number, created_at) VALUES(?,?,?)",
               (key, db.normalize_phone(body.number) or body.number, db.now()))
    return {"spam": True}


@router.delete("/spam", tags=["calls"])
def unmark_spam(number: str):
    db.execute("DELETE FROM spam_numbers WHERE key=?", (db.normalize_phone(number)[-10:],))
    return {"spam": False}


@router.post("/calls/seen", tags=["calls"])
def calls_seen(thread: str | None = Query(None, description="Только звонки этого абонента: номер или hidden")):
    """The user has seen the calls (of one person, or all): their «new» badges go away."""
    if thread == "hidden":
        db.execute("UPDATE calls SET seen=1 WHERE seen=0 AND ended_at IS NOT NULL AND number=''")
    elif thread:
        tail = db.normalize_phone(thread)[-10:] or thread
        db.execute("UPDATE calls SET seen=1 WHERE seen=0 AND ended_at IS NOT NULL AND number LIKE ?", (f"%{tail}",))
    else:
        db.execute("UPDATE calls SET seen=1 WHERE seen=0 AND ended_at IS NOT NULL")
    return {"calls_new": _calls_new()}


@router.get("/stats", tags=["calls"])
def stats(request: Request):
    today = datetime.now().astimezone().date().isoformat()
    return {
        "calls_new": _calls_new(),
        "calls_total": db.scalar("SELECT COUNT(*) FROM calls"),
        "calls_today": db.scalar("SELECT COUNT(*) FROM calls WHERE substr(created_at,1,10)=?", (today,)),
        "calls_completed": db.scalar("SELECT COUNT(*) FROM calls WHERE status='completed'"),
        "calls_missed": db.scalar("SELECT COUNT(*) FROM calls WHERE status='missed'"),
        "calls_queued": db.scalar("SELECT COUNT(*) FROM calls WHERE status='queued'"),
        "talk_seconds": db.scalar("SELECT COALESCE(SUM(duration),0) FROM calls"),
        "sms_total": db.scalar("SELECT COUNT(*) FROM sms"),
        "sms_unread": db.scalar("SELECT COUNT(*) FROM sms WHERE is_read=0"),
        "contacts": db.scalar("SELECT COUNT(*) FROM contacts"),
        "agents": db.scalar("SELECT COUNT(*) FROM agents"),
        "scripts": db.scalar("SELECT COUNT(*) FROM scripts"),
    }


# ---------------------------------------------------------------- sms

class SmsIn(BaseModel):
    number: str
    text: str = Field(..., min_length=1, max_length=1600)


@router.get("/sms", tags=["sms"])
def list_sms(number: str | None = None, limit: int = Query(200, le=1000), offset: int = 0):
    if number:
        return db.fetch_all("sms", "SELECT * FROM sms WHERE number=? ORDER BY id DESC LIMIT ? OFFSET ?",
                            (db.normalize_phone(number) or number, limit, offset))
    return db.fetch_all("sms", "SELECT * FROM sms ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset))


@router.get("/sms/threads", tags=["sms"])
def sms_threads():
    rows = db.fetch_all("sms", """
        SELECT s.number, s.text, s.ts, s.direction, s.status,
               (SELECT COUNT(*) FROM sms u WHERE u.number=s.number AND u.is_read=0) AS unread
        FROM sms s
        WHERE s.id IN (SELECT MAX(id) FROM sms GROUP BY number)
        ORDER BY s.id DESC""")
    spam = db.spam_keys()
    for r in rows:
        r["spam"] = db.normalize_phone(r["number"])[-10:] in spam
    return db.attach_contacts(rows)


@router.post("/sms", tags=["sms"], status_code=201)
async def send_sms(body: SmsIn):
    if not modem.connected:
        raise HTTPException(503, "модем не подключён")
    return await modem.send_sms(body.number, body.text)


@router.post("/sms/read", tags=["sms"])
def mark_read(number: str = Query(...)):
    db.execute("UPDATE sms SET is_read=1 WHERE number=?", (db.normalize_phone(number) or number,))
    return {"ok": True}


@router.delete("/sms/{sms_id}", tags=["sms"])
def delete_sms(sms_id: int):
    return {"deleted": db.delete("sms", sms_id)}


@router.delete("/sms", tags=["sms"])
def delete_thread(number: str = Query(...)):
    n = db.execute("DELETE FROM sms WHERE number=?", (db.normalize_phone(number) or number,)).rowcount
    return {"deleted": n}

