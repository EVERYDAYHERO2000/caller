"""«История» of a contact: a feed of calls, their summaries and SMS, and an AI chat about it.

The user asks a question («когда мы договорились встретиться?»); the model (YandexGPT via the AI Studio
Responses API, as for summaries) gets the whole history of dealings with the contact — every call with its date,
transcript, summary and saved result, every SMS — plus today's date and the earlier questions of this chat, and
answers only from it. Long histories: the latest calls go with full transcripts, older ones with summaries only.
"""
import json
import logging
from datetime import datetime

import aiohttp

from . import db
from .summary import RESPONSES_URL, _output_text

log = logging.getLogger("history_chat")

MAX_CHARS = 60000          # ~20–30k tokens of history in one request
FULL_TRANSCRIPTS = 12      # the latest calls go in full, older ones by their summary (if the history is long)
CHAT_TURNS = 10            # earlier questions / answers of this chat, for follow-ups

WEEKDAYS = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]

INSTRUCTIONS = """Ты помощник пользователя. Он спрашивает про один свой контакт и историю общения с ним.
Ниже — карточка контакта из телефонной книги (все её поля) и вся история общения: телефонные звонки
(с датой, расшифровкой, резюме и итогом) и SMS, по времени.
Отвечай только по карточке и истории. Ничего не придумывай. Если ответа там нет — так и скажи.
Если нужное есть в карточке (почта, компания, теги, комментарий), отвечай по ней и говори, что это из карточки.
Указывай, откуда ответ: например «в звонке 28.09 в 12:44» или «в SMS от 27.09».
Относительные даты («завтра», «через неделю», «в понедельник») всегда пересчитывай в конкретную дату от даты
того звонка или SMS, где о них договорились, и называй её с днём недели. Например: договорились 28.09.2026
(понедельник) «через неделю» — значит 05.10.2026, понедельник.
«Агент» в расшифровках — голосовой ИИ-агент, который говорил от имени пользователя; «Пользователь» — сам пользователь
(звонил через браузер); «Собеседник» — контакт.
Отвечай по-русски, коротко и по делу, без разметки."""


class HistoryError(Exception):
    pass


def _key(number: str) -> str:
    return db.normalize_phone(number or "")[-10:]


def _when(ts: str | None) -> str:
    if not ts:
        return "дата неизвестна"
    d = datetime.fromisoformat(ts)
    return f"{d:%d.%m.%Y} ({WEEKDAYS[d.weekday()]}) {d:%H:%M}"


def _calls(contact: dict) -> list[dict]:
    key = _key(contact["phone"])
    if not key:
        return []
    rows = db.fetch_all("calls", """
        SELECT c.*, a.name AS agent_name, s.name AS script_name, cs.text AS ai_summary FROM calls c
        LEFT JOIN agents a ON a.id=c.agent_id LEFT JOIN scripts s ON s.id=c.script_id
        LEFT JOIN call_summaries cs ON cs.call_id=c.id
        WHERE c.number LIKE ? AND c.status NOT IN ('queued') ORDER BY c.id""", (f"%{key}",))
    return [r for r in rows if _key(r["number"]) == key]


def _sms(contact: dict) -> list[dict]:
    key = _key(contact["phone"])
    if not key:
        return []
    rows = db.fetch_all("sms", "SELECT * FROM sms WHERE number LIKE ? ORDER BY id", (f"%{key}",))
    return [r for r in rows if _key(r["number"]) == key]


def chat(contact_id: int) -> list[dict]:
    return db.fetch_all("contact_chat", "SELECT * FROM contact_chat WHERE contact_id=? ORDER BY id", (contact_id,))


def timeline(contact: dict) -> list[dict]:
    """The feed: calls, SMS and the chat, oldest first."""
    items = []
    for c in _calls(contact):
        c = {k: v for k, v in c.items() if k not in ("variables",)}
        items.append({"kind": "call", "ts": c.get("started_at") or c.get("created_at"), "call": c})
    for m in _sms(contact):
        items.append({"kind": "sms", "ts": m.get("ts"), "sms": m})
    for m in chat(contact["id"]):
        items.append({"kind": "chat", "ts": m.get("created_at"), "chat": m})
    return sorted(items, key=lambda x: x["ts"] or "")


