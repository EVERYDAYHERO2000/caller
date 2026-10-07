"""Modem control, settings, live events."""
import asyncio
import logging
import aiohttp
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from .. import config, db, netprobe, voices
from .. import system as host
from ..calls import calls
from ..events import hub
from ..modem import parsers as P
from ..modem.at import ATError
from ..modem.manager import modem
from .auth import ws_authorized

router = APIRouter()
log = logging.getLogger("api.system")
ws_router = APIRouter()

MASK = "••••••"


# ---------------------------------------------------------------- modem

class ATIn(BaseModel):
    command: str = Field(..., examples=["AT+CSQ"])
    timeout: float = Field(5, le=120)


@router.get("/modem", tags=["modem"])
def modem_status():
    return {**modem.snapshot(), "active_call": calls.active(),
            "network_modes": P.CNMP_MODES, "sms_services": P.SMS_SERVICES}


@router.post("/modem/refresh", tags=["modem"])
async def modem_refresh():
    if not modem.connected:
        raise HTTPException(503, "модем не подключён")
    await modem.refresh_info()
    await modem.refresh_status()
    return modem.snapshot()


@router.post("/modem/reconnect", tags=["modem"])
async def modem_reconnect():
    await modem.connect()
    return modem.snapshot()


@router.post("/modem/at", tags=["modem"])
async def modem_at(body: ATIn):
    """Raw AT command console."""
    cmd = body.command.strip()
    if not cmd.upper().startswith("AT"):
        raise HTTPException(422, "command must start with AT")
    try:
        r = await modem.cmd(cmd, timeout=body.timeout, check=False)
    except ATError as e:
        raise HTTPException(503, str(e))
    return {"lines": r.lines, "final": r.final}


class UssdIn(BaseModel):
    code: str = Field(..., description="USSD-запрос, например *100#, или ответ в меню оператора (1, 2…)")


@router.post("/modem/ussd", tags=["modem"])
async def modem_ussd(body: UssdIn):
    """Send a USSD request and wait for the operator's answer (up to 30 s)."""
    if calls.current:
        raise HTTPException(409, "Идёт звонок — USSD-запрос отправьте после него")
    try:
        return await modem.ussd(body.code)
    except ValueError as e:
        raise HTTPException(422, str(e))
    except ATError as e:
        log.warning("USSD %s failed: %s", body.code, e)
        raise HTTPException(503, str(e))


@router.post("/modem/ussd/cancel", tags=["modem"])
async def modem_ussd_cancel():
    try:
        await modem.ussd_cancel()
    except ATError as e:
        raise HTTPException(503, str(e))
    return {"ok": True}


@router.get("/modem/urc", tags=["modem"])
def modem_urc_log():
    return list(modem.urc_log)


@router.post("/modem/restart", tags=["modem"])
async def modem_restart():
    """Soft reset the module (AT+CRESET). It re-appears on USB in ~20 s."""
    try:
        await modem.cmd("AT+CRESET", timeout=5)
    except ATError as e:
        raise HTTPException(503, str(e))
    modem.connected = False
    modem.error = "перезагрузка модема…"
    return {"ok": True}


@router.post("/modem/airplane", tags=["modem"])
async def modem_airplane(enabled: bool):
    await modem.cmd("AT+CFUN=4" if enabled else "AT+CFUN=1", timeout=15)
    return {"ok": True}


class MockCallIn(BaseModel):
    number: str = "+79161234567"


class MockSmsIn(BaseModel):
    number: str = "+79161234567"
    text: str = "Тестовое сообщение"


@router.post("/modem/mock/incoming-call", tags=["modem"])
def mock_incoming_call(body: MockCallIn):
    if not config.MOCK:
        raise HTTPException(400, "only in mock mode")
    modem.at.simulate_incoming_call(body.number)
    return {"ok": True}


@router.post("/modem/mock/incoming-sms", tags=["modem"])
def mock_incoming_sms(body: MockSmsIn):
    if not config.MOCK:
        raise HTTPException(400, "only in mock mode")
    modem.at.simulate_incoming_sms(body.number, body.text)
    return {"ok": True}


# ---------------------------------------------------------------- settings

@router.get("/settings", tags=["settings"])
def get_settings():
    s = db.get_settings()
    for k in db.SECRET_SETTINGS:
        if s.get(k):
            s[k] = MASK
    return s


