"""Call state machine: dialing / ringing / active, agent bridge, queue."""
import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime

from . import ambience, config, db, greetings, history_chat, summary, transcribe
from .agent.realtime import AgentSession, greeting_note
from .events import hub
from .modem import parsers as P
from .modem.at import ATError
from .modem.audio import AudioPort, MockAudioPort
from .modem.manager import AUDIO_LINK, modem, resolve_port

log = logging.getLogger("calls")

RING_PERIOD = 5  # s between rings (GSM cadence ~1 s on / 4 s off): «answer after N rings» = (N-1) periods
PREPARE_TIMEOUT = 10  # s: an outgoing call is dialed only once the agent is ready (connections + greeting)
TERMINAL = {"completed", "missed", "rejected", "busy", "no_answer", "failed", "cancelled"}


class LineBusy(Exception):
    pass


class AgentNotReady(Exception):
    """The agent could not be prepared (connections / greeting), so the number was not dialed."""


@dataclass
class ActiveCall:
    id: int
    direction: str
    number: str
    state: str                      # dialing | ringing | answering | active
    agent_id: int | None = None
    script_id: int | None = None
    variables: dict = field(default_factory=dict)
    rings: int = 0
    answered: bool = False
    audio: AudioPort | None = None
    session: AgentSession | None = None
    tasks: list = field(default_factory=list)
    result: dict = field(default_factory=dict)
    finishing: bool = False
    hangup_status: str = ""
    browser: bool = False           # audio goes to the operator's browser instead of an agent
    routed: bool = False            # inbound: script/agent chosen by the caller's number
    dialed: bool = False            # outgoing: ATD sent (the agent is prepared first)
    ring_started: float = 0.0       # incoming: loop time of the first RING
    prepared_for: tuple = ()        # (agent_id, script_id) the session was started for before the answer
    history: bool = True            # the agent knows the previous calls with this number
    prompt: str = ""                # this call's own task, on top of the script (e.g. from the assistant)

    def public(self) -> dict:
        return {"id": self.id, "direction": self.direction, "number": self.number,
                "state": self.state, "agent_id": self.agent_id, "script_id": self.script_id,
                "rings": self.rings, "browser": self.browser,
                "agent_active": self.session is not None and not self.session.closed and self.session.live}


def render_template(text: str, variables: dict) -> str:
    return re.sub(r"\{\{\s*(\w+)\s*\}\}", lambda m: str(variables.get(m.group(1), m.group(0))), text or "")


def template_variables(text: str) -> list[str]:
    return list(dict.fromkeys(re.findall(r"\{\{\s*(\w+)\s*\}\}", text or "")))


CALL_TOOLS = ("hangup_call", "save_result", "send_dtmf")
DEFAULT_SCRIPT_TOOLS = ["hangup_call", "save_result"]


def effective_tools(agent: dict, script: dict | None) -> list[str]:
    """Functions available in a call — the script decides («что нужно сделать»); the agent is only the voice and
    the character. Without a script: the agent's old list (calls before scripts had their own)."""
    if not script:
        return [t for t in (agent.get("tools") or DEFAULT_SCRIPT_TOOLS) if t in CALL_TOOLS]
    wanted = script.get("call_tools")
    return [t for t in (DEFAULT_SCRIPT_TOOLS if wanted is None else wanted) if t in CALL_TOOLS]


def script_skills(script: dict | None) -> tuple[list[dict], list[dict]]:
    """The script's skills: (loaded from the start, loaded on demand)."""
    ids = [i for i in (script or {}).get("skills") or [] if isinstance(i, int)]
    rows = [db.get("skills", i) for i in ids]
    rows = [x for x in rows if x and (x.get("name") or "").strip()]
    return [x for x in rows if x.get("always")], [x for x in rows if not x.get("always")]


def owner_text() -> str:
    """The owner's card («Этот номер») for a skill allowed to know it: the address and the other fields."""
    c = db.self_contact() or {}
    rows = [("Адрес", c.get("address")), ("Телефон", spoken_phone(c.get("phone") or "") if c.get("phone") else ""),
            *db.contact_fields(c), ("Комментарий", c.get("notes"))]
    lines = [f"- {k}: {str(v).strip()}" for k, v in rows if v and str(v).strip()]
    if not any(k == "Адрес" for k, v in rows if v):
        lines.insert(0, "- Адрес: не указан — скажи, что уточнишь у хозяина и пришлёшь SMS")
    return ("Данные хозяина (карточка «Этот номер») — называй их только в рамках этого скилла и только тому, кому "
            "они нужны по делу:\n" + "\n".join(lines))


