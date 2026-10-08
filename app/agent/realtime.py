"""Bridge between a phone call (8 kHz PCM from SIM7600) and a Yandex AI Studio
voice agent (Realtime API over WebSocket).

Protocol reference: https://aistudio.yandex.ru/docs/ru/ai-studio/operations/agents/create-voice-agent.html
"""
import asyncio
import base64
import json
import logging
import re

import aiohttp
from array import array

from .. import db, greetings
from .. import fillers as voice_fillers
from ..audio import Resampler, apply_gain
from ..modem.audio import RATE as MODEM_RATE
from . import emotions, fish

log = logging.getLogger("agent")

# в режиме Fish модель пишет текст, а читает его TTS — числа словами звучат надёжнее
FISH_INSTRUCTIONS = ("\n\nТвои ответы озвучивает синтезатор речи. Пиши числа, время, даты, суммы и единицы "
                     "измерения словами, без цифр, символов, списков и разметки.")
SENTENCE_END = ".!?…"
FINISH_MAX_S = 2.0  # an interrupted Fish sentence may sound this much longer
GREETING_TAG = "greeting"  # Fish phrase tag of the greeting synthesized before the answer
# In a text-only session the model sometimes writes a function call into the reply text instead of calling it,
# and the form keeps changing: «[TOOL_CALL_START]save_result {…}», a ``` block, «save_result({…})»,
# «{{save_result "status": …}}», JSON {"name": …}, or just a line «Завершить звонок». Everything from such a
# start on is not speech: it's cut from what is spoken and saved (_visible) and executed as a call (leaked_calls).
CALL_NAMES = ("hangup_call", "save_result", "send_dtmf", "use_skill", "notify_sms")
_NAMES = "|".join(CALL_NAMES)
# a line that only names an action in words — the model "calling" a function in Russian
CALL_WORDS = {"hangup_call": r"(?:завершить|заверши|завершаю|положить трубку|кладу трубку)(?:\s+(?:звонок|разговор|вызов))?",
              "save_result": r"(?:сохранить|сохраняю)\s+(?:итог|результат)(?:\s+(?:звонка|разговора))?"}
_WORDS = "|".join(CALL_WORDS.values())
LEAK_START = re.compile(
    r"\[TOOL_CALL|```"
    rf"|(?m:^[^\w\n]*(?:{_NAMES})\b)"            # a line starting with a function name, after {{ [ ` * etc.
    rf"|[{{\[<`(]\s*(?:{_NAMES})\b"               # …or right after an opening bracket anywhere
    r"|\{\s*\"name\"\s*:"
    rf"|(?im:^[^\w\n]*(?:{_WORDS})[^\w\n]*$)"    # «Завершить звонок» alone on a line
    # a made-up continuation of the dialogue («Пользователь: … Ассистент: …») — never to be spoken
    r"|(?im:^\s*(?:Пользователь|Собеседник|Ассистент|Ассисток|Агент|Курьер|Водитель|User|Assistant)\s*:)")
_JSON = json.JSONDecoder()
_PAIR = re.compile(r'"(\w+)"\s*:\s*("(?:[^"\\]|\\.)*"|\{.*?\}|-?\d+(?:\.\d+)?|true|false|null)', re.S)


def greeting_note(text: str, said: bool) -> str:
    """The opening line for the prompt: to be said by the model, or already played (pre-synthesized)."""
    if not said:
        return f"Начни разговор фразой: «{text}»"
    return (f"Разговор уже начат: как только собеседник ответил, прозвучало твоё приветствие «{text}». "
            "Второй раз не здоровайся и не повторяй его, даже если собеседник перебил тебя или переспросил "
            "«алло?» — отвечай на его слова и продолжай разговор.")


def _visible(text: str) -> str:
    """Reply text without leaked function-call markup (it must not be spoken or saved)."""
    m = LEAK_START.search(text)
    return text if m is None else text[:m.start()].rstrip()


def _loose_args(text: str) -> dict:
    """Arguments of a mangled call: real JSON if there is one, otherwise the "key": value pairs."""
    brace = text.find("{")
    if brace >= 0 and not text[:brace].strip(" \t\n({:"):
        try:
            obj, _ = _JSON.raw_decode(text, brace)
            if isinstance(obj, dict):
                return obj
        except ValueError:
            pass
    out = {}
    for k, v in _PAIR.findall(text):
        try:
            out[k] = json.loads(v)
        except ValueError:
            out[k] = v.strip('"')
    return out


def leaked_calls(text: str) -> list[tuple[str, str]]:
    """(name, JSON arguments) of the function calls written into the reply text."""
    m = LEAK_START.search(text)
    if m is None:
        return []
    tail = text[m.start():]
    found = []  # (position, name, args)
    for hit in re.finditer(rf"\b({_NAMES})\b", tail):
        nxt = re.search(rf"\b(?:{_NAMES})\b", tail[hit.end():])
        chunk = tail[hit.end(): hit.end() + nxt.start() if nxt else len(tail)]
        found.append((hit.start(), hit.group(1), _loose_args(chunk)))
    for hit in re.finditer(r'\{\s*"name"\s*:', tail):  # {"name": …, "arguments": …}
        try:
            obj, _ = _JSON.raw_decode(tail, hit.start())
        except ValueError:
            continue
        if isinstance(obj, dict) and obj.get("name") in CALL_NAMES:
            a = obj.get("arguments") or obj.get("parameters") or {}
            if isinstance(a, str):
                try:
                    a = json.loads(a)
                except ValueError:
                    a = {}
            found = [f for f in found if not (hit.start() <= f[0] <= hit.start() + len(json.dumps(obj)))]
            found.append((hit.start(), obj["name"], a))
    for name, words in CALL_WORDS.items():
        for hit in re.finditer(rf"(?im)^[^\w\n]*(?:{words})[^\w\n]*$", tail):
            if not any(f[1] == name for f in found):
                found.append((hit.start(), name, {}))
    seen, calls = set(), []
    for _, name, args in sorted(found, key=lambda f: f[0]):
        if name == "save_result" and not args:  # nothing to save — don't wipe a real result
            continue
        key = (name, json.dumps(args, ensure_ascii=False, sort_keys=True))
        if key not in seen:
            seen.add(key)
            calls.append((name, json.dumps(args, ensure_ascii=False)))
    # hangup last: save the result first, then put the phone down
    return sorted(calls, key=lambda c: c[0] == "hangup_call")


