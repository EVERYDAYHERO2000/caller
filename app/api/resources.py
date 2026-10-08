"""CRUD for agents, scripts and contacts."""
from datetime import datetime
from typing import Any, Literal

import io
import wave

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

from .. import db
from .. import fillers as voice_fillers
from .. import greetings, history_chat
from .. import voices as voices_sync
from ..audio import apply_gain
from ..agent import fish
from ..agent.realtime import VoiceTestError, synthesize_sample
from ..agent import emotions
from ..agent.realtime import FISH_INSTRUCTIONS
from ..calls import build_instructions, contact_variables, render_template, template_variables

router = APIRouter()


def _or_404(row):
    if not row:
        raise HTTPException(404, "not found")
    return row


# ---------------------------------------------------------------- agents

class AgentIn(BaseModel):
    name: str | None = None
    description: str | None = None
    role: str | None = Field(None, description="Роль агента (кто он в разговоре)")
    instructions: str | None = Field(None, description="Системный промпт агента")
    voice: str | None = Field(None, description="Голос синтеза, например dasha, alena, filipp")
    voice_role: str | None = Field(None, description="Эмоция голоса (SpeechKit role): neutral, good, evil, "
                                                     "friendly, strict, whisper…; пусто — по умолчанию")
    voice_speed: float | None = Field(None, ge=0.5, le=2.0, description="Скорость речи, 1.0 — обычная")
    model: str | None = Field(None, description="Модель Realtime API; пусто = из настроек")
    speaks_first: bool | None = None
    greeting: str | None = None
    greeting_delay_ms: int | None = Field(None, ge=0, le=5000, description="Исходящий звонок: пауза между ответом "
                                          "абонента и приветствием агента (человек подносит телефон к уху)")
    vad_threshold: float | None = Field(None, ge=0, le=1)
    silence_ms: int | None = Field(None, ge=100, le=5000)
    max_duration_sec: int | None = Field(None, ge=0)
    tools: list[str] | None = Field(None, description="hangup_call, save_result, send_dtmf")
    extra: dict[str, Any] | None = Field(None, description="Доп. поля, вливаются в session.update")
    voice_id: int | None = Field(None, description="Голос из раздела «Голоса» (GET /api/voices)")
    tts_engine: Literal["yandex", "fish"] | None = Field(
        None, description="Чем озвучивать: yandex — голос Realtime API; fish — Fish Audio (Yandex отвечает текстом)")
    fish_voice: str | None = Field(None, description="voiceId голоса Fish Audio")
    fish_voice_name: str | None = Field(None, description="Название голоса Fish (для интерфейса)")
    fish_model: str | None = Field(None, description="Модель Fish; пусто = fishaudio-s21pro-flash")
    fillers: bool | None = Field(None, description="Fish: заполнять паузу заготовкой («Ммм...») тем же голосом")
    filler_kind: Literal["short", "long", "any"] | None = None
    filler_delay_ms: int | None = Field(None, ge=0, le=3000, description="Пауза перед заготовкой после конца реплики")
    emotions_allowed: str | None = Field(None, description="Fish: интонации, которые агент может ставить тегом "
                                         "[тег] перед фразой, через запятую; пусто — без эмоций")
    emotions_forbidden: str | None = Field(None, description="Fish: интонации, которых агент избегает, через запятую")


@router.get("/agents", tags=["agents"])
def list_agents():
    return db.fetch_all("agents", "SELECT * FROM agents ORDER BY id")


@router.get("/agents/voices", tags=["agents"])
def list_voices():
    """Voices with their available roles (emotion / delivery)."""
    return [{"name": n, "lang": lang, "gender": g,
             "roles": [{"id": r, "label": db.ROLE_LABELS.get(r, r)} for r in roles]}
            for n, lang, g, roles in db.VOICE_CATALOG]


