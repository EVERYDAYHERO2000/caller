"""Emulated SIM7600 for development without hardware (CALLER_MOCK=1)."""
import logging
import random
import threading
import time

from .at import ATError, ATResponse

log = logging.getLogger("modem.mock")


class MockATPort:
    def __init__(self, port, baudrate, on_urc, on_disconnect=None):
        self.on_urc = on_urc
        self.connected = False
        self.in_call = False
        self.answered_ring = False
        self.call_started = 0.0
        self.sms_store: dict[int, str] = {}
        self._lock = threading.Lock()

    def open(self):
        self.connected = True

    def close(self):
        self.connected = False

    def _urc(self, line, delay=0.0):
        threading.Timer(delay, self.on_urc, args=(line,)).start()

    def command(self, cmd: str, timeout=5.0, data=None, check=True) -> ATResponse:
        with self._lock:
            resp = self._handle(cmd.strip(), data)
            time.sleep(0.02)
        if check and not resp.ok:
            raise ATError(f"{cmd}: {resp.final}")
        return resp

    def _handle(self, cmd: str, data) -> ATResponse:
        c = cmd.upper()
        ok = lambda *lines: ATResponse(list(lines), "OK")  # noqa: E731
        rsrp = random.randint(-1050, -850)
        table = {
            "AT+CSQ": ok(f"+CSQ: {random.randint(14, 24)},99"),
            "AT+COPS?": ok('+COPS: 0,0,"MTS RUS",7'),
            "AT+CREG?": ok("+CREG: 0,1"),
            "AT+CEREG?": ok("+CEREG: 0,1"),
            "AT+CNSMOD?": ok("+CNSMOD: 0,8"),
            "AT+CPSI?": ok(f"+CPSI: LTE,Online,250-01,0x1A2B,26844162,112,EUTRAN-BAND3,1602,5,5,"
                           f"{random.randint(-120, -70)},{rsrp},{rsrp + 250},{random.randint(3, 22)}"),
            "AT+CPMUTEMP": ok(f"+CPMUTEMP: {random.randint(38, 45)}"),
            "AT+CBC": ok("+CBC: 3.921V"),
            "AT+CGMI": ok("SIMCOM INCORPORATED"),
            "AT+CGMM": ok("SIMCOM_SIM7600G-H"),
            "AT+CGMR": ok("+CGMR: LE20B04SIM7600G22"),
            "AT+CGSN": ok("862636050000000"),
            "AT+CIMI": ok("250010000000000"),
            "AT+CICCID": ok("+ICCID: 89701010000000000000"),
            "AT+CNUM": ok('+CNUM: "","+79990000000",145'),
            "AT+CPIN?": ok("+CPIN: READY"),
            "AT+CNMP?": ok("+CNMP: 2"),
        }
        if c in table:
            return table[c]
        if c.startswith("AT+CUSD=1"):  # a balance answer in UCS2, like Russian operators send
            code = c.split('"')[1] if '"' in c else ""
            if code == "*102#":  # like an operator refusing USSD in LTE: OK first, then a late error
                self._urc("+CME ERROR: retry operation", 1.0)
                return ok()
            text = "Баланс: 123,45 р. Тариф «Тестовый»." if code == "*100#" else f"Запрос {code} принят. 1 — да, 2 — нет"
            self._urc(f'+CUSD: {0 if code == "*100#" else 1},"{text.encode("utf-16-be").hex().upper()}",72', 1.0)
            return ok()
        if c.startswith("ATD"):
            self.in_call = True
            self.call_started = time.time()
            self._urc("VOICE CALL: BEGIN", 3.0)
            return ok()
        if c == "ATA":
            self.answered_ring = True
            self.in_call = True
            self.call_started = time.time()
            self._urc("VOICE CALL: BEGIN", 0.5)
            return ok()
        if c in ("AT+CHUP", "ATH"):
            self.answered_ring = True  # also stops a ringing incoming call
            if self.in_call:
                self.in_call = False
                dur = int(time.time() - self.call_started)
                self._urc(f"VOICE CALL: END: {dur // 60:02d}{dur % 60:04d}", 0.2)
            return ok()
        if c.startswith("AT+CMGS="):
            return ok(f"+CMGS: {random.randint(1, 255)}")
        if c.startswith("AT+CMGR="):
            idx = int(c.split("=")[1])
            if idx in self.sms_store:
                return ok("+CMGR: 0,,30", self.sms_store[idx])
            return ATResponse([], "+CMS ERROR: invalid memory index")
        if c.startswith("AT+CMGD="):
            self.sms_store.pop(int(c.split("=")[1].split(",")[0]), None)
            return ok()
        if c.startswith("AT+CMGL"):
            return ok()
        if c == "AT+CRESET":
            return ok()
        return ok()

    # ---- helpers used by the /api/modem/mock/* endpoints

    def simulate_incoming_call(self, number: str):
        self.answered_ring = False
        def run():
            for _ in range(4):
                if self.in_call or self.answered_ring:
                    return
                self.on_urc("RING")
                self.on_urc(f'+CLIP: "{number}",145,,,,0')
                time.sleep(3)
            if not self.in_call:
                self.on_urc(f"MISSED_CALL: 12:00 {number}")
        threading.Thread(target=run, daemon=True).start()

    def simulate_incoming_sms(self, number: str, text: str):
        idx = max(self.sms_store, default=0) + 1
        self.sms_store[idx] = _deliver_pdu(number, text)
        self._urc(f'+CMTI: "SM",{idx}')


def _deliver_pdu(number: str, text: str) -> str:
    """Minimal SMS-DELIVER PDU (UCS2, single part) for the emulator."""
    digits = number.lstrip("+")
    toa = "91" if number.startswith("+") else "81"
    padded = digits + ("F" if len(digits) % 2 else "")
    semi = "".join(padded[i + 1] + padded[i] for i in range(0, len(padded), 2))
    ud = text[:70].encode("utf-16-be")
    ts = time.strftime("%y%m%d%H%M%S")
    ts_sw = "".join(ts[i + 1] + ts[i] for i in range(0, 12, 2)) + "21"
    return ("00" + "04" + f"{len(digits):02X}" + toa + semi + "00" + "08" + ts_sw
            + f"{len(ud):02X}" + ud.hex().upper())
