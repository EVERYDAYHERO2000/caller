"""Transcripts of calls without an agent (you talk through the browser): the recording is recognized after the call.

The recording is stereo — left: the other person (modem RX), right: you (browser mic → modem TX) — and SpeechKit
v3 async recognition tags every phrase with its channel, so the transcript says who said what. The phrases are
stored like an agent call's transcript (call_messages: user = the other person, operator = you), so the summary,
the call card and the contact's «История» AI work the same.
"""
import asyncio
import base64
import json
import logging
from datetime import datetime, timedelta

import aiohttp

from . import config, db
from .events import hub

log = logging.getLogger("transcribe")

SUBMIT_URL = "https://stt.api.cloud.yandex.net/stt/v3/recognizeFileAsync"
RESULT_URL = "https://stt.api.cloud.yandex.net/stt/v3/getRecognition"
OPERATION_URL = "https://operation.api.cloud.yandex.net/operations/"
CHANNEL_ROLE = {"0": "user", "1": "operator"}   # left = the other person, right = you
MAX_BYTES = 10 * 1024 * 1024                    # inline content of an async request (≈ 5 min of 8 kHz stereo)


class TranscribeError(Exception):
    pass


def has_transcript(call_id: int) -> bool:
    return bool(db.scalar("SELECT COUNT(*) FROM call_messages WHERE call_id=? AND role IN ('user','assistant','operator')",
                          (call_id,)))


def can_transcribe(call: dict) -> bool:
    return bool(call.get("recording")) and not has_transcript(call["id"]) \
        and (config.RECORDINGS_DIR / call["recording"]).exists()


def _auth(s: dict) -> dict:
    key = s.get("yandex.api_key") or ""
    if not key or not s.get("yandex.folder_id"):
        raise TranscribeError("не заданы API-ключ и ID каталога Yandex AI Studio")
    return {"Authorization": ("Bearer " if key.startswith("t1.") else "Api-Key ") + key, "x-folder-id": s["yandex.folder_id"]}


async def transcribe(call_id: int) -> int:
    """Recognize the call's recording and store the phrases. Returns how many; raises TranscribeError."""
    call = db.get("calls", call_id)
    if not call:
        raise TranscribeError("звонок не найден")
    if has_transcript(call_id):
        raise TranscribeError("у звонка уже есть расшифровка")
    path = config.RECORDINGS_DIR / (call.get("recording") or "")
    if not call.get("recording") or not path.exists():
        raise TranscribeError("нет записи звонка (включите «Записывать разговоры» в настройках звонков)")
    data = path.read_bytes()
    if len(data) > MAX_BYTES:
        raise TranscribeError(f"запись слишком длинная для распознавания ({len(data) // 1024 // 1024} МБ, можно до 10 МБ)")
    headers = _auth(db.get_settings())
    body = {"content": base64.b64encode(data).decode(),
            "recognitionModel": {"model": "general", "audioFormat": {"containerAudio": {"containerAudioType": "WAV"}},
                                 "textNormalization": {"textNormalization": "TEXT_NORMALIZATION_ENABLED",
                                                       "literatureText": True},
                                 "languageRestriction": {"restrictionType": "WHITELIST", "languageCode": ["ru-RU"]}}}
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as http:
            async with http.post(SUBMIT_URL, json=body, headers=headers) as r:
                text = await r.text()
                if r.status != 200:
                    raise TranscribeError(f"SpeechKit ответил {r.status}: {text[:300]}")
                op = json.loads(text)["id"]
            for _ in range(150):  # up to ~5 min; a minute of audio takes seconds
                await asyncio.sleep(2)
                async with http.get(OPERATION_URL + op, headers=headers) as r:
                    o = await r.json()
                if o.get("done"):
                    if o.get("error"):
                        raise TranscribeError(f"SpeechKit: {o['error'].get('message') or o['error']}")
                    break
            else:
                raise TranscribeError("SpeechKit не успел распознать запись")
            async with http.get(RESULT_URL, params={"operationId": op}, headers=headers) as r:
                if r.status != 200:
                    raise TranscribeError(f"SpeechKit ответил {r.status}: {(await r.text())[:300]}")
                lines = (await r.text()).splitlines()
    except (aiohttp.ClientError, TimeoutError) as e:
        raise TranscribeError(f"нет связи со SpeechKit: {e}")

    phrases = []
    for line in lines:
        if not line.strip():
            continue
        res = json.loads(line).get("result") or {}
        alt = (((res.get("finalRefinement") or {}).get("normalizedText") or {}).get("alternatives") or [{}])[0]
        if alt.get("text") and res.get("channelTag") in CHANNEL_ROLE:
            phrases.append((int(alt.get("startTimeMs") or 0), CHANNEL_ROLE[res["channelTag"]], alt["text"].strip()))
    phrases.sort(key=lambda p: p[0])
    start = datetime.fromisoformat(call.get("answered_at") or call.get("started_at") or db.now())
    for ms, role, text in phrases:
        db.insert("call_messages", {"call_id": call_id, "role": role, "text": text,
                                    "ts": (start + timedelta(milliseconds=ms)).isoformat(timespec="seconds")})
    log.info("call %s transcribed by SpeechKit: %s phrases", call_id, len(phrases))
    hub.publish("call.updated", db.get("calls", call_id))
    return len(phrases)


async def after_call(call_id: int):
    """Called when a call ends: the transcript of a browser call first, then the summary and «Дела»."""
    from . import summary, tasks
    call = db.get("calls", call_id)
    if call and call.get("mode") == "browser" and db.setting("transcribe.browser_calls", True) and can_transcribe(call):
        try:
            await transcribe(call_id)
        except TranscribeError as e:
            log.warning("transcript of call %s failed: %s", call_id, e)
            db.insert("call_messages", {"call_id": call_id, "role": "system", "text": f"Расшифровка не получилась: {e}",
                                        "ts": db.now()})
    await summary.auto(call_id)
    await tasks.auto(call_id)