def skill_text(skill: dict) -> str:
    """What the agent gets when a skill is loaded."""
    parts = [f"Скилл «{skill['name']}»" + (f" (когда {skill['trigger'].strip().rstrip('.')})" if skill.get("trigger") else "")
             + ":\n" + (skill.get("instructions") or "").strip()]
    if skill.get("collect"):
        parts.append("Узнай у собеседника и сохрани в итог (save_result, в поле data): " + ", ".join(skill["collect"]) + ".")
    if skill.get("sms_to"):
        parts.append("Когда всё нужное узнаешь, отправь короткую сводку функцией notify_sms (одним сообщением, "
                     "без лишних слов) — её получит владелец.")
    if skill.get("knows_owner"):
        parts.append(owner_text())
    return "\n".join(p for p in parts if p.strip())


def _persona_name(agent: dict) -> str:
    """'Алина — ассистент' -> 'Алина': the agent's name without the description after a dash."""
    return (agent.get("name") or "").split("—")[0].split(" - ")[0].strip()


def own_number() -> str:
    """The SIM's phone number: from the settings (Оператор), else what the modem reports (often nothing)."""
    return db.normalize_phone(db.setting("modem.own_number", "") or "") or (modem.info or {}).get("own_number") or ""


def spoken_phone(number: str) -> str:
    """+79161234567 -> '+7 916 123-45-67' — the way a person says a number."""
    d = re.sub(r"\D", "", number)
    if len(d) == 11 and d[0] in "78":
        return f"+7 {d[1:4]} {d[4:7]}-{d[7:9]}-{d[9:]}"
    return number


def contact_variables(contact: dict | None) -> dict:
    """Built-in {{contact_*}} variables for scripts."""
    c = contact or {}
    return {"contact_name": c.get("name") or "", "contact_last_name": c.get("last_name") or "",
            "contact_full_name": db.contact_label(c), "contact_company": c.get("company") or "",
            "contact_email": c.get("email") or "", "contact_notes": c.get("notes") or "",
            "contact_relation": c.get("relation") or ""}


def contact_brief(contact: dict | None) -> str:
    """What the phone book knows about the other person, for the agent."""
    if not contact:
        return ""
    rows = [("Имя", contact.get("name")), ("Фамилия", contact.get("last_name")),
            ("Кем приходится владельцу этого телефона (тому, от чьего имени ты говоришь)", contact.get("relation")),
            ("Адрес", contact.get("address")),
            ("Компания", contact.get("company")), ("Телефон", contact.get("phone")), ("Почта", contact.get("email")),
            ("Теги", contact.get("tags")), ("Комментарий", contact.get("notes")), *db.contact_fields(contact)]
    lines = [f"- {k}: {str(v).strip()}" for k, v in rows if v and str(v).strip()]
    if not lines:
        return ""
    return ("Что известно о собеседнике (из телефонной книги):\n" + "\n".join(lines)
            + "\nИспользуй эти сведения, чтобы разговор был личным и по делу: обращайся по имени, учитывай "
              "комментарий и контекст. Не зачитывай их дословно и не пересказывай собеседнику служебные заметки.")


def first_phrase(agent: dict, script: dict | None, variables: dict) -> str:
    """The agent's opening line for this call ('' if it waits for the other person)."""
    if not agent.get("speaks_first", True):
        return ""
    return greetings.render((script or {}).get("first_message") or agent.get("greeting") or "", variables)


