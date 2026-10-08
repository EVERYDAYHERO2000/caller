"""Car numbers written with digits in what is saved after a call.

The voice agent writes numbers as words (the synthesizer reads them better), so the call's summary and the
result the agent saved say «А двести тридцать четыре МР, регион семьсот семьдесят семь». While the summary is
prepared, a separate pass asks the model only to find such car numbers and say how each is written properly
(«А 234 МР 777»); the replacements are applied here, word for word — the model never rewrites the text itself.
"""
import json
import logging
import re

import aiohttp

from . import db

log = logging.getLogger("plates")

_NUM = ("ноль|один|одна|два|две|три|четыре|пять|шесть|семь|восемь|девять|десять|одиннадцать|двенадцать|тринадцать|"
        "четырнадцать|пятнадцать|шестнадцать|семнадцать|восемнадцать|девятнадцать|двадцать|тридцать|сорок|"
        "пятьдесят|шестьдесят|семьдесят|восемьдесят|девяносто|сто|двести|триста|четыреста|пятьсот|шестьсот|"
        "семьсот|восемьсот|девятьсот")
# worth a pass: «регион», or a capital letter right before a number in words («А двести…», «Т четыреста…»)
HINT = re.compile(rf"(?i:\bрегион)|(?<![\w])[А-ЯЁA-Z]{{1,2}}\s+(?i:{_NUM})\b")
# where a car number begins in a fragment: its first letter (the model sometimes takes a word before it too)
START = re.compile(rf"(?<![\w])[А-ЯЁA-Z]{{1,2}}\s+(?i:{_NUM})\b")

INSTRUCTIONS = """В текстах ниже могут быть номера автомобилей (госномера), записанные словами, например \
«А двести тридцать четыре МР, регион семьсот семьдесят семь» или «номер Т четыреста восемьдесят два НО пятьдесят».
Найди каждый такой номер и напиши, как он записывается правильно: буквы — заглавные кириллицей, цифры — цифрами, \
через пробелы: буква, три цифры, буквы, регион. Например: «А 234 МР 777», «Т 482 НО 50». Если номер неполный — \
запиши то, что есть, цифрами: «А 367 М 777».
Ответь ТОЛЬКО JSON-массивом без пояснений: [{"from": "фрагмент текста ровно как он написан, от первой буквы \
номера до последнего слова региона", "to": "номер цифрами"}]. Фрагмент from должен в точности совпадать с текстом. \
Ничего, кроме номеров автомобилей, не трогай (время, суммы, телефоны — не номера автомобилей). Если номеров нет — [].
"""


def needed(*texts: str) -> bool:
    return any(t and HINT.search(t) for t in texts)


def _parse(text: str) -> list[tuple[str, str]]:
    text = re.sub(r"^```\w*\s*|\s*```$", "", (text or "").strip())
    i, j = text.find("["), text.rfind("]")
    if i < 0 or j < i:
        return []
    try:
        items = json.loads(text[i:j + 1])
    except ValueError:
        return []
    out = []
    for x in items:
        if isinstance(x, dict):
            a, b = str(x.get("from") or "").strip(), str(x.get("to") or "").strip()
            m = START.search(a)
            if m:
                a = a[m.start():]           # «Машина Т четыреста…» → «Т четыреста…»
            a = a.rstrip(" .,;:!?")         # the sentence's end stays
            # a car number: letters and digits only, with at least one digit and one letter
            if a and b and a != b and re.fullmatch(r"[А-ЯЁA-Z0-9 ]{3,20}", b) and re.search(r"\d", b) \
                    and re.search(r"[А-ЯЁA-Z]", b):
                out.append((a, b))
    return sorted(set(out), key=lambda p: -len(p[0]))  # longer fragments first


def apply(text: str, pairs: list[tuple[str, str]]) -> str:
    for a, b in pairs:
        text = text.replace(a, b)
    return text


def apply_deep(value, pairs):
    """The same in the agent's result: strings inside dicts and lists."""
    if isinstance(value, str):
        return apply(value, pairs)
    if isinstance(value, dict):
        return {k: apply_deep(v, pairs) for k, v in value.items()}
    if isinstance(value, list):
        return [apply_deep(v, pairs) for v in value]
    return value


async def find(texts: list[str], call_id: int | None = None) -> list[tuple[str, str]]:
    """(как написано, как надо) for the car numbers in the texts; [] if none or the model is unavailable."""
    texts = [t for t in texts if t]
    if not needed(*texts):
        return []
    s = db.get_settings()
    if not s.get("yandex.api_key") or not s.get("yandex.folder_id"):
        return []
    model = s.get("summary.model") or "yandexgpt-lite/latest"
    uri = model if model.startswith("gpt://") else f"gpt://{s['yandex.folder_id']}/{model}"
    key = s["yandex.api_key"]
    auth = f"Bearer {key}" if key.startswith("t1.") else f"Api-Key {key}"
    payload = {"model": uri, "instructions": INSTRUCTIONS, "temperature": 0, "max_output_tokens": 400,
               "input": "\n\n".join(f"Текст {i + 1}:\n{t}" for i, t in enumerate(texts))}
    from .summary import RESPONSES_URL, _output_text
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=40)) as http:
            async with http.post(RESPONSES_URL, json=payload, headers={"Authorization": auth}) as r:
                body = await r.text()
                if r.status != 200:
                    log.warning("car numbers: the model answered %s: %s", r.status, body[:200])
                    return []
                resp = json.loads(body)
    except (aiohttp.ClientError, TimeoutError, ValueError) as e:
        log.warning("car numbers: %s", e)
        return []
    u = resp.get("usage") or {}
    db.log_usage("yandex", "summary", tokens_in=u.get("input_tokens") or 0, tokens_out=u.get("output_tokens") or 0,
                 call_id=call_id)
    whole = "\n".join(texts)
    pairs = [(a, b) for a, b in _parse(_output_text(resp)) if a in whole]  # only what really is in the texts
    if pairs:
        log.info("call %s: car numbers %s", call_id, [b for _, b in pairs])
    return pairs