def _transcript(call_id: int) -> str:
    rows = db.rows("SELECT role, text FROM call_messages WHERE call_id=? AND role IN ('user','assistant','operator') "
                   "ORDER BY id", (call_id,))
    who = {"user": "Собеседник", "assistant": "Агент", "operator": "Пользователь"}
    return "\n".join(f"{who[r]}: {t}" for r, t in rows)


# the phone book card as the model reads it: every field that has a value
CARD_FIELDS = [("name", "Имя"), ("last_name", "Фамилия"), ("relation", "Кем приходится владельцу системы"),
               ("phone", "Телефон"), ("address", "Адрес"), ("company", "Компания"),
               ("email", "E-mail"), ("tags", "Теги"), ("notes", "Комментарий"),
               ("created_at", "Добавлен в контакты"), ("updated_at", "Карточка изменена")]


def card_text(contact: dict) -> str:
    lines = []
    for key, label in CARD_FIELDS:
        v = contact.get(key)
        if v in (None, ""):
            continue
        if key in ("created_at", "updated_at"):
            v = _when(v)
        lines.append(f"{label}: {v}")
    lines += [f"{k}: {v}" for k, v in db.contact_fields(contact)]  # the contact's own fields
    known = {k for k, _ in CARD_FIELDS} | {"id", "fields"}
    for key, v in contact.items():  # fields added to the card later reach the model too
        if key not in known and v not in (None, ""):
            lines.append(f"{key}: {v}")
    return "\n".join(lines)


def history_text(contact: dict) -> str:
    """The history of dealings as the model reads it."""
    events = []
    calls = _calls(contact)
    full_from = max(0, len(calls) - FULL_TRANSCRIPTS)
    for i, c in enumerate(calls):
        head = [f"ЗВОНОК {_when(c.get('started_at') or c.get('created_at'))}",
                f"{'входящий' if c['direction'] == 'in' else 'исходящий'}, статус: {c['status']}"
                + (f", длительность {c['duration']} с" if c.get("duration") else "")]
        if c.get("agent_name") or c.get("script_name"):
            head.append("агент: " + " · ".join(x for x in (c.get("agent_name"), c.get("script_name")) if x))
        body = []
        if c.get("ai_summary"):
            body.append("Резюме:\n" + c["ai_summary"])
        if c.get("summary"):  # the agent's save_result: summary text and the structured result
            body.append("Итог, сохранённый агентом: " + c["summary"])
        if c.get("result"):
            body.append("Данные итога: " + json.dumps(c["result"], ensure_ascii=False))
        t = _transcript(c["id"])
        if t:
            body.append(("Расшифровка:\n" + t) if i >= full_from or not c.get("ai_summary")
                        else "(расшифровка опущена — старый звонок, см. резюме)")
        events.append((c.get("started_at") or c.get("created_at") or "", "\n".join(head + body)))
    for m in _sms(contact):
        who = "контакт → пользователю" if m["direction"] == "in" else "пользователь → контакту"
        events.append((m.get("ts") or "", f"SMS {_when(m.get('ts'))}, {who}:\n{m['text']}"))
    events.sort(key=lambda e: e[0])
    text = "\n\n".join(e[1] for e in events) or "(общения с этим контактом пока не было)"
    if len(text) > MAX_CHARS:  # the newest part matters most
        text = "(начало истории не поместилось)\n…" + text[-MAX_CHARS:]
    return text