class VoiceTestIn(BaseModel):
    engine: Literal["yandex", "fish"] = "yandex"
    voice: str = Field("dasha", description="Голос Yandex или voiceId Fish Audio")
    language: str = Field("ru", description="Язык речи (Fish)")
    role: str = Field("", description="Эмоция голоса (SpeechKit role)")
    speed: float = Field(1.0, ge=0.5, le=2.0, description="Скорость речи")
    text: str = Field("Здравствуйте! Так звучит мой голос.", min_length=1, max_length=300)
    model: str = ""
    phone: bool = Field(False, description="Как услышит собеседник: 8 кГц и усиление звонка")


@router.post("/agents/voice-test", tags=["agents"],
             responses={200: {"content": {"audio/wav": {}}, "description": "WAV со звучанием голоса"}})
async def voice_test(body: VoiceTestIn):
    """Synthesize a sample phrase with the given voice (Realtime API or Fish Audio)."""
    try:
        if body.engine == "fish":
            s = db.get_settings()
            wav = await fish.synthesize(s, body.voice, body.text.strip(), body.model, body.speed, body.language)
            if not body.phone:
                return Response(wav, media_type="audio/wav")
            rate = 8000
            pcm = apply_gain(fish.wav_to_pcm(wav, rate), float(s.get("audio.tx_gain") or 1.0))
        else:
            pcm, rate = await synthesize_sample(db.get_settings(), body.voice, body.text.strip(), body.model,
                                                body.phone, body.role, body.speed)
    except (VoiceTestError, fish.FishError) as e:
        raise HTTPException(502, str(e))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    return Response(buf.getvalue(), media_type="audio/wav")


@router.get("/agents/fish-voices", tags=["agents"])
async def fish_voices(search: str = "", language: str = "ru"):
    """Поиск в библиотеке Fish Audio (голоса, совместимые с realtime-моделью); language — пусто = любой."""
    try:
        return await fish.list_voices(db.get_settings(), search.strip(), language.strip())
    except fish.FishError as e:
        raise HTTPException(502, str(e))


@router.get("/agents/{agent_id}", tags=["agents"])
def get_agent(agent_id: int):
    return _or_404(db.get("agents", agent_id))


def _with_fillers(agent: dict) -> dict:
    """Голос без хезитаций: набор генерируется фоном при сохранении агента и хранится у голоса
    (его видно и можно прослушать в разделе «Голоса»), звонок его только загружает."""
    voice = db.get("voices", agent["voice_id"]) if agent.get("voice_id") else None
    if voice and agent.get("fillers", True):
        voice_fillers.ensure(voice)
        return {**agent, "fillers_status": voice_fillers.status(voice["id"])}
    return agent


@router.post("/agents", tags=["agents"], status_code=201)
async def create_agent(body: AgentIn):
    data = body.model_dump(exclude_none=True)
    if not data.get("name"):
        raise HTTPException(422, "name is required")
    ts = db.now()
    return _with_fillers(db.insert("agents", {**data, "created_at": ts, "updated_at": ts}))


@router.put("/agents/{agent_id}", tags=["agents"])
async def update_agent(agent_id: int, body: AgentIn):
    _or_404(db.get("agents", agent_id))
    return _with_fillers(db.update("agents", agent_id, {**body.model_dump(exclude_none=True), "updated_at": db.now()}))


@router.delete("/agents/{agent_id}", tags=["agents"])
def delete_agent(agent_id: int):
    return {"deleted": db.delete("agents", agent_id)}


# ---------------------------------------------------------------- voices (Голоса)

class VoiceIn(BaseModel):
    name: str | None = Field(None, description="Название в списке")
    engine: Literal["yandex", "fish"] | None = Field(None, description="yandex — SpeechKit в Realtime API; fish — Fish Audio")
    voice: str | None = Field(None, description="Имя голоса SpeechKit (dasha, filipp…) или voiceId Fish Audio")
    role: str | None = Field(None, description="Эмоция SpeechKit (только yandex)")
    speed: float | None = Field(None, ge=0.5, le=2.0)
    model: str | None = Field(None, description="Модель Fish; пусто = fishaudio-s21pro-flash")
    language: str | None = Field(None, description="Язык речи голоса Fish (ru, en, …)")
    description: str | None = None


