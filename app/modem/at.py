"""AT command channel for SIM7600 (thread-based, pyserial).

A reader thread splits incoming data into lines. Lines belonging to the
currently executing command are collected as its response; everything else is
treated as an unsolicited result code (URC) and passed to `on_urc`.
"""
import logging
import re
import threading
from dataclasses import dataclass, field

log = logging.getLogger("modem.at")

URC_PREFIXES = (
    "RING", "+CRING:", "+CLIP:", "+CMTI:", "+CMT:", "+CDS:", "+CDSI:", "VOICE CALL:",
    "NO CARRIER", "BUSY", "NO ANSWER", "MISSED_CALL:", "+CPIN:", "SMS DONE", "PB DONE",
    "+CREG:", "+CGREG:", "+CEREG:", "RDY", "+CFUN:", "+CUSD:", "+RXDTMF:", "+CGEV:",
    "+CLCC:", "+CNMP:", "+CPSI:",
)
CALL_END_CODES = ("NO CARRIER", "BUSY", "NO ANSWER", "NO DIALTONE")


class ATError(Exception):
    pass


@dataclass
class ATResponse:
    lines: list[str] = field(default_factory=list)
    final: str = ""

    @property
    def ok(self) -> bool:
        return self.final == "OK"


def _is_urc(line: str) -> bool:
    return any(line.startswith(p) for p in URC_PREFIXES)


class ATPort:
    def __init__(self, port: str, baudrate: int, on_urc, on_disconnect=None):
        self.port = port
        self.baudrate = baudrate
        self.on_urc = on_urc
        self.on_disconnect = on_disconnect
        self._ser = None
        self._lock = threading.Lock()
        self._pending = None
        self._running = False

    @property
    def connected(self) -> bool:
        return self._running and self._ser is not None

    def open(self):
        import serial
        self._ser = serial.Serial(self.port, self.baudrate, timeout=0.2)
        self._running = True
        threading.Thread(target=self._reader, name="at-reader", daemon=True).start()

    def close(self):
        self._running = False
        if self._ser:
            try:
                self._ser.close()
            except Exception:
                pass
        self._ser = None

    # ------------------------------------------------------------ reading

    def _reader(self):
        buf = b""
        while self._running:
            try:
                data = self._ser.read(512)
            except Exception as e:  # serial.SerialException / OSError
                if not self._running:  # port closed on purpose (shutdown / reconnect)
                    break
                log.error("AT port read error: %s", e)
                self._running = False
                try:  # release the tty so the kernel can reuse its number
                    self._ser.close()
                except Exception:
                    pass
                self._ser = None
                if self.on_disconnect:
                    self.on_disconnect(str(e))
                break
            if not data:
                continue
            buf += data
            while b"\n" in buf:
                raw, buf = buf.split(b"\n", 1)
                line = raw.strip(b"\r \x00").decode("utf-8", "replace")
                if line:
                    self._handle_line(line)
            p = self._pending
            if p is not None and p["want_prompt"] and buf.strip().startswith(b">"):
                buf = b""
                p["prompt"].set()

    def _handle_line(self, line: str):
        p = self._pending
        if p is not None:
            if line == p["cmd"]:
                return  # echo
            if line == "OK":
                p["final"] = "OK"
                p["done"].set()
                return
            if line == "ERROR" or line.startswith("+CME ERROR") or line.startswith("+CMS ERROR"):
                p["final"] = line
                p["done"].set()
                return
            if p["prefix"] and line.startswith(p["prefix"] + ":"):
                p["lines"].append(line)
                return
            if p["dial"] and line in CALL_END_CODES:
                p["final"] = line
                p["done"].set()
            elif not _is_urc(line):
                p["lines"].append(line)
                return
        log.debug("URC: %s", line)
        try:
            self.on_urc(line)
        except Exception:
            log.exception("URC handler failed")

    # ------------------------------------------------------------ commands

    def command(self, cmd: str, timeout: float = 5.0, data: str | None = None,
                check: bool = True) -> ATResponse:
        with self._lock:
            if not self.connected:
                raise ATError("AT port is not open")
            m = re.match(r"^AT([+$^#][A-Z0-9]+)", cmd.upper())
            pending = {
                "cmd": cmd, "prefix": m.group(1) if m else None, "lines": [], "final": "",
                "done": threading.Event(), "prompt": threading.Event(),
                "want_prompt": data is not None,
                "dial": cmd.upper().startswith(("ATD", "ATA")),
            }
            self._pending = pending
            try:
                log.debug(">> %s", cmd)
                self._ser.write((cmd + "\r").encode())
                if data is not None:
                    if not pending["prompt"].wait(timeout):
                        self._ser.write(b"\x1b")
                        raise ATError(f"{cmd}: no '>' prompt")
                    self._ser.write(data.encode() + b"\x1a")
                if not pending["done"].wait(timeout):
                    if data is not None:
                        # abort the pending send, otherwise the modem keeps swallowing
                        # every following command as message data
                        self._ser.write(b"\x1b")
                    raise ATError(f"{cmd}: timeout")
            finally:
                self._pending = None
            resp = ATResponse(pending["lines"], pending["final"])
            log.debug("<< %s %s", resp.lines, resp.final)
            if check and not resp.ok:
                raise ATError(f"{cmd}: {resp.final}")
            return resp
