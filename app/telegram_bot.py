"""Telegram bot: the assistant (the right-hand chat panel) in Telegram.

Long polling (getUpdates) — the Pi needs no public address. Access: an account is linked with a one-time code
from «Настройки → Telegram»; nobody else gets an answer. Each linked account has its own assistant chat (/new
starts another). What the assistant shows as widgets becomes text lines with buttons: «Позвонить» / «Отмена» on a
call card, «Отменить» on a task marked done, «▶» to get a call's recording as MP3, a map point as a venue.
Voice messages are recognized by SpeechKit and handled as text. Notifications: new tasks after a call, missed
calls, incoming SMS (each can be switched off).
"""
import asyncio
import html
import json
import logging
import random
import tempfile
import time
from pathlib import Path

import aiohttp

from . import assistant, config, db
from .events import hub

log = logging.getLogger("telegram")

API = "https://api.telegram.org"
CODE_TTL = 30 * 60   # s a pairing code is valid
MAX_TEXT = 3900      # Telegram allows 4096 characters per message

HELP = ("Я ассистент Caller. Спросите о контактах, делах, встречах и звонках или попросите позвонить — "
        "например: «что мне просили напомнить?», «какие встречи на неделе?», «позвони маме и узнай, как дела». "
        "Можно голосом.\n\n/new — новый разговор\n/help — подсказка")


def esc(s) -> str:
    return html.escape(str(s or ""), quote=False)


