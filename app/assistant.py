"""The assistant: a chat with YandexGPT that works with the app's data through functions.

It finds contacts, tells what was asked to be done and what is planned, marks tasks done and prepares calls.
The model calls functions (Responses API function calling); they run here, inside the server. A call is never
dialed by the model: propose_call only shows a card in the chat, and the number is dialed when the user presses
«Позвонить» there (confirm_action). A task the assistant marks done can be undone from its card.

Messages of a chat: user / assistant (text) and action (a card: data = {type, status, …}).
"""
import json
import logging
import re
from datetime import datetime, timedelta

import aiohttp

from . import db, tasks
from .summary import RESPONSES_URL, _output_text

log = logging.getLogger("assistant")

WEEKDAYS = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
MAX_STEPS = 6          # function calls in one answer
HISTORY = 20           # previous messages the model sees

INSTRUCTIONS = """Ты — личный ассистент владельца этого телефона в приложении Caller. Через Caller звонят голосовые \
агенты (и сам владелец), после звонков ИИ выписывает договорённости в «Дела»; у дел бывают события в календаре и места \
на карте. Ты помогаешь владельцу: находишь контакты, рассказываешь, что ему поручили и что запланировано, \
отмечаешь дела выполненными и готовишь звонки.

Правила:
- Сначала действуй, потом спрашивай. На любой вопрос о контактах, делах, планах сразу вызывай функцию с тем, что \
уже известно, — не проси уточнений заранее. Уточняй, только если функция вернула несколько подходящих вариантов или \
ничего не нашла.
- Примеры:
  «что мне просили напомнить?», «что я обещал?», «что надо сделать?» → list_tasks() без параметров;
  «что просрочено?» → list_tasks(overdue=true);
  «что я обещал Илье?» → list_tasks(contact_query="Илья");
  «какие ближайшие встречи?», «что запланировано?» → list_agenda с сегодняшнего дня на 7 дней вперёд;
  «что завтра?» → list_agenda(завтра, завтра);
  «найди маму», «номер Ильи» → find_contacts("мама"), find_contacts("Илья");
  «что я знаю об Илье?», «какой комментарий у Юли?», «когда у мамы день рождения?» → find_contacts, затем get_contact(id);
  «покажи контакт Ильи» → find_contacts("Илья") и show_cards(contact_ids=[id]); ответ — одна строка, карточку \
покажет виджет; дела и звонки не перечисляй, если о них не спросили;
  «покажи все контакты» → find_contacts("");
  «где встреча с Иваном?» → list_tasks(contact_query="Иван"), затем show_place(task_id=…);
  «покажи на карте Тверскую 7», «найди на карте кафе Пушкин» → show_place(query="…");
  «о чём я говорил с Ильёй?», «кто звонил вчера?» → list_calls(contact_query="Илья") / list_calls(date_from=вчера, date_to=вчера);
  «позвони Илье и узнай…» → find_contacts("Илья"), затем propose_call(contact_id, prompt="узнай…");
  «отметь, что я передал сообщение Илье» → list_tasks(contact_query="Илья"), выбери дело по смыслу, complete_task(id).
- Обращайся к владельцу на «вы» и не называй его «владельцем» в ответах.
- В prompt для звонка пиши поручение агенту от третьего лица: вместо «скажи, что я перезвоню» — «Скажи, что \
хозяин телефона перезвонит вечером».
- Отвечай по-русски, коротко и по делу, простым текстом без markdown (без звёздочек, решёток и таблиц); список — \
строками с «—».
- Данные бери только из функций, ничего не выдумывай: ни контакты, ни номера, ни дела, ни id. Карточка контакта — \
все его поля, включая «Комментарий» и свои поля: отвечай по ним.
- Под ответом показываются виджеты объектов, о которых ты говоришь: перед финальным ответом вызови функцию \
show_cards с id контактов, дел и звонков из ответа (только тех, о которых действительно говоришь). Это вызов \
функции, а не текст: никогда не пиши show_cards, JSON, id или картинки в самом ответе. Номера и подробности, \
которые видны в виджете, в тексте не повторяй. Если ответ — это сами объекты, напиши только вводную фразу: \
«Вот ваши дела:», «Вот контакт Ильи:», «Вот звонки с Юлей:» — список покажут виджеты. Перечисляй текстом, только \
если добавляешь то, чего в виджетах нет (например, вывод или совет).
- Карту показывает show_place — не описывай маршрут и не придумывай адрес; скажи, что показал на карте.
- Даты и время считай от текущего момента (он ниже). Называй даты по-человечески: «завтра в 12:00», «в пятницу, 9 октября».
- В списке дел просроченные называй первыми и помечай «просрочено».
- Если под запрос подходят несколько контактов или дел и по смыслу не понять, какой нужен, — перечисли их и спроси.
- Звонок начнётся, только когда владелец нажмёт «Позвонить» в карточке, — не пиши, что звонок идёт или состоялся; \
скажи, что карточка готова. Что агенту узнать или сообщить, передай в prompt как поручение агенту.
"""

