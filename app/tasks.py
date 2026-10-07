"""«Дела»: agreements made in phone calls.

After a call the AI (YandexGPT via the Responses API) reads the transcript and lists what was agreed: who does
what, when and where. Each agreement becomes a row in «Дела». Relative times («в пятницу вечером», «через
неделю») are resolved against the call's date; the words as said are kept too (due_text), so the user can check.
Calendar events and map points are never created by the AI — the user confirms them in a form (event / geo).
"""
import json
import logging
import re
from datetime import datetime

import aiohttp

from . import db
from .events import hub
from .summary import RESPONSES_URL, ROLE_NAMES, _output_text

log = logging.getLogger("tasks")

WEEKDAYS = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]

INSTRUCTIONS = """Ты читаешь расшифровку телефонного разговора и выписываешь договорённости — дела, которые \
кто-то пообещал или поручил сделать: встречи, визиты, перезвонить, отправить, купить, привезти, оплатить и т.п.
Владелец телефона — тот, от чьего имени говорил агент (или сам пользователь); собеседник — другой человек.

Ответь ТОЛЬКО JSON-массивом без пояснений и разметки. Каждый элемент:
{"title": "коротко, что сделать, 3–8 слов, с глагола: «Встреча с Иваном в кафе»",
 "details": "подробности из разговора одной-двумя фразами или пустая строка",
 "assignee": "кто делает: «я» (владелец), «собеседник», «агент» или «вместе»",
 "due": "когда: YYYY-MM-DDTHH:MM, или YYYY-MM-DD если время не названо, или null если срока нет",
 "due_text": "срок так, как его сказали: «в пятницу вечером», или пустая строка",
 "place": "место или адрес так, как сказали (с городом, если он понятен из разговора), или пустая строка"}

Правила:
- Только то, о чём действительно договорились или что поручили. Не выдумывай, не пиши общие темы разговора.
- Относительные сроки переводи в даты от даты звонка: «завтра», «в пятницу» — ближайшая будущая пятница, \
«через неделю». «Утром» — 09:00, «днём» — 13:00, «вечером» — 19:00, если точное время не названо.
- Одно дело — одна договорённость; повторы одного и того же объединяй.
- Если договорённостей нет (не ответили, автоответчик, просто поговорили) — ответь [].
"""


class TaskError(Exception):
    pass


def _when(iso: str) -> str:
    d = datetime.fromisoformat(iso)
    return f"{d:%d.%m.%Y} ({WEEKDAYS[d.weekday()]}) {d:%H:%M}"


def _input(call: dict, messages: list[dict]) -> str:
    start = call.get("answered_at") or call.get("started_at") or call.get("created_at") or db.now()
    head = [f"Дата и время звонка: {_when(start)}",
            f"Звонок: {'входящий' if call['direction'] == 'in' else 'исходящий'}",
            f"Собеседник: {call.get('contact_name') or call.get('number') or 'номер скрыт'}"]
    if call.get("result"):
        head.append("Итог, сохранённый агентом: " + json.dumps(call["result"], ensure_ascii=False))
    return "\n".join(head) + "\n\nРасшифровка:\n" + "\n".join(f"{ROLE_NAMES[m['role']]}: {m['text']}" for m in messages)


def _parse(text: str) -> list[dict]:
    text = re.sub(r"^```\w*\s*|\s*```$", "", text.strip())
    i, j = text.find("["), text.rfind("]")
    if i < 0 or j < i:
        raise TaskError(f"модель ответила не списком: {text[:200]}")
    try:
        items = json.loads(text[i:j + 1])
    except ValueError as e:
        raise TaskError(f"не разобрать ответ модели: {e}")
    return [x for x in items if isinstance(x, dict) and str(x.get("title") or "").strip()]


def _due(value) -> str:
    """The model's date as YYYY-MM-DD or YYYY-MM-DDTHH:MM; anything else — no date."""
    v = str(value or "").strip()
    for fmt, n in (("%Y-%m-%dT%H:%M", 16), ("%Y-%m-%d %H:%M", 16), ("%Y-%m-%d", 10)):
        try:
            d = datetime.strptime(v[:n], fmt)
            # «завтра» without a time comes as midnight: that's a date, not a meeting at 00:00
            return d.strftime("%Y-%m-%dT%H:%M" if n == 16 and (d.hour, d.minute) != (0, 0) else "%Y-%m-%d")
        except ValueError:
            continue
    return ""