class Bot:
    def __init__(self):
        self._task: asyncio.Task | None = None
        self._events: asyncio.Task | None = None
        self.http: aiohttp.ClientSession | None = None
        self.token = ""
        self.me: dict = {}
        self.error = ""
        self.running = False
        self._busy: set[int] = set()

    # ------------------------------------------------------------ lifecycle

    def start(self):
        """(Re)start polling with the current token; nothing runs without a token or when switched off."""
        asyncio.create_task(self._restart())

    async def _restart(self):
        await self.stop()
        s = db.get_settings()
        self.token = (s.get("telegram.token") or "").strip()
        self.me, self.error = {}, ""
        if not self.token or not s.get("telegram.enabled", True):
            return
        self.http = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=70))
        self._task = asyncio.create_task(self._poll())
        self._events = asyncio.create_task(self._notify_loop())

    async def stop(self):
        for t in (self._task, self._events):
            if t:
                t.cancel()
        self._task = self._events = None
        self.running = False
        if self.http:
            await self.http.close()
            self.http = None

    def status(self) -> dict:
        return {"configured": bool(self.token), "running": self.running, "error": self.error,
                "bot": self.me.get("username") or "", "name": self.me.get("first_name") or "",
                "users": db.fetch_all("telegram_users", "SELECT * FROM telegram_users ORDER BY id")}

    # ------------------------------------------------------------ Telegram API

    async def call(self, method: str, **params) -> dict:
        async with self.http.post(f"{API}/bot{self.token}/{method}", json=params) as r:
            body = await r.json(content_type=None)
        if not body.get("ok"):
            raise RuntimeError(f"{method}: {body.get('description') or body}")
        return body["result"]

    async def send(self, chat_id: int, text: str, buttons: list[list[dict]] | None = None) -> dict | None:
        params = {"chat_id": chat_id, "text": text[:MAX_TEXT], "parse_mode": "HTML", "disable_web_page_preview": True}
        if buttons:
            params["reply_markup"] = {"inline_keyboard": buttons}
        try:
            return await self.call("sendMessage", **params)
        except Exception as e:  # noqa: BLE001
            log.warning("send to %s failed: %s", chat_id, e)
            return None

    async def _poll(self):
        offset = 0
        backoff = 2
        while True:
            try:
                if not self.me:
                    self.me = await self.call("getMe")
                    await self.call("setMyCommands", commands=[
                        {"command": "new", "description": "Новый разговор"},
                        {"command": "help", "description": "Что я умею"}])
                    log.info("telegram bot @%s is up", self.me.get("username"))
                updates = await self.call("getUpdates", offset=offset, timeout=50,
                                          allowed_updates=["message", "callback_query"])
                self.running, self.error, backoff = True, "", 2
                for u in updates:
                    offset = u["update_id"] + 1
                    asyncio.create_task(self._handle(u))
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001 — no network, a wrong token: tell the settings, try again
                self.running = False
                self.error = str(e) or type(e).__name__
                log.warning("telegram polling: %s", self.error)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)

    # ------------------------------------------------------------ access

    def user(self, tg_id: int) -> dict | None:
        return db.fetch_one("telegram_users", "SELECT * FROM telegram_users WHERE tg_user_id=?", (tg_id,))

    @staticmethod
    def new_code() -> str:
        code = f"{random.SystemRandom().randint(0, 999999):06d}"
        db.set_settings({"telegram.pair_code": code, "telegram.pair_until": int(time.time()) + CODE_TTL})
        return code

    def _pair(self, msg: dict) -> dict | None:
        s = db.get_settings()
        text = (msg.get("text") or "").strip()
        if not s.get("telegram.pair_code") or text != s["telegram.pair_code"] \
                or int(s.get("telegram.pair_until") or 0) < time.time():
            return None
        frm = msg["from"]
        db.set_settings({"telegram.pair_code": "", "telegram.pair_until": 0})  # one-time
        chat = assistant.new_chat()
        db.update("assistant_chats", chat["id"], {"title": "Telegram"})
        name = " ".join(x for x in (frm.get("first_name"), frm.get("last_name")) if x)
        return db.insert("telegram_users", {"tg_user_id": frm["id"], "chat_id": msg["chat"]["id"], "name": name,
                                            "username": frm.get("username") or "", "assistant_chat_id": chat["id"],
                                            "created_at": db.now()})

    # ------------------------------------------------------------ updates

    async def _handle(self, u: dict):
        try:
            if "callback_query" in u:
                await self._on_button(u["callback_query"])
            elif "message" in u:
                await self._on_message(u["message"])
        except Exception:  # noqa: BLE001
            log.exception("telegram update failed")

    async def _on_message(self, msg: dict):
        if msg.get("chat", {}).get("type") != "private":
            return
        chat_id, frm = msg["chat"]["id"], msg.get("from") or {}
        me = self.user(frm.get("id"))
        text = (msg.get("text") or "").strip()
        if not me:
            paired = self._pair(msg)
            if paired:
                await self.send(chat_id, f"Готово, {esc(paired['name'] or 'вы')} привязаны к Caller.\n\n{esc(HELP)}")
            else:
                await self.send(chat_id, "Это личный бот Caller. Чтобы пользоваться им, отправьте код привязки "
                                         "из раздела «Настройки → Telegram».")
            return
        if me["chat_id"] != chat_id:
            db.update("telegram_users", me["id"], {"chat_id": chat_id})
        if text in ("/start", "/help"):
            await self.send(chat_id, esc(HELP))
            return
        if text == "/new":
            chat = assistant.new_chat()
            db.update("assistant_chats", chat["id"], {"title": "Telegram"})
            db.update("telegram_users", me["id"], {"assistant_chat_id": chat["id"]})
            await self.send(chat_id, "Начали новый разговор.")
            return
        if msg.get("voice") or msg.get("audio"):
            text = await self._recognize(msg.get("voice") or msg.get("audio"), chat_id)
            if not text:
                return
            await self.send(chat_id, f"🎤 <i>{esc(text)}</i>")
        if not text:
            await self.send(chat_id, "Пришлите текст или голосовое сообщение.")
            return
        await self._ask(me, chat_id, text)

    async def _ask(self, me: dict, chat_id: int, text: str):
        if me["id"] in self._busy:
            await self.send(chat_id, "Секунду, ещё отвечаю на предыдущее сообщение.")
            return
        self._busy.add(me["id"])
        typing = asyncio.create_task(self._typing(chat_id))
        try:
            chat_ref = me.get("assistant_chat_id")
            if not chat_ref or not db.get("assistant_chats", chat_ref):  # the chat was deleted in the web panel
                chat = assistant.new_chat()
                db.update("assistant_chats", chat["id"], {"title": "Telegram"})
                db.update("telegram_users", me["id"], {"assistant_chat_id": chat["id"]})
                chat_ref = chat["id"]
            try:
                fresh = await assistant.ask(chat_ref, text)
            except assistant.AssistantError as e:
                await self.send(chat_id, f"Не получилось: {esc(e)}")
                return
            for m in fresh:
                if m["role"] != "user":
                    await self._render(chat_id, m)
        finally:
            typing.cancel()
            self._busy.discard(me["id"])

    async def _typing(self, chat_id: int):
        try:
            while True:
                await self.call("sendChatAction", chat_id=chat_id, action="typing")
                await asyncio.sleep(4)
        except asyncio.CancelledError:
            pass
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------ what the assistant said → Telegram

    async def _render(self, chat_id: int, m: dict):
        d = m.get("data") or {}
        if m["role"] == "assistant":
            lines, buttons = [esc(m["text"])], []
            for o in m.get("objects") or []:
                line, btn = object_line(o)
                lines.append(line)
                if btn:
                    buttons.append([btn])
            link = d.get("link")
            if link and link.get("count", 0) > len(m.get("objects") or []):
                lines.append(f"<i>…всего {link['count']} — откройте раздел в Caller</i>")
            await self.send(chat_id, "\n\n".join(x for x in [lines[0], "\n".join(lines[1:])] if x), buttons[:10] or None)
        elif d.get("type") == "call":
            await self.send(chat_id, call_card_text(d), [[{"text": "📞 Позвонить", "callback_data": f"call:{m['id']}"},
                                                          {"text": "Отмена", "callback_data": f"cancel:{m['id']}"}]])
        elif d.get("type") == "task_done":
            await self.send(chat_id, f"✅ «{esc(d['title'])}» — выполнено",
                            [[{"text": "Отменить", "callback_data": f"undo:{m['id']}"}]])
        elif d.get("type") == "place":
            await self._place(chat_id, d)

    async def _place(self, chat_id: int, d: dict):
        from . import geo
        point = (d["lat"], d["lon"], d.get("address") or "") if d.get("lat") else await geo.geocode(d.get("query") or "")
        if point:
            try:
                await self.call("sendVenue", chat_id=chat_id, latitude=point[0], longitude=point[1],
                                title=(d.get("title") or point[2] or d.get("query") or "Место")[:100],
                                address=(point[2] or d.get("query") or "")[:100])
                return
            except Exception as e:  # noqa: BLE001
                log.warning("venue failed: %s", e)
        from urllib.parse import quote
        await self.send(chat_id, f"📍 {esc(d.get('title') or d.get('query'))}\n"
                                 f"<a href=\"https://yandex.ru/maps/?text={quote(d.get('query') or '')}\">Открыть в Яндекс Картах</a>")

    # ------------------------------------------------------------ buttons

    async def _on_button(self, q: dict):
        me = self.user((q.get("from") or {}).get("id"))
        msg = q.get("message") or {}
        if not me:
            await self.call("answerCallbackQuery", callback_query_id=q["id"], text="Нет доступа")
            return
        kind, _, ref = (q.get("data") or "").partition(":")
        note = ""
        try:
            if kind == "call":
                await self.call("answerCallbackQuery", callback_query_id=q["id"], text="Готовим агента…")
                try:
                    row = await assistant.confirm_call(int(ref))
                except Exception as e:  # noqa: BLE001 — line busy, the agent not ready: said in the chat
                    await self.send(msg["chat"]["id"], f"Не удалось позвонить: {esc(e)}")
                    return
                await self._edit(msg, call_card_text(row["data"]) + "\n\n<b>Звонок начат</b>")
                return
            if kind == "cancel":
                row = assistant.cancel_call(int(ref))
                await self._edit(msg, call_card_text(row["data"]) + "\n\n<i>Отменено</i>")
            elif kind == "undo":
                row = assistant.undo_done(int(ref))
                await self._edit(msg, f"↩️ «{esc(row['data']['title'])}» — снова в работе")
            elif kind == "done":
                t = db.get("tasks", int(ref))
                if t and t["status"] != "done":
                    db.update("tasks", t["id"], {"status": "done", "updated_at": db.now()})
                    hub.publish("tasks.updated", {"id": t["id"], "action": "updated"})
                note = "Отмечено выполненным"
            elif kind == "rec":
                note = "Отправляю запись…"
                await self.call("answerCallbackQuery", callback_query_id=q["id"], text=note)
                await self._send_recording(msg["chat"]["id"], int(ref))
                return
        except assistant.AssistantError as e:
            note = str(e)
        except Exception as e:  # noqa: BLE001 — line busy, agent not ready…
            note = str(e)[:180] or "Не получилось"
        await self.call("answerCallbackQuery", callback_query_id=q["id"], text=note[:200])

    async def _edit(self, msg: dict, text: str):
        try:
            await self.call("editMessageText", chat_id=msg["chat"]["id"], message_id=msg["message_id"], text=text,
                            parse_mode="HTML")
        except Exception as e:  # noqa: BLE001
            log.debug("edit failed: %s", e)

    async def _send_recording(self, chat_id: int, call_id: int):
        c = db.get("calls", call_id)
        path = config.RECORDINGS_DIR / ((c or {}).get("recording") or "")
        if not c or not c.get("recording") or not path.exists():
            await self.send(chat_id, "У этого звонка нет записи.")
            return
        with tempfile.TemporaryDirectory() as tmp:
            mp3 = Path(tmp) / f"call_{call_id}.mp3"
            proc = await asyncio.create_subprocess_exec("ffmpeg", "-v", "error", "-y", "-i", str(path), "-b:a", "64k",
                                                        str(mp3))
            await proc.wait()
            if proc.returncode or not mp3.exists():
                await self.send(chat_id, "Не удалось подготовить запись.")
                return
            who = db.attach_contacts([dict(c)])[0].get("contact_name") or c.get("number") or "звонок"
            form = aiohttp.FormData()
            form.add_field("chat_id", str(chat_id))
            form.add_field("title", f"{who}, {fmt_when(c.get('started_at'))}")
            form.add_field("performer", "Caller")
            form.add_field("audio", mp3.read_bytes(), filename=mp3.name, content_type="audio/mpeg")
            async with self.http.post(f"{API}/bot{self.token}/sendAudio", data=form) as r:
                body = await r.json(content_type=None)
            if not body.get("ok"):
                await self.send(chat_id, f"Не удалось отправить запись: {esc(body.get('description'))}")

    # ------------------------------------------------------------ voice

    async def _recognize(self, voice: dict, chat_id: int) -> str:
        from .transcribe import TranscribeError, _auth
        try:
            f = await self.call("getFile", file_id=voice["file_id"])
            async with self.http.get(f"{API}/file/bot{self.token}/{f['file_path']}") as r:
                audio = await r.read()
            headers = _auth(db.get_settings())
            fmt = "oggopus" if (voice.get("mime_type") or "audio/ogg").endswith("ogg") else "mp3"
            async with self.http.post("https://stt.api.cloud.yandex.net/speech/v1/stt:recognize",
                                      params={"folderId": headers.pop("x-folder-id"), "lang": "ru-RU", "format": fmt},
                                      headers=headers, data=audio) as r:
                body = await r.json(content_type=None)
            text = (body.get("result") or "").strip()
            if not text:
                await self.send(chat_id, "Не расслышал — повторите, пожалуйста.")
            return text
        except TranscribeError as e:
            await self.send(chat_id, f"Голос не распознать: {esc(e)}")
        except Exception as e:  # noqa: BLE001
            log.warning("voice recognition failed: %s", e)
            await self.send(chat_id, "Не удалось распознать голосовое сообщение.")
        return ""

    # ------------------------------------------------------------ notifications

    async def broadcast(self, text: str, buttons: list[list[dict]] | None = None):
        for u in db.fetch_all("telegram_users", "SELECT * FROM telegram_users"):
            await self.send(u["chat_id"], text, buttons)

    async def _notify_loop(self):
        q = hub.subscribe()
        try:
            while True:
                ev = await q.get()
                try:
                    await self._notify(ev["event"], ev.get("data") or {})
                except Exception:  # noqa: BLE001
                    log.exception("telegram notification failed")
        finally:
            hub.unsubscribe(q)

    async def _notify(self, event: str, data: dict):
        s = db.get_settings()
        if not db.fetch_one("telegram_users", "SELECT id FROM telegram_users LIMIT 1"):
            return
        if event == "call.ended" and data.get("direction") == "in" and data.get("status") == "missed" \
                and s.get("telegram.notify_missed", True):
            c = db.attach_contacts([dict(data)])[0]
            who = c.get("contact_name") or c.get("number") or "скрытый номер"
            await self.broadcast(f"📵 Пропущенный звонок: <b>{esc(who)}</b>"
                                 + (f" ({esc(c['number'])})" if c.get("contact_name") and c.get("number") else "")
                                 + f"\n{fmt_when(c.get('started_at'))}")
        elif event == "sms.new" and data.get("direction") == "in" and s.get("telegram.notify_sms", True):
            c = db.attach_contacts([dict(data)])[0]
            who = c.get("contact_name") or c.get("number") or "неизвестный номер"
            await self.broadcast(f"✉️ SMS от <b>{esc(who)}</b>:\n{esc(c.get('text'))}")
        elif event == "tasks.updated" and data.get("added") and data.get("call_id") and s.get("telegram.notify_tasks", True):
            rows = db.attach_contacts(db.fetch_all("tasks", "SELECT * FROM tasks WHERE call_id=? AND source='call' "
                                                            "ORDER BY id DESC LIMIT ?", (data["call_id"], data["added"])))
            if not rows:
                return
            who = rows[0].get("contact_name") or rows[0].get("number") or ""
            lines = [object_line({"type": "task", "item": t})[0] for t in reversed(rows)]
            buttons = [[{"text": f"✓ {t['title'][:40]}", "callback_data": f"done:{t['id']}"}] for t in reversed(rows)]
            await self.broadcast(f"🗒 Новые дела после звонка{(' с ' + esc(who)) if who else ''}:\n\n" + "\n".join(lines),
                                 buttons[:8])