VOICE_FIELDS = ("id", "name", "engine", "voice", "role", "speed", "model", "description", "source", "language")


def _voice_out(v: dict, agents: int | None = None, fcounts: dict | None = None) -> dict:
    if agents is None:
        agents = db.scalar("SELECT COUNT(*) FROM agents WHERE voice_id=?", (v["id"],))
    if fcounts is None:
        fcounts = voice_fillers.counts()
    return {**{k: v.get(k) for k in VOICE_FIELDS}, "agents": agents,
            "fillers_status": voice_fillers.status(v["id"]), "fillers_count": fcounts.get(v["id"], 0)}


@router.get("/voices", tags=["voices"])
def list_voice_presets():
    """Голоса для агентов: Yandex SpeechKit (с эмоцией и скоростью) и Fish Audio."""
    used = dict(db.rows("SELECT voice_id, COUNT(*) FROM agents WHERE voice_id IS NOT NULL GROUP BY voice_id"))
    fcounts = voice_fillers.counts()
    order = "ORDER BY CASE source WHEN 'custom' THEN 0 WHEN 'personal' THEN 1 WHEN 'builtin' THEN 2 ELSE 3 END, " \
            "CASE WHEN language IN ('ru', '') THEN 0 ELSE 1 END, name"
    return [_voice_out(v, used.get(v["id"], 0), fcounts) for v in db.fetch_all("voices", f"SELECT * FROM voices {order}")]


@router.get("/voices/library", tags=["voices"])
def fish_library_status():
    """Добавлен ли стартовый набор из 50 русских голосов Fish для текущего ключа."""
    return voices_sync.status()


@router.post("/voices/library/import", tags=["voices"])
async def fish_library_import():  # async: starts a background task on the event loop
    """Добавить ещё до 50 русских голосов Fish Audio из библиотеки (фоном); остальные — поиском."""
    if not db.setting("fish.api_key"):
        raise HTTPException(400, "Не задан API-ключ Fish Audio (Настройки → Fish Audio)")
    voices_sync.start_import(force=True)
    return voices_sync.status()


@router.get("/voices/{voice_id}", tags=["voices"])
def get_voice_preset(voice_id: int):
    return _voice_out(_or_404(db.get("voices", voice_id)))


def _check_voice(data: dict):
    if data.get("engine") == "yandex" and data.get("role"):
        roles = db.VOICE_ROLES.get(data.get("voice") or "")
        if roles is not None and data["role"] not in roles:
            raise HTTPException(422, f"у голоса {data.get('voice')} нет эмоции {data['role']}")


SOUND_FIELDS = ("engine", "voice", "role", "speed", "model", "language")  # what the hesitations depend on


@router.post("/voices", tags=["voices"], status_code=201)
async def create_voice_preset(body: VoiceIn):
    data = body.model_dump(exclude_none=True)
    if not data.get("name") or not data.get("voice") or not data.get("engine"):
        raise HTTPException(422, "нужны name, engine и voice")
    _check_voice(data)
    ts = db.now()
    v = db.insert("voices", {**data, "created_at": ts, "updated_at": ts})
    voice_fillers.ensure(v)  # the default hesitations, in the background
    return _voice_out(v)


@router.put("/voices/{voice_id}", tags=["voices"])
async def update_voice_preset(voice_id: int, body: VoiceIn):
    old = _or_404(db.get("voices", voice_id))
    data = body.model_dump(exclude_none=True)
    _check_voice({**old, **data})
    v = db.update("voices", voice_id, {**data, "updated_at": db.now()})
    changed = any(str(old.get(k) or "") != str(v.get(k) or "") for k in SOUND_FIELDS)
    # the voice sounds different now — its hesitations are re-made with the same phrases
    voice_fillers.ensure(v, force=changed)
    return _voice_out(v)


