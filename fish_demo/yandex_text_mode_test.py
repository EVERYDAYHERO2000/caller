"""Проверка: может ли Yandex Realtime API отвечать только текстом (для озвучки через Fish Audio).

Ключи: переменные окружения YANDEX_API_KEY и YANDEX_FOLDER_ID или строки в fish_demo/.env.
Запуск:  .venv/bin/python fish_demo/yandex_text_mode_test.py

Тесты:
  1. text→text   session.update с output_modalities=["text"], вопрос текстом
  2. voice→text  та же сессия, но вопрос голосом (server VAD + распознавание), как в звонке
  3. override    сессия в режиме audio, текст запрошен только в response.create
"""

import asyncio
import json
import os
import subprocess
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

import aiohttp

HERE = Path(__file__).parent
RATE = 16000
MODEL = "speech-realtime-250923"
QUESTION = "До скольки вы сегодня работаете?"
INSTRUCTIONS = ("Ты вежливый оператор салона красоты «Лотос». Отвечай коротко, одним-двумя предложениями. "
                "Сегодня салон работает до девяти вечера.")


def load_env():
    env = HERE / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
    key, folder = os.environ.get("YANDEX_API_KEY"), os.environ.get("YANDEX_FOLDER_ID")
    if not key or not folder:
        sys.exit("Нужны YANDEX_API_KEY и YANDEX_FOLDER_ID (env или fish_demo/.env)")
    return key, folder


def question_pcm() -> bytes:
    """Фраза «абонента» голосом macOS Milena -> PCM16 mono 16 кГц."""
    with tempfile.TemporaryDirectory() as d:
        aiff, raw = Path(d) / "q.aiff", Path(d) / "q.raw"
        subprocess.run(["say", "-v", "Milena", "-o", str(aiff), QUESTION], check=True)
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(aiff), "-ac", "1", "-ar", str(RATE),
                        "-f", "s16le", str(raw)], check=True)
        return raw.read_bytes()


def session_update(modalities: list[str]) -> dict:
    session = {
        "instructions": INSTRUCTIONS,
        "output_modalities": modalities,
        "audio": {
            "input": {
                "format": {"type": "audio/pcm", "rate": RATE},
                "turn_detection": {"type": "server_vad", "threshold": 0.5, "silence_duration_ms": 500},
            },
        },
    }
    if "audio" in modalities:
        session["audio"]["output"] = {"format": {"type": "audio/pcm", "rate": RATE}, "voice": "dasha"}
    return {"type": "session.update", "session": session}


class Probe:
    def __init__(self, name: str):
        self.name = name
        self.t0 = time.perf_counter()
        self.counts = Counter()
        self.marks: dict[str, float] = {}
        self.text = ""
        self.transcript = ""
        self.audio_bytes = 0
        self.errors = []
        self.session = None

    def ms(self) -> int:
        return round((time.perf_counter() - self.t0) * 1000)

    def mark(self, k: str):
        self.marks.setdefault(k, self.ms())

    def handle(self, ev: dict) -> bool:
        """Возвращает True, когда ответ завершён."""
        t = ev.get("type", "")
        self.counts[t] += 1
        if self.counts[t] == 1 and "delta" not in t:
            print(f"  [{self.ms():5}] {t}")
        if t in ("session.updated", "session.created"):
            self.session = ev.get("session")
        elif t == "error":
            self.errors.append(ev.get("error") or ev)
            print(f"  [{self.ms():5}] ERROR {json.dumps(ev, ensure_ascii=False)[:400]}")
        elif t == "input_audio_buffer.speech_stopped":
            self.mark("speech_stopped")
        elif t == "conversation.item.input_audio_transcription.completed":
            self.transcript = ev.get("transcript", "")
            self.mark("transcript")
        elif t in ("response.output_text.delta", "response.text.delta"):
            self.mark("first_text")
            self.text += ev.get("delta", "")
        elif t in ("response.output_audio_transcript.delta", "response.audio_transcript.delta"):
            self.mark("first_transcript_delta")
            self.text += ev.get("delta", "")
        elif t in ("response.output_audio.delta", "response.audio.delta"):
            self.mark("first_audio")
            self.audio_bytes += len(ev.get("delta", "")) * 3 // 4
        elif t == "response.created":
            self.mark("response_created")
        elif t == "response.done":
            self.mark("done")
            return True
        return False

    def report(self, start_key: str):
        start = self.marks.get(start_key)
        rel = lambda k: (f"{self.marks[k] - start} мс" if k in self.marks and start is not None else "—")
        print(f"\n  == {self.name}")
        if self.session is not None:
            print(f"  session.output_modalities = {self.session.get('output_modalities', self.session.get('modalities'))}")
        if self.transcript:
            print(f"  распознано: «{self.transcript}»")
        print(f"  ответ: «{self.text.strip()}»")
        print(f"  аудио в ответе: {self.audio_bytes} байт ({self.counts['response.output_audio.delta'] + self.counts['response.audio.delta']} delta)")
        print(f"  от {start_key}: первый текст {rel('first_text')}, первый транскрипт {rel('first_transcript_delta')}, "
              f"первое аудио {rel('first_audio')}, готово {rel('done')}")
        print(f"  события: {dict(self.counts)}")
        return {
            "text_only": self.audio_bytes == 0 and bool(self.text.strip()),
            "first_text_ms": (self.marks["first_text"] - start) if "first_text" in self.marks and start is not None else None,
        }


