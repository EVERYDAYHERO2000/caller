"""Post-call summaries (YandexGPT via the AI Studio Responses API).

A summary is written once per call and never changed: the table has a trigger that
rejects UPDATE, and there is no API to edit it. If generation fails, the call simply has
no summary yet and one can be requested again (POST /api/calls/{id}/summary)."""
import json
import logging

import aiohttp

from . import db
from .events import hub

log = logging.getLogger("summary")

RESPONSES_URL = "https://ai.api.cloud.yandex.net/v1/responses"

INSTRUCTIONS = """Ты анализируешь расшифровку телефонного разговора с человеком (говорил голосовой агент или сам пользователь).
Напиши краткое резюме на русском строго по фактам из расшифровки, ничего не придумывай.
Формат — четыре строки без разметки:
Суть: 1–2 предложения, о чём был разговор.
Договорённости: что решили или пообещали; «нет», если ничего.
Следующий шаг: что нужно сделать после звонка и кому; «нет», если ничего.
Настроение собеседника: одно-два слова.
Если разговора по сути не было (не ответили, тишина, автоответчик) — напиши об этом одной строкой."""

ROLE_NAMES = {"user": "Собеседник", "assistant": "Агент", "operator": "Пользователь (говорил сам через браузер)"}


class SummaryError(Exception):
    pass


def get(call_id: int) -> dict | None:
    return db.fetch_one("call_summaries", "SELECT * FROM call_summaries WHERE call_id=?", (call_id,))


def _transcript(call_id: int) -> list[dict]:
    return db.fetch_all("call_messages", "SELECT * FROM call_messages WHERE call_id=? AND role IN "
                                         "('user','assistant','operator') ORDER BY id", (call_id,))


def can_summarize(call_id: int) -> bool:
    return bool(_transcript(call_id))


def _build_input(call: dict, messages: list[dict]) -> str:
    head = [f"Звонок: {'входящий' if call['direction'] == 'in' else 'исходящий'}",
            f"Собеседник: {call.get('contact_name') or call.get('number') or 'номер скрыт'}",
            f"Длительность: {call.get('duration') or 0} с"]
    if call.get("script_name"):
        head.append(f"Сценарий: {call['script_name']}")
    if call.get("result"):
        head.append("Итог, сохранённый агентом: " + json.dumps(call["result"], ensure_ascii=False))
    lines = [f"{ROLE_NAMES[m['role']]}: {m['text']}" for m in messages]
    return "\n".join(head) + "\n\nРасшифровка:\n" + "\n".join(lines)


def _output_text(resp: dict) -> str:
    if resp.get("output_text"):
        return resp["output_text"]
    parts = []
    for item in resp.get("output") or []:
        for c in item.get("content") or []:
            if c.get("text"):
                parts.append(c["text"])
    return "\n".join(parts)


async def create(call_id: int) -> dict:
    """Generate and store the summary. Raises SummaryError; never overwrites an existing one."""
    if get(call_id):
        raise SummaryError("суммаризация уже есть и не может быть изменена")
    call = db.fetch_one("calls", "SELECT c.*, s.name AS script_name FROM calls c "
                                 "LEFT JOIN scripts s ON s.id=c.script_id WHERE c.id=?", (call_id,))
    if not call:
        raise SummaryError("звонок не найден")
    db.attach_contacts([call])
    messages = _transcript(call_id)
    if not messages:
        raise SummaryError("нет расшифровки разговора")
    s = db.get_settings()
    if not s.get("yandex.api_key") or not s.get("yandex.folder_id"):
        raise SummaryError("не заданы API-ключ и ID каталога Yandex AI Studio")
    model = s.get("summary.model") or "yandexgpt-lite/latest"
    uri = model if model.startswith("gpt://") else f"gpt://{s['yandex.folder_id']}/{model}"
    key = s["yandex.api_key"]
    auth = f"Bearer {key}" if key.startswith("t1.") else f"Api-Key {key}"
    payload = {"model": uri, "instructions": INSTRUCTIONS, "input": _build_input(call, messages),
               "temperature": 0.2, "max_output_tokens": 600}
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as http:
            async with http.post(RESPONSES_URL, json=payload, headers={"Authorization": auth}) as r:
                body = await r.text()
                if r.status != 200:
                    raise SummaryError(f"YandexGPT ответил {r.status}: {body[:300]}")
                resp = json.loads(body)
    except (aiohttp.ClientError, TimeoutError) as e:
        raise SummaryError(f"нет связи с YandexGPT: {e}")
    text = _output_text(resp).strip()
    if not text:
        raise SummaryError("модель вернула пустой ответ")
    usage = resp.get("usage") or {}
    try:
        # plain INSERT (not REPLACE): a second summary for the same call is rejected by the PK
        db.execute("INSERT INTO call_summaries(call_id, text, model, input_tokens, output_tokens, created_at) "
                   "VALUES(?,?,?,?,?,?)", (call_id, text, model, usage.get("input_tokens"),
                                          usage.get("output_tokens"), db.now()))
    except Exception as e:
        raise SummaryError(f"не удалось сохранить: {e}")
    row = get(call_id)
    log.info("summary for call %s saved (%s tokens)", call_id, usage.get("total_tokens"))
    hub.publish("call.summary", row)
    return row


async def auto(call_id: int):
    """Called after a call ends."""
    if not db.setting("summary.enabled", True) or not can_summarize(call_id):
        return
    try:
        await create(call_id)
    except SummaryError as e:
        log.warning("summary for call %s failed: %s", call_id, e)