TOOLS = [
    {"type": "function", "name": "find_contacts",
     "description": "Найти контакты по имени, фамилии, номеру, компании, связи с владельцем («мама», «директор»), "
                    "тегу или своим полям. Возвращает до 10 контактов со всеми полями карточки.",
     "parameters": {"type": "object", "properties": {
         "query": {"type": "string", "description": "Что искать: «Илья», «мама», «+7916», «Ромашка»; "
                                                    "пусто — все контакты"}}}},
    {"type": "function", "name": "list_tasks",
     "description": "Дела — договорённости из звонков и добавленные вручную. По умолчанию открытые, новые сверху.",
     "parameters": {"type": "object", "properties": {
         "status": {"type": "string", "enum": ["open", "done", "all"], "description": "open — в работе (по умолчанию)"},
         "overdue": {"type": "boolean", "description": "true — только просроченные"},
         "contact_query": {"type": "string", "description": "Только дела с этим человеком: имя или номер"},
         "due_from": {"type": "string", "description": "Срок не раньше, YYYY-MM-DD"},
         "due_to": {"type": "string", "description": "Срок не позже, YYYY-MM-DD"},
         "text": {"type": "string", "description": "Слова из названия или подробностей дела"}}}},
    {"type": "function", "name": "list_agenda",
     "description": "Что запланировано на период: события календаря и сроки открытых дел, по времени. Для вопросов "
                    "о встречах и планах.",
     "parameters": {"type": "object", "properties": {
         "date_from": {"type": "string", "description": "Первый день, YYYY-MM-DD"},
         "date_to": {"type": "string", "description": "Последний день включительно, YYYY-MM-DD"}},
         "required": ["date_from", "date_to"]}},
    {"type": "function", "name": "get_contact",
     "description": "Вся карточка контакта (все поля, комментарий, свои поля), сколько у него открытых дел и что "
                    "было в последних звонках и SMS. Вызывай, когда спрашивают подробности о человеке. Сами дела — "
                    "list_tasks, и только если о них спросили.",
     "parameters": {"type": "object", "properties": {"contact_id": {"type": "integer", "description": "id из find_contacts"}},
                    "required": ["contact_id"]}},
    {"type": "function", "name": "show_place",
     "description": "Показать место на карте в чате: адрес, название места («кафе Пушкин на Тверской») или место "
                    "дела (task_id). Карта сама найдёт адрес.",
     "parameters": {"type": "object", "properties": {
         "query": {"type": "string", "description": "Что искать: адрес или название места с городом, если он известен"},
         "task_id": {"type": "integer", "description": "Показать место этого дела"},
         "title": {"type": "string", "description": "Подпись к карте, например «Встреча с Иваном»"}}}},
    {"type": "function", "name": "list_calls",
     "description": "Звонки, новые сверху: с кем, когда, кто звонил, суть разговора и договорённости.",
     "parameters": {"type": "object", "properties": {
         "contact_query": {"type": "string", "description": "Только звонки с этим человеком: имя или номер"},
         "date_from": {"type": "string", "description": "Не раньше, YYYY-MM-DD"},
         "date_to": {"type": "string", "description": "Не позже, YYYY-MM-DD"},
         "limit": {"type": "integer", "description": "Сколько звонков, по умолчанию 10"}}}},
    {"type": "function", "name": "show_cards",
     "description": "Показать под твоим ответом виджеты объектов, о которых ты говоришь: контактов, дел, звонков. "
                    "Вызывай перед ответом всегда, когда в ответе есть конкретные люди, дела или звонки.",
     "parameters": {"type": "object", "properties": {
         "contact_ids": {"type": "array", "items": {"type": "integer"}},
         "task_ids": {"type": "array", "items": {"type": "integer"}},
         "call_ids": {"type": "array", "items": {"type": "integer"}}}}},
    {"type": "function", "name": "complete_task",
     "description": "Отметить дело выполненным. Владелец увидит карточку и сможет отменить.",
     "parameters": {"type": "object", "properties": {"task_id": {"type": "integer"}}, "required": ["task_id"]}},
    {"type": "function", "name": "propose_call",
     "description": "Подготовить звонок контакту: в чате появится карточка с кнопкой «Позвонить». Сам звонок "
                    "начнётся только после подтверждения владельцем.",
     "parameters": {"type": "object", "properties": {
         "contact_id": {"type": "integer", "description": "id из find_contacts"},
         "number": {"type": "string", "description": "Номер, если контакта нет в книге"},
         "prompt": {"type": "string", "description": "Поручение голосовому агенту на этот звонок: что узнать или "
                                                     "сообщить. Пусто — обычный сценарий."},
         "agent": {"type": "string", "description": "Имя агента, если владелец назвал"},
         "script": {"type": "string", "description": "Название сценария, если владелец назвал"}}}},
]


class AssistantError(Exception):
    pass


# ---------------------------------------------------------------- chats

def chats() -> list[dict]:
    return db.fetch_all("assistant_chats", "SELECT * FROM assistant_chats ORDER BY updated_at DESC, id DESC")


def new_chat() -> dict:
    ts = db.now()
    return db.insert("assistant_chats", {"title": "Новый чат", "created_at": ts, "updated_at": ts})


def messages(chat_id: int) -> list[dict]:
    rows = db.fetch_all("assistant_messages", "SELECT * FROM assistant_messages WHERE chat_id=? ORDER BY id", (chat_id,))
    for r in rows:
        r["data"] = json.loads(r["data"]) if r.get("data") else None
        if r["role"] == "assistant":  # answers saved before a cleanup rule appeared are shown clean too
            r["text"] = _strip_leaks(r["text"], {"shown": [], "seen": []})
        _expand(r)
    return rows