@router.delete("/voices/{voice_id}", tags=["voices"])
def delete_voice_preset(voice_id: int):
    _or_404(db.get("voices", voice_id))
    used = db.fetch_all("agents", "SELECT name FROM agents WHERE voice_id=?", (voice_id,))
    if used:
        raise HTTPException(409, "Голос используют агенты: " + ", ".join(a["name"] for a in used))
    voice_fillers.delete_voice(voice_id)
    greetings.forget(voice_id)
    return {"deleted": db.delete("voices", voice_id)}


# hesitations of a voice («Ммм...», «Секундочку...») — table in the voice editor

class FillerIn(BaseModel):
    text: str = Field(..., min_length=1, max_length=120)
    kind: Literal["short", "long"] = "short"


def _filler_out(voice_id: int, f: dict) -> dict:
    return {**{k: f[k] for k in ("id", "text", "kind", "duration_ms")},
            "url": f"/api/voices/{voice_id}/fillers/{f['id']}.wav"}


@router.get("/voices/{voice_id}/fillers", tags=["voices"])
def voice_fillers_list(voice_id: int):
    """Хезитации голоса и состояние генерации: ready | generating | missing | error: …"""
    _or_404(db.get("voices", voice_id))
    return {"status": voice_fillers.status(voice_id),
            "items": [_filler_out(voice_id, f) for f in voice_fillers.list_fillers(voice_id)]}


@router.post("/voices/{voice_id}/fillers", tags=["voices"], status_code=201)
async def voice_fillers_add(voice_id: int, body: FillerIn):
    """Добавить фразу: синтезируется этим голосом и сохраняется аудиофайлом."""
    voice = _or_404(db.get("voices", voice_id))
    try:
        f = await voice_fillers.add_filler(voice, body.text, body.kind)
    except (fish.FishError, VoiceTestError) as e:
        raise HTTPException(502, str(e))
    return _filler_out(voice_id, f)


@router.delete("/voices/{voice_id}/fillers/{filler_id}", tags=["voices"])
def voice_fillers_delete(voice_id: int, filler_id: int):
    return {"deleted": voice_fillers.delete_filler(voice_id, filler_id)}


@router.post("/voices/{voice_id}/fillers/regenerate", tags=["voices"])
async def voice_fillers_regenerate(voice_id: int):  # async: starts a background task on the event loop
    """Перегенерировать все фразы голоса (фоном); пустой список — стандартный набор."""
    voice = _or_404(db.get("voices", voice_id))
    voice_fillers.ensure(voice, force=True)
    return {"status": voice_fillers.status(voice_id)}


@router.get("/voices/{voice_id}/fillers/{filler_id}.wav", tags=["voices"], include_in_schema=False)
def voice_filler_audio(voice_id: int, filler_id: int):
    path = voice_fillers.wav_path(voice_id, filler_id)
    if not path.exists():
        raise HTTPException(404, "not found")
    return Response(path.read_bytes(), media_type="audio/wav")


# ---------------------------------------------------------------- scripts

class ScriptVariable(BaseModel):
    name: str
    label: str = ""
    default: str = ""


class ScriptIn(BaseModel):
    name: str | None = None
    description: str | None = None
    direction: Literal["inbound", "outbound", "any"] | None = None
    prompt: str | None = Field(None, description="Промпт сценария, поддерживает {{переменные}}")
    first_message: str | None = None
    variables: list[ScriptVariable] | None = None
    default_agent_id: int | None = None
    call_tools: list[Literal["hangup_call", "save_result", "send_dtmf"]] | None = Field(
        None, description="Функции, нужные сценарию (пересекаются с функциями агента)")
    inbound_scope: Literal["all", "contacts", "numbers"] | None = Field(
        None, description="Кого обрабатывает входящий сценарий: all — все входящие; contacts — абоненты из "
                          "контактов (inbound_contacts); numbers — номера и префиксы (inbound_numbers)")
    inbound_contacts: list[int] | None = Field(None, description="id контактов (inbound_scope=contacts)")
    ambience: str | None = Field(None, description="Фоновый звук под голосом агента: '' — нет, id звука из "
                                                   "/ambience или 'random'")
    inbound_numbers: list[str] | None = Field(
        None, description="Номера звонящих, которые обрабатывает сценарий (входящие): "
                          "'+79161234567' или префикс '+7926*'")
    history: bool | None = Field(None, description="Агент знает предыдущие разговоры (суть и договорённости "
                                                   "прошлых звонков и SMS с этим номером)")
    skills: list[int] | None = Field(None, description="Скиллы сценария (id из /skills): агент подключает их по ситуации")