TOOL_DEFS = {
    "hangup_call": {
        "type": "function",
        "name": "hangup_call",
        "description": "Завершить телефонный звонок. Вызывай после того, как попрощался с собеседником.",
        "parameters": {
            "type": "object",
            "properties": {"reason": {"type": "string", "description": "Причина завершения"}},
        },
    },
    "save_result": {
        "type": "function",
        "name": "save_result",
        "description": "Сохранить итог разговора (результат сценария) в CRM.",
        "parameters": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "description": "Короткий статус итога, например confirmed / declined / lead"},
                "summary": {"type": "string", "description": "Краткое резюме разговора"},
                "data": {"type": "object", "description": "Собранные данные (имя, дата и т.п.)"},
            },
            "required": ["status", "summary"],
        },
    },
    "notify_sms": {
        "type": "function",
        "name": "notify_sms",
        "description": "Отправить владельцу короткую SMS-сводку по подключённому скиллу (например, номер машины "
                       "курьера для пропуска).",
        "parameters": {
            "type": "object",
            "properties": {"text": {"type": "string", "description": "Текст SMS, коротко"},
                           "skill": {"type": "string", "description": "Название скилла"}},
            "required": ["text"],
        },
    },
    "send_dtmf": {
        "type": "function",
        "name": "send_dtmf",
        "description": "Отправить тоновые сигналы DTMF (например, для навигации по голосовому меню).",
        "parameters": {
            "type": "object",
            "properties": {"digits": {"type": "string", "description": "Цифры 0-9, * и #"}},
            "required": ["digits"],
        },
    },
}


def use_skill_def(names: list[str]) -> dict:
    return {"type": "function", "name": "use_skill",
            "description": "Подключить скилл — получить инструкцию для ситуации в разговоре. Вызывай молча.",
            "parameters": {"type": "object", "properties": {
                "name": {"type": "string", "enum": names, "description": "Название скилла"}}, "required": ["name"]}}


def voice_role(voice: str, role: str | None) -> str:
    """The role to send, only if this voice has it (unknown voices, e.g. Brand Voice, pass through)."""
    from ..db import VOICE_ROLES
    if not role:
        return ""
    roles = VOICE_ROLES.get(voice)
    return role if roles is None or role in roles else ""