CALL_ROW = ("SELECT c.*, a.name AS agent_name, s.name AS script_name, cs.text AS ai_summary FROM calls c "
            "LEFT JOIN call_summaries cs ON cs.call_id=c.id LEFT JOIN agents a ON a.id=c.agent_id "
            "LEFT JOIN scripts s ON s.id=c.script_id WHERE c.id=?")


def _expand(msg: dict) -> dict:
    """The widgets under an answer, as they are now: [{type: contact | task | call, item}] (deleted ones dropped)."""
    objs = (msg.get("data") or {}).get("objects") if msg.get("role") == "assistant" else None
    if not objs:
        return msg
    out = []
    for o in objs:
        if o["type"] == "contact":
            item = db.get("contacts", o["id"])
            if item:
                item["label"] = db.contact_label(item)
        elif o["type"] == "task":
            item = db.get("tasks", o["id"])
            item = db.attach_contacts([item])[0] if item else None
        else:
            item = db.fetch_one("calls", CALL_ROW, (o["id"],))
            item = db.attach_contacts([item])[0] if item else None
        if item:
            out.append({"type": o["type"], "item": item})
    msg["objects"] = out
    return msg


def _add(chat_id: int, role: str, text: str = "", data: dict | None = None, **extra) -> dict:
    row = db.insert("assistant_messages", {"chat_id": chat_id, "role": role, "text": text,
                                           "data": json.dumps(data, ensure_ascii=False) if data else None,
                                           "created_at": db.now(), **extra})
    db.update("assistant_chats", chat_id, {"updated_at": db.now()})
    row["data"] = data
    return row


def _set_action(msg_id: int, data: dict) -> dict:
    db.update("assistant_messages", msg_id, {"data": json.dumps(data, ensure_ascii=False)})
    row = db.get("assistant_messages", msg_id)
    row["data"] = data
    return row


# ---------------------------------------------------------------- functions

def _contact_out(c: dict) -> dict:
    """The whole card of a contact, with the labels of the form — the comment and the contact's own fields too."""
    card = {"id": c["id"], "Имя": c.get("name") or "", "Фамилия": c.get("last_name") or "", "Телефон": c.get("phone"),
            "Кем приходится владельцу": c.get("relation") or "", "Компания": c.get("company") or "",
            "E-mail": c.get("email") or "", "Адрес": c.get("address") or "", "Теги": c.get("tags") or "",
            "Комментарий": c.get("notes") or ""}
    if c.get("is_self"):
        card["Это"] = "вы сами — карточка «Этот номер» (номер SIM-карты Caller)"
    card.update({k: v for k, v in db.contact_fields(c)})
    return {k: v for k, v in card.items() if v not in ("", None) or k in ("id", "Имя", "Телефон")}


def _get_contact(contact_id) -> dict:
    """One contact: the whole card and what was said in the latest calls and SMS with them."""
    from .history_chat import past_calls_brief
    c = db.get("contacts", int(contact_id))
    if not c:
        return {"error": "контакт не найден"}
    out = _contact_out(c)
    out["Последние звонки и SMS"] = past_calls_brief(c["phone"]) or "нет"
    out["Открытых дел"] = len(tasks.query("open", number=c["phone"]))  # how many; the tasks — list_tasks
    return out


def _show_place(chat_id: int, query: str = "", task_id=None, title: str = "") -> tuple[dict, dict]:
    """A map card in the chat: a task's place (coordinates known) or a search on the map (the browser finds it)."""
    card = {"type": "place", "query": (query or "").strip(), "title": (title or "").strip()}
    if task_id:
        t = db.get("tasks", int(task_id))
        if not t:
            return {"error": "дело не найдено"}, {}
        geo = json.loads(t["geo"]) if isinstance(t.get("geo"), str) else t.get("geo")
        card.update({"task_id": t["id"], "title": card["title"] or t["title"]})
        if geo:
            card.update({"lat": geo["lat"], "lon": geo["lon"], "address": geo.get("address") or ""})
        elif t.get("place"):
            card["query"] = card["query"] or t["place"]
        else:
            return {"error": "у дела нет места"}, {}
    if not card.get("lat") and not card["query"]:
        return {"error": "что искать на карте?"}, {}
    msg = _add(chat_id, "action", data=card)
    return {"shown": "карта показана владельцу в чате", "address": card.get("address") or card["query"]}, msg


def _find_contacts(query: str) -> list[dict]:
    q = (query or "").strip().lower()
    if q in ("", "*", "все", "всех", "all"):  # «покажи все контакты»
        return [_contact_out(c) for c in db.fetch_all("contacts", "SELECT * FROM contacts ORDER BY name, last_name")][:30]
    digits = "".join(ch for ch in q if ch.isdigit())
    q = q.replace("ё", "е")

    def stems(w: str) -> list[str]:  # a declined word: «юле» → «юл», «ильей» → «илье», «иль»
        return [w] + [w[:-k] for k in (1, 2) if len(w) - k >= (2 if len(w) <= 3 else 3)]

    out = []
    for c in db.fetch_all("contacts", "SELECT * FROM contacts ORDER BY name, last_name"):
        hay = " ".join(str(c.get(k) or "") for k in ("name", "last_name", "company", "email", "tags", "notes",
                                                      "relation")).lower()
        hay = (hay + " " + " ".join(f"{k} {v}" for k, v in db.contact_fields(c)).lower()).replace("ё", "е")
        words = hay.split()
        phone = "".join(ch for ch in c.get("phone") or "" if ch.isdigit())
        if all(any(word.startswith(st) for st in stems(w) for word in words) or w in hay for w in q.split()) \
                or (len(digits) >= 3 and digits in phone):
            out.append(_contact_out(c))
    return out[:10]