def _one_catch_all(data: dict, script_id: int | None = None):
    """Only one script may take all incoming calls — the rest (contacts, numbers) are more specific rules."""
    current = db.get("scripts", script_id) if script_id else {}
    scope = data.get("inbound_scope", (current or {}).get("inbound_scope"))
    direction = data.get("direction", (current or {}).get("direction"))
    if scope != "all" or direction == "outbound":
        return
    other = db.fetch_one("scripts", "SELECT * FROM scripts WHERE inbound_scope='all' AND direction IN ('inbound','any') "
                                    "AND id<>?", (script_id or 0,))
    if other:
        raise HTTPException(409, f"Все входящие уже обрабатывает сценарий «{other['name']}». "
                                 "Сценарий для всех входящих может быть только один.")


def _clean_numbers(data: dict) -> dict:
    if data.get("inbound_numbers") is not None:
        seen, out = set(), []
        for v in data["inbound_numbers"]:
            n = db.normalize_number_pattern(v)
            if n and n not in seen:
                seen.add(n)
                out.append(n)
        data["inbound_numbers"] = out
    return data


class RenderIn(BaseModel):
    variables: dict[str, Any] = {}
    agent_id: int | None = None
    number: str = Field("", description="Номер собеседника для предпросмотра (необязательно)")
    direction: Literal["in", "out"] | None = Field(None, description="По умолчанию — из типа сценария")


class PreviewIn(RenderIn):
    script: ScriptIn = Field(..., description="Несохранённый сценарий (текущее состояние формы)")


def _render(script: dict, body: RenderIn) -> dict:
    direction = body.direction or ("in" if script.get("direction") == "inbound" else "out")
    agent_id = body.agent_id or script.get("default_agent_id")
    if not agent_id and direction == "in":
        agent_id = db.setting("calls.inbound_agent_id")
    agent = db.get("agents", int(agent_id)) if agent_id else None
    contact = db.find_contact(body.number)
    now = datetime.now()
    # same variables a real call gets: built-ins, script defaults, then explicit values
    variables = {k: v for k, v in {"phone": body.number, **contact_variables(contact),
                                   "today": now.strftime("%d.%m.%Y"), "now": now.strftime("%H:%M")}.items() if v}
    # in a preview, a variable without a value stays visible as {{name}} instead of vanishing
    variables.update({v["name"]: v["default"] for v in script.get("variables") or []
                      if v.get("name") and v.get("default")})
    variables.update({k: v for k, v in body.variables.items() if v not in (None, "")})
    return {
        "agent": agent["name"] if agent else None,
        "first_message": render_template(script.get("first_message") or "", variables),
        # exactly what the model gets: with Fish the session adds its text-mode note
        "instructions": build_instructions(agent or {}, script, variables, direction, body.number, contact=contact)
                        + (FISH_INSTRUCTIONS + emotions.instructions(emotions.parse(agent.get("emotions_allowed")),
                                                                     emotions.parse(agent.get("emotions_forbidden")))
                           if agent and (db.agent_voice(agent).get("tts_engine") == "fish") else ""),
    }


# ---------------------------------------------------------------- skills

class SkillIn(BaseModel):
    name: str | None = Field(None, description="Название: «Курьер»")
    trigger: str | None = Field(None, description="Когда применять: «звонит курьер или служба доставки»")
    instructions: str | None = Field(None, description="Что знать и делать: адрес, ориентиры, код домофона…")
    collect: list[str] | None = Field(None, description="Что узнать и сохранить в итог: «номер машины», «время приезда»")
    sms_to: str | None = Field(None, description="Номер, на который скилл может отправить SMS со сводкой")
    always: bool | None = Field(None, description="Подключать сразу, в начале звонка")
    knows_owner: bool | None = Field(None, description="Скилл знает адрес и поля контакта «Этот номер»")


