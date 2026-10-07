"""Демостенд Fish Audio (Kitta, fishaudio.org): скорость генерации и стриминг голоса.

Браузер <-> этот сервер (JSON + бинарные mp3-чанки) <-> wss://realtime.fishaudio.org (MessagePack).
API-ключ остаётся на сервере и в браузер не попадает.

Запуск:  ../.venv/bin/python server.py   ->  http://localhost:8765
"""

import asyncio
import json
import os
import time
import uuid
from pathlib import Path

import aiohttp
import msgpack
import uvicorn
import websockets
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

HERE = Path(__file__).parent
REST = "https://fishaudio.org/api/open"
RT_WS = "wss://realtime.fishaudio.org/v3/tts/live"
RT_HTTP = "https://realtime.fishaudio.org/v3/tts"
SUBPROTOCOL = "realtime.tts.msgpack.v3"
PORT = int(os.environ.get("PORT", 8765))


def load_key() -> str:
    env = HERE / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("FISH_API_KEY="):
                os.environ.setdefault("FISH_API_KEY", line.split("=", 1)[1].strip())
    key = os.environ.get("FISH_API_KEY")
    if not key:
        raise SystemExit("FISH_API_KEY не задан (fish_demo/.env)")
    return key


API_KEY = load_key()
AUTH = {"Authorization": f"Bearer {API_KEY}"}

app = FastAPI()
http: aiohttp.ClientSession | None = None


@app.on_event("startup")
async def _startup():
    global http
    http = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=120))


@app.on_event("shutdown")
async def _shutdown():
    await http.close()


def eid() -> str:
    return "evt_" + uuid.uuid4().hex


# ---------------------------------------------------------------- REST helpers


@app.get("/api/profile")
async def profile():
    async with http.get(f"{REST}/v1/profile", headers=AUTH) as r:
        return JSONResponse(await r.json(), status_code=r.status)


@app.get("/api/capabilities")
async def capabilities():
    async with http.get(f"{RT_HTTP}/capabilities", headers=AUTH) as r:
        return JSONResponse(await r.json(), status_code=r.status)


@app.get("/api/voices")
async def voices(search: str = "", page: int = 1):
    # language — недокументированный, но рабочий фильтр
    params = {"page": page, "pageSize": 100, "includePersonal": "true", "language": "ru"}
    if search:
        params["search"] = search
    async with http.get(f"{REST}/v3/voices", headers=AUTH, params=params) as r:
        return JSONResponse(await r.json(), status_code=r.status)


@app.post("/api/http-tts")
async def http_tts(req: Request):
    """Обычный синхронный HTTP-синтез — для сравнения со стримингом."""
    body = await req.json()
    payload = {
        "text": body["text"],
        "voiceId": body["voiceId"],
        "modelId": body.get("modelId", "fishaudio-s21pro-flash"),
        "format": "mp3",
        "language": "ru",
    }
    t0 = time.perf_counter()
    async with http.post(f"{REST}/v3/speech/tts", headers=AUTH, json=payload) as r:
        ttfb = (time.perf_counter() - t0) * 1000
        data = await r.read()
        total = (time.perf_counter() - t0) * 1000
        if r.status != 200:
            return Response(data, status_code=r.status, media_type=r.content_type)
        return Response(
            data,
            media_type="audio/mpeg",
            headers={
                "X-Ttfb-Ms": f"{ttfb:.0f}",
                "X-Total-Ms": f"{total:.0f}",
                "X-Credits-Used": r.headers.get("X-OpenAPI-Credits-Used", ""),
                "X-Quota-Remaining": r.headers.get("X-OpenAPI-Quota-Remaining", ""),
            },
        )


# ---------------------------------------------------------------- заготовки хезитаций

FILLERS = [
    # (id, текст, вид) — короткие маскируют ~0.5 с, длинные почти всю паузу
    ("mmm", "Ммм...", "short"),
    ("tak", "Так...", "short"),
    ("ugu", "Угу.", "short"),
    ("nu", "Ну...", "short"),
    ("hm", "Хм...", "short"),
    ("eee", "Эээ...", "short"),
    ("taktak", "Так-так...", "short"),
    ("sekundochku", "Секундочку...", "long"),
    ("posmotryu", "Сейчас посмотрю.", "long"),
    ("podumat", "Так, дайте подумать...", "long"),
    ("minutku", "Минутку, уточняю.", "long"),
    ("odnu_sek", "Сейчас, одну секунду.", "long"),
]
FILLER_DIR = HERE / "static" / "fillers"