def _task_out(t: dict) -> dict:
    return {"id": t["id"], "title": t["title"], "details": t.get("details") or "", "status": t.get("status"),
            "with": t.get("contact_name") or t.get("number") or "", "assignee": t.get("assignee") or "",
            "due": t.get("due_at") or "", "due_as_said": t.get("due_text") or "", "overdue": tasks.is_overdue(t),
            "place": (t.get("geo") or {}).get("address") or t.get("place") or "",
            "event": t.get("event"), "from_call": t.get("call_id")}


def _list_tasks(status="open", overdue=None, contact_query="", due_from="", due_to="", text="") -> list[dict]:
    number = ""
    if contact_query:
        found = _find_contacts(contact_query)
        if not found:
            return []
        number = found[0]["Телефон"] if len(found) == 1 else ""
        if len(found) > 1:  # several people: their tasks together, the model sees whose is whose
            keys = {db.normalize_phone(c["Телефон"])[-10:] for c in found}
            return [_task_out(t) for t in tasks.query(status or "open", overdue, due_from=due_from, due_to=due_to, q=text)
                    if db.normalize_phone(t.get("number") or "")[-10:] in keys][:30]
    return [_task_out(t) for t in tasks.query(status or "open", overdue, number, due_from=due_from, due_to=due_to,
                                              q=text)][:30]


def _list_agenda(date_from: str, date_to: str) -> list[dict]:
    return [{"kind": "событие в календаре" if a["kind"] == "event" else "срок дела", "at": a["at"],
             "all_day": a["all_day"], "end": a["end"], "title": a["title"], "place": a["place"], "notes": a["notes"],
             "with": a["task"].get("contact_name") or a["task"].get("number") or "", "task_id": a["task"]["id"]}
            for a in tasks.agenda(date_from, date_to)][:40]


def _by_name(table: str, name: str) -> dict | None:
    name = (name or "").strip().lower()
    if not name:
        return None
    rows = db.fetch_all(table, f"SELECT * FROM {table}")
    return next((r for r in rows if r["name"].strip().lower() == name), None) \
        or next((r for r in rows if name in r["name"].lower()), None)


def _propose_call(chat_id: int, contact_id=None, number="", prompt="", agent="", script="") -> tuple[dict, dict]:
    c = db.get("contacts", int(contact_id)) if contact_id else None
    if not c and number:
        c = db.find_contact(number)
    phone = (c or {}).get("phone") or db.normalize_phone(number or "")
    if not phone:
        return {"error": "не указан контакт или номер"}, {}
    a = _by_name("agents", agent)
    sc = _by_name("scripts", script)
    if not sc:  # the first outgoing script, like the call form
        sc = next((x for x in db.fetch_all("scripts", "SELECT * FROM scripts ORDER BY id")
                   if x.get("direction") in ("outbound", "any")), None)
    if not a:
        a = (db.get("agents", sc["default_agent_id"]) if sc and sc.get("default_agent_id") else None) \
            or db.fetch_one("agents", "SELECT * FROM agents ORDER BY id LIMIT 1")
    card = {"type": "call", "status": "pending", "number": phone, "contact_id": (c or {}).get("id"),
            "name": db.contact_label(c) if c else "", "relation": (c or {}).get("relation") or "",
            "agent_id": (a or {}).get("id"), "script_id": (sc or {}).get("id"), "prompt": (prompt or "").strip()}
    msg = _add(chat_id, "action", data=card)
    return {"card": "показана владельцу", "number": phone, "name": card["name"], "agent": (a or {}).get("name"),
            "script": (sc or {}).get("name"), "note": "звонок начнётся только после нажатия «Позвонить»"}, msg


def _complete_task(chat_id: int, task_id: int) -> tuple[dict, dict]:
    t = db.get("tasks", int(task_id))
    if not t:
        return {"error": "дело не найдено"}, {}
    if t.get("status") == "done":
        return {"already": "дело уже выполнено", "title": t["title"]}, {}
    db.update("tasks", t["id"], {"status": "done", "updated_at": db.now()})
    from .events import hub
    hub.publish("tasks.updated", {"id": t["id"], "action": "updated"})
    msg = _add(chat_id, "action", data={"type": "task_done", "status": "done", "task_id": t["id"], "title": t["title"]})
    return {"done": True, "title": t["title"]}, msg


# ---------------------------------------------------------------- the model

def _now_text() -> str:
    n = datetime.now()
    week = [(n + timedelta(days=i)) for i in range(8)]
    days = ", ".join(f"{WEEKDAYS[d.weekday()]} {d:%d.%m}" for d in week)
    return f"Сейчас {n:%d.%m.%Y} ({WEEKDAYS[n.weekday()]}), {n:%H:%M}. Ближайшие дни: {days}."


