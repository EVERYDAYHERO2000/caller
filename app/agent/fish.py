"""Fish Audio TTS (через Kitta, fishaudio.org) для голосового агента.

Yandex Realtime API ведёт диалог в текстовом режиме, а озвучивает ответы Fish:
  - FishTTS      — WebSocket Realtime TTS v3 в режиме reliable (сегмент = фраза, одна сессия на звонок);
  - звук идёт в формате wav: на каждую фразу 44-байтный заголовок и сырой PCM16 44.1 кГц mono
    (format "pcm" у Kitta сломан); заголовок срезается здесь, частоту понижает app.audio.Resampler;
  - хезитации голоса («Ммм...») — в app/fillers.py (общие для Yandex и Fish).

Протокол: https://docs.fishaudio.org/ru/docs/api-reference/text-to-speech/realtime
"""
import asyncio
import json
import logging
import uuid

import aiohttp

from .. import config, db
from ..audio import Resampler

log = logging.getLogger("agent.fish")

DEFAULT_WS_URL = "wss://realtime.fishaudio.org/v3/tts/live"
DEFAULT_API_URL = "https://fishaudio.org/api/open"
SUBPROTOCOL = "realtime.tts.msgpack.v3"
DEFAULT_MODEL = "fishaudio-s21pro-flash"
FILLER_DIR = config.DATA_DIR / "fish_fillers"  # hesitations of the first version; app/fillers.py moves them



class FishError(Exception):
    pass


def _msgpack():
    try:
        import msgpack
    except ImportError as e:  # pragma: no cover
        raise FishError("Не установлен пакет msgpack (pip install -r requirements.txt)") from e
    return msgpack


def _auth(settings: dict) -> dict:
    key = settings.get("fish.api_key") or ""
    if not key:
        raise FishError("Не задан API-ключ Fish Audio (Настройки → Fish Audio)")
    return {"Authorization": f"Bearer {key}"}


def _eid() -> str:
    return "evt_" + uuid.uuid4().hex


# ---------------------------------------------------------------- WAV → PCM

def parse_wav(data: bytes) -> tuple[bytes, int] | None:
    """(PCM, частота) из WAV-потока или None, если заголовок ещё не пришёл целиком."""
    i = data.find(b"data", 12)
    if data[:4] != b"RIFF" or i < 0 or len(data) < i + 8:
        return None
    rate = int.from_bytes(data[24:28], "little")
    channels = int.from_bytes(data[22:24], "little")
    bits = int.from_bytes(data[34:36], "little")
    if channels != 1 or bits != 16:
        raise FishError(f"Fish Audio: неожиданный WAV ({channels} кан., {bits} бит)")
    return data[i + 8:], rate


def wav_to_pcm(data: bytes, rate: int) -> bytes:
    """Целый WAV → PCM16 mono нужной частоты."""
    parsed = parse_wav(data)
    if not parsed:
        raise FishError("Fish Audio: некорректный WAV")
    pcm, src = parsed
    pcm = pcm[: len(pcm) - len(pcm) % 2]
    return Resampler(src, rate).process(pcm) if src != rate else pcm


# ---------------------------------------------------------------- realtime TTS