class AgentSession:
    """One Realtime API session per phone call.

    `controller` is the CallManager and must provide:
      - add_message(role, text)
      - save_result(dict)
      - send_dtmf(digits) (async)
      - hangup(reason) (async)
    """

    def __init__(self, controller, audio_port, agent: dict, instructions: str, settings: dict,
                 direction: str = "out", greeting: str = ""):
        self.ctl = controller
        self.audio = audio_port   # None until the call is answered (see go_live)
        self.direction = direction
        self.agent = agent
        self.instructions = instructions
        # skills: offered ones (loaded with use_skill during the call) and loaded ones (from the start or later)
        self.skills = list(agent.get("skills") or [])
        self.skills_loaded = list(agent.get("skills_loaded") or [])
        self._skills_added: list[dict] = []  # loaded during the call — their text goes into the session
        self.s = settings
        self.rate = int(settings.get("audio.agent_rate") or 16000)
        self.rx_gain = float(settings.get("audio.rx_gain") or 1.0)
        self.tx_gain = float(settings.get("audio.tx_gain") or 1.0)
        self.up = Resampler(MODEM_RATE, self.rate)
        self.down = Resampler(self.rate, MODEM_RATE)
        self.loop = asyncio.get_running_loop()
        self.frames: asyncio.Queue = asyncio.Queue(maxsize=500)
        self.ws = None
        self.closed = False
        self._agent_text = ""
        self._agent_text_saved = False
        self._responding = False
        # --- barge-in control (see _gate) ---
        self.speech_level = int(settings.get("audio.speech_level") or 300)   # RMS of speech on the line
        self.barge_ms = int(settings.get("audio.barge_in_ms") or 400)        # how long before it counts as interrupting
        self._holding = False
        self._held = bytearray()
        self._held_voiced = 0
        self._held_quiet = 0
        self._epoch = 0          # bumps on every interruption; audio of older responses is dropped
        self._resp_epoch = None
        self._hangup_task = None
        # --- Fish Audio TTS: Yandex answers with text, Fish speaks it (see _fish_*) ---
        self.fish_mode = agent.get("tts_engine") == "fish"
        self.emotions = emotions.parse(agent.get("emotions_allowed")) if self.fish_mode else []  # intonation tags
        self.fish: fish.FishTTS | None = None
        self._resp_called = False         # the current reply made a real function call
        self.usage = {"tokens_in": 0, "tokens_out": 0, "tokens_cached": 0, "fish_chars": 0, "fish_credits": 0}
        self._repeat_pending = False      # re-say the reply Fish failed to speak (Yandex voice)
        self._fish_queue: asyncio.Queue = asyncio.Queue()
        self._fish_tasks: list[asyncio.Task] = []
        self._resp_n = 0                  # current response number (a tag for its Fish phrases)
        self._fish_sent = 0               # chars of the current reply already sent to Fish
        self._fish_pending: dict[int, int] = {}   # response -> phrases still being synthesized
        self._fish_resp_done: set[int] = set()
        self._resamplers: dict[int, Resampler] = {}  # response -> Fish PCM (44.1 kHz) → modem rate
        # jitter buffer: Fish streams in bursts (the first chunk of a phrase is often followed by a ~0.5 s gap),
        # so a phrase starts only with a reserve of audio; if the stream starves, it waits for a reserve again
        # (a short pause instead of a stutter) and the reserve grows for the rest of the call
        self._prebuffer_ms = int(settings.get("audio.fish_prebuffer_ms") or 600)
        self._tx_hold = bytearray()       # Fish audio waiting for the reserve (not the caller's _held!)
        self._tx_owner: dict | None = None  # the phrase that audio belongs to
        self._sounding: list[dict] = []   # phrases handed to the modem, with the byte offset where each ends
        self._phrases: list[dict] = []    # phrases sent to Fish, in order (timings for the log)
        # interrupted while a sentence is sounding: it is finished (≤ FINISH_MAX_S), the rest of the reply dropped
        self._finishing: dict | None = None
        self._fillers: voice_fillers.FillerPicker | None = None   # hesitations of the voice (both engines)
        # --- warm start: connect and synthesize the greeting while the phone is still ringing (see go_live) ---
        self.greeting = greeting          # the opening line ('' — the agent waits for the other person)
        self._greeting_task: asyncio.Task | None = None
        self._greet_note = ""             # how the prompt mentions the opening line
        self._live = asyncio.Event()
        self.live = False
        self._connected = False           # the Yandex session is set up (see wait_ready)
        self._greet_buf, self._greet_rate, self._greet_done = bytearray(), 0, asyncio.Event()
        self._t_speech_end = None         # when the caller stopped talking (for the log)
        self.error = ""

    # called from the audio reader thread
    def feed(self, frame: bytes):
        if self.closed:
            return
        try:
            self.loop.call_soon_threadsafe(self._put, frame)
        except RuntimeError:  # loop closed
            pass

    def _put(self, frame: bytes):
        if self.frames.full():
            self.frames.get_nowait()  # drop the oldest frame rather than lag behind
        self.frames.put_nowait(frame)

    def _url(self) -> str:
        base = self.s.get("yandex.ws_url") or "wss://ai.api.cloud.yandex.net/v1/realtime"
        model = self.agent.get("model") or self.s.get("yandex.model") or "speech-realtime-250923"
        if not model.startswith("gpt://"):
            model = f"gpt://{self.s.get('yandex.folder_id')}/{model}"
        sep = "&" if "?" in base else "?"
        return f"{base}{sep}model={model}"

    def _headers(self) -> dict:
        key = self.s.get("yandex.api_key") or ""
        # IAM tokens start with "t1." — use Bearer for them, Api-Key otherwise.
        if key.startswith("t1."):
            return {"Authorization": f"Bearer {key}"}
        return {"Authorization": f"Api-Key {key}"}

    def _session_config(self) -> dict:
        a = self.agent
        tools = [TOOL_DEFS[t] for t in (a.get("tools") or []) if t in TOOL_DEFS]
        left = [sk["name"] for sk in self.skills if sk not in self._skills_added]
        if left:
            tools.append(use_skill_def(left))
        if any(sk.get("sms_to") for sk in self.skills_loaded + self._skills_added):
            tools.append(TOOL_DEFS["notify_sms"])
        instructions = self.instructions
        if self._skills_added:
            from ..calls import skill_text
            instructions += "\n\nПодключённые скиллы:\n\n" + "\n\n".join(skill_text(sk) for sk in self._skills_added)
        session = {
            "instructions": instructions,
            "output_modalities": ["audio"],
            "audio": {
                "input": {
                    "format": {"type": "audio/pcm", "rate": self.rate},
                    "turn_detection": {
                        "type": "server_vad",
                        "threshold": float(a.get("vad_threshold") or 0.5),
                        "silence_duration_ms": int(a.get("silence_ms") or 800),
                    },
                },
                "output": {
                    "format": {"type": "audio/pcm", "rate": self.rate},
                    "voice": a.get("voice") or "dasha",
                },
            },
        }
        role = voice_role(a.get("voice") or "dasha", a.get("voice_role"))
        if role:
            session["audio"]["output"]["role"] = role
        speed = float(a.get("voice_speed") or 1.0)
        if abs(speed - 1.0) > 0.001:
            session["audio"]["output"]["speed"] = round(speed, 2)
        if tools:
            session["tools"] = tools
        extra = a.get("extra") or {}
        if isinstance(extra, dict):
            _deep_merge(session, extra)
        if self.fish_mode:
            # text-only session: works only on the session level, not per response.create
            session["output_modalities"] = ["text"]
            session["audio"].pop("output", None)
            session["instructions"] = (session.get("instructions") or "") + FISH_INSTRUCTIONS + emotions.instructions(
                self.emotions, emotions.parse(a.get("emotions_forbidden")))
        if self._greet_note:
            session["instructions"] = (session.get("instructions") or "") + "\n\n" + self._greet_note
        return {"type": "session.update", "session": session}

    # ------------------------------------------------------------ main loop

    async def run(self):
        try:
            await self._run()
        except Exception as e:
            self.error = str(e) or type(e).__name__
            raise
        finally:
            self.closed = True

    def _not_ready(self) -> str:
        """What the agent still lacks before the call ('' — ready)."""
        if self.closed:
            return self.error or "сессия агента закрыта"
        if self._greeting_task and self._greeting_task.done():
            e = None if self._greeting_task.cancelled() else self._greeting_task.exception()
            if self._greeting_task.cancelled() or e:
                return f"не удалось синтезировать приветствие: {e or 'отменено'}"
        missing = []
        if not self._connected:
            missing.append("нет соединения с Yandex AI Studio")
        if self.fish_mode and not (self.fish and self.fish.ready.is_set()):
            missing.append(self.fish.error if self.fish and self.fish.error else "Fish Audio не подключился")
        if self._greeting_task and not self._greeting_task.done():
            missing.append("приветствие ещё синтезируется")
        return "; ".join(missing)

    async def wait_ready(self, timeout: float) -> str:
        """Before dialing: wait until Yandex and Fish are connected and the greeting is synthesized.
        Returns '' when ready, otherwise why not (the call is not made then)."""
        end = self.loop.time() + timeout
        while True:
            reason = self._not_ready()
            if not reason:
                return ""
            if self.closed or self.loop.time() >= end or reason.startswith("не удалось"):
                return reason
            await asyncio.sleep(0.05)

    def go_live(self, audio_port):
        """The call is answered: audio flows, the agent greets (the session may have been started while ringing)."""
        self.audio = audio_port
        self.live = True
        self._live.set()

    async def _run(self):
        """Starts before the answer: Fish and Yandex connect and the greeting is synthesized during dialing /
        ringing (Kitta takes 1.2–1.9 s to get ready), then waits for go_live. Closed with the call if nobody answers."""
        if not self.s.get("yandex.api_key") or not self.s.get("yandex.folder_id"):
            raise RuntimeError("Не заданы API-ключ и folder_id Yandex AI Studio (Настройки → Yandex AI Studio)")
        if self.closed:
            return
        if self.fish_mode:
            await self._fish_start()
        if self.agent.get("fillers", True) and self.agent.get("voice_id"):
            self._fish_tasks.append(asyncio.create_task(self._load_fillers()))
        if self.greeting and self.agent.get("voice_id"):
            self._greeting_task = asyncio.create_task(self._make_greeting())
        timeout = aiohttp.ClientTimeout(total=None, connect=15)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as http:
                while not self.closed:
                    async with http.ws_connect(self._url(), headers=self._headers(), heartbeat=20.0,
                                               max_msg_size=0) as ws:
                        self.ws = ws
                        if self.closed:
                            return
                        log.info("realtime session connected%s", "" if self.live else " (waiting for the answer)")
                        await ws.send_json(self._session_config())
                        self._connected = True
                        downlink = asyncio.create_task(self._downlink())
                        if not self.live:
                            answered = asyncio.create_task(self._live.wait())
                            await asyncio.wait({downlink, answered}, return_when=asyncio.FIRST_COMPLETED)
                            answered.cancel()
                            if downlink.done():  # the session dropped while the phone was ringing
                                if self.closed:
                                    return
                                log.info("realtime session closed before the answer, reconnecting")
                                await asyncio.sleep(1)
                                continue
                        uplink = asyncio.create_task(self._open_conversation())
                        try:
                            await downlink
                        finally:
                            uplink.cancel()
                        return
        finally:
            self.closed = True
            if self._greeting_task:
                self._greeting_task.cancel()
            await self._fish_stop()

    async def close(self):
        self.closed = True
        self._live.set()
        if self._greeting_task:
            self._greeting_task.cancel()
        if self.ws is not None and not self.ws.closed:
            await self.ws.close()
        await self._fish_stop()

    # ------------------------------------------------------------ the opening line

    async def _make_greeting(self) -> bytes | None:
        voice = db.get("voices", self.agent["voice_id"])
        if not voice:
            return None
        t0 = self.loop.time()
        how = "from the cache"
        data = greetings.cached(voice, self.greeting)
        if data is None and self.fish_mode and self.fish:
            try:  # the realtime connection is being opened anyway, and it streams faster than HTTP
                raw, rate = await self._fish_say_once(self.greeting)
                data = greetings.store(voice, self.greeting, raw, rate)
                how = "over the realtime connection"
            except Exception as e:  # noqa: BLE001
                log.warning("greeting over the realtime connection failed (%s), trying HTTP", e)
        if data is None:
            data = await greetings.pcm(voice, self.greeting, MODEM_RATE)
            how = "over HTTP"
            pcm = data
        else:
            pcm = await greetings.to_rate(data, MODEM_RATE)
        log.info("greeting ready in %.1f s %s (%.1f s of speech)", self.loop.time() - t0, how,
                 len(pcm) / 2 / MODEM_RATE)
        return apply_gain(pcm, self.tx_gain)

    async def _fish_say_once(self, text: str) -> tuple[bytes, int]:
        """Synthesize one phrase through the call's Fish session (before the answer) and return (PCM, rate)."""
        await asyncio.wait_for(self.fish.ready.wait(), 10)
        self._greet_buf, self._greet_rate, self._greet_done = bytearray(), 0, asyncio.Event()
        await self.fish.speak(text, GREETING_TAG)
        self.usage["fish_chars"] += len(text)
        await asyncio.wait_for(self._greet_done.wait(), 15)
        if not self._greet_buf or not self._greet_rate:
            raise RuntimeError("Fish не вернул звук")
        return bytes(self._greet_buf), self._greet_rate

    async def _pause_before_greeting(self) -> bytes | None:
        """Outgoing: give the person time to bring the phone to the ear (the agent's greeting_delay_ms); in any
        case don't talk over their «Алло?». Their sound here isn't sent to the model — only listened to.
        Returns the pre-synthesized greeting, or None if it isn't ready (the model will say it itself)."""
        delay = int(self.agent.get("greeting_delay_ms") if self.agent.get("greeting_delay_ms") is not None
                    else 1000) / 1000 if self.direction == "out" else 0.0
        t0 = self.loop.time()
        task = self._greeting_task
        last_loud = None
        while True:
            now = self.loop.time()
            ready = task is None or task.done()
            quiet = last_loud is None or now - last_loud >= 0.4
            if now >= t0 + delay + 2.5:  # they keep talking: greet anyway
                break
            # waiting for the synthesis longer than ~1.5 s is slower than letting the model greet
            if now >= t0 + delay and quiet and (ready or now >= t0 + delay + 1.5):
                break
            try:
                frame = await asyncio.wait_for(self.frames.get(), 0.05)
                if self._rms(frame) >= self.speech_level:
                    last_loud = now
            except asyncio.TimeoutError:
                pass
        if task is None or not task.done() or task.cancelled():
            if task:
                log.info("greeting is not synthesized yet — the model says it")
            return None
        if task.exception():
            log.warning("greeting synthesis failed: %s", task.exception())
            return None
        return task.result()

    async def _open_conversation(self):
        """After the answer: the opening line, then the caller's audio goes to the model."""
        if self.greeting:
            pcm = await self._pause_before_greeting()
            if pcm:
                self.audio.play(pcm)
                self.ctl.add_message("assistant", self.greeting)
                self._greet_note = greeting_note(self.greeting, said=True)
                await self._send(self._session_config())
                # and in the history as the agent's own reply: then the model doesn't greet again on «алло?»
                # (Yandex accepts an assistant message only with input_text content)
                await self._send({"type": "conversation.item.create", "item": {
                    "type": "message", "role": "assistant",
                    "content": [{"type": "input_text", "text": self.greeting}]}})
                log.info("pre-synthesized greeting played")
            else:
                self._greet_note = greeting_note(self.greeting, said=False)
                await self._send(self._session_config())
                await self._send({"type": "response.create"})
        elif self.agent.get("speaks_first", True):  # no fixed opening line: the model starts in its own words
            await self._send({"type": "response.create"})
        await self._uplink()

    async def _send(self, payload: dict):
        if self.ws is not None and not self.ws.closed:
            await self.ws.send_json(payload)

    # ------------------------------------------------------------ barge-in control
    #
    # Yandex's server VAD cancels the agent's reply on any sound and answers it, so a caller's
    # "а" / "ага" / "алло" used to cut the agent mid-word and trigger a new reply. While the agent
    # is talking we hold the caller's sound for up to `barge_ms`: a short sound is replaced with
    # silence (the agent is only ducked for a moment), a longer one is a real interruption — the
    # held audio is released intact and the agent fades out instead of being cut.

    def _agent_speaking(self) -> bool:
        return self._responding or self._fish_busy() or self.audio.pending_ms > 40

    @staticmethod
    def _rms(frame: bytes) -> float:
        x = array("h")
        x.frombytes(frame)
        return (sum(v * v for v in x) / len(x)) ** 0.5 if x else 0.0

    def _release(self, real: bool) -> bytes:
        data = bytes(self._held) if real else bytes(len(self._held))  # silence keeps the timeline
        self._holding, self._held = False, bytearray()
        self.audio.set_volume(1.0)
        return data

    def _gate(self, frame: bytes) -> bytes:
        if self._finishing is not None and not self._holding:
            return frame  # already interrupted: the sentence is being finished, the caller is heard as is
        loud = self._rms(frame) >= self.speech_level
        if self._holding:
            self._held.extend(frame)
            if loud:
                self._held_voiced += 20
                self._held_quiet = 0
            else:
                self._held_quiet += 20
            if not self._agent_speaking():          # the agent finished meanwhile: a normal turn
                return self._release(real=True)
            if self._held_voiced >= self.barge_ms:  # a real interruption
                log.info("barge-in after %s ms of speech", self._held_voiced)
                self._interrupt()
                return self._release(real=True)
            if self._held_quiet >= 200:             # a short "а"/"ага": don't let it cut the agent
                log.debug("ignored %s ms sound while the agent was talking", self._held_voiced)
                return self._release(real=False)
            return b""
        if loud and self._agent_speaking():
            self._holding, self._held = True, bytearray(frame)
            self._held_voiced, self._held_quiet = 20, 0
            self.audio.set_volume(0.6)              # duck a little while we decide
            return b""
        return frame

    def _interrupt(self):
        """The caller interrupts: ignore the rest of the reply that is still streaming in.

        Yandex voice: fade out. Fish: the sentence that is sounding is finished, like people do (at most
        FINISH_MAX_S more, then it fades); what comes after it and the rest of the reply are dropped. Fish can't
        cancel a phrase, but only one is in flight (see _fish_sender), so there's nothing to reconnect for."""
        self._epoch += 1
        self._resp_epoch = None
        log.debug("interrupt -> epoch %s", self._epoch)
        if not self.fish_mode:
            self.audio.fade_out(150)
            return
        while not self._fish_queue.empty():
            self._fish_queue.get_nowait()
        self._fish_pending.clear()
        if self._finishing is not None:  # already finishing a sentence: just drop what came since
            self._jb_clear()
            self._resamplers = {k: v for k, v in self._resamplers.items() if k == self._finishing["resp"]}
            return
        played = self.audio.played
        self._sounding = [r for r in self._sounding if r["end"] > played]
        cur = self._sounding[0] if self._sounding else None
        streaming = self._phrases[0] if self._phrases else None
        if cur is None:  # no Fish sentence is audible (a filler, the greeting or silence)
            self.audio.fade_out(150)
            self._jb_clear()
            self._resamplers.clear()
            return
        cap = int(FINISH_MAX_S * MODEM_RATE) * 2
        rest = cur["end"] - played
        if cur is streaming and not cur["done"].is_set():
            # still arriving: let the rest of it through as it comes (see _fish_on_audio)
            self._finishing = cur
            if self._tx_owner is cur:
                self._jb_release()
            else:
                self._jb_clear()
            self._resamplers = {k: v for k, v in self._resamplers.items() if k == cur["resp"]}
            self._fish_tasks.append(asyncio.create_task(self._finish_sentence(cur)))
            log.info("interrupted: finishing the sentence %r (still streaming)", cur["text"][:40])
        else:
            self._jb_clear()
            self._resamplers.clear()
            self.audio.keep(min(rest, cap), fade_ms=150 if rest > cap else 0)
            log.info("interrupted: finishing the sentence %r (%.1f s left%s)", cur["text"][:40],
                     rest / 2 / MODEM_RATE, ", cut" if rest > cap else "")
        self._sounding = [cur]

    async def _finish_sentence(self, ph: dict):
        """The interrupted sentence is still streaming: let it sound to its end, but no longer than FINISH_MAX_S."""
        end = self.loop.time() + FINISH_MAX_S
        while self.loop.time() < end:
            if ph["done"].is_set() and self.audio.played >= ph["end"]:
                break
            await asyncio.sleep(0.02)
        else:
            log.info("the interrupted sentence is too long — fading out")
            self.audio.fade_out(150)
        if self._finishing is ph:
            self._finishing = None
            self._resamplers.pop(ph["resp"], None)
            self._jb_release()  # the next reply may have been waiting

    # ------------------------------------------------------------ Fish Audio TTS
    #
    # Yandex runs the dialogue in a text-only session. Each reply is cut into sentences which go to Fish
    # as separate phrases of one realtime session; 44.1 kHz PCM comes back (wav) and is resampled to 8 kHz
    # for the modem. Phrases are tagged (epoch, response) so the tail of an interrupted reply is dropped.
    # While Fish synthesizes (~1 s) a pre-recorded hesitation ("Ммм...") in the same voice fills the pause.

    async def _fish_start(self):
        a = self.agent
        if not a.get("fish_voice"):
            raise RuntimeError("Не выбран голос Fish Audio (Агенты → голос)")
        if not self.s.get("fish.api_key"):
            raise RuntimeError("Не задан API-ключ Fish Audio (Настройки → Fish Audio)")
        self.fish = fish.FishTTS(self.s, a["fish_voice"], a.get("fish_model") or "", self._fish_on_audio,
                                 self._fish_on_done, speed=float(a.get("voice_speed") or 1.0),
                                 language=a.get("fish_language") or "ru", on_usage=self._fish_usage)
        self.fish.start()
        self._fish_tasks.append(asyncio.create_task(self._fish_sender()))

    def _fish_usage(self, units):
        self.usage["fish_credits"] += int(units or 0)

    async def _load_fillers(self):
        """Hesitations of the agent's voice (Yandex or Fish), made when the voice/agent was saved."""
        voice = db.get("voices", self.agent["voice_id"])
        if not voice:
            return
        try:
            job = voice_fillers.ensure(voice)  # an older voice without a set gets one now, in the background
            if job:
                log.info("fillers of voice %s are not ready yet, waiting for generation", voice["id"])
                await job
            items = await voice_fillers.load_pcm(voice["id"], MODEM_RATE)
            items = [{**f, "pcm": apply_gain(f["pcm"], self.tx_gain)} for f in items]
            self._fillers = voice_fillers.FillerPicker(items, self.agent.get("filler_kind") or "short")
            log.info("fillers ready: %s", len(items))
        except Exception as e:  # noqa: BLE001 — fillers are optional
            log.warning("fillers unavailable: %s", e)

    async def _fish_stop(self):
        for t in self._fish_tasks:
            t.cancel()
        self._fish_tasks.clear()
        self._resamplers.clear()
        self._jb_clear()
        self._phrases.clear()
        self._sounding.clear()
        self._finishing = None
        if self.fish:
            f, self.fish = self.fish, None
            await f.close()

    def _fish_busy(self) -> bool:
        return self.fish_mode and (any(self._fish_pending.values()) or not self._fish_queue.empty())

    def _fish_feed(self, final: bool):
        """Send complete sentences of the reply (everything that is left if final) to Fish."""
        if self._resp_epoch != self._epoch:
            return
        rest = _visible(self._agent_text)[self._fish_sent:]
        if final:
            cut = len(rest)
        else:
            ends = [i for i, ch in enumerate(rest) if ch in SENTENCE_END and (i + 1 == len(rest) or rest[i + 1].isspace())]
            cut = ends[-1] + 1 if ends else 0
        if cut <= 0:
            return
        self._fish_sent += cut
        chunk, sentence = rest[:cut], ""
        for i, ch in enumerate(chunk):  # one Fish phrase per sentence: the first one starts sooner
            sentence += ch
            if ch in SENTENCE_END and (i + 1 == len(chunk) or chunk[i + 1].isspace()) and sentence.strip():
                self._fish_enqueue(sentence)
                sentence = ""
        if sentence.strip():
            self._fish_enqueue(sentence)

    def _fish_enqueue(self, text: str):
        text = emotions.for_fish(text.strip(), self.emotions)
        if not emotions.strip(text):  # only a tag — nothing to say
            return
        tag = (self._epoch, self._resp_n)
        self._fish_pending[self._resp_n] = self._fish_pending.get(self._resp_n, 0) + 1
        self._fish_queue.put_nowait((text, tag))

    async def _fish_sender(self):
        while True:
            text, tag = await self._fish_queue.get()
            if tag[0] != self._epoch or not self.fish:
                continue
            ph = {"text": text, "sent": self.loop.time(), "first": None, "audio": 0.0, "rebuffers": 0,
                  "resp": tag[1], "done": asyncio.Event()}
            self._phrases.append(ph)
            try:
                await self.fish.speak(text, tag)
                self.usage["fish_chars"] += len(text)
            except Exception as e:  # noqa: BLE001
                if ph in self._phrases:
                    self._phrases.remove(ph)
                log.error("fish speak failed: %s", e)
                await self._fish_fallback(str(e), tag)
                return
            # One phrase in flight: the next is sent when this one has fully arrived. Fish synthesizes 3-10x
            # faster than speech, so it's still ahead of the playback — and an interruption leaves at most
            # one phrase to wait for (Fish can't cancel), so no reconnect is needed.
            try:
                await asyncio.wait_for(ph["done"].wait(), 30)
            except asyncio.TimeoutError:
                log.warning("fish phrase not finished in 30 s: %r", text[:40])

    async def _fish_fallback(self, reason: str, tag):
        """Fish is unavailable: finish the call with the Yandex voice and re-say the reply that wasn't heard."""
        if not self.fish_mode:
            return
        self.ctl.add_message("system", f"Fish Audio недоступен ({reason}) — дальше говорит голос Яндекса")
        unsaid = tag[0] == self._epoch
        self.fish_mode = False  # from now on replies come as Yandex audio (see _handle)
        self._resamplers.clear()
        self._jb_clear()
        self._sounding.clear()
        self._finishing = None
        self._fish_pending.clear()
        while not self._fish_queue.empty():
            self._fish_queue.get_nowait()
        if self.fish:
            f, self.fish = self.fish, None
            asyncio.create_task(f.close())
        await self._send(self._session_config())  # the Realtime API switches modalities mid-session
        if unsaid:
            self._repeat_pending = True
            if not self._responding:
                await self._repeat_unheard()

    async def _repeat_unheard(self):
        self._repeat_pending = False
        await self._send({"type": "response.create", "response": {"instructions": (
            "Твою предыдущую реплику собеседник не услышал из-за сбоя связи. "
            "Повтори её дословно, ничего не добавляя" + (", но без пометок интонации в квадратных скобках — "
                                                         "дальше их не используй" if self.emotions else "") + ".")}})

    def _jb_clear(self):
        self._tx_hold = bytearray()
        self._tx_owner = None

    def _play_fish(self, ph: dict | None, data: bytes):
        self.audio.play(data)
        if ph is not None:
            ph["end"] = self.audio.queued  # where this sentence ends in the modem's stream
            if not self._sounding or self._sounding[-1] is not ph:
                self._sounding.append(ph)
            played = self.audio.played
            while len(self._sounding) > 1 and self._sounding[0]["end"] <= played:
                self._sounding.pop(0)

    def _hold(self, ph: dict | None, data: bytes):
        if self._tx_hold and self._tx_owner is not ph:
            self._jb_release()  # never mix two sentences in the hold
        self._tx_owner = ph
        self._tx_hold.extend(data)

    def _jb_release(self):
        if self._tx_hold:
            data, ph = bytes(self._tx_hold), self._tx_owner
            self._jb_clear()
            self._play_fish(ph, data)

    def _fish_on_audio(self, tag, pcm: bytes, rate: int):
        if tag == GREETING_TAG:  # synthesized before the answer: collected, not played
            self._greet_buf.extend(pcm)
            self._greet_rate = rate
            return
        epoch, resp = tag
        if not pcm:
            return
        ph = self._phrases[0] if self._phrases else None
        finishing = self._finishing is not None and ph is self._finishing
        if epoch != self._epoch and not finishing:
            return  # the rest of an interrupted reply
        now = self.loop.time()
        if ph is not None:
            if ph["first"] is None:
                ph["first"] = now
            ph["audio"] += len(pcm) / 2 / rate
        rs = self._resamplers.get(resp)
        if rs is None:  # one resampler per reply keeps its sentences click-free
            log.debug("fish audio starts: epoch %s response %s", epoch, resp)
            rs = self._resamplers[resp] = Resampler(rate, MODEM_RATE)
        data = apply_gain(rs.process(pcm), self.tx_gain)
        if finishing:  # the interrupted sentence goes on as it streams
            self._play_fish(ph, data)
            return
        if self._finishing is not None:  # the new reply waits until the interrupted sentence ends
            self._hold(ph, data)
            return
        queued = self.audio.pending_ms
        if not self._tx_hold and queued >= self._prebuffer_ms:  # enough is already playing — keep streaming
            self._play_fish(ph, data)
            return
        if not self._tx_hold and queued == 0 and ph is not None and ph.get("playing"):
            ph["rebuffers"] += 1  # the stream fell behind the playback
            self._prebuffer_ms = min(int(self._prebuffer_ms * 1.5), 2500)
            log.info("fish stream starved — waiting for a reserve, prebuffer now %s ms", self._prebuffer_ms)
        self._hold(ph, data)
        if queued + len(self._tx_hold) * 1000 // (2 * MODEM_RATE) >= self._prebuffer_ms:
            if ph is not None:
                ph["playing"] = True
            self._jb_release()

    def _fish_on_done(self, tag):
        if tag == GREETING_TAG:
            if not (self.fish and self.fish.ready.is_set()):  # the connection dropped: the audio is incomplete
                self._greet_buf = bytearray()
            self._greet_done.set()
            return
        epoch, resp = tag
        if self._phrases:
            ph = self._phrases.pop(0)
            ph["done"].set()
            if ph["first"] is not None:
                took = max(self.loop.time() - ph["first"], 0.01)
                log.info("fish phrase: first sound %.2f s, %.1f s of speech streamed in %.2f s (x%.1f realtime), "
                         "rebuffers %s%s: %r", ph["first"] - ph["sent"], ph["audio"], took, ph["audio"] / took,
                         ph["rebuffers"], "" if epoch == self._epoch or ph is self._finishing else " (dropped)",
                         ph["text"][:60])
        if epoch != self._epoch:
            return
        if self._finishing is None:
            self._jb_release()  # the phrase is complete: play whatever is held
        self._fish_pending[resp] = max(0, self._fish_pending.get(resp, 0) - 1)
        self._fish_maybe_finish(resp)

    def _fish_maybe_finish(self, resp: int):
        if resp in self._fish_resp_done and not self._fish_pending.get(resp):
            self._fish_pending.pop(resp, None)
            self._fish_resp_done.discard(resp)
            self._resamplers.pop(resp, None)

    def _play_filler(self):
        """The caller stopped talking: fill the pause until the answer starts sounding."""
        if not self._fillers or self.audio.pending_ms > 0 or self._fish_busy():
            return
        delay = int(self.agent.get("filler_delay_ms") or 0) / 1000

        async def play():
            if delay:
                await asyncio.sleep(delay)
            if self.audio.pending_ms > 0 or self._resamplers:  # the answer is already sounding
                return
            f = self._fillers.pick()
            if f:
                log.debug("filler %s", f["id"])
                self.audio.play(f["pcm"])
        self._fish_tasks.append(asyncio.create_task(play()))

    async def _uplink(self):
        batch = bytearray()
        while not self.closed:
            frame = await self.frames.get()
            batch.extend(self._gate(frame))
            if len(batch) < 1600:  # 100 ms @ 8 kHz
                continue
            pcm = self.up.process(apply_gain(bytes(batch), self.rx_gain))
            batch.clear()
            try:
                await self._send({"type": "input_audio_buffer.append",
                                  "audio": base64.b64encode(pcm).decode("ascii")})
            except (aiohttp.ClientError, ConnectionError, RuntimeError):
                return

    async def _downlink(self):
        async for msg in self.ws:
            if msg.type == aiohttp.WSMsgType.ERROR:
                log.error("ws error: %s", self.ws.exception())
                break
            if msg.type != aiohttp.WSMsgType.TEXT:
                continue
            try:
                ev = json.loads(msg.data)
            except ValueError:
                continue
            try:
                await self._handle(ev)
            except Exception:
                log.exception("failed to handle realtime event %s", ev.get("type"))

    async def _handle(self, ev: dict):
        t = ev.get("type", "")
        if t in ("response.output_audio.delta", "response.audio.delta"):
            if self._resp_epoch != self._epoch:
                return  # tail of a reply that was interrupted
            pcm = base64.b64decode(ev.get("delta") or "")
            pcm = apply_gain(self.down.process(pcm), self.tx_gain)
            self.audio.play(pcm)
        elif t == "input_audio_buffer.speech_started":
            log.info("yandex: caller speech started")
            # the server heard the caller; if the agent is still audible, fade it out
            if self.audio.pending_ms > 0 or self._fish_busy():
                self._interrupt()
        elif t == "input_audio_buffer.speech_stopped":
            self._t_speech_end = self.loop.time()
            log.info("yandex: caller speech stopped")
            self._play_filler()  # both engines; the agent's filler delay decides how eager it is
        elif t == "conversation.item.input_audio_transcription.completed":
            text = (ev.get("transcript") or "").strip()
            log.info("yandex: heard %r", text)
            if text:
                self.ctl.add_message("user", text)
        elif t == "response.created":
            log.info("yandex: reply started%s", "" if self._t_speech_end is None else
                     f" {self.loop.time() - self._t_speech_end:.2f} s after the caller stopped")
            self._resp_epoch = self._epoch
            self._responding = True
            self._agent_text = ""
            self._agent_text_saved = False
            self._resp_called = False
            if self.fish_mode:
                self._resp_n += 1
                self._fish_sent = 0
        elif t in ("response.output_text.delta", "response.output_audio_transcript.delta",
                   "response.audio_transcript.delta", "response.text.delta"):
            self._agent_text += ev.get("delta") or ""
            if self.fish_mode:
                self._fish_feed(final=False)
        elif t in ("response.output_text.done", "response.output_audio_transcript.done",
                   "response.audio_transcript.done", "response.text.done"):
            raw = ev.get("transcript") or ev.get("text") or self._agent_text
            if len(raw.strip()) > len(self._agent_text.strip()):
                self._agent_text = raw
            text = emotions.strip(_visible(raw)).strip()
            if self.fish_mode:
                self._fish_feed(final=True)
            if text and not self._agent_text_saved:
                self.ctl.add_message("assistant", text)
                self._agent_text_saved = True
        elif t == "response.done":
            self._responding = False
            r = ev.get("response") or {}
            log.info("yandex: reply done (%s)%s: %r", r.get("status") or "?",
                     "" if self._t_speech_end is None else f" {self.loop.time() - self._t_speech_end:.2f} s after the caller stopped",
                     _visible(self._agent_text).strip()[:80])
            u = r.get("usage") or {}
            self.usage["tokens_in"] += u.get("input_tokens") or 0
            self.usage["tokens_out"] += u.get("output_tokens") or 0
            self.usage["tokens_cached"] += (u.get("input_token_details") or {}).get("cached_tokens") or 0
            if self.fish_mode:
                self._fish_feed(final=True)
                self._fish_resp_done.add(self._resp_n)
                self._fish_maybe_finish(self._resp_n)
            text = emotions.strip(_visible(self._agent_text)).strip()
            if text and not self._agent_text_saved:
                self.ctl.add_message("assistant", text)
            self._agent_text_saved = True
            if self._repeat_pending and not self._resp_called:  # after a switch from Fish to the Yandex voice
                await self._repeat_unheard()
            if not getattr(self, "_resp_called", False):
                allowed = set(self.agent.get("tools") or []) | ({"use_skill"} if self.skills else set()) \
                    | ({"notify_sms"} if any(x.get("sms_to") for x in self.skills + self.skills_loaded) else set())
                for name, args in leaked_calls(self._agent_text):
                    if name not in allowed:  # the script doesn't allow it (e.g. hangup) — the text is dropped anyway
                        log.warning("function call leaked into the reply text, not allowed in this call: %s", name)
                        continue
                    log.warning("function call leaked into the reply text: %s %s", name, args)
                    await self._tool_call({"name": name, "arguments": args or "{}", "call_id": None})
        elif t == "response.output_item.done":
            item = ev.get("item") or {}
            if item.get("type") == "function_call":
                self._resp_called = True
                await self._tool_call(item)
        elif t == "session.created":
            log.info("realtime session created: %s", (ev.get("session") or {}).get("id"))
        elif t == "error":
            err = ev.get("error") or ev
            log.error("realtime error: %s", err)
            self.ctl.add_message("system", f"Ошибка агента: {err.get('message') if isinstance(err, dict) else err}")

    async def _tool_call(self, item: dict):
        name = item.get("name")
        call_id = item.get("call_id")
        try:
            args = json.loads(item.get("arguments") or "{}")
        except ValueError:
            args = {}
        log.info("tool call %s %s", name, args)
        self.ctl.add_message("tool", f"{name}({json.dumps(args, ensure_ascii=False)})")
        output = {"ok": True}
        follow_up = True
        if name == "hangup_call":
            follow_up = False
            if not self._hangup_task:
                self._hangup_task = asyncio.create_task(self._hangup_after_speech(args.get("reason", "")))
        elif name == "save_result":
            self.ctl.save_result(args)
        elif name == "send_dtmf":
            try:
                await self.ctl.send_dtmf(str(args.get("digits", "")))
            except Exception as e:
                output = {"ok": False, "error": str(e)}
        elif name == "use_skill":
            output = await self._use_skill(str(args.get("name") or args.get("skill") or ""))
        elif name == "notify_sms":
            output = await self._notify_sms(str(args.get("text") or ""), str(args.get("skill") or ""))
        else:
            output = {"ok": False, "error": f"unknown function {name}"}
        if not call_id:  # a call leaked into the text: nothing to answer on the Realtime side
            return
        await self._send({"type": "conversation.item.create", "item": {
            "type": "function_call_output", "call_id": call_id,
            "output": json.dumps(output, ensure_ascii=False)}})
        if follow_up:
            await self._send({"type": "response.create"})

    async def _use_skill(self, name: str) -> dict:
        """Load a skill mid-call: its instructions (and functions) join the session; the model also gets them in
        the function's answer, so it can follow them in its very next phrase."""
        from ..calls import skill_text
        key = name.strip().lower()
        sk = next((x for x in self.skills if x["name"].strip().lower() == key), None) \
            or next((x for x in self.skills if key and key in x["name"].lower()), None)
        if not sk:
            return {"ok": False, "error": f"нет скилла «{name}»", "available": [x["name"] for x in self.skills]}
        if sk in self._skills_added:
            return {"ok": True, "already": True, "instructions": skill_text(sk)}
        self._skills_added.append(sk)
        log.info("skill loaded: %s", sk["name"])
        self.ctl.skill_loaded(sk["name"])
        try:
            await self._send(self._session_config())  # the instructions and the functions of the skill
        except Exception as e:  # noqa: BLE001 — the answer below still carries the instructions
            log.warning("session.update with the skill failed: %s", e)
        return {"ok": True, "skill": sk["name"], "instructions": skill_text(sk)}

    async def _notify_sms(self, text: str, skill: str) -> dict:
        loaded = [x for x in self.skills_loaded + self._skills_added if x.get("sms_to")]
        sk = next((x for x in loaded if skill and x["name"].lower() == skill.strip().lower()), None) or (loaded[0] if loaded else None)
        if not sk or not text.strip():
            return {"ok": False, "error": "нет подключённого скилла с SMS или пустой текст"}
        try:
            await self.ctl.skill_sms(sk["sms_to"], text.strip()[:600], sk["name"])
            return {"ok": True, "sent_to": "владельцу"}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": str(e)}

    async def _hangup_after_speech(self, reason: str):
        # let the agent finish the goodbye phrase before hanging up
        await asyncio.sleep(1.0)
        for _ in range(300):
            if not self._responding and not self._fish_busy() and self.audio.pending_ms == 0:
                break
            await asyncio.sleep(0.1)
        await asyncio.sleep(0.4)
        await self.ctl.hangup(reason or "agent")


