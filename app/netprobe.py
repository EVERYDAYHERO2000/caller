"""Connection to the providers (Yandex AI Studio, Kitta / Fish Audio) — for the «Провайдеры» dashboard.

Every minute each host is probed: ICMP ping, DNS, TCP connect, TLS handshake and an HTTP response; the last day
is kept for the charts. For hosts behind Cloudflare /cdn-cgi/trace tells which exit the traffic takes (IP,
country, Cloudflare node) — whether the VPN is in the path. Probes cost nothing: no sessions, no synthesis.

On request: a Yandex Realtime handshake (WebSocket until session.created, no tokens) and a Kitta stream test
(two short phrases through the realtime connection — a couple of credits, holds the single Kitta connection for
a few seconds, so never during a call).
"""
import asyncio
import logging
import re
import ssl
import sys
import time
from collections import deque
from urllib.parse import urlparse

import aiohttp

from . import db

log = logging.getLogger("netprobe")

PERIOD = 60          # s between probes
HISTORY = 24 * 60    # one day of minutes
TIMEOUT = 8


def targets(s: dict | None = None) -> list[dict]:
    s = s or db.get_settings()
    yws = urlparse(s.get("yandex.ws_url") or "wss://ai.api.cloud.yandex.net/v1/realtime")
    fws = urlparse(s.get("fish.ws_url") or "wss://realtime.fishaudio.org/v3/tts/live")
    fapi = urlparse(s.get("fish.api_url") or "https://fishaudio.org/api/open")
    return [
        {"id": "yandex", "provider": "Yandex AI Studio", "name": "Realtime API и суммаризация", "host": yws.hostname,
         "path": "/", "trace": False},
        {"id": "kitta_rt", "provider": "Kitta · Fish Audio", "name": "Realtime-синтез (WebSocket)", "host": fws.hostname,
         "path": "/cdn-cgi/trace", "trace": True},
        # fishaudio.org is on Vercel, not Cloudflare: no trace — the API itself (401 without a key is enough)
        {"id": "kitta_api", "provider": "Kitta · Fish Audio", "name": "HTTP API (хезитации, приветствия, голоса)",
         "host": fapi.hostname, "path": (fapi.path.rstrip("/") or "") + "/v1/profile", "trace": False},
    ]


async def _ping(ip: str) -> dict:
    """ICMP: 3 packets. Linux and macOS print «min/avg/max/…» the same way."""
    args = ["ping", "-c", "3", "-i", "0.3", "-W", "1" if sys.platform.startswith("linux") else "1000", ip]
    try:
        proc = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        out, _ = await asyncio.wait_for(proc.communicate(), 6)
    except (OSError, asyncio.TimeoutError):
        return {}
    text = out.decode(errors="replace")
    loss = re.search(r"([\d.]+)% packet loss", text)
    rtt = re.search(r"= [\d.]+/([\d.]+)/([\d.]+)/", text)
    return {"ping_ms": round(float(rtt.group(1)), 1) if rtt else None,
            "ping_max_ms": round(float(rtt.group(2)), 1) if rtt else None,
            "loss_pct": float(loss.group(1)) if loss else None}


async def probe(t: dict) -> dict:
    """One measurement of a host. Times in ms; None where a step failed (error says which)."""
    host, loop = t["host"], asyncio.get_running_loop()
    r = {"t": int(time.time()), "ok": False, "error": ""}
    try:
        t0 = loop.time()
        infos = await asyncio.wait_for(loop.getaddrinfo(host, 443, type=1), TIMEOUT)
        r["dns_ms"] = round((loop.time() - t0) * 1000, 1)
        ips = list(dict.fromkeys(i[4][0] for i in infos if ":" not in i[4][0])) or [infos[0][4][0]]
        r["ips"] = ips
        ping = asyncio.create_task(_ping(ips[0]))

        t0 = loop.time()
        _, w = await asyncio.wait_for(asyncio.open_connection(ips[0], 443), TIMEOUT)
        r["tcp_ms"] = round((loop.time() - t0) * 1000, 1)
        w.close()

        t0 = loop.time()
        _, w = await asyncio.wait_for(asyncio.open_connection(ips[0], 443, ssl=ssl.create_default_context(),
                                                              server_hostname=host), TIMEOUT)
        r["tls_ms"] = round(max(0.0, (loop.time() - t0) * 1000 - r["tcp_ms"]), 1)
        w.close()

        t0 = loop.time()
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=TIMEOUT)) as http:
            async with http.get(f"https://{host}{t['path']}", allow_redirects=False) as resp:
                r["http_status"] = resp.status
                body = await resp.text(errors="replace") if t["trace"] else ""
        r["http_ms"] = round((loop.time() - t0) * 1000, 1)
        if t["trace"] and resp.status == 200:
            kv = dict(line.split("=", 1) for line in body.splitlines() if "=" in line)
            r["exit"] = {"ip": kv.get("ip"), "loc": kv.get("loc"), "colo": kv.get("colo")}
        r.update(await ping)
        r["ok"] = True
    except asyncio.TimeoutError:
        r["error"] = "нет ответа за %s с" % TIMEOUT
    except Exception as e:  # noqa: BLE001
        r["error"] = str(e) or type(e).__name__
    return r