def _history(chat_id: int) -> list[dict]:
    """The chat as the model reads it: texts, and what happened to the cards."""
    out = []
    for m in messages(chat_id)[-HISTORY:]:
        if m["role"] == "user":
            out.append({"role": "user", "content": m["text"]})
        elif m["role"] == "assistant" and m["text"]:
            out.append({"role": "assistant", "content": m["text"]})
        elif m["role"] == "action" and m["data"]:
            d = m["data"]
            note = (f"[карточка звонка {d.get('name') or d.get('number')}: {d.get('status')}]" if d["type"] == "call"
                    else f"[карта: {d.get('address') or d.get('query')}]" if d["type"] == "place"
                    else f"[дело «{d.get('title')}»: {'выполнено' if d.get('status') == 'done' else 'отмена выполнения'}]")
            out.append({"role": "assistant", "content": note})
    return out


async def ask(chat_id: int, text: str) -> list[dict]:
    """The user's message → the assistant's answer. Returns the new messages (the user's, cards, the answer)."""
    chat = db.get("assistant_chats", chat_id)
    if not chat:
        raise AssistantError("чат не найден")
    s = db.get_settings()
    if not s.get("yandex.api_key") or not s.get("yandex.folder_id"):
        raise AssistantError("не заданы API-ключ и ID каталога Yandex AI Studio")
    text = (text or "").strip()
    if not text:
        raise AssistantError("пустое сообщение")
    inputs = _history(chat_id)
    new = [_add(chat_id, "user", text)]
    if chat["title"] == "Новый чат":
        db.update("assistant_chats", chat_id, {"title": text[:60]})
    inputs.append({"role": "user", "content": text})

    model = s.get("assistant.model") or "yandexgpt/latest"
    uri = model if model.startswith("gpt://") else f"gpt://{s['yandex.folder_id']}/{model}"
    key = s["yandex.api_key"]
    auth = f"Bearer {key}" if key.startswith("t1.") else f"Api-Key {key}"
    instructions = INSTRUCTIONS + "\n" + _now_text()
    ctx = {"shown": [], "seen": [], "link": None, "called": False}
    nudged = False  # widgets the model asked for; objects the functions returned
    used_in = used_out = 0
    answer = ""
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=90)) as http:
            for _ in range(MAX_STEPS):
                payload = {"model": uri, "instructions": instructions, "input": inputs, "tools": TOOLS,
                           "temperature": 0.2, "max_output_tokens": 1500}
                async with http.post(RESPONSES_URL, json=payload, headers={"Authorization": auth}) as r:
                    body = await r.text()
                    if r.status != 200:
                        raise AssistantError(f"YandexGPT ответил {r.status}: {body[:300]}")
                    resp = json.loads(body)
                u = resp.get("usage") or {}
                used_in += u.get("input_tokens") or 0
                used_out += u.get("output_tokens") or 0
                calls = [o for o in resp.get("output") or [] if o.get("type") == "function_call"]
                if not calls:
                    answer = _output_text(resp).strip()
                    # a question about the data answered from memory (YandexGPT ignores tool_choice): that answer
                    # is dropped and the model is asked once more, to use the functions
                    if not ctx["called"] and not nudged and DATA_QUESTION.search(text):
                        nudged = True
                        log.info("assistant %s: answered without functions — asking again", chat_id)
                        inputs.append({"role": "assistant", "content": answer})
                        inputs.append({"role": "user", "content": "Это нужно взять из данных Caller: вызови подходящие "
                                       "функции (list_tasks, list_agenda, find_contacts, list_calls…) и ответь "
                                       "только по их результатам, не по памяти и не по прошлым сообщениям."})
                        continue
                    break
                ctx["called"] = True
                for fc in calls:
                    try:
                        args = json.loads(fc.get("arguments") or "{}")
                    except ValueError:
                        args = {}
                    result, card = _run(chat_id, fc["name"], args, ctx)
                    _remember(ctx, fc["name"], result)
                    _link(ctx, fc["name"], args, result)
                    if card:
                        new.append(card)
                    log.info("assistant %s: %s(%s) → %s", chat_id, fc["name"], json.dumps(args, ensure_ascii=False)[:200],
                             json.dumps(result, ensure_ascii=False)[:200])
                    inputs.append({"type": "function_call", "call_id": fc["call_id"], "name": fc["name"],
                                   "arguments": fc.get("arguments") or "{}"})
                    inputs.append({"type": "function_call_output", "call_id": fc["call_id"],
                                   "output": json.dumps(result, ensure_ascii=False)})
            else:
                answer = "Не получилось ответить: слишком много шагов. Попробуйте сформулировать иначе."
    except (aiohttp.ClientError, TimeoutError) as e:
        raise AssistantError(f"нет связи с YandexGPT: {e}")
    finally:
        db.log_usage("yandex", "assistant", tokens_in=used_in, tokens_out=used_out)
    answer = _strip_leaks(answer, ctx)
    # what the model asked to show, plus what it mentions from the data it got (or from everything, if it answered
    # from the chat's earlier messages)
    objects = list(ctx["shown"])
    for o in _mentioned(ctx["seen"], answer) or ([] if objects else _mentioned(_everything(), answer)):
        if o not in objects:
            objects.append(o)
    if ctx.get("list") and _lead_in(answer, ctx["seen"]):  # «Вот ваши просроченные дела:» — the list is the answer
        objects = ctx["list"] + [o for o in objects if o not in ctx["list"]]
    objects = objects[:8]
    if objects:
        answer = _without_repeats(answer, objects, ctx["seen"])
    data = {"objects": objects} if objects else {}
    link = ctx["link"]
    if link and link["count"] > LINK_FROM:  # many things: a link to the section, filtered the same way
        data["link"] = link
    new.append(_expand(_add(chat_id, "assistant", answer or "…", data=data or None)))
    return new