@router.put("/settings", tags=["settings"])
async def put_settings(values: dict[str, Any]):
    """Update any subset of settings (flat dotted keys, see GET /api/settings)."""
    unknown = [k for k in values if k not in db.DEFAULT_SETTINGS]
    if unknown:
        raise HTTPException(422, f"unknown settings: {', '.join(unknown)}")
    values = {k: v for k, v in values.items() if not (k in db.SECRET_SETTINGS and v == MASK)}
    old = db.get_settings()
    db.set_settings(values)
    if values.get("fish.api_key") and values["fish.api_key"] != old.get("fish.api_key"):
        voices.start_import()  # a new Fish key: add 50 Russian voices from its library
    if "modem.own_number" in values:
        db.ensure_self_contact()  # the contact «Этот номер» follows the SIM's number
    if any(k in values and values[k] != old.get(k) for k in ("telegram.token", "telegram.enabled")):
        from ..telegram_bot import bot
        bot.start()  # a new token / switched on or off
    errors = []
    # the SIM's number is only for the agents' prompts — nothing to push to the modem
    if any(k.startswith("modem.") and k != "modem.own_number" for k in values) and modem.connected:
        if any(values.get(k) != old.get(k) for k in ("modem.at_port", "modem.baudrate") if k in values):
            asyncio.create_task(modem.connect())
        else:
            errors = await modem.apply_settings()
            await modem.refresh_info()
    return {"settings": get_settings(), "errors": errors}


# ---------------------------------------------------------------- browser handset

@ws_router.websocket("/api/calls/audio")
async def call_audio(ws: WebSocket):
    """Two-way call audio for the browser: binary frames of 8 kHz mono PCM16 (20 ms = 320 bytes).
    Only one tab is attached at a time; a new connection replaces the previous one."""
    await ws.accept()
    if not ws_authorized(ws):
        await ws.close(code=4401)
        return
    q = calls.browser_audio.attach()

    async def sender():
        while True:
            frame = await q.get()
            if frame is None:  # another tab took over
                await ws.close(code=4409)
                return
            await ws.send_bytes(frame)

    task = asyncio.create_task(sender())
    try:
        while True:
            msg = await ws.receive()
            if msg["type"] == "websocket.disconnect":
                break
            if msg.get("bytes"):
                calls.browser_input(msg["bytes"])
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        task.cancel()
        calls.browser_audio.detach(q)


# ---------------------------------------------------------------- events

@ws_router.websocket("/api/events")
async def events(ws: WebSocket):
    """Live events: modem.status, modem.urc, call.state, call.message, call.incoming,
    call.ended, sms.new, sms.updated."""
    await ws.accept()
    if not ws_authorized(ws):
        await ws.close(code=4401)  # client shows the login screen
        return
    q = hub.subscribe()
    try:
        await ws.send_json({"event": "hello", "data": {"active": calls.active(),
                                                        "modem": modem.snapshot()}})
        while True:
            msg = await q.get()
            await ws.send_json(msg)
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        hub.unsubscribe(q)


# ---------------------------------------------------------------- host (Raspberry Pi): «Система»

@router.get("/system", tags=["system"])
def system_info():
    """Raspberry Pi: model, OS, CPU, temperature, throttling, memory, disk, Wi-Fi, the Caller process and the
    last hour of CPU / temperature / memory (a point every 10 s)."""
    return host.info()


class PowerIn(BaseModel):
    wifi_powersave: bool | None = Field(None, description="Энергосбережение Wi-Fi")
    cpu_governor: str | None = Field(None, description="Режим процессора: ondemand, performance, powersave…")


@router.put("/system/power", tags=["system"])
async def system_power(body: PowerIn):
    """Энергосбережение: Wi-Fi power save (сохраняется в NetworkManager) и режим процессора."""
    try:
        return await host.set_power(body.wifi_powersave, body.cpu_governor)
    except (RuntimeError, asyncio.TimeoutError) as e:
        raise HTTPException(400, str(e) or "не удалось применить")


# ---------------------------------------------------------------- providers: usage / balance (Настройки)

def _period_starts() -> dict:
    now = datetime.now().astimezone()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return {"today": today.isoformat(timespec="seconds"),
            "month": (today - timedelta(days=30)).isoformat(timespec="seconds"), "total": ""}