async def extract(call_id: int, replace: bool = False) -> list[dict]:
    """Find the call's agreements and add them to «Дела». replace: drop the AI's tasks of this call the user
    hasn't touched (edited, done, put into the calendar or on the map) and look again."""
    call = db.fetch_one("calls", "SELECT * FROM calls WHERE id=?", (call_id,))
    if not call:
        raise TaskError("звонок не найден")
    db.attach_contacts([call])
    messages = db.fetch_all("call_messages", "SELECT * FROM call_messages WHERE call_id=? AND role IN "
                                             "('user','assistant','operator') ORDER BY id", (call_id,))
    if not messages:
        raise TaskError("нет расшифровки разговора")
    s = db.get_settings()
    if not s.get("yandex.api_key") or not s.get("yandex.folder_id"):
        raise TaskError("не заданы API-ключ и ID каталога Yandex AI Studio")
    model = s.get("tasks.model") or "yandexgpt/latest"
    uri = model if model.startswith("gpt://") else f"gpt://{s['yandex.folder_id']}/{model}"
    key = s["yandex.api_key"]
    auth = f"Bearer {key}" if key.startswith("t1.") else f"Api-Key {key}"
    payload = {"model": uri, "instructions": INSTRUCTIONS, "input": _input(call, messages),
               "temperature": 0.1, "max_output_tokens": 1200}
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=90)) as http:
            async with http.post(RESPONSES_URL, json=payload, headers={"Authorization": auth}) as r:
                body = await r.text()
                if r.status != 200:
                    raise TaskError(f"YandexGPT ответил {r.status}: {body[:300]}")
                resp = json.loads(body)
    except (aiohttp.ClientError, TimeoutError) as e:
        raise TaskError(f"нет связи с YandexGPT: {e}")
    u = resp.get("usage") or {}
    db.log_usage("yandex", "tasks", tokens_in=u.get("input_tokens") or 0, tokens_out=u.get("output_tokens") or 0,
                 call_id=call_id)
    items = _parse(_output_text(resp))
    if replace:
        db.execute("DELETE FROM tasks WHERE call_id=? AND source='call' AND status='open' AND event IS NULL "
                   "AND geo IS NULL AND updated_at=created_at", (call_id,))
    ts = db.now()
    added = []
    for x in items:
        added.append(db.insert("tasks", {
            "call_id": call_id, "number": call.get("number") or "", "source": "call", "status": "open",
            "title": str(x.get("title")).strip()[:200], "details": str(x.get("details") or "").strip()[:1000],
            "assignee": str(x.get("assignee") or "").strip()[:40], "due_at": _due(x.get("due")),
            "due_text": str(x.get("due_text") or "").strip()[:100], "place": str(x.get("place") or "").strip()[:300],
            "created_at": ts, "updated_at": ts}))
    db.update("calls", call_id, {"tasks_done": 1})
    log.info("call %s: %s agreements → «Дела»", call_id, len(added))
    if added or replace:
        hub.publish("tasks.updated", {"call_id": call_id, "added": len(added)})
    return added


async def auto(call_id: int):
    """After a call: once per call, if enabled."""
    call = db.get("calls", call_id)
    if not call or call.get("tasks_done") or not db.setting("tasks.auto", True):
        return
    try:
        await extract(call_id)
    except TaskError as e:
        log.warning("agreements of call %s: %s", call_id, e)


def listing() -> list[dict]:
    rows = db.fetch_all("tasks", "SELECT * FROM tasks ORDER BY id DESC")
    return db.attach_contacts(rows)


def is_overdue(t: dict, now: datetime | None = None) -> bool:
    """An open task whose deadline has passed (a date without a time — once that day is over)."""
    due = t.get("due_at") or ""
    if not due or t.get("status") == "done":
        return False
    now = now or datetime.now()
    return due < now.strftime("%Y-%m-%dT%H:%M") if len(due) > 10 else due < now.strftime("%Y-%m-%d")


def query(status: str = "open", overdue: bool | None = None, number: str = "", contact_id: int | None = None,
          call_id: int | None = None, due_from: str = "", due_to: str = "", q: str = "", tag: str = "",
          limit: int = 0) -> list[dict]:
    """Tasks by the filters of «Дела» (newest first). status: open | done | all; due_from / due_to: YYYY-MM-DD
    (the deadline's day, inclusive); number: any form of the phone; q: words in the title, details, place,
    the time as said or the person's name."""
    items = listing()
    if contact_id:
        c = db.get("contacts", contact_id)
        number = (c or {}).get("phone") or "-"
    key = db.normalize_phone(number)[-10:] if number else ""
    words = [w for w in (q or "").lower().split() if w]
    out = []
    for t in items:
        if status != "all" and (t.get("status") or "open") != status:
            continue
        if overdue is not None and is_overdue(t) != overdue:
            continue
        if key and db.normalize_phone(t.get("number") or "")[-10:] != key:
            continue
        if call_id and t.get("call_id") != call_id:
            continue
        day = (t.get("due_at") or "")[:10]
        if (due_from or due_to) and not day:
            continue
        if (due_from and day < due_from) or (due_to and day > due_to):
            continue
        if tag:
            c = db.find_contact(t.get("number") or "")
            if tag.lower() not in [x.strip().lower() for x in ((c or {}).get("tags") or "").split(",")]:
                continue
        if words:
            hay = " ".join(str(t.get(k) or "") for k in ("title", "details", "place", "due_text", "contact_name",
                                                         "assignee")).lower()
            if not all(w in hay for w in words):
                continue
        out.append(t)
    return out[:limit] if limit else out


def agenda(start: str, end: str) -> list[dict]:
    """What is planned between two days (YYYY-MM-DD, inclusive), by time: the calendar events, and open tasks
    with a deadline in the period that have no event yet (kind = event | deadline)."""
    out = []
    for t in listing():
        ev = t.get("event")
        if ev:
            day = ev["start"][:10]
            if start <= day <= end:
                out.append({"kind": "event", "at": ev["start"], "all_day": ev.get("all_day", False),
                            "end": ev.get("end"), "title": ev["title"], "notes": ev.get("notes") or "",
                            "place": (t.get("geo") or {}).get("address") or t.get("place") or "", "task": t})
        elif t.get("due_at") and t.get("status") != "done" and start <= t["due_at"][:10] <= end:
            out.append({"kind": "deadline", "at": t["due_at"], "all_day": len(t["due_at"]) == 10, "end": None,
                        "title": t["title"], "notes": t.get("details") or "", "place": t.get("place") or "", "task": t})
    return sorted(out, key=lambda x: x["at"])