@router.get("/skills", tags=["skills"])
def list_skills():
    """Скиллы: что агент умеет в звонке. Сценарий выбирает свои."""
    rows = db.fetch_all("skills", "SELECT * FROM skills ORDER BY name")
    used: dict[int, list[str]] = {}
    for sc in db.fetch_all("scripts", "SELECT id, name, skills FROM scripts"):
        for sid in sc.get("skills") or []:
            used.setdefault(sid, []).append(sc["name"])
    for r in rows:
        r["scripts"] = used.get(r["id"], [])
    return rows


@router.post("/skills", tags=["skills"], status_code=201)
def create_skill(body: SkillIn):
    data = body.model_dump(exclude_none=True)
    if not (data.get("name") or "").strip():
        raise HTTPException(422, "укажите название скилла")
    if data.get("sms_to"):
        data["sms_to"] = db.normalize_phone(data["sms_to"])
    ts = db.now()
    return db.insert("skills", {**data, "created_at": ts, "updated_at": ts})


@router.put("/skills/{skill_id}", tags=["skills"])
def update_skill(skill_id: int, body: SkillIn):
    _or_404(db.get("skills", skill_id))
    data = body.model_dump(exclude_unset=True)
    if data.get("sms_to"):
        data["sms_to"] = db.normalize_phone(data["sms_to"])
    return db.update("skills", skill_id, {**data, "updated_at": db.now()})


@router.delete("/skills/{skill_id}", tags=["skills"])
def delete_skill(skill_id: int):
    """Удалить скилл (из сценариев он тоже уходит)."""
    for sc in db.fetch_all("scripts", "SELECT id, skills FROM scripts"):
        if skill_id in (sc.get("skills") or []):
            db.update("scripts", sc["id"], {"skills": [x for x in sc["skills"] if x != skill_id]})
    return {"deleted": db.delete("skills", skill_id)}


@router.get("/scripts", tags=["scripts"])
def list_scripts():
    return db.fetch_all("scripts", "SELECT * FROM scripts ORDER BY id")


@router.get("/scripts/{script_id}", tags=["scripts"])
def get_script(script_id: int):
    s = _or_404(db.get("scripts", script_id))
    s["detected_variables"] = template_variables((s.get("prompt") or "") + (s.get("first_message") or ""))
    return s


@router.post("/scripts", tags=["scripts"], status_code=201)
def create_script(body: ScriptIn):
    data = _clean_numbers(body.model_dump(exclude_none=True))
    if not data.get("name"):
        raise HTTPException(422, "name is required")
    _one_catch_all(data)
    ts = db.now()
    return db.insert("scripts", {**data, "created_at": ts, "updated_at": ts})


@router.put("/scripts/{script_id}", tags=["scripts"])
def update_script(script_id: int, body: ScriptIn):
    _or_404(db.get("scripts", script_id))
    data = _clean_numbers(body.model_dump(exclude_unset=True))
    _one_catch_all(data, script_id)
    return db.update("scripts", script_id, {**data, "updated_at": db.now()})


@router.delete("/scripts/{script_id}", tags=["scripts"])
def delete_script(script_id: int):
    return {"deleted": db.delete("scripts", script_id)}


@router.post("/scripts/{script_id}/render", tags=["scripts"])
def render_script(script_id: int, body: RenderIn):
    """Preview the full instructions the agent will receive for a saved script."""
    return _render(_or_404(db.get("scripts", script_id)), body)


@router.post("/scripts/preview", tags=["scripts"])
def preview_script(body: PreviewIn):
    """Preview instructions for an unsaved script (e.g. the editor's current form)."""
    return _render(body.script.model_dump(), body)


# ---------------------------------------------------------------- contacts

class ContactField(BaseModel):
    key: str = Field(..., description="Название поля, например «День рождения»")
    value: str = ""


