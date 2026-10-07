"""High level modem service: connection, status polling, SMS, URC routing."""
import asyncio
import re
import logging
import os
import time
from collections import deque

from gsmmodem.pdu import decodeSmsPdu, encodeSmsSubmitPdu

from .. import config, db
from ..events import hub
from . import parsers as P
from .at import ATError, ATPort, ATResponse

log = logging.getLogger("modem")


def _ussd_error(line: str, status: dict) -> str:
    """A human explanation of a refused USSD request."""
    reason = line.replace("+CME ERROR:", "").strip()
    if "retry" in reason.lower() and "LTE" in str(status.get("network_type", "")) + str(status.get("access_tech", "")):
        return ("Оператор не принял USSD-запрос: модем сейчас в сети LTE, а USSD у многих операторов работает только "
                "в 2G/3G. Переключите режим сети (например, «Любой кроме LTE») и повторите.")
    return f"Оператор не принял USSD-запрос ({reason or line})"

AT_LINK = "/dev/sim7600-at"
AUDIO_LINK = "/dev/sim7600-audio"


def resolve_port(configured: str, link: str) -> str:
    """ttyUSB numbers change after a modem reset; the udev symlink does not."""
    if config.MOCK or os.path.exists(configured) or not os.path.exists(link):
        return configured
    log.info("port %s not found, using %s", configured, link)
    return link