@router.get("/providers/usage", tags=["system"])
async def providers_usage():
    """Что приложение потратило у провайдеров (сегодня / 30 дней / всего) и баланс, где он доступен.

    Считает сам Caller (журнал usage_log): Yandex — токены звонков, хезитаций и проверки голоса плюс
    суммаризация; Fish Audio — кредиты, как их сообщает Kitta (units фраз в звонке, X-OpenAPI-Credits-Used
    при синтезе). Баланс: Fish — остаток API-квоты из профиля; Yandex Cloud по ключу AI Studio недоступен."""
    periods = _period_starts()
    yandex, fish_used = {}, {}
    for name, since in periods.items():
        rows = db.rows("SELECT provider, kind, COALESCE(SUM(tokens_in),0), COALESCE(SUM(tokens_out),0), "
                       "COALESCE(SUM(credits),0) FROM usage_log WHERE created_at >= ? GROUP BY provider, kind", (since,))
        sm = db.rows("SELECT COALESCE(SUM(input_tokens),0), COALESCE(SUM(output_tokens),0) "
                     "FROM call_summaries WHERE created_at >= ?", (since,))[0]
        y = {"call": 0, "summary": sm[0] + sm[1], "filler": 0, "greeting": 0, "voice_test": 0, "history_chat": 0, "tokens_in": sm[0], "tokens_out": sm[1]}
        f = {"call": 0, "filler": 0, "greeting": 0, "voice_test": 0}
        for provider, kind, t_in, t_out, credits in rows:
            if provider == "yandex":
                y[kind] = y.get(kind, 0) + t_in + t_out
                y["tokens_in"] += t_in
                y["tokens_out"] += t_out
            elif provider == "fish":
                f[kind] = f.get(kind, 0) + credits
        y["total"] = y["call"] + y["summary"] + y["filler"] + y["greeting"] + y["voice_test"] + y["history_chat"]
        f["total"] = f["call"] + f["filler"] + f["greeting"] + f["voice_test"]
        yandex[name], fish_used[name] = y, {k: round(v) for k, v in f.items()}
    fish_out = {"configured": bool(db.setting("fish.api_key")), "usage": fish_used}
    if fish_out["configured"]:
        from ..agent import fish as fish_api
        try:
            s = db.get_settings()
            url = (s.get("fish.api_url") or fish_api.DEFAULT_API_URL) + "/v1/profile"
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8)) as http:
                async with http.get(url, headers=fish_api._auth(s)) as r:
                    if r.status != 200:
                        raise RuntimeError(f"{r.status} {(await r.text())[:120]}")
                    p = await r.json()
            fish_out.update(api_quota_remaining=p.get("api_quota_remaining"), tier=p.get("tier"))
        except Exception as e:  # noqa: BLE001
            fish_out["error"] = str(e) or type(e).__name__
    return {"yandex": {"configured": bool(db.setting("yandex.api_key")), "usage": yandex, "balance_available": False},
            "fish": fish_out}


# ---------------------------------------------------------------- connection to the providers («Провайдеры»)

@router.get("/providers/network", tags=["system"])
def providers_network(hours: float = 1):
    """Ping, DNS, TCP, TLS, HTTP and the internet exit of every provider host, measured each minute."""
    return {"targets": netprobe.monitor.snapshot(hours), "period": netprobe.PERIOD}


@router.post("/providers/network/check", tags=["system"])
async def providers_network_check():
    """Measure right now (plus the Yandex Realtime handshake — no tokens)."""
    await netprobe.monitor.check()
    return {"targets": netprobe.monitor.snapshot(), "period": netprobe.PERIOD,
            "yandex_handshake": await netprobe.yandex_handshake(db.get_settings())}


@router.post("/providers/kitta/stream-test", tags=["system"])
async def kitta_stream_test():
    """Two short phrases through the Kitta realtime connection: first sound and stream speed. Costs a couple of
    credits and holds Kitta's single connection for a few seconds — refused while a call is going on."""
    if calls.current:
        raise HTTPException(409, "Идёт звонок — тест потока займёт единственное соединение Kitta. Попробуйте после звонка.")
    s = db.get_settings()
    if not s.get("fish.api_key"):
        raise HTTPException(409, "Не задан API-ключ Fish Audio (Настройки → Провайдеры)")
    voice = db.fetch_one("voices", "SELECT v.* FROM voices v JOIN agents a ON a.voice_id=v.id WHERE v.engine='fish' "
                                   "ORDER BY a.id LIMIT 1") \
        or db.fetch_one("voices", "SELECT * FROM voices WHERE engine='fish' ORDER BY id LIMIT 1")
    if not voice:
        raise HTTPException(409, "Нет ни одного голоса Fish Audio")
    r = await netprobe.kitta_stream_test(s, voice["voice"], voice.get("model") or "", voice.get("language") or "ru")
    return {**r, "voice": voice["name"]}


# ---------------------------------------------------------------- Telegram bot

@router.get("/telegram", tags=["telegram"])
def telegram_status():
    """The bot: its name, whether polling works, the linked accounts."""
    from ..telegram_bot import bot
    return bot.status()


@router.post("/telegram/pair-code", tags=["telegram"])
def telegram_pair_code():
    """A one-time code (30 min): sent to the bot, it links that Telegram account."""
    from ..telegram_bot import CODE_TTL, bot
    return {"code": bot.new_code(), "ttl": CODE_TTL, "bot": bot.me.get("username") or ""}


@router.delete("/telegram/users/{user_id}", tags=["telegram"])
def telegram_unlink(user_id: int):
    """Unlink an account: the bot stops answering it."""
    return {"deleted": db.delete("telegram_users", user_id)}
