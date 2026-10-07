"""Имитация звонка без модема: реальный AgentSession (Yandex text + Fish) и реальный AudioPort,
у которого чтение/запись последовательного порта заменены на «абонента» из синтезированных фраз.

Запуск:  .venv/bin/python fish_demo/call_sim.py [--yandex]  → fish_demo/out/call_sim_*.wav (слева абонент, справа агент)
Ключи берутся из fish_demo/.env (FISH_API_KEY, YANDEX_API_KEY, YANDEX_FOLDER_ID).
"""
import asyncio
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from array import array
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent
TMP = Path(tempfile.mkdtemp(prefix="caller_sim_"))
os.environ["CALLER_DATA_DIR"] = str(TMP)  # не трогаем настоящую data/
sys.path.insert(0, str(ROOT))

from app import db  # noqa: E402
from app.agent import fish  # noqa: E402
from app.agent.realtime import AgentSession  # noqa: E402
from app.modem.audio import FRAME_BYTES, RATE, SILENCE, AudioPort  # noqa: E402

VOICE = "4b6d1ad3-97a4-4c60-bcae-c6a34537ad77"  # «Спокойный женский голос»
# (пауза перед фразой, с; фраза абонента)
TURNS = [(1.0, "До скольки вы сегодня работаете?"), (7.0, "А в воскресенье вы открыты?"), (7.0, "Спасибо, до свидания.")]
# --barge: абонент перебивает агента посреди ответа
TURNS_BARGE = [(1.0, "Расскажите, какие у вас есть услуги?"), (3.2, "Подождите, а в субботу вы работаете?"),
               (7.0, "Спасибо, до свидания.")]
TAIL = 7.0
INSTRUCTIONS = ("Ты вежливый администратор салона красоты «Лотос». Отвечай коротко, одним-двумя предложениями, "
                "но про услуги рассказывай подробно, три-четыре предложения. Услуги: стрижки, окрашивание, маникюр, "
                "педикюр, массаж, косметология. Сегодня салон работает до девяти вечера, "
                "в субботу и воскресенье — с десяти до шести.")


def env() -> dict:
    keys = ("FISH_API_KEY", "YANDEX_API_KEY", "YANDEX_FOLDER_ID")
    if all(os.environ.get(k) for k in keys):  # на Pi ключи приходят через окружение
        return {k: os.environ[k] for k in keys}
    out = {}
    for line in (HERE / ".env").read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def say(text: str) -> bytes:
    with tempfile.TemporaryDirectory() as d:
        aiff = Path(d) / "a.aiff"
        subprocess.run(["say", "-v", "Milena", "-o", str(aiff), text], check=True)
        return subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(aiff), "-ac", "1", "-ar", str(RATE),
                               "-f", "s16le", "-"], check=True, capture_output=True).stdout