def _deep_merge(dst: dict, src: dict):
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            _deep_merge(dst[k], v)
        else:
            dst[k] = v


class VoiceTestError(Exception):
    pass


async def synthesize_sample(settings: dict, voice: str, text: str, model: str = "",
                            phone: bool = False, role: str = "", speed: float = 1.0,
                            kind: str = "voice_test") -> tuple[bytes, int]:
    """Have the realtime model say `text` with `voice`; returns (pcm16 mono, sample rate).

    Goes through the same Realtime API as a real call, so what you hear is what callers get.
    With phone=True the audio is converted like on a call: 8 kHz + the agent output gain."""
    if not settings.get("yandex.api_key") or not settings.get("yandex.folder_id"):
        raise VoiceTestError("Не заданы API-ключ и ID каталога (Настройки → Yandex AI Studio)")
    agent = {"voice": voice or "dasha", "voice_role": role, "voice_speed": speed, "model": model,
             "speaks_first": True, "tools": []}
    probe = AgentSession.__new__(AgentSession)  # reuse URL / auth / session config building
    probe.s, probe.agent = settings, agent
    probe.fish_mode = False  # the sample is always the Yandex voice
    probe._greet_note = ""   # (fields _session_config reads; __init__ isn't run for the probe)
    probe.skills, probe.skills_loaded, probe._skills_added = [], [], []
    probe.rate = int(settings.get("audio.agent_rate") or 16000)
    probe.instructions = ("Ты диктор. Произнеси дословно текст из кавычек, естественно и с живой интонацией, "
                          f"без приветствий и комментариев: «{text}»")
    config = probe._session_config()
    config["session"]["audio"]["input"].pop("turn_detection", None)

    pcm = bytearray()
    timeout = aiohttp.ClientTimeout(total=40, connect=10)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as http:
            async with http.ws_connect(probe._url(), headers=probe._headers()) as ws:
                await ws.send_json(config)
                await ws.send_json({"type": "response.create"})
                async for msg in ws:
                    if msg.type != aiohttp.WSMsgType.TEXT:
                        break
                    ev = json.loads(msg.data)
                    t = ev.get("type", "")
                    if t in ("response.output_audio.delta", "response.audio.delta"):
                        pcm.extend(base64.b64decode(ev.get("delta") or ""))
                    elif t == "error":
                        err = ev.get("error") or ev
                        raise VoiceTestError(err.get("message") if isinstance(err, dict) else str(err))
                    elif t == "response.done":
                        u = (ev.get("response") or {}).get("usage") or {}
                        db.log_usage("yandex", kind, tokens_in=u.get("input_tokens") or 0,
                                     tokens_out=u.get("output_tokens") or 0)
                        break
    except aiohttp.WSServerHandshakeError as e:
        raise VoiceTestError(f"Yandex отклонил подключение: {e.status} {e.message}")
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        raise VoiceTestError(f"Нет связи с Yandex AI Studio: {e}")
    if not pcm:
        raise VoiceTestError("Модель не вернула звук")
    rate = probe.rate
    if phone:
        pcm = bytearray(apply_gain(Resampler(rate, MODEM_RATE).process(bytes(pcm)),
                                   float(settings.get("audio.tx_gain") or 1.0)))
        rate = MODEM_RATE
    return bytes(pcm), rate