class FishTTS:
    """Одна reliable-сессия Realtime TTS v3 на звонок.

    speak(text, tag) отправляет фразу отдельным сегментом; звук приходит в on_audio(tag, pcm, rate) —
    PCM16 mono без заголовков, конец фразы — в on_segment_done(tag). tag помогает отбросить хвост
    перебитого ответа."""

    def __init__(self, settings: dict, voice: str, model: str, on_audio, on_segment_done, speed: float = 1.0,
                 language: str = "ru", on_usage=None):
        self.s = settings
        self.voice = voice
        self.language = language or "ru"
        self.on_usage = on_usage  # credits (units) of each finished phrase
        self.model = model or DEFAULT_MODEL
        self.speed = speed
        self.on_audio = on_audio
        self.on_segment_done = on_segment_done
        self.mp = _msgpack()
        self.ws = None
        self.http: aiohttp.ClientSession | None = None
        self.ready = asyncio.Event()
        self.closed = False
        self.error = ""
        self._seq = 0
        self._n = 0
        self._tags: dict[str, str] = {}
        self._wav: dict[str, dict] = {}   # сегмент → {"head": bytearray до конца заголовка, "rate", "odd"}
        self._reader: asyncio.Task | None = None
        self._connecting: asyncio.Task | None = None
        self._restarting = False
        self._backoff = 0.0

    def start(self):
        """Подключиться в фоне (1–2 с), не блокируя начало звонка."""
        if not self._connecting or self._connecting.done():
            self.ready.clear()
            self._connecting = asyncio.create_task(self._connect())

    async def _connect(self, delay: float = 0.0):
        if delay:
            await asyncio.sleep(delay)
        try:
            if self.http is None:
                self.http = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=None, connect=15))
            self.ws = await self.http.ws_connect(self.s.get("fish.ws_url") or DEFAULT_WS_URL,
                                                 protocols=(SUBPROTOCOL,), headers=_auth(self.s),
                                                 heartbeat=20.0, max_msg_size=0)
            self._seq = 0  # sequence нумеруется заново в каждой сессии
            request = {"voiceId": self.voice, "modelId": self.model, "format": "wav", "language": self.language,
                       "latency": "balanced"}
            if abs(self.speed - 1.0) > 0.001:
                request["speed"] = round(self.speed, 2)
            await self._send({"event": "start", "mode": "reliable", "eventId": _eid(),
                              "requestId": "req_" + uuid.uuid4().hex, "request": request})
            self._reader = asyncio.create_task(self._read())
        except Exception as e:
            self.error = f"Fish Audio: не удалось подключиться: {e}"
            log.error(self.error)
            self._schedule_reconnect()

    async def _send(self, msg: dict):
        await self.ws.send_bytes(self.mp.packb(msg))

    async def _read(self):
        try:
            async for msg in self.ws:
                if msg.type != aiohttp.WSMsgType.BINARY:
                    continue
                ev = self.mp.unpackb(msg.data, raw=False)
                name = ev.get("event")
                if name == "audio":
                    seg = ev.get("segmentId")
                    tag = self._tags.get(seg)
                    if tag is not None:
                        self._audio(seg, tag, ev.get("audio") or b"")
                elif name == "segment_completed":
                    if self.on_usage and ev.get("units"):
                        self.on_usage(ev["units"])
                    self._wav.pop(ev.get("segmentId"), None)
                    tag = self._tags.pop(ev.get("segmentId"), None)
                    if tag is not None:
                        self.on_segment_done(tag)
                elif name == "ready":
                    self.error = ""
                    self._backoff = 0.0
                    self.ready.set()
                    log.info("fish session ready (%s, %s)", self.voice, self.model)
                elif name == "error":
                    log.error("fish error: %s %s", ev.get("code"), ev.get("message"))
                    if ev.get("terminal"):
                        self.error = f"Fish Audio: {ev.get('code')}: {ev.get('message')}"
                        break
                elif name == "finish":
                    break
        except Exception as e:  # noqa: BLE001
            log.warning("fish session dropped: %s", e)
        finally:
            self.ready.clear()
            # незавершённые фразы больше не придут — отпускаем ожидающих
            for seg, tag in list(self._tags.items()):
                self._tags.pop(seg, None)
                self.on_segment_done(tag)
            if not self.closed and not self._restarting:
                self._schedule_reconnect()

    def _audio(self, seg: str, tag, data: bytes):
        """Каждая фраза — отдельный WAV-поток: срезать заголовок, выровнять PCM по 2 байта."""
        st = self._wav.setdefault(seg, {"head": bytearray(), "rate": 0, "odd": b""})
        if not st["rate"]:
            st["head"].extend(data)
            parsed = parse_wav(bytes(st["head"]))
            if not parsed:
                return
            data, st["rate"] = parsed
            st["head"] = bytearray()
        data = st["odd"] + data
        cut = len(data) - len(data) % 2
        st["odd"] = data[cut:]
        if cut:
            self.on_audio(tag, data[:cut], st["rate"])

    def _schedule_reconnect(self):
        if self.closed or self._restarting:
            return
        # permission_denied (лимит — одно соединение на ключ) и сетевые сбои: не долбим сервер
        self._backoff = min(10.0, self._backoff * 2 or 1.0)
        log.info("fish reconnect in %.0f s", self._backoff)
        self._connecting = asyncio.create_task(self._connect(self._backoff))

    async def restart(self):
        """Бросить незавершённые фразы (их нельзя отменить внутри сессии) и переподключиться."""
        self._restarting = True
        try:
            self.ready.clear()
            if self._reader and not self._reader.done():
                self._reader.cancel()
            if self.ws is not None and not self.ws.closed:
                await self.ws.close()
            for seg, tag in list(self._tags.items()):
                self._tags.pop(seg, None)
                self.on_segment_done(tag)
            self._wav.clear()
        finally:
            self._restarting = False
        self._backoff = 0.0
        self.start()

    async def speak(self, text: str, tag: str) -> bool:
        text = text.strip()
        if not text:
            return False
        if not self.ready.is_set():
            if self.error:  # подключение уже не удалось (лимит, ключ, сеть) — не заставляем абонента ждать
                raise FishError(self.error)
            self.start()
            try:
                await asyncio.wait_for(self.ready.wait(), 8)
            except asyncio.TimeoutError:
                self.error = self.error or "Fish Audio: нет ответа от сервера"
        if not self.ready.is_set():
            raise FishError(self.error or "Fish Audio недоступен")
        self._n += 1
        seg = f"s{self._n}"
        self._tags[seg] = tag
        for i in range(0, len(text), 1900):  # лимит 2000 символов на кадр
            self._seq += 1
            await self._send({"event": "text", "eventId": _eid(), "sequence": self._seq, "text": text[i:i + 1900]})
        await self._send({"event": "flush", "eventId": _eid(), "segmentId": seg})
        return True

    @property
    def pending(self) -> int:
        return len(self._tags)

    async def close(self):
        """Штатно завершить сессию: stop → дождаться finish → закрыть.

        Kitta иногда не освобождает слот (одно соединение на ключ) после резкого обрыва — ключ может
        оставаться заблокированным больше часа, поэтому закрываемся как можно аккуратнее."""
        self.closed = True
        if self._connecting and not self._connecting.done():
            self._connecting.cancel()
        try:
            if self.ws is not None and not self.ws.closed:
                await self._send({"event": "stop", "eventId": _eid()})
                if self._reader and not self._reader.done():
                    await asyncio.wait_for(asyncio.shield(self._reader), 2)  # читатель выходит на finish
        except Exception:  # noqa: BLE001
            pass
        finally:
            if self._reader and not self._reader.done():
                self._reader.cancel()
            try:
                if self.ws is not None and not self.ws.closed:
                    await self.ws.close()
            except Exception:  # noqa: BLE001
                pass
            if self.http:
                await self.http.close()