async def ask(contact_id: int, question: str) -> dict:
    question = (question or "").strip()
    if not question:
        raise HistoryError("пустой вопрос")
    contact = db.get("contacts", contact_id)
    if not contact:
        raise HistoryError("контакт не найден")
    s = db.get_settings()
    if not s.get("yandex.api_key") or not s.get("yandex.folder_id"):
        raise HistoryError("не заданы API-ключ и ID каталога Yandex AI Studio (Настройки → Yandex AI Studio)")
    earlier = chat(contact_id)[-CHAT_TURNS * 2:]
    db.insert("contact_chat", {"contact_id": contact_id, "role": "user", "text": question, "created_at": db.now()})

    now = datetime.now().astimezone()
    context = (f"Сегодня: {_when(now.isoformat())}\n\nКАРТОЧКА КОНТАКТА:\n{card_text(contact)}"
               f"\n\nИСТОРИЯ ОБЩЕНИЯ:\n\n{history_text(contact)}")
    messages = [{"role": "user", "content": context},
                {"role": "assistant", "content": "Понял, история загружена. Задавайте вопрос."}]
    for m in earlier:
        if not m.get("error"):
            messages.append({"role": m["role"], "content": m["text"]})
    messages.append({"role": "user", "content": question})

    model = s.get("history_chat.model") or "yandexgpt/latest"
    uri = model if model.startswith("gpt://") else f"gpt://{s['yandex.folder_id']}/{model}"
    key = s["yandex.api_key"]
    auth = f"Bearer {key}" if key.startswith("t1.") else f"Api-Key {key}"
    payload = {"model": uri, "instructions": INSTRUCTIONS, "input": messages, "temperature": 0.2,
               "max_output_tokens": 800}
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=90)) as http:
            async with http.post(RESPONSES_URL, json=payload, headers={"Authorization": auth}) as r:
                body = await r.text()
                if r.status != 200:
                    raise HistoryError(f"модель ответила {r.status}: {body[:300]}")
                resp = json.loads(body)
        text = _output_text(resp).strip()
        if not text:
            raise HistoryError("модель вернула пустой ответ")
    except (aiohttp.ClientError, TimeoutError, HistoryError) as e:
        err = str(e) if isinstance(e, HistoryError) else f"нет связи с Yandex AI Studio: {e}"
        row = db.insert("contact_chat", {"contact_id": contact_id, "role": "assistant", "text": f"Не удалось ответить: {err}",
                                         "model": model, "error": err, "created_at": db.now()})
        log.warning("history chat for contact %s failed: %s", contact_id, err)
        return row
    u = resp.get("usage") or {}
    row = db.insert("contact_chat", {"contact_id": contact_id, "role": "assistant", "text": text, "model": model,
                                     "tokens_in": u.get("input_tokens") or 0, "tokens_out": u.get("output_tokens") or 0,
                                     "created_at": db.now()})
    db.log_usage("yandex", "history_chat", tokens_in=u.get("input_tokens") or 0, tokens_out=u.get("output_tokens") or 0)
    log.info("history chat for contact %s: %s tokens", contact_id, u.get("total_tokens"))
    return row


# ---------------------------------------------------------------- for the voice agent in a call

def _gist(c: dict) -> tuple[str, str]:
    """(суть, договорённости) of a call — from the AI summary, or what the agent saved."""
    fields = {}
    for line in (c.get("ai_summary") or "").splitlines():
        k, sep, v = line.partition(":")
        if sep and k.strip():
            fields[k.strip().lower()] = v.strip()
    gist = fields.get("суть") or ("" if fields else (c.get("ai_summary") or "").strip()) or (c.get("summary") or "")
    agreed = fields.get("договорённости") or fields.get("договоренности") or ""
    if agreed.lower().rstrip(".") in ("нет", "—", "-", ""):
        agreed = ""
    return gist.strip(), agreed.strip()


def past_calls_brief(number: str, exclude_call_id: int | None = None, calls_limit: int = 8, sms_limit: int = 5) -> str:
    """What the voice agent should remember about this number: the latest calls (date, gist, agreements) and SMS.
    Summaries only, not transcripts — the Realtime model re-reads its instructions with every reply."""
    key = _key(number)
    if not key:
        return ""
    contact = {"phone": number}
    events = []
    for c in _calls(contact):
        if c["id"] == exclude_call_id or c["status"] in ("dialing", "ringing", "answering", "active"):
            continue
        gist, agreed = _gist(c)
        when = _when(c.get("started_at") or c.get("created_at"))
        kind = "входящий" if c["direction"] == "in" else "исходящий"
        if not gist and not agreed:
            if c["status"] in ("missed", "no_answer", "busy", "rejected", "cancelled"):
                gist = "не дозвонились" if c["direction"] == "out" else "пропущенный звонок"
            else:
                continue
        line = f"- {when}, {kind} звонок: {gist}" + (f" Договорились: {agreed}" if agreed else "")
        events.append((c.get("started_at") or c.get("created_at") or "", line))
    events = events[-calls_limit:]
    sms = _sms(contact)[-sms_limit:]
    for m in sms:
        who = "от него" if m["direction"] == "in" else "ему"
        events.append((m.get("ts") or "", f"- {_when(m.get('ts'))}, SMS {who}: {m['text'][:300]}"))
    events.sort(key=lambda e: e[0])
    return "\n".join(e[1] for e in events)