def build_instructions(agent: dict, script: dict | None, variables: dict, direction: str,
                       number: str, tools: list[str] | None = None, contact: dict | None = None,
                       with_first: bool = True, history: str = "", prompt: str = "",
                       skills: tuple[list[dict], list[dict]] | None = None) -> str:
    """One coherent prompt: who the agent is (character) -> what to do in this call (script)
    -> how to behave on the phone (only the functions this call really has).

    with_first=False leaves out the opening line: in a call the session adds it itself, depending on
    whether the pre-synthesized greeting has already been played (see AgentSession.go_live)."""
    parts = []

    # 1. who is speaking
    character = (agent.get("instructions") or "").strip()
    intro = f"Ты — {(agent.get('role') or 'голосовой ассистент').strip().rstrip('.')}."
    name = _persona_name(agent)
    if name:
        intro += f" Тебя зовут {name}."
    me = db.self_contact() or {}
    owner = db.contact_label(me) if (me.get("name") or "").strip() not in ("", db.SELF_NAME) else ""
    if owner:
        intro += f" Хозяина этого телефона, от чьего имени ты говоришь, зовут {owner}."
    mine = own_number()
    if mine:
        intro += (f" Твой номер телефона — {spoken_phone(mine)}"
                  + (" (с него ты звонишь)" if direction != "in" else " (на него тебе позвонили)")
                  + ". Называй его, если спросят, по цифрам, без ошибок.")
    parts.append(intro + ("\n" + character if character else ""))

    # 2. this call's task
    who = variables.get("contact_full_name") or variables.get("contact_name") or ""
    if direction == "in":
        call = f"Тебе звонит {who}." if who else "Тебе позвонили по телефону."
    else:
        call = f"Сейчас ты звонишь по телефону. Собеседник — {who}." if who else "Сейчас ты звонишь человеку по телефону."
    task = render_template((script or {}).get("prompt") or "", variables).strip()
    parts.append(call + ("\nЗадача этого звонка:\n" + task if task else ""))
    if prompt.strip():
        parts[-1] += ("\nОсобое задание на этот звонок (от владельца телефона, важнее общего сценария):\n"
                      + prompt.strip())
    first = first_phrase(agent, script, variables)
    if first and with_first:
        parts[-1] += "\n" + greeting_note(first, said=False)
    brief = contact_brief(contact)
    if brief:
        parts.append(brief)
    if history:
        parts.append("Прошлые разговоры с этим человеком (от старых к новым):\n" + history
                     + "\nУчитывай прошлые договорённости и то, о чём уже говорили: не спрашивай заново то, что уже "
                       "известно, продолжай с того места. Не пересказывай историю без нужды и не говори, что у тебя "
                       "есть записи или расшифровки разговоров — веди себя как человек, который помнит прошлые звонки.")

    # 2b. skills: loaded ones in full, the rest as «name — when» to load with use_skill
    always, on_demand = skills if skills is not None else script_skills(script)
    for sk in always:
        parts.append(skill_text(sk))
    if on_demand:
        parts.append("Скиллы, которые можно подключить по ходу разговора:\n"
                     + "\n".join(f"- {sk['name']}: {(sk.get('trigger') or 'по ситуации').strip()}" for sk in on_demand)
                     + "\nКак только из слов собеседника понятно, что подходит скилл, сразу вызови use_skill с его "
                       "названием — в этом же ответе, до любых слов, — получишь инструкцию и ответишь уже по ней. "
                       "Никогда не говори «сейчас подключу», «уточню информацию», «подождите» и не упоминай скиллы: "
                       "для собеседника ты просто знаешь, что ответить.")

    # 3. phone manners + only the functions that exist in this call
    tools = effective_tools(agent, script) if tools is None else tools
    rules = ["Говори как в живом телефонном разговоре: коротко, одна мысль за реплику, без списков и разметки.",
             "Здоровайся только один раз, в начале разговора. Если собеседник перебил приветствие или переспросил "
             "«алло?», не здоровайся снова — продолжай разговор с того места."]
    if "hangup_call" in tools:
        rules.append("Когда задача выполнена или собеседник хочет закончить — попрощайся и вызови функцию hangup_call.")
    else:
        rules.append("Ты не можешь сама завершить звонок: попрощайся и дождись, пока собеседник положит трубку. "
                     "Не пиши «завершить звонок» и не изображай завершение словами.")
    if "save_result" in tools:
        rules.append("Перед тем как попрощаться, сохрани итог разговора вызовом функции save_result.")
    if "send_dtmf" in tools:
        rules.append("Если попадёшь в голосовое меню, выбирай пункты функцией send_dtmf.")
    if tools:
        rules.append("Функции вызывай только как функции, молча. Никогда не пиши в ответе их названия, параметры, "
                     "JSON, фигурные скобки или служебные слова вроде «сохраняю итог» и «завершить звонок»: "
                     "всё, что ты пишешь, зачитывается собеседнику вслух.")
    parts.append("Как вести разговор:\n" + "\n".join(f"- {r}" for r in rules))

    # 4. facts
    now = datetime.now()
    facts = f"Сегодня {now:%d.%m.%Y}, {now:%H:%M}."
    if number:
        facts += f" Номер собеседника: {number}."
    elif direction == "in":
        facts += " Номер собеседника скрыт."
    parts.append(facts)
    return "\n\n".join(parts)