# the model sometimes writes show_cards into the text instead of calling it: «![Виджет](show_cards)» and a JSON
# block {"task_ids": [6, 5]} — the ids are taken from it and it is cut from the answer
_LEAK = re.compile(r"!?\[[^\]]*\]\(\s*show_cards[^)]*\)|`{1,3}\s*(?:json)?\s*\{[^{}]*_ids[^{}]*\}\s*`{0,3}"
                   r"|\{[^{}]*\"(?:contact|task|call)_ids\"[^{}]*\}|\bshow_cards\b\s*\(?[^\n]*", re.S)


def _strip_leaks(answer: str, ctx: dict) -> str:
    # a function call imitated in the text («Ассистент:\n[TOOL_CALL_START]…»): everything from there on goes
    cut = re.search(r"\[TOOL_CALL|<tool_call|```tool|^\s*(?:Пользователь|Владелец|User)\s*:", answer or "", re.M)
    if cut:
        answer = re.sub(r"\s*(?:Ассистент|Assistant)\s*:\s*$", "", answer[:cut.start()].rstrip())
    for m in _LEAK.finditer(answer or ""):
        for kind in ("contact", "task", "call"):
            ids = re.search(rf'{kind}_ids"?\s*[:=]\s*\[([\d,\s]*)\]', m.group(0))  # JSON or show_cards(task_ids=[…])
            for i in re.findall(r"\d+", ids.group(1)) if ids else []:
                if {"type": kind, "id": int(i)} not in ctx["shown"]:
                    ctx["shown"].append({"type": kind, "id": int(i)})
    text = _LEAK.sub("", answer or "")
    text = re.sub(r"(?m)^[\s\[\]\(\)\{\}`*!]+$", "", text)        # lines left with only brackets / backticks
    text = re.sub(r"[\s\[\(\{`!]+$", "", text)                       # an opening bracket left at the end
    return re.sub(r"\n{3,}", "\n\n", text).strip()


# a question about the data: tasks, plans, calls, contacts — answered only through the functions
DATA_QUESTION = re.compile(r"дел[аоу]?\b|дела|задач|напомн|обещ|поруч|встреч|план|календар|срок|просроч|выполн|"
                           r"звон|разговор|контакт|номер|телефон|кто так|найди|покажи|где\b|карт|sms|смс", re.I)
LINK_FROM = 4   # more objects than this — the answer gets a link to the section with the same filter


def _link(ctx: dict, name: str, args: dict, result):
    """Where the same list is in the interface: «Дела» with a folder / search, the calendar, a person's calls,
    the phone book. The biggest list of the turn wins."""
    if not isinstance(result, list):
        return
    from urllib.parse import urlencode
    n = len(result)
    link = None
    if name == "list_tasks":
        who = (args.get("contact_query") or "").strip()
        folder = "@overdue" if args.get("overdue") else "@done" if args.get("status") == "done" else ""
        params = {k: v for k, v in (("folder", folder), ("q", who or (args.get("text") or "").strip())) if v}
        label = {"@overdue": "Просроченные дела", "@done": "Выполненные дела"}.get(folder, "Все открытые дела") + (f": {who}" if who else "")
        link = {"href": "#/tasks?" + urlencode({"tab": "list", "folder": folder, **params}), "label": f"{label} ({n})"}
    elif name == "list_agenda" and args.get("date_from"):
        link = {"href": "#/tasks?" + urlencode({"tab": "calendar", "folder": "", "month": args["date_from"][:7]}),
                "label": f"Календарь ({n})"}
    elif name == "list_calls":
        found = _find_contacts(args["contact_query"]) if args.get("contact_query") else []
        if len(found) == 1:
            link = {"href": "#/calls?" + urlencode({"person": found[0]["Телефон"]}),
                    "label": f"Звонки: {db.contact_label(db.get('contacts', found[0]['id']))} ({n})"}
        else:
            link = {"href": "#/calls", "label": f"Звонки ({n})"}
    elif name == "find_contacts":
        q = (args.get("query") or "").strip()
        link = ({"href": "#/contacts?" + urlencode({"q": q}), "label": f"Найденные контакты ({n})"}
                if q not in ("", "*", "все", "всех", "all") else {"href": "#/contacts", "label": f"Все контакты ({n})"})
    if link and (not ctx["link"] or n > ctx["link"]["count"]):
        ctx["link"] = {**link, "count": n}