class ContactIn(BaseModel):
    name: str | None = None
    last_name: str | None = Field(None, description="Фамилия")
    relation: str | None = Field(None, description="Кем контакт приходится владельцу системы: мама, жена, директор…")
    address: str | None = Field(None, description="Адрес")
    fields: list[ContactField] | None = Field(None, description="Свои поля контакта (ключ — значение)")
    phone: str | None = None
    company: str | None = None
    email: str | None = None
    tags: str | None = None
    notes: str | None = None


@router.get("/contacts", tags=["contacts"])
def list_contacts(q: str = Query("", description="Поиск по имени, фамилии, телефону, компании, связи, своим полям")):
    if q:
        like = f"%{q}%"
        return db.fetch_all("contacts", "SELECT * FROM contacts WHERE name LIKE ? OR last_name LIKE ? OR phone LIKE ? "
                                        "OR company LIKE ? OR tags LIKE ? OR (name || ' ' || last_name) LIKE ? "
                                        "OR relation LIKE ? OR fields LIKE ? "
                                        "OR address LIKE ? ORDER BY is_self DESC, name, last_name", (like,) * 9)
    return db.fetch_all("contacts", "SELECT * FROM contacts ORDER BY is_self DESC, name, last_name")


@router.get("/contacts/{contact_id}", tags=["contacts"])
def get_contact(contact_id: int):
    return _or_404(db.get("contacts", contact_id))


@router.post("/contacts", tags=["contacts"], status_code=201)
def create_contact(body: ContactIn):
    data = body.model_dump(exclude_none=True)
    if not data.get("name") or not data.get("phone"):
        raise HTTPException(422, "name and phone are required")
    data["phone"] = db.normalize_phone(data["phone"])
    ts = db.now()
    return db.insert("contacts", {**data, "created_at": ts, "updated_at": ts})


@router.put("/contacts/{contact_id}", tags=["contacts"])
def update_contact(contact_id: int, body: ContactIn):
    c = _or_404(db.get("contacts", contact_id))
    data = body.model_dump(exclude_none=True)
    if "phone" in data:
        data["phone"] = db.normalize_phone(data["phone"])
        if c.get("is_self") and data["phone"] != db.normalize_phone(c.get("phone") or ""):
            db.set_settings({"modem.own_number": data["phone"]})  # «Этот номер» is the SIM's number
    return db.update("contacts", contact_id, {**data, "updated_at": db.now()})


class AskIn(BaseModel):
    question: str = Field(..., description="Вопрос к ИИ об истории общения с контактом")


@router.get("/contacts/{contact_id}/history", tags=["contacts"])
def contact_history(contact_id: int):
    """«История»: calls (with summaries), SMS and the AI chat about them, oldest first."""
    contact = _or_404(db.get("contacts", contact_id))
    return {"contact": contact, "items": history_chat.timeline(contact),
            "model": db.setting("history_chat.model", "yandexgpt/latest")}


@router.post("/contacts/{contact_id}/history/ask", tags=["contacts"])
async def contact_history_ask(contact_id: int, body: AskIn):
    """Ask the AI about the history of dealings with the contact; returns the answer (saved in the chat)."""
    _or_404(db.get("contacts", contact_id))
    try:
        return await history_chat.ask(contact_id, body.question)
    except history_chat.HistoryError as e:
        raise HTTPException(422, str(e))


@router.delete("/contacts/{contact_id}/history/chat", tags=["contacts"])
def contact_history_clear(contact_id: int):
    """Clear the AI chat of the contact (calls and SMS stay)."""
    return {"deleted": db.execute("DELETE FROM contact_chat WHERE contact_id=?", (contact_id,)).rowcount}


@router.delete("/contacts/{contact_id}", tags=["contacts"])
def delete_contact(contact_id: int):
    if (db.get("contacts", contact_id) or {}).get("is_self"):
        raise HTTPException(409, "контакт «Этот номер» удалить нельзя")
    return {"deleted": db.delete("contacts", contact_id)}