class Monitor:
    def __init__(self):
        self.history: dict[str, deque] = {}
        self.last: dict[str, dict] = {}
        self._task: asyncio.Task | None = None
        self._lock = asyncio.Lock()

    def start(self):
        self._task = asyncio.create_task(self._loop())

    async def stop(self):
        if self._task:
            self._task.cancel()

    async def check(self) -> None:
        async with self._lock:
            ts = targets()
            results = await asyncio.gather(*(probe(t) for t in ts))
            for t, r in zip(ts, results):
                self.last[t["id"]] = r
                self.history.setdefault(t["id"], deque(maxlen=HISTORY)).append(
                    {k: r.get(k) for k in ("t", "ok", "ping_ms", "tcp_ms", "tls_ms", "http_ms")})

    async def _loop(self):
        await asyncio.sleep(5)  # let the service start first
        while True:
            try:
                await self.check()
            except Exception as e:  # noqa: BLE001
                log.debug("provider probe failed: %s", e)
            await asyncio.sleep(PERIOD)

    def snapshot(self, hours: float = 1) -> list[dict]:
        since = time.time() - hours * 3600
        out = []
        for t in targets():
            h = [p for p in self.history.get(t["id"], []) if p["t"] >= since]
            day = list(self.history.get(t["id"], []))
            fails = sum(1 for p in day if not p["ok"])
            out.append({**t, "last": self.last.get(t["id"]), "history": h,
                        "day": {"probes": len(day), "failed": fails}})
        return out


monitor = Monitor()


# ---------------------------------------------------------------- on request

async def yandex_handshake(s: dict) -> dict:
    """Realtime WebSocket until session.created — how long the start of a call's session takes (no tokens)."""
    if not s.get("yandex.api_key") or not s.get("yandex.folder_id"):
        return {"ok": False, "error": "не заданы ключ и каталог Yandex AI Studio"}
    from .agent.realtime import AgentSession
    probe_ = AgentSession.__new__(AgentSession)
    probe_.s, probe_.agent = s, {}
    loop = asyncio.get_running_loop()
    t0 = loop.time()
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as http:
            async with http.ws_connect(probe_._url(), headers=probe_._headers()) as ws:
                connected = loop.time()
                async for msg in ws:
                    if msg.type != aiohttp.WSMsgType.TEXT:
                        break
                    if '"session.created"' in msg.data:
                        return {"ok": True, "connect_ms": round((connected - t0) * 1000),
                                "session_ms": round((loop.time() - t0) * 1000)}
                    if '"error"' in msg.data:
                        return {"ok": False, "error": msg.data[:200]}
        return {"ok": False, "error": "сессия не создана"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e) or type(e).__name__}


STREAM_PHRASES = ["Расскажи, пожалуйста, по какому вопросу ты звонишь?", "Хорошо, я всё записала."]


async def kitta_stream_test(s: dict, voice: str, model: str = "", language: str = "ru") -> dict:
    """Two phrases through the Kitta realtime connection: time to the first sound and how fast the audio comes
    (×1 = as fast as it plays; below 1 the voice stutters in a call). Closed gracefully (stop → finish)."""
    from .agent import fish
    loop = asyncio.get_running_loop()
    st: dict[str, dict] = {}

    def on_audio(tag, pcm, rate):
        p = st[tag]
        if p["first"] is None:
            p["first"] = loop.time()
        p["audio"] += len(pcm) / 2 / rate

    def on_done(tag):
        st[tag]["done"] = loop.time()

    t0 = loop.time()
    tts = fish.FishTTS(s, voice, model, on_audio, on_done, language=language)
    phrases = []
    try:
        tts.start()
        await asyncio.wait_for(tts.ready.wait(), 15)
        ready_ms = round((loop.time() - t0) * 1000)
        for i, text in enumerate(STREAM_PHRASES):
            tag = f"p{i}"
            st[tag] = {"sent": loop.time(), "first": None, "audio": 0.0, "done": None}
            await tts.speak(text, tag)
            end = loop.time() + 40
            while st[tag]["done"] is None and loop.time() < end:
                await asyncio.sleep(0.02)
            p = st[tag]
            if p["first"] is None or p["done"] is None:
                phrases.append({"text": text, "error": "звук не пришёл за 40 с"})
                break
            took = max(p["done"] - p["first"], 0.01)
            phrases.append({"text": text, "first_ms": round((p["first"] - p["sent"]) * 1000),
                            "audio_s": round(p["audio"], 2), "stream_s": round(took, 2),
                            "speed": round(p["audio"] / took, 1)})
        return {"ok": all("error" not in p for p in phrases), "ready_ms": ready_ms, "phrases": phrases}
    except asyncio.TimeoutError:
        return {"ok": False, "error": tts.error or "Kitta не ответила за 15 с", "phrases": phrases}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e) or type(e).__name__, "phrases": phrases}
    finally:
        await tts.close()