async def recv_until_done(ws, p: Probe, timeout=30):
    async def loop():
        async for msg in ws:
            if msg.type != aiohttp.WSMsgType.TEXT:
                continue
            if p.handle(json.loads(msg.data)):
                return
    await asyncio.wait_for(loop(), timeout)


async def wait_for(ws, p: Probe, types: set[str], timeout=10):
    async def loop():
        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                ev = json.loads(msg.data)
                p.handle(ev)
                if ev.get("type") in types:
                    return ev
    return await asyncio.wait_for(loop(), timeout)


async def main():
    key, folder = load_env()
    url = f"wss://ai.api.cloud.yandex.net/v1/realtime?model=gpt://{folder}/{MODEL}"
    headers = {"Authorization": f"Bearer {key}" if key.startswith("t1.") else f"Api-Key {key}"}
    pcm = question_pcm()
    print(f"вопрос «{QUESTION}» — {len(pcm) / 2 / RATE:.1f} с аудио")
    results = {}

    async with aiohttp.ClientSession() as http:
        # 1 + 2: сессия в режиме text
        async with http.ws_connect(url, headers=headers, max_msg_size=0) as ws:
            print("\n### 1. text→text")
            p = Probe("text→text")
            await ws.send_json(session_update(["text"]))
            await wait_for(ws, p, {"session.updated", "error"})
            p.t0 = time.perf_counter()
            p.mark("sent")
            await ws.send_json({"type": "conversation.item.create", "item": {
                "type": "message", "role": "user", "content": [{"type": "input_text", "text": QUESTION}]}})
            await ws.send_json({"type": "response.create"})
            await recv_until_done(ws, p)
            results["text→text"] = p.report("sent")

            print("\n### 2. voice→text (как в звонке)")
            p = Probe("voice→text")
            frame = RATE * 2 // 50  # 20 мс
            audio = pcm + b"\x00" * (RATE * 2 * 2)  # + 2 с тишины, чтобы сработал VAD

            async def uplink():
                for i in range(0, len(audio), frame):
                    await ws.send_json({"type": "input_audio_buffer.append",
                                        "audio": __import__("base64").b64encode(audio[i:i + frame]).decode()})
                    await asyncio.sleep(0.02)

            up = asyncio.create_task(uplink())
            await recv_until_done(ws, p, timeout=40)
            up.cancel()
            results["voice→text"] = p.report("speech_stopped")

        # 3: сессия audio, текст только в конкретном ответе
        async with http.ws_connect(url, headers=headers, max_msg_size=0) as ws:
            print("\n### 3. override: сессия audio, response.create с output_modalities=[text]")
            p = Probe("override")
            await ws.send_json(session_update(["audio"]))
            await wait_for(ws, p, {"session.updated", "error"})
            p.t0 = time.perf_counter()
            p.mark("sent")
            await ws.send_json({"type": "conversation.item.create", "item": {
                "type": "message", "role": "user", "content": [{"type": "input_text", "text": QUESTION}]}})
            await ws.send_json({"type": "response.create", "response": {"output_modalities": ["text"]}})
            await recv_until_done(ws, p)
            results["override"] = p.report("sent")

    print("\n### ИТОГ")
    for k, v in results.items():
        ok = "✅ только текст" if v["text_only"] else "❌ пришло аудио или нет текста"
        print(f"  {k:12} {ok}; первый текст через {v['first_text_ms']} мс")


if __name__ == "__main__":
    asyncio.run(main())