class BrowserAudio:
    """The single browser tab that currently acts as the handset (WS /api/calls/audio)."""

    def __init__(self):
        self.queue: asyncio.Queue | None = None
        self.loop = None

    def attach(self) -> asyncio.Queue:
        if self.queue is not None:
            self.queue.put_nowait(None)  # tell the previous tab to disconnect
        self.loop = asyncio.get_running_loop()
        self.queue = asyncio.Queue(maxsize=50)
        return self.queue

    def detach(self, q: asyncio.Queue):
        if self.queue is q:
            self.queue = None

    @property
    def connected(self) -> bool:
        return self.queue is not None

    def push(self, frame: bytes):
        """Called from the modem audio thread with 20 ms of caller audio."""
        q = self.queue
        if q is not None and self.loop is not None:
            self.loop.call_soon_threadsafe(self._put, q, frame)

    @staticmethod
    def _put(q: asyncio.Queue, frame: bytes):
        if q.full():
            q.get_nowait()
        q.put_nowait(frame)


class CallManager:
    def __init__(self):
        self.current: ActiveCall | None = None
        self._queue_task = None
        self.browser_audio = BrowserAudio()

    async def start(self):
        modem.on_call_urc = self.on_urc
        # calls left in a non-terminal state after a crash/restart
        db.execute("UPDATE calls SET status='failed', error='прервано перезапуском' "
                   "WHERE status IN ('dialing','ringing','answering','active')")
        self._queue_task = asyncio.create_task(self._queue_worker())

    async def stop(self):
        if self._queue_task:
            self._queue_task.cancel()
        if self.current:
            await self.hangup("shutdown")

    # ------------------------------------------------------------ public API

    def active(self) -> dict | None:
        return self.current.public() if self.current else None

    async def dial(self, number: str, agent_id=None, script_id=None, variables=None,
                   queue: bool = False, scheduled_at: str | None = None, no_agent: bool = False,
                   browser: bool = False, history: bool = True, prompt: str = "") -> dict:
        number = db.normalize_phone(number)
        if not number:
            raise ValueError("пустой номер")
        if browser and (queue or scheduled_at):
            raise ValueError("звонок через браузер нельзя поставить в очередь")
        if no_agent or browser:
            agent_id = script_id = None
        else:
            agent_id, script_id = self._resolve_agent(agent_id, script_id)
        contact = db.find_contact(number)
        variables = dict(variables or {})
        row = {
            "direction": "out", "number": number, "contact_id": contact["id"] if contact else None,
            "agent_id": agent_id, "script_id": script_id, "variables": variables,
            "created_at": db.now(), "scheduled_at": scheduled_at,
            "mode": "browser" if browser else ("none" if no_agent else "agent"),
            "history": bool(history),
            "prompt": "" if (browser or no_agent) else (prompt or "").strip(),
        }
        if queue or scheduled_at or self.current:
            if not queue and not scheduled_at:
                raise LineBusy("линия занята")
            call = db.insert("calls", {**row, "status": "queued"})
            hub.publish("call.updated", call)
            return call
        call = db.insert("calls", {**row, "status": "dialing", "started_at": db.now()})
        await self._dial(call)
        return db.get("calls", call["id"])

    async def answer(self, agent_id=None, script_id=None, browser: bool = False):
        c = self.current
        if not c or c.direction != "in" or c.state != "ringing":
            raise ValueError("нет входящего звонка")
        if browser:
            c.browser = True
            c.agent_id = c.script_id = None
            db.update("calls", c.id, {"agent_id": None, "script_id": None, "mode": "browser"})
        elif agent_id is not None or script_id is not None:
            c.agent_id, c.script_id = self._resolve_agent(agent_id, script_id)
            db.update("calls", c.id, {"agent_id": c.agent_id, "script_id": c.script_id})
        await self._answer(c)

    async def hangup(self, reason: str = "user"):
        c = self.current
        if not c:
            return
        log.info("hangup call %s (%s)", c.id, reason)
        status = "completed" if c.answered else ("rejected" if c.direction == "in" else "cancelled")
        c.hangup_status = status  # first: a call still being prepared must not be dialed after this
        if c.direction == "out" and not c.dialed:
            await self._finish(c, status)  # nothing was dialed yet — nothing to hang up in the modem
            return
        try:
            await modem.cmd("AT+CHUP", timeout=5)
        except ATError as e:
            log.warning("CHUP failed: %s", e)
        # the modem normally reports VOICE CALL: END; don't wait forever for it
        await asyncio.sleep(2)
        if self.current is c:
            await self._finish(c, status)

    async def send_dtmf(self, digits: str):
        for d in digits:
            if d in "0123456789*#ABCD":
                await modem.cmd(f"AT+VTS={d}", timeout=5)
                await asyncio.sleep(0.15)

    def browser_input(self, pcm: bytes):
        """Microphone audio (8 kHz PCM16) from the browser handset."""
        c = self.current
        if c and c.browser and c.audio:
            c.audio.play(pcm, max_ms=300)

    def add_message(self, role: str, text: str):
        c = self.current
        if not c:
            return
        msg = db.insert("call_messages", {"call_id": c.id, "role": role, "text": text, "ts": db.now()})
        hub.publish("call.message", msg)

    async def skill_sms(self, to: str, text: str, skill: str = ""):
        """A skill's SMS summary (notify_sms) to the number set in the skill."""
        c = self.current
        await modem.send_sms(to, text)
        self.add_message("system", f"SMS от скилла «{skill}» на {to}: {text}")
        log.info("call %s: skill %s sent an SMS to %s", c.id if c else "-", skill, to)

    def skill_loaded(self, name: str):
        self.add_message("system", f"⚙ Подключён скилл «{name}»")

    def save_result(self, data: dict):
        c = self.current
        if not c:
            return
        c.result.update(data)
        db.update("calls", c.id, {"result": c.result, "summary": data.get("summary", "")})

    # ------------------------------------------------------------ internals

    def _resolve_agent(self, agent_id, script_id):
        if script_id and not agent_id:
            script = db.get("scripts", int(script_id))
            if script:
                agent_id = script.get("default_agent_id")
        if not agent_id:
            first = db.fetch_one("agents", "SELECT * FROM agents ORDER BY id LIMIT 1")
            agent_id = first["id"] if first else None
        return (int(agent_id) if agent_id else None, int(script_id) if script_id else None)

    @staticmethod
    def route_inbound(number: str) -> tuple[int | None, int | None, str]:
        """Pick (agent_id, script_id, reason) for an incoming call.

        Among scripts for inbound/any calls the most specific wins: the exact number, then a contact from the
        phone book, then a number prefix, then a script for all callers; otherwise the defaults from
        Settings → Calls. Same level — the older script."""
        default_agent = db.setting("calls.inbound_agent_id")
        default_script = db.setting("calls.inbound_script_id")
        scripts = db.fetch_all("scripts", "SELECT * FROM scripts WHERE direction IN ('inbound','any') ORDER BY id")
        contact = db.find_contact(number) if number else None

        def pick(s, why):
            return s.get("default_agent_id") or default_agent, s["id"], f"сценарий «{s['name']}» выбран: {why}"
        numbered = [s for s in scripts if (s.get("inbound_scope") or "numbers") == "numbers"]
        if number:
            for s in numbered:
                for pattern in s.get("inbound_numbers") or []:
                    if not pattern.endswith("*") and db.number_matches(pattern, number):
                        return pick(s, f"по номеру ({pattern})")
        if contact:
            for s in scripts:
                if s.get("inbound_scope") == "contacts" and contact["id"] in (s.get("inbound_contacts") or []):
                    return pick(s, f"абонент из контактов ({db.contact_label(contact)})")
        if number:
            for s in numbered:
                for pattern in s.get("inbound_numbers") or []:
                    if pattern.endswith("*") and db.number_matches(pattern, number):
                        return pick(s, f"по префиксу номера ({pattern})")
        for s in scripts:
            if s.get("inbound_scope") == "all":
                return pick(s, "для всех входящих")
        if default_script or default_agent:
            return default_agent, default_script, "сценарий по умолчанию для входящих"
        return None, None, "для этого номера нет сценария и агента по умолчанию"

    def _maybe_auto_answer(self, c: ActiveCall):
        if (c.direction == "in" and c.state == "ringing" and c.agent_id
                and db.setting("calls.auto_answer", True)
                and c.rings >= int(db.setting("calls.answer_after_rings", 2))):
            asyncio.create_task(self._answer(c))

    def _publish(self, c: ActiveCall | None = None):
        row = db.get("calls", c.id) if c else None
        hub.publish("call.state", {"active": self.active(), "call": row})

    def _route(self, c: ActiveCall):
        c.agent_id, c.script_id, reason = self.route_inbound(c.number)
        c.routed = True
        db.update("calls", c.id, {"agent_id": c.agent_id, "script_id": c.script_id})
        log.info("call %s from %s: %s", c.id, c.number or "hidden", reason)
        self.add_message("system", reason[:1].upper() + reason[1:])
        self._prepare(c)
        if c.agent_id and db.setting("calls.auto_answer", True):
            c.tasks.append(asyncio.create_task(self._auto_answer_later(c)))

    async def _auto_answer_later(self, c: ActiveCall):
        """Auto-answer by time: the modem may send RING only once, so counting RINGs isn't reliable. Waits
        «N rings» worth of time from the first RING, and up to 3 s more for the warmed-up agent (greeting)."""
        loop = asyncio.get_running_loop()
        rings = int(db.setting("calls.answer_after_rings", 2))
        await asyncio.sleep(max(0.0, c.ring_started + (rings - 1) * RING_PERIOD - loop.time()))
        if c.session and not c.session.closed:
            reason = await c.session.wait_ready(3)
            if reason:
                log.info("call %s: answering before the agent is ready (%s)", c.id, reason)
        if self.current is c and c.state == "ringing" and not c.finishing:
            log.info("call %s: auto-answer", c.id)
            await self._answer(c)

    async def _dial(self, row: dict):
        c = ActiveCall(id=row["id"], direction="out", number=row["number"], state="dialing",
                       agent_id=row.get("agent_id"), script_id=row.get("script_id"),
                       variables=row.get("variables") or {}, browser=row.get("mode") == "browser",
                       history=row.get("history", 1) not in (0, False), prompt=row.get("prompt") or "")
        self.current = c
        db.update("calls", c.id, {"status": "dialing", "started_at": db.now()})
        self._publish(c)
        self._prepare(c)
        if c.agent_id and not c.browser:  # dial only when the agent can speak right away
            t0 = asyncio.get_running_loop().time()
            reason = await c.session.wait_ready(PREPARE_TIMEOUT) if c.session else "не удалось запустить агента"
            if self.current is not c or c.finishing or c.hangup_status:  # cancelled while preparing
                return
            if reason:
                error = f"Агент не готов, звонок не совершён: {reason}"
                log.warning("call %s: %s", c.id, error)
                self.add_message("system", error)
                await self._finish(c, "failed", error=error)
                raise AgentNotReady(error)
            log.info("call %s: agent ready in %.1f s", c.id, asyncio.get_running_loop().time() - t0)
        log.info("dialing %s (call %s)", c.number, c.id)
        c.dialed = True
        try:
            await modem.cmd(f"ATD{c.number};", timeout=30)
        except ATError as e:
            await self._finish(c, "failed", error=str(e))
            return
        c.tasks.append(asyncio.create_task(self._dial_timeout(c)))

    async def _dial_timeout(self, c: ActiveCall):
        await asyncio.sleep(int(db.setting("calls.dial_timeout", 60)))
        if self.current is c and not c.answered:
            log.info("dial timeout for call %s", c.id)
            try:
                await modem.cmd("AT+CHUP")
            except ATError:
                pass
            await self._finish(c, "no_answer")

    async def _answer(self, c: ActiveCall):
        c.state = "answering"
        self._publish(c)
        try:
            await modem.cmd("ATA", timeout=15)
        except ATError as e:
            log.error("ATA failed: %s", e)
            if self.current is c and not c.answered:
                c.state = "ringing"
                self._publish(c)

    def on_urc(self, line: str):
        c = self.current
        if line == "RING" or line.startswith(("+CRING", "+CLIP", "VOICE CALL", "MISSED_CALL", "NO CARRIER")):
            log.info("modem: %s", line)
        if line == "RING" or line.startswith("+CRING"):
            if c is None:
                # the caller's number arrives right after the first RING (+CLIP);
                # the script is chosen once it is known
                row = db.insert("calls", {"direction": "in", "number": "", "status": "ringing",
                                          "started_at": db.now(), "created_at": db.now()})
                c = self.current = ActiveCall(id=row["id"], direction="in", number="", state="ringing",
                                              ring_started=asyncio.get_running_loop().time(),
                                              history=bool(db.setting("calls.inbound_history", True)))
                db.update("calls", c.id, {"history": c.history})
                log.info("incoming call %s", c.id)
            if c.direction != "in" or c.state != "ringing":
                return
            c.rings += 1
            if not c.routed and c.rings >= 2:  # hidden number: no +CLIP will come
                self._route(c)
            self._publish(c)
            if c.routed:
                self._maybe_auto_answer(c)
        elif line.startswith("+CLIP:"):
            if c and c.direction == "in" and not c.number:
                c.number = db.normalize_phone(P.parse_clip(line)) or P.parse_clip(line)
                contact = db.find_contact(c.number)
                db.update("calls", c.id, {"number": c.number,
                                          "contact_id": contact["id"] if contact else None})
                if not c.routed:
                    self._route(c)
                self._publish(c)
                hub.publish("call.incoming", {"id": c.id, "number": c.number,
                                              "contact": db.contact_label(contact) or None})
                self._maybe_auto_answer(c)
        elif line.startswith("VOICE CALL: BEGIN"):
            if c and not c.answered:
                asyncio.create_task(self._on_connected(c))
        elif line.startswith("VOICE CALL: END") or line in ("NO CARRIER", "BUSY", "NO ANSWER") \
                or line.startswith("MISSED_CALL"):
            if not c:
                return
            if c.hangup_status:
                status = c.hangup_status
            elif c.answered:
                status = "completed"
            elif c.direction == "in":
                status = "missed"
            else:
                status = {"BUSY": "busy", "NO ANSWER": "no_answer"}.get(line, "no_answer")
            asyncio.create_task(self._finish(c, status))

    async def _on_connected(self, c: ActiveCall):
        c.answered = True
        c.state = "active"
        db.update("calls", c.id, {"status": "active", "answered_at": db.now()})
        self._publish(c)
        log.info("call %s connected", c.id)
        await self._start_media(c)

    async def _open_audio(self, c: ActiveCall, s: dict) -> bool:
        try:
            if not config.MOCK:
                await modem.cmd("AT+CPCMREG=1", timeout=5)
            port_cls = MockAudioPort if config.MOCK else AudioPort
            c.audio = port_cls(resolve_port(s["modem.audio_port"], AUDIO_LINK), on_frame=lambda f: None,
                               record=bool(s.get("calls.record")))
            await asyncio.to_thread(c.audio.start)
            return True
        except Exception as e:
            log.error("audio channel failed: %s", e)
            self.add_message("system", f"Не удалось открыть аудиоканал: {e}")
            return False

    def _agent_context(self, c: ActiveCall) -> tuple[dict, str, str] | None:
        """(agent with its voice and tools, prompt, opening line) for this call; None without an agent."""
        agent = db.get("agents", c.agent_id) if c.agent_id else None
        if not agent:
            return None
        script = db.get("scripts", c.script_id) if c.script_id else None
        contact = db.find_contact(c.number) if c.number else None
        now = datetime.now()
        variables = {"phone": c.number, **contact_variables(contact),
                     "today": now.strftime("%d.%m.%Y"), "now": now.strftime("%H:%M"),
                     **{v.get("name"): v.get("default", "") for v in (script or {}).get("variables") or []
                        if isinstance(v, dict) and v.get("name")},
                     **c.variables}
        tools = effective_tools(agent, script)
        past = history_chat.past_calls_brief(c.number, exclude_call_id=c.id) if c.history and c.number else ""
        always, on_demand = script_skills(script)
        if any(sk.get("collect") for sk in always + on_demand) and "save_result" not in tools:
            tools = tools + ["save_result"]  # a skill that collects data saves it to the result
        instructions = build_instructions(agent, script, variables, c.direction, c.number, tools, contact, prompt=c.prompt,
                                          with_first=False, history=past, skills=(always, on_demand))
        greeting = first_phrase(agent, script, variables)
        # the model only gets the functions this call needs; the voice comes from Голоса; skills load on demand
        return ({**agent, **db.agent_voice(agent), "tools": tools, "skills": on_demand,
                 "skills_loaded": always}, instructions, greeting)

    def _new_session(self, c: ActiveCall, s: dict) -> AgentSession | None:
        ctx = self._agent_context(c)
        if not ctx:
            return None
        agent, instructions, greeting = ctx
        c.session = AgentSession(self, None, agent, instructions, s, direction=c.direction, greeting=greeting)
        c.prepared_for = (c.agent_id, c.script_id)
        c.tasks.append(asyncio.create_task(self._run_session(c, c.session)))
        return c.session

    def _prepare(self, c: ActiveCall):
        """Warm start, before the answer (dialing / ringing): the agent session connects to Yandex and Fish and
        synthesizes the greeting, so the agent speaks right after pickup. Closed with the call if nobody answers."""
        if c.browser or c.session or not c.agent_id or self.current is not c:
            return
        try:
            if self._new_session(c, db.get_settings()):
                log.info("call %s: agent session is warming up", c.id)
        except Exception:  # noqa: BLE001 — _start_media will try again after the answer
            log.exception("warm start failed")

    async def _drop_session(self, c: ActiveCall):
        if c.session:
            sess, c.session = c.session, None
            await sess.close()

    async def _start_media(self, c: ActiveCall):
        s = db.get_settings()
        if c.browser:
            await self._drop_session(c)  # answered in the browser: the warmed-up agent isn't needed
            if await self._open_audio(c, s):
                c.audio.on_frame = self.browser_audio.push
                self.add_message("system", "Разговор через браузер"
                                 + ("" if self.browser_audio.connected else " — откройте интерфейс, чтобы подключить звук"))
                self._publish(c)
            return
        agent = db.get("agents", c.agent_id) if c.agent_id else None
        if not agent:
            await self._drop_session(c)
            self.add_message("system", "Звонок без голосового агента")
            return
        if c.session and (c.session.closed or c.prepared_for != (c.agent_id, c.script_id)):
            await self._drop_session(c)  # failed while ringing, or answered with another agent / script
        if not await self._open_audio(c, s):
            return
        session = c.session or self._new_session(c, s)
        c.audio.on_frame = session.feed
        session.go_live(c.audio)
        self._start_ambience(c)
        self._publish(c)
        max_dur = int(agent.get("max_duration_sec") or 0)
        if max_dur > 0:
            c.tasks.append(asyncio.create_task(self._max_duration(c, max_dur)))

    def _start_ambience(self, c: ActiveCall):
        """The script's background sound (incoming and outgoing calls alike). It goes only to the modem (and the
        recording) — the recognition hears the caller only."""
        script = db.get("scripts", c.script_id) if c.script_id else None
        sound_id, samples, gain = ambience.for_call((script or {}).get("ambience"))
        if samples is not None and gain > 0:
            c.audio.set_ambience(samples, gain)
            log.info("call %s: background sound %s at %.2f", c.id, sound_id, gain)
            db.update("calls", c.id, {"ambience": sound_id})  # 'random' → the sound it picked

    async def _run_session(self, c: ActiveCall, session: AgentSession):
        try:
            await session.run()
            log.info("agent session for call %s closed", c.id)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.error("agent session failed: %s", e)
            self.add_message("system", f"Ошибка подключения к агенту: {e}")
            db.update("calls", c.id, {"error": str(e)})
        if self.current is c:
            self._publish(c)

    async def _max_duration(self, c: ActiveCall, seconds: int):
        await asyncio.sleep(seconds)
        if self.current is c:
            self.add_message("system", f"Превышена максимальная длительность ({seconds} c)")
            await self.hangup("max_duration")

    async def _finish(self, c: ActiveCall, status: str, error: str = ""):
        if c.finishing:
            return
        c.finishing = True
        log.info("call %s finished: %s", c.id, status)
        for t in c.tasks:
            if t is not asyncio.current_task():
                t.cancel()
        if c.session:
            await c.session.close()
        recording = ""
        if c.audio:
            c.audio.stop()
            if not config.MOCK:
                try:
                    await modem.cmd("AT+CPCMREG=0", timeout=3)
                except ATError:
                    pass
            path = config.RECORDINGS_DIR / f"call_{c.id}.wav"
            try:
                if await asyncio.to_thread(c.audio.save_wav, path):
                    recording = path.name
            except Exception as e:
                log.warning("cannot save recording: %s", e)
        row = db.get("calls", c.id) or {}
        ended = db.now()
        duration = 0
        if row.get("answered_at"):
            duration = int((datetime.fromisoformat(ended) - datetime.fromisoformat(row["answered_at"])).total_seconds())
        upd = {"status": status, "ended_at": ended, "duration": duration, "recording": recording}
        if c.session and getattr(c.session, "usage", None):
            u = c.session.usage  # Yandex tokens / Fish credits of this call
            upd.update(u)
            db.log_usage("yandex", "call", tokens_in=u["tokens_in"], tokens_out=u["tokens_out"], call_id=c.id)
            db.log_usage("fish", "call", credits=u["fish_credits"], chars=u["fish_chars"], call_id=c.id)
        if error:
            upd["error"] = error
        db.update("calls", c.id, upd)
        if self.current is c:
            self.current = None
        self._publish(c)
        hub.publish("call.ended", db.get("calls", c.id))
        asyncio.create_task(transcribe.after_call(c.id))  # a browser call is transcribed first, then summarized

    async def _queue_worker(self):
        while True:
            await asyncio.sleep(3)
            try:
                if self.current or not modem.connected or not db.setting("calls.queue_enabled", True):
                    continue
                row = db.fetch_one(
                    "calls",
                    "SELECT * FROM calls WHERE status='queued' AND (scheduled_at IS NULL OR scheduled_at='' "
                    "OR scheduled_at <= ?) ORDER BY COALESCE(scheduled_at, created_at), id LIMIT 1",
                    (db.now(),))
                if row:
                    await self._dial(row)
                    await asyncio.sleep(5)
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("queue worker error")


calls = CallManager()