def filler_manifest(voice_id: str) -> Path:
    return FILLER_DIR / voice_id / "manifest.json"


@app.get("/api/fillers")
async def fillers(voiceId: str):
    m = filler_manifest(voiceId)
    items = json.loads(m.read_text()) if m.exists() else []
    cost = sum(len(t) for _, t, _ in FILLERS)
    return {"items": items, "estimate": cost}


@app.post("/api/fillers/generate")
async def fillers_generate(req: Request):
    """Синтезирует все заготовки выбранным голосом за одну reliable-сессию (сегмент на заготовку)."""
    body = await req.json()
    voice_id = body["voiceId"]
    out = FILLER_DIR / voice_id
    out.mkdir(parents=True, exist_ok=True)
    audio: dict[str, bytearray] = {fid: bytearray() for fid, _, _ in FILLERS}
    units = 0
    errors = []
    async with websockets.connect(RT_WS, subprotocols=[SUBPROTOCOL], additional_headers=AUTH, max_size=None) as ws:
        await ws.send(msgpack.packb({
            "event": "start", "mode": "reliable", "eventId": eid(), "requestId": "req_" + uuid.uuid4().hex,
            "request": {"voiceId": voice_id, "modelId": "fishaudio-s21pro-flash", "format": "mp3",
                        "language": "ru", "latency": "normal"},
        }))
        async for raw in ws:
            ev = msgpack.unpackb(raw, raw=False)
            name = ev.get("event")
            if name == "ready":
                for seq, (fid, text, _) in enumerate(FILLERS, 1):
                    await ws.send(msgpack.packb({"event": "text", "eventId": eid(), "sequence": seq, "text": text}))
                    await ws.send(msgpack.packb({"event": "flush", "eventId": eid(), "segmentId": fid}))
                await ws.send(msgpack.packb({"event": "stop", "eventId": eid()}))
            elif name == "audio":
                audio[ev["segmentId"]] += ev.get("audio") or b""
            elif name == "segment_completed":
                units += ev.get("units") or 0
            elif name == "error":
                errors.append(f"{ev.get('code')}: {ev.get('message')}")
                if ev.get("terminal"):
                    break
            elif name == "finish":
                break
    items = []
    for fid, text, kind in FILLERS:
        if not audio[fid]:
            continue
        (out / f"{fid}.mp3").write_bytes(audio[fid])
        items.append({"id": fid, "text": text, "kind": kind, "url": f"/static/fillers/{voice_id}/{fid}.mp3"})
    filler_manifest(voice_id).write_text(json.dumps(items, ensure_ascii=False, indent=1))
    return {"items": items, "units": units, "errors": errors}


# ---------------------------------------------------------------- realtime proxy