# ---------------------------------------------------------------- REST: синтез, голоса

async def synthesize(settings: dict, voice: str, text: str, model: str = "", speed: float = 1.0,
                     language: str = "ru", kind: str = "voice_test") -> bytes:
    """Синхронный синтез (заготовки, «прослушать» в интерфейсе); возвращает WAV 44.1 кГц."""
    payload = {"text": text, "voiceId": voice, "modelId": model or DEFAULT_MODEL, "format": "wav",
               "language": language or "ru"}
    if abs(speed - 1.0) > 0.001:
        payload["speed"] = round(speed, 2)
    url = (settings.get("fish.api_url") or DEFAULT_API_URL) + "/v3/speech/tts"
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as http:
        async with http.post(url, headers=_auth(settings), json=payload) as r:
            if r.status != 200:
                raise FishError(f"Fish Audio: {r.status} {(await r.text())[:200]}")
            data = await r.read()
            try:
                credits = float(r.headers.get("X-OpenAPI-Credits-Used") or 0)
            except ValueError:
                credits = 0
            db.log_usage("fish", kind, credits=credits, chars=len(text))
            return data


async def list_voices(settings: dict, search: str = "", language: str = "ru") -> list[dict]:
    params = {"page": 1, "pageSize": 100, "includePersonal": "true"}
    if language:
        params["language"] = language
    if search:
        params["search"] = search
    url = (settings.get("fish.api_url") or DEFAULT_API_URL) + "/v3/voices"
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as http:
        async with http.get(url, headers=_auth(settings), params=params) as r:
            if r.status != 200:
                raise FishError(f"Fish Audio: {r.status} {(await r.text())[:200]}")
            data = await r.json()
    return [{"id": v["voiceId"], "name": v.get("name", ""), "description": v.get("description", ""),
             "personal": v.get("isPersonal", False), "language": v.get("primaryLanguage") or ""}
            for v in data.get("items", []) if DEFAULT_MODEL in (v.get("modelIds") or [])]