class SimPort(AudioPort):
    """AudioPort без железа: «абонент» читает заготовленный поток, наш звук копится в tx (record=True)."""

    def __init__(self, caller_pcm: bytes, on_frame):
        super().__init__("sim", on_frame, record=True)
        self.caller = caller_pcm
        self.pos = 0
        self.t0 = None
        self.first_voiced_tx = []

    def _open(self):
        self.t0 = time.monotonic()

    def _read_frame(self) -> bytes:
        # читаем в реальном времени, как модем
        target = self.t0 + (self.pos // FRAME_BYTES + 1) * 0.02
        delay = target - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        frame = self.caller[self.pos:self.pos + FRAME_BYTES]
        self.pos += FRAME_BYTES
        return frame + SILENCE[len(frame):]

    def _write_frame(self, frame: bytes):
        pass


class Ctl:
    def __init__(self, t0):
        self.t0 = t0
        self.messages = []
        self.hung_up = asyncio.Event()

    def add_message(self, role, text):
        t = time.monotonic() - self.t0()
        self.messages.append((t, role, text))
        print(f"[{t:6.2f}] {role:9} {text}")

    def save_result(self, data):
        print("save_result", data)

    async def send_dtmf(self, digits):
        print("dtmf", digits)

    async def hangup(self, reason):
        print("hangup", reason)
        self.hung_up.set()


def speech_spans(pcm: bytes, level=400, min_gap_ms=300):
    """Отрезки звука (начало, конец) в секундах по кадрам 20 мс."""
    x = array("h")
    x.frombytes(pcm)
    n = FRAME_BYTES // 2
    spans, start, quiet = [], None, 0
    for i in range(0, len(x) - n, n):
        rms = (sum(v * v for v in x[i:i + n]) / n) ** 0.5
        t = i / RATE
        if rms >= level:
            if start is None:
                start = t
            quiet = 0
        elif start is not None:
            quiet += 20
            if quiet >= min_gap_ms:
                spans.append((start, t - quiet / 1000 + 0.02))
                start, quiet = None, 0
    if start is not None:
        spans.append((start, len(x) / RATE))
    return spans


async def main():
    use_yandex_voice = "--yandex" in sys.argv
    e = env()
    db.connect()
    s = db.get_settings()
    s.update({"yandex.api_key": e["YANDEX_API_KEY"], "yandex.folder_id": e["YANDEX_FOLDER_ID"],
              "fish.api_key": e["FISH_API_KEY"]})
    # заготовки кэшируются в out/fillers между прогонами, чтобы не тратить кредиты
    fillers_cache = HERE / "out" / "fillers" / VOICE
    if fillers_cache.exists() and "--gen-fillers" not in sys.argv:
        shutil.copytree(fillers_cache, fish.FILLER_DIR / VOICE, dirs_exist_ok=True)

    # реплики абонента кэшируются в out/, чтобы запускать имитацию там, где нет macOS `say` (на Pi)
    name = "barge" if "--barge" in sys.argv else "normal"
    cache, cache_meta = HERE / "out" / f"caller_{name}.pcm", HERE / "out" / f"caller_{name}.json"
    if cache.exists() and cache_meta.exists():
        caller, ends = bytearray(cache.read_bytes()), json.loads(cache_meta.read_text())
    else:
        caller, ends = bytearray(), []
        for pause, text in (TURNS_BARGE if "--barge" in sys.argv else TURNS):
            caller += bytes(int(pause * RATE) * 2)
            caller += say(text)
            ends.append(len(caller) / 2 / RATE)
        caller += bytes(int(TAIL * RATE) * 2)
        cache.parent.mkdir(exist_ok=True)
        cache.write_bytes(bytes(caller))
        cache_meta.write_text(json.dumps(ends))

    agent = {"voice": "dasha", "speaks_first": False, "tools": ["hangup_call"], "vad_threshold": 0.5,
             "silence_ms": 800, "tts_engine": "yandex" if use_yandex_voice else "fish", "fish_voice": VOICE,
             "fillers": True, "filler_kind": "short", "filler_delay_ms": 0}
    port = SimPort(bytes(caller), on_frame=lambda f: None)
    ctl = Ctl(lambda: port.t0 or time.monotonic())
    session = AgentSession(ctl, port, agent, INSTRUCTIONS, s)
    port.on_frame = session.feed

    # отметки: когда в буфер модема легли заготовка и первый звук ответа
    marks = []
    orig_play = port.play

    def play(pcm, max_ms=None):
        kind = "filler" if any(pcm == f["pcm"] for f in (session._fillers.fillers if session._fillers else [])) else "answer"
        marks.append((time.monotonic() - port.t0 + port.pending_ms / 1000, kind))
        orig_play(pcm, max_ms)
    port.play = play

    orig_handle = session._handle

    async def handle(ev):  # RAW: сырой текст ответов модели
        if ev.get("type") in ("response.output_text.done", "response.output_item.done"):
            print("RAW", ev.get("type"), repr(ev.get("text") or ev.get("item"))[:400])
        await orig_handle(ev)
    session._handle = handle

    port.start()
    task = asyncio.create_task(session.run())
    total = len(caller) / 2 / RATE
    try:
        await asyncio.wait_for(ctl.hung_up.wait(), total + 2)
    except asyncio.TimeoutError:
        pass
    await session.close()
    task.cancel()
    port.stop()

    out = HERE / "out"
    out.mkdir(exist_ok=True)
    wav = out / f"call_sim_{'yandex' if use_yandex_voice else 'fish'}{'_barge' if '--barge' in sys.argv else ''}.wav"
    port.save_wav(wav)

    print(f"\nзапись: {wav}")
    if "--debug" in sys.argv:
        print("отметки (с от начала, что легло в буфер):", [(round(t, 2), k) for t, k in marks][:60])
        print("звук агента:", [(round(a, 2), round(b, 2)) for a, b in speech_spans(bytes(port.tx))])
    agent_spans = speech_spans(bytes(port.tx))
    for i, end in enumerate(ends):
        nxt = ends[i + 1] - 0 if i + 1 < len(ends) else 1e9
        after = [sp for sp in agent_spans if end < sp[0] < nxt]
        m = [(t, k) for t, k in marks if end < t < nxt]
        first_f = next((t for t, k in m if k == "filler"), None)
        first_a = next((t for t, k in m if k == "answer"), None)
        print(f"реплика {i + 1}: абонент замолчал в {end:.2f} с → "
              f"первый звук агента +{(after[0][0] - end) if after else float('nan'):.2f} с"
              + (f", заготовка +{first_f - end:.2f} с" if first_f else "")
              + (f", ответ +{first_a - end:.2f} с" if first_a else ""))
    if (fish.FILLER_DIR / VOICE / "manifest.json").exists():
        shutil.copytree(fish.FILLER_DIR / VOICE, fillers_cache, dirs_exist_ok=True)
    shutil.rmtree(TMP, ignore_errors=True)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(relativeCreated)6d %(name)s %(levelname)s %(message)s")
    if "--debug" in sys.argv:
        logging.getLogger("agent").setLevel(logging.DEBUG)
    asyncio.run(main())