class Session:
    """Одна upstream-сессия Realtime TTS v3 в режиме reliable (много сегментов на сессию)."""

    def __init__(self, client: WebSocket, send_lock: asyncio.Lock):
        self.client = client
        self.lock = send_lock
        self.ws = None
        self.reader: asyncio.Task | None = None
        self.t0 = time.perf_counter()
        self.seq = 0
        self.seg_n = 0
        self.flush_at: dict[str, float] = {}
        self.first_audio: set[str] = set()
        self.params: dict = {}
        self.alive = False

    def ms(self) -> int:
        return round((time.perf_counter() - self.t0) * 1000)

    async def emit(self, event: str, **fields):
        async with self.lock:
            await self.client.send_text(json.dumps({"type": "event", "event": event, "t": self.ms(), **fields}))

    async def open(self, params: dict):
        self.params = params
        self.t0 = time.perf_counter()
        self.ws = await websockets.connect(
            RT_WS, subprotocols=[SUBPROTOCOL], additional_headers=AUTH, max_size=None, open_timeout=15
        )
        self.alive = True
        await self.emit("upstream_connected")
        request = {
            "voiceId": params["voiceId"],
            "modelId": params.get("modelId", "fishaudio-s21pro-flash"),
            "format": "mp3",
            "language": "ru",
            "latency": params.get("latency", "balanced"),
        }
        if params.get("chunkLength"):
            request["chunkLength"] = int(params["chunkLength"])
        if params.get("speed"):
            request["speed"] = float(params["speed"])
        await self.send_up(
            {"event": "start", "mode": "reliable", "eventId": eid(), "requestId": "req_" + uuid.uuid4().hex,
             "request": request}
        )
        self.reader = asyncio.create_task(self.read_loop())

    async def send_up(self, msg: dict):
        await self.ws.send(msgpack.packb(msg))

    async def text(self, text: str):
        self.seq += 1
        await self.send_up({"event": "text", "eventId": eid(), "sequence": self.seq, "text": text})

    async def flush(self) -> str:
        self.seg_n += 1
        seg = f"seg{self.seg_n}"
        self.flush_at[seg] = time.perf_counter()
        await self.send_up({"event": "flush", "eventId": eid(), "segmentId": seg})
        await self.emit("flush_sent", segmentId=seg)
        return seg

    async def stop(self):
        await self.send_up({"event": "stop", "eventId": eid()})

    async def read_loop(self):
        try:
            async for raw in self.ws:
                ev = msgpack.unpackb(raw, raw=False)
                name = ev.get("event")
                if name == "audio":
                    seg = ev.get("segmentId")
                    audio = ev.get("audio") or b""
                    extra = {}
                    if seg not in self.first_audio:
                        self.first_audio.add(seg)
                        if seg in self.flush_at:
                            extra["segTtfa"] = round((time.perf_counter() - self.flush_at[seg]) * 1000)
                    async with self.lock:
                        await self.client.send_text(json.dumps(
                            {"type": "event", "event": "audio", "t": self.ms(), "segmentId": seg,
                             "bytes": len(audio), **extra}))
                        await self.client.send_bytes(audio)
                    continue
                keep = {k: ev[k] for k in (
                    "segmentId", "characters", "units", "sessionUnits", "quotaRemaining", "audioBytes",
                    "reason", "code", "message", "retryable", "terminal", "effectiveRequest", "quota",
                ) if k in ev}
                await self.emit(name, **keep)
                if name == "finish" or (name == "error" and ev.get("terminal")):
                    break
        except websockets.ConnectionClosed as e:
            await self.safe_emit("upstream_closed", code=e.code, reason=str(e.reason))
        except Exception as e:  # noqa: BLE001
            await self.safe_emit("error", code="proxy_error", message=repr(e), terminal=True)
        finally:
            self.alive = False
            await self.safe_emit("session_closed")
            try:
                await self.ws.close()
            except Exception:  # noqa: BLE001
                pass

    async def safe_emit(self, event, **fields):
        try:
            await self.emit(event, **fields)
        except Exception:  # noqa: BLE001
            pass

    async def close(self):
        if self.reader and not self.reader.done():
            self.reader.cancel()
        if self.ws:
            await self.ws.close()
        self.alive = False


@app.websocket("/ws/tts")
async def ws_tts(client: WebSocket):
    await client.accept()
    lock = asyncio.Lock()
    session: Session | None = None
    try:
        while True:
            msg = json.loads(await client.receive_text())
            kind = msg.get("type")
            try:
                if kind == "connect":
                    if session:
                        await session.close()
                    session = Session(client, lock)
                    await session.open(msg)
                elif kind == "text" and session and session.alive:
                    await session.text(msg["text"])
                elif kind == "flush" and session and session.alive:
                    await session.flush()
                elif kind == "stop" and session and session.alive:
                    await session.stop()
                elif kind == "close" and session:
                    await session.close()
                    session = None
                elif kind in ("text", "flush", "stop"):
                    async with lock:
                        await client.send_text(json.dumps(
                            {"type": "event", "event": "error", "code": "no_session",
                             "message": "Нет активной сессии", "terminal": True}))
            except Exception as e:  # noqa: BLE001
                async with lock:
                    await client.send_text(json.dumps(
                        {"type": "event", "event": "error", "code": "proxy_error", "message": repr(e),
                         "terminal": True}))
    except WebSocketDisconnect:
        pass
    finally:
        if session:
            await session.close()


@app.get("/")
async def index():
    return FileResponse(HERE / "static" / "index.html")


app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=PORT)