def _remember(ctx: dict, name: str, result):
    """Objects the functions returned this turn — for widgets, if the model doesn't call show_cards."""
    items = result if isinstance(result, list) else [result] if isinstance(result, dict) else []
    before = len(ctx["seen"])
    for x in items:
        if not isinstance(x, dict) or "id" not in x and "task_id" not in x:
            continue
        if name in ("find_contacts", "get_contact"):
            ctx["seen"].append({"type": "contact", "id": x["id"], "name": x.get("Имя") or ""})
        elif name == "list_tasks":
            ctx["seen"].append({"type": "task", "id": x["id"], "name": x.get("title") or ""})
        elif name == "list_agenda":
            ctx["seen"].append({"type": "task", "id": x["task_id"], "name": x.get("title") or ""})
        elif name == "list_calls":
            ctx["seen"].append({"type": "call", "id": x["id"], "name": x.get("when") or "", "only": len(items) <= 2})
    if isinstance(result, list) and name in ("find_contacts", "list_tasks", "list_agenda", "list_calls"):
        refs = [{"type": o["type"], "id": o["id"]} for o in ctx["seen"][before:]]
        if len(refs) > len(ctx.setdefault("list", [])):
            ctx["list"] = refs  # the biggest list of the turn


def _mentioned(seen: list[dict], answer: str) -> list[dict]:
    """The returned objects the answer talks about: a contact by name, a task by most words of its title, a call by
    its date (or the only one or two found)."""
    text = (answer or "").lower()
    out = []

    def stem(w: str) -> str:
        return w[:-1] if len(w) >= 4 else w

    for o in seen:
        name = (o.get("name") or "").lower()
        hit = False
        if o["type"] == "contact":
            hit = bool(name) and stem(name.split()[0]) in text
        elif o["type"] == "task":
            words = [w[:5] for w in name.replace("«", " ").replace("»", " ").split() if len(w) >= 4]
            need = 1 if len(words) == 1 else max(2, -(-len(words) * 2 // 3))  # most of the title's words
            hit = bool(words) and sum(w in text for w in words) >= need
        elif o["type"] == "call":
            hit = o.get("only") or (bool(name) and name[:5] in text)
        ref = {"type": o["type"], "id": o["id"]}
        if hit and ref not in out:
            out.append(ref)
    return out


_FIELD_LINE = re.compile(r"^(?:Имя|Фамилия|Телефон|Номер|Компания|E-?mail|Почта|Теги|Комментарий|Кем приходится[^:]*|"
                         r"Связь[^:]*)\s*:", re.I)
_ITEM = re.compile(r"^\s*(?:[-—–•*]|\d+[.)])\s+")


def _lead_in(answer: str, seen: list[dict]) -> bool:
    """The answer introduces a list: its first paragraph ends with a colon, or it lists the found objects."""
    first = (answer or "").strip().split("\n\n")[0].strip()
    return first.endswith(":") or len(_mentioned(seen, answer)) >= 3


def _without_repeats(answer: str, objects: list[dict], seen: list[dict] | None = None) -> str:
    """The widgets show the objects, so the text doesn't list them again: list lines about a shown contact, task
    or call go, and so do the card's fields («Телефон: …») under a contact widget. What's left is the lead-in
    («Вот ваши дела:») and anything else the answer says."""
    names = []
    for o in objects:
        item = _expand({"role": "assistant", "data": {"objects": [o]}}).get("objects") or []
        if not item:
            continue
        x = item[0]["item"]
        when = x.get("started_at") or x.get("created_at") or ""
        name = x.get("label") or x.get("title") or (f"{when[8:10]}.{when[5:7]}" if when else "")
        names.append({"type": o["type"], "id": o["id"], "name": name, "only": len(objects) <= 2})
    # the rest of the found list is behind the section link — not repeated in the text either
    names += [{**n, "name": (n["name"] or "")[:10] if n["type"] == "call" else n["name"]}
              for n in seen or [] if {"type": n["type"], "id": n["id"]} not in objects]
    has_contact = any(o["type"] == "contact" for o in objects)
    kept, dropped = [], 0
    for line in answer.split("\n"):
        bare = _ITEM.sub("", line).strip()
        if has_contact and _FIELD_LINE.match(bare):
            dropped += 1
            continue
        if (_ITEM.match(line) and _repeats(bare, names)) or any(bare.lower() == (n["name"] or "").lower() for n in names):
            dropped += 1
            continue
        kept.append(line)
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip()
    if dropped and not text:
        text = "Вот что нашлось:"
    return text


def _repeats(line: str, names: list[dict]) -> bool:
    """A list line that is about a shown object: starts with the contact's name or the call's date, or carries
    most of a task's title. («— SMS от Ильи: …» under Илья's widget stays — it says something else.)"""
    low = line.lower()
    for n in names:
        name = (n["name"] or "").lower()
        if not name:
            continue
        if n["type"] == "contact" and low.startswith(name.split()[0][:max(3, len(name.split()[0]) - 1)]):
            return True
        if n["type"] == "call" and low.startswith(name):
            return True
        if n["type"] == "task" and _mentioned([n], line):
            return True
    return False


def _everything() -> list[dict]:
    """All open tasks — for an answer given from the chat's earlier messages, without functions. (Not contacts:
    a name in such an answer is usually just a name, and a contact widget there was a wrong guess.)"""
    return [{"type": "task", "id": t["id"], "name": t["title"]} for t in tasks.query("open")]


def _list_calls(contact_query: str = "", date_from: str = "", date_to: str = "", limit: int = 10) -> list[dict]:
    from .history_chat import _gist
    rows = db.attach_contacts(db.fetch_all("calls", CALL_ROW.replace("WHERE c.id=?", "ORDER BY c.id DESC LIMIT 300")))
    keys = None
    if contact_query:
        found = _find_contacts(contact_query)
        digits = "".join(ch for ch in contact_query if ch.isdigit())
        keys = {db.normalize_phone(c["Телефон"])[-10:] for c in found} | ({digits[-10:]} if len(digits) >= 7 else set())
    out = []
    for c in rows:
        if keys is not None and db.normalize_phone(c.get("number") or "")[-10:] not in keys:
            continue
        day = (c.get("started_at") or c.get("created_at") or "")[:10]
        if (date_from and day < date_from) or (date_to and day > date_to):
            continue
        gist, agreed = ("(агент не помнит этот звонок: история очищена)", "") if c.get("forgotten") else _gist(c)
        when = c.get("started_at") or c.get("created_at") or ""
        out.append({"id": c["id"], "when": f"{when[8:10]}.{when[5:7]}.{when[:4]} {when[11:16]}" if when else "",
                    "direction": "входящий" if c["direction"] == "in" else "исходящий",
                    "with": c.get("contact_name") or c.get("number") or "скрытый номер", "status": c.get("status"),
                    "duration_s": c.get("duration") or 0, "agent": c.get("agent_name") or "",
                    "gist": gist, "agreed": agreed})
        if len(out) >= max(1, min(int(limit), 30)):
            break
    return out


def _run(chat_id: int, name: str, args: dict, ctx: dict) -> tuple[object, dict | None]:
    try:
        if name == "find_contacts":
            return _find_contacts(args.get("query", "")), None
        if name == "list_tasks":
            return _list_tasks(args.get("status") or "open", args.get("overdue"), args.get("contact_query", ""),
                               args.get("due_from", ""), args.get("due_to", ""), args.get("text", "")), None
        if name == "list_agenda":
            return _list_agenda(args.get("date_from", ""), args.get("date_to", "")), None
        if name == "list_calls":
            return _list_calls(args.get("contact_query", ""), args.get("date_from", ""), args.get("date_to", ""),
                               args.get("limit") or 10), None
        if name == "show_cards":
            for kind, key in (("contact", "contact_ids"), ("task", "task_ids"), ("call", "call_ids")):
                for i in args.get(key) or []:
                    if isinstance(i, int) and {"type": kind, "id": i} not in ctx["shown"]:
                        ctx["shown"].append({"type": kind, "id": i})
            return {"ok": "виджеты будут показаны под ответом"}, None
        if name == "get_contact":
            return _get_contact(args.get("contact_id")), None
        if name == "show_place":
            result, card = _show_place(chat_id, args.get("query", ""), args.get("task_id"), args.get("title", ""))
            return result, card or None
        if name == "complete_task":
            result, card = _complete_task(chat_id, args.get("task_id"))
            return result, card or None
        if name == "propose_call":
            result, card = _propose_call(chat_id, args.get("contact_id"), args.get("number", ""),
                                         args.get("prompt", ""), args.get("agent", ""), args.get("script", ""))
            return result, card or None
        return {"error": f"нет функции {name}"}, None
    except Exception as e:  # noqa: BLE001 — the model gets the error and tells the user
        log.exception("assistant function %s failed", name)
        return {"error": str(e) or type(e).__name__}, None


# ---------------------------------------------------------------- the user's answer to a card

async def confirm_call(msg_id: int, prompt: str | None = None, agent_id: int | None = None,
                       script_id: int | None = None) -> dict:
    """«Позвонить» in a call card: only now the number is dialed."""
    from .calls import calls
    m = db.get("assistant_messages", msg_id)
    d = json.loads(m["data"]) if m and m.get("data") else None
    if not d or d.get("type") != "call":
        raise AssistantError("карточка не найдена")
    if d.get("status") != "pending":
        raise AssistantError("по этой карточке уже звонили или она отменена")
    if prompt is not None:
        d["prompt"] = prompt.strip()
    if agent_id:
        d["agent_id"] = agent_id
    if script_id is not None:
        d["script_id"] = script_id or None
    call = await calls.dial(d["number"], d.get("agent_id"), d.get("script_id"), {}, prompt=d.get("prompt") or "")
    d.update({"status": "dialed", "call_id": call["id"]})
    return _set_action(msg_id, d)


def cancel_call(msg_id: int) -> dict:
    m = db.get("assistant_messages", msg_id)
    d = json.loads(m["data"]) if m and m.get("data") else None
    if not d or d.get("type") != "call" or d.get("status") != "pending":
        raise AssistantError("карточку нельзя отменить")
    d["status"] = "cancelled"
    return _set_action(msg_id, d)


def undo_done(msg_id: int) -> dict:
    """«Отменить» in a «выполнено» card: the task is open again."""
    m = db.get("assistant_messages", msg_id)
    d = json.loads(m["data"]) if m and m.get("data") else None
    if not d or d.get("type") != "task_done" or d.get("status") != "done":
        raise AssistantError("нечего отменять")
    if db.get("tasks", d["task_id"]):
        db.update("tasks", d["task_id"], {"status": "open", "updated_at": db.now()})
        from .events import hub
        hub.publish("tasks.updated", {"id": d["task_id"], "action": "updated"})
    d["status"] = "undone"
    return _set_action(msg_id, d)