# ---------------------------------------------------------------- formatting

def fmt_when(iso: str | None) -> str:
    if not iso:
        return ""
    return f"{iso[8:10]}.{iso[5:7]} {iso[11:16]}".strip()


def call_card_text(d: dict) -> str:
    agent = db.get("agents", d["agent_id"]) if d.get("agent_id") else None
    script = db.get("scripts", d["script_id"]) if d.get("script_id") else None
    who = esc(d.get("name") or d.get("number")) + (f" ({esc(d['relation'])})" if d.get("relation") else "")
    parts = [f"📞 Позвонить: <b>{who}</b>", esc(d.get("number")),
             f"Агент: {esc((agent or {}).get('name') or '—')}" + (f" · сценарий: {esc(script['name'])}" if script else "")]
    if d.get("prompt"):
        parts.append(f"Поручение: <i>{esc(d['prompt'])}</i>")
    return "\n".join(parts)


def object_line(o: dict) -> tuple[str, dict | None]:
    """A widget as a text line (and a button, if it has an action)."""
    from .tasks import is_overdue
    x = o["item"]
    if o["type"] == "contact":
        rest = " · ".join(v for v in (x.get("relation"), x.get("phone"), x.get("company")) if v)
        return f"👤 <b>{esc(x.get('label') or x.get('name'))}</b>" + (f" — {esc(rest)}" if rest else ""), None
    if o["type"] == "task":
        mark = "✅" if x.get("status") == "done" else "🔴" if is_overdue(x) else "▫️"
        due = x.get("due_at") or ""
        when = (f"{due[8:10]}.{due[5:7]}" + (f" {due[11:16]}" if len(due) > 10 else "")) if due else ""
        rest = " · ".join(v for v in (when, x.get("contact_name"), (x.get("geo") or {}).get("address") or x.get("place")) if v)
        return f"{mark} <b>{esc(x['title'])}</b>" + (f" — {esc(rest)}" if rest else ""), None
    if o["type"] == "call":
        from .history_chat import _gist
        gist, agreed = _gist(x)
        who = x.get("contact_name") or x.get("number") or "скрытый номер"
        head = f"📞 {fmt_when(x.get('started_at') or x.get('created_at'))} · {'входящий' if x.get('direction') == 'in' else 'исходящий'} · {esc(who)}"
        text = head + (f"\n{esc(gist)}" if gist else "") + (f"\nДоговорились: {esc(agreed)}" if agreed else "")
        btn = {"text": f"▶ {fmt_when(x.get('started_at'))} {who}"[:60], "callback_data": f"rec:{x['id']}"} \
            if x.get("recording") else None
        return text, btn
    return "", None


bot = Bot()