class Modem:
    def __init__(self):
        self.at = None
        self.loop: asyncio.AbstractEventLoop | None = None
        self.connected = False
        self.error = ""
        self.status: dict = {}
        self.info: dict = {}
        self.history: deque = deque(maxlen=180)
        self.urc_log: deque = deque(maxlen=100)
        self.on_call_urc = None  # set by CallManager
        self._ussd: asyncio.Future | None = None
        self._ussd_lock = asyncio.Lock()
        self._task = None

    # ------------------------------------------------------------ lifecycle

    async def start(self):
        self.loop = asyncio.get_running_loop()
        await self.connect()
        self._task = asyncio.create_task(self._poll_loop())

    async def stop(self):
        if self._task:
            self._task.cancel()
        if self.at:
            self.at.close()

    async def connect(self):
        if self.at:
            self.at.close()
            self.at = None
        s = db.get_settings()
        if config.MOCK:
            from .mock import MockATPort
            port_cls = MockATPort
        else:
            port_cls = ATPort
        at_port = resolve_port(s["modem.at_port"], AT_LINK)
        port = port_cls(at_port, int(s["modem.baudrate"]),
                        on_urc=self._urc_from_thread, on_disconnect=self._disconnect_from_thread)
        try:
            await asyncio.to_thread(port.open)
            self.at = port
            await self._init_modem()
            self.connected = True
            self.error = ""
            log.info("modem connected on %s%s", at_port, " (mock)" if config.MOCK else "")
            await self.refresh_info()
            await self.refresh_status()
            asyncio.create_task(self.read_stored_sms())
        except Exception as e:
            self.connected = False
            self.error = str(e)
            log.error("modem connect failed: %s", e)
            if port:
                port.close()
            self.at = None
        self._publish_status()

    async def _init_modem(self):
        s = db.get_settings()
        await self.cmd("AT", check=True)
        # right after a modem restart the port answers before the SIM is ready, and settings sent then are lost
        # (the caller's number, +CLIP, stayed off) — wait for the SIM first
        for _ in range(30):
            if any("READY" in ln for ln in await self._try("AT+CPIN?")):
                break
            await asyncio.sleep(1)
        for cmd in ("ATE0", "AT+CMEE=2", "AT+CLIP=1", "AT+CVHU=0", "AT+COPS=3,0",
                    "AT+CMGF=0", "AT+CNMI=2,1,0,0,0", "AT+CREG=0"):
            await self.cmd(cmd, check=False)
        await self.ensure_clip()
        await self.apply_settings(s, init=True)

    async def ensure_clip(self):
        """The caller's number (+CLIP) must be on: without it every incoming call is «скрытый номер»."""
        for _ in range(3):
            lines = await self._try("AT+CLIP?")
            if any(ln.replace(" ", "").startswith("+CLIP:1") for ln in lines):
                return True
            log.warning("caller ID (+CLIP) is off — turning it on")
            await self._try("AT+CLIP=1")
            await asyncio.sleep(1)
        return False

    async def apply_settings(self, s: dict | None = None, init: bool = False):
        """Push modem-related settings to the device."""
        s = s or db.get_settings()
        cmds = [
            f"AT+CLVL={int(s['modem.speaker_volume'])}",
            f"AT+CMICGAIN={int(s['modem.mic_gain'])}",
            f"AT+COUTGAIN={int(s['modem.out_gain'])}",
            f"AT+CGSMS={int(s['modem.sms_service'])}",
        ]
        if not init:
            cmds.append(f"AT+CNMP={int(s['modem.network_mode'])}")
        else:
            # after a modem reset the mode may be back to «automatic» (LTE, where calls of this SIM don't come in):
            # the saved mode is set again — only if it differs, a change makes the modem re-register
            try:
                cur = P.parse_int_value(await self._try("AT+CNMP?"), "+CNMP")
            except Exception:  # noqa: BLE001
                cur = None
            if cur is None or cur != int(s["modem.network_mode"]):
                cmds.append(f"AT+CNMP={int(s['modem.network_mode'])}")
        if s.get("modem.apn"):
            cmds.append(f'AT+CGDCONT=1,"IP","{s["modem.apn"]}"')
        errors = []
        for c in cmds:
            try:
                await self.cmd(c, timeout=10)
            except ATError as e:
                errors.append(str(e))
        return errors

    def _urc_from_thread(self, line: str):
        if self.loop:
            self.loop.call_soon_threadsafe(self._on_urc, line)

    def _disconnect_from_thread(self, reason: str):
        if self.loop:
            self.loop.call_soon_threadsafe(self._on_disconnect, reason)

    def _on_disconnect(self, reason: str):
        self.connected = False
        self.error = f"порт отключён: {reason}"
        self._publish_status()

    # ------------------------------------------------------------ commands

    async def cmd(self, command: str, timeout: float = 5.0, data: str | None = None,
                  check: bool = True) -> ATResponse:
        if not self.at:
            raise ATError("модем не подключён")
        return await asyncio.to_thread(self.at.command, command, timeout, data, check)

    async def _try(self, command: str, timeout: float = 3.0) -> list[str]:
        try:
            return (await self.cmd(command, timeout)).lines
        except ATError:
            return []

    # ------------------------------------------------------------ status

    async def refresh_info(self):
        info = {
            "manufacturer": P.plain(await self._try("AT+CGMI")),
            "model": P.plain(await self._try("AT+CGMM")),
            "firmware": P.plain(await self._try("AT+CGMR")),
            "imei": P.plain(await self._try("AT+CGSN")),
            "imsi": P.plain(await self._try("AT+CIMI")),
            "iccid": P.plain(await self._try("AT+CICCID")),
            "own_number": P.parse_cnum(await self._try("AT+CNUM")),
            "sim": P.plain(await self._try("AT+CPIN?")),
        }
        if not info["sim"]:
            try:
                r = await self.cmd("AT+CPIN?", check=False)
                info["sim"] = P.plain(r.lines) or r.final.replace("+CME ERROR: ", "")
            except ATError as e:
                info["sim"] = str(e)
        mode = P.parse_int_value(await self._try("AT+CNMP?"), "+CNMP")
        info["network_mode"] = mode
        info["network_mode_name"] = P.CNMP_MODES.get(mode, str(mode))
        self.info = info

    async def refresh_status(self):
        st: dict = {}
        st.update(P.parse_csq(await self._try("AT+CSQ")))
        st.update(P.parse_cops(await self._try("AT+COPS?")))
        st.update(P.parse_creg(await self._try("AT+CREG?")))
        if st.get("reg_code") not in (1, 5):
            eps = P.parse_creg(await self._try("AT+CEREG?"), "+CEREG")
            if eps:
                st.update(eps)
        st.update(P.parse_cnsmod(await self._try("AT+CNSMOD?")))
        st.update(P.parse_cpsi(await self._try("AT+CPSI?")))
        st["temperature"] = P.parse_int_value(await self._try("AT+CPMUTEMP"), "+CPMUTEMP")
        st["voltage"] = P.parse_cbc(await self._try("AT+CBC"))
        st["updated_at"] = db.now()
        self.status = st
        self.history.append({
            "t": int(time.time()), "rssi": st.get("rssi_dbm"), "rsrp": st.get("rsrp"),
            "sinr": st.get("sinr"), "rsrq": st.get("rsrq"),
        })
        self._publish_status()

    def snapshot(self) -> dict:
        return {
            "connected": self.connected, "mock": config.MOCK, "error": self.error,
            "status": self.status, "info": self.info, "history": list(self.history),
        }

    def _publish_status(self):
        hub.publish("modem.status", {
            "connected": self.connected, "error": self.error, "status": self.status,
            "point": self.history[-1] if self.history else None,
        })

    async def _poll_loop(self):
        while True:
            interval = max(3, int(db.setting("modem.poll_interval", 10)))
            try:
                if not self.connected:
                    await asyncio.sleep(10)
                    await self.connect()
                    continue
                if self._ussd is None:  # a USSD answer may arrive as a late +CME ERROR — don't let a poll take it
                    await self.refresh_status()
                    self._polls = getattr(self, "_polls", 0) + 1
                    if self._polls % 6 == 0:  # about once a minute: the modem may have lost the setting (a reset)
                        await self.ensure_clip()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                log.warning("status poll failed: %s", e)
            await asyncio.sleep(interval)

    # ------------------------------------------------------------ URC routing

    def _on_urc(self, line: str):
        self.urc_log.append({"t": db.now(), "line": line})
        hub.publish("modem.urc", line)
        if line.startswith("+CUSD:"):
            log.info("modem: %s", line[:200])
            if self._ussd and not self._ussd.done():
                self._ussd.set_result(line)
            return
        # the network refused the USSD after the modem's OK: the error comes on its own, after the command
        if self._ussd and not self._ussd.done() and (line.startswith("+CME ERROR") or line == "ERROR"):
            log.info("modem: %s (USSD)", line)
            self._ussd.set_exception(ATError(_ussd_error(line, self.status)))
            return
        if line.startswith("+CMTI:"):
            idx = P.parse_cmti(line)
            if idx is not None:
                asyncio.create_task(self._read_sms(idx))
            return
        if self.on_call_urc:
            try:
                self.on_call_urc(line)
            except Exception:
                log.exception("call URC handler failed")

    # ------------------------------------------------------------ USSD

    async def ussd(self, code: str, timeout: float = 30.0) -> dict:
        """Send a USSD request (*100#, or an answer in an operator's menu) and wait for the network's reply."""
        code = code.strip()
        if not re.fullmatch(r"[0-9*#+]{1,64}", code):
            raise ValueError("USSD — это цифры, * и # (например *100#)")
        async with self._ussd_lock:
            self._ussd = asyncio.get_running_loop().create_future()
            try:
                r = await self.cmd(f'AT+CUSD=1,"{code}",15', timeout=10, check=False)
                log.info("USSD %s: AT+CUSD -> %s %s", code, r.final, r.lines)
                if r.final != "OK":
                    raise ATError(f"модем отклонил запрос: {r.final}")
                line = await asyncio.wait_for(self._ussd, timeout)
            except asyncio.TimeoutError:
                log.warning("USSD %s: no +CUSD from the network in %s s", code, timeout)
                raise ATError("оператор не ответил за %d с" % timeout)
            finally:
                self._ussd = None
        r = P.parse_cusd(line)
        log.info("USSD %s -> %s %s", code, r["status"], r["text"][:80])
        return r

    async def ussd_cancel(self):
        """End an operator's USSD menu session."""
        await self.cmd("AT+CUSD=2", timeout=5, check=False)

    # ------------------------------------------------------------ SMS

    async def send_sms(self, number: str, text: str) -> dict:
        number = db.normalize_phone(number)
        row = db.insert("sms", {"direction": "out", "number": number, "text": text,
                                "status": "sending", "is_read": True, "ts": db.now()})
        hub.publish("sms.new", row)
        try:
            pdus = encodeSmsSubmitPdu(number, text, reference=int(time.time()) % 256,
                                      requestStatusReport=False)
            for pdu in pdus:
                # SIM7600 may take up to 120 s to get the network acknowledgement
                await self.cmd(f"AT+CMGS={pdu.tpduLength}", timeout=125,
                               data=pdu.data.hex().upper())
            row = db.update("sms", row["id"], {"status": "sent", "parts": len(pdus)})
        except Exception as e:
            log.error("send sms failed: %s", e)
            err = str(e)
            if "timeout" in err:
                err += " — сеть не подтвердила отправку (проверьте SMS в LTE / режим отправки в настройках модема)"
            row = db.update("sms", row["id"], {"status": "failed", "error": err})
        hub.publish("sms.updated", row)
        return row

    async def read_stored_sms(self):
        """Import messages left on the SIM (e.g. received while the service was down)."""
        try:
            resp = await self.cmd("AT+CMGL=4", timeout=30)
        except ATError as e:
            log.warning("CMGL failed: %s", e)
            return
        for idx, pdu in P.parse_cmgl(resp.lines):
            await self._store_pdu(idx, pdu)

    async def _read_sms(self, idx: int):
        try:
            resp = await self.cmd(f"AT+CMGR={idx}", timeout=10)
        except ATError as e:
            log.warning("CMGR %s failed: %s", idx, e)
            return
        pdu = P.parse_cmgr(resp.lines)
        if pdu:
            await self._store_pdu(idx, pdu)

    async def _store_pdu(self, idx: int, pdu_hex: str):
        try:
            sms = decodeSmsPdu(pdu_hex)
        except Exception as e:
            log.warning("cannot decode PDU at %s: %s", idx, e)
            return
        if sms.get("type") != "SMS-DELIVER":
            await self._delete_sms(idx)
            return
        number = sms.get("number") or ""
        text = sms.get("text") or ""
        ts = sms["time"].astimezone().isoformat(timespec="seconds") if sms.get("time") else db.now()
        concat = None
        for ie in sms.get("udh") or []:
            if hasattr(ie, "reference") and hasattr(ie, "parts"):
                concat = ie
        if concat and concat.parts > 1:
            db.execute(
                "INSERT OR REPLACE INTO sms_parts(number, ref, total, seq, text, ts) VALUES(?,?,?,?,?,?)",
                (number, concat.reference, concat.parts, concat.number, text, ts))
            parts = db.fetch_all("sms_parts", "SELECT * FROM sms_parts WHERE number=? AND ref=? ORDER BY seq",
                                 (number, concat.reference))
            await self._delete_sms(idx)
            if len(parts) < concat.parts:
                return
            text = "".join(p["text"] for p in parts)
            ts = parts[0]["ts"]
            db.execute("DELETE FROM sms_parts WHERE number=? AND ref=?", (number, concat.reference))
        else:
            await self._delete_sms(idx)
        row = db.insert("sms", {"direction": "in", "number": db.normalize_phone(number) or number,
                                "text": text, "status": "received", "is_read": False,
                                "parts": concat.parts if concat else 1, "ts": ts})
        log.info("SMS from %s: %s", number, text[:60])
        hub.publish("sms.new", row)

    async def _delete_sms(self, idx: int):
        if db.setting("modem.sms_delete_after_read", True):
            try:
                await self.cmd(f"AT+CMGD={idx}")
            except ATError:
                pass


modem = Modem()
