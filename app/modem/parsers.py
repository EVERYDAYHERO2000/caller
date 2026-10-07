"""Parsers for SIM7600 AT responses."""
import re

REG_STATUS = {
    0: "не зарегистрирован", 1: "домашняя сеть", 2: "поиск сети", 3: "регистрация отклонена",
    4: "неизвестно", 5: "роуминг", 6: "домашняя (только SMS)", 7: "роуминг (только SMS)",
}
NET_MODES = {
    0: "Нет сервиса", 1: "GSM", 2: "GPRS", 3: "EDGE", 4: "WCDMA", 5: "HSDPA", 6: "HSUPA",
    7: "HSPA", 8: "LTE", 9: "TDS-CDMA", 10: "TDS-HSDPA", 11: "TDS-HSUPA", 12: "TDS-HSPA",
    13: "CDMA", 14: "EVDO", 15: "CDMA/EVDO", 16: "CDMA/LTE", 23: "eHRPD", 24: "CDMA/eHRPD",
}
ACT = {0: "GSM", 2: "UTRAN (3G)", 3: "GSM/EGPRS", 4: "HSDPA", 5: "HSUPA", 6: "HSPA", 7: "LTE"}
SMS_SERVICES = {0: "Пакетная сеть (PS)", 1: "Только CS", 2: "PS, при неудаче CS", 3: "CS, при неудаче PS"}
CNMP_MODES = {2: "Автоматически", 13: "Только GSM", 14: "Только WCDMA", 38: "Только LTE",
              48: "Любой кроме LTE", 51: "GSM + LTE", 54: "WCDMA + LTE", 39: "GSM + WCDMA + LTE"}


def _fields(line: str) -> list[str]:
    body = line.split(":", 1)[1] if ":" in line else line
    return [f.strip().strip('"') for f in body.split(",")]


def first(lines: list[str], prefix: str) -> str | None:
    for ln in lines:
        if ln.startswith(prefix):
            return ln
    return None


def plain(lines: list[str]) -> str:
    """For commands that answer with a bare value (AT+CGSN, AT+CIMI...)."""
    for ln in lines:
        if ln and not ln.startswith("+") and ln != "OK":
            return ln.strip()
    for ln in lines:
        if ":" in ln:
            return ln.split(":", 1)[1].strip().strip('"')
    return ""


def parse_csq(lines) -> dict:
    ln = first(lines, "+CSQ")
    if not ln:
        return {}
    f = _fields(ln)
    rssi = int(f[0])
    ber = int(f[1]) if len(f) > 1 and f[1].isdigit() else 99
    if rssi == 99 or rssi > 31:
        return {"csq": rssi, "rssi_dbm": None, "signal_percent": 0, "ber": ber}
    return {"csq": rssi, "rssi_dbm": -113 + 2 * rssi,
            "signal_percent": round(rssi * 100 / 31), "ber": ber}


def parse_cops(lines) -> dict:
    ln = first(lines, "+COPS")
    if not ln:
        return {}
    f = _fields(ln)
    out = {"operator": f[2] if len(f) > 2 else ""}
    if len(f) > 3 and f[3].isdigit():
        out["access_tech"] = ACT.get(int(f[3]), f[3])
    return out


def parse_creg(lines, prefix="+CREG") -> dict:
    ln = first(lines, prefix)
    if not ln:
        return {}
    f = _fields(ln)
    try:
        stat = int(f[1] if len(f) > 1 else f[0])
    except ValueError:
        return {}
    return {"reg_code": stat, "registration": REG_STATUS.get(stat, str(stat))}


def parse_cnsmod(lines) -> dict:
    ln = first(lines, "+CNSMOD")
    if not ln:
        return {}
    f = _fields(ln)
    try:
        mode = int(f[1] if len(f) > 1 else f[0])
    except ValueError:
        return {}
    return {"network_type": NET_MODES.get(mode, str(mode))}


def _tenth(v):
    try:
        return round(int(v) / 10, 1)
    except (TypeError, ValueError):
        return None


def parse_cpsi(lines) -> dict:
    ln = first(lines, "+CPSI")
    if not ln:
        return {}
    f = _fields(ln)
    out = {"system_mode": f[0], "operation_mode": f[1] if len(f) > 1 else "", "cpsi_raw": ln}
    if len(f) > 2:
        out["mcc_mnc"] = f[2]
    if f[0] == "LTE" and len(f) >= 14:
        out.update({
            "tac": f[3], "cell_id": f[4], "pci": f[5], "band": f[6].replace("EUTRAN-", ""),
            "earfcn": f[7], "dl_bw": f[8], "ul_bw": f[9],
            "rsrq": _tenth(f[10]), "rsrp": _tenth(f[11]), "rssi": _tenth(f[12]),
            "sinr": int(f[13]) if f[13].lstrip("-").isdigit() else None,
        })
    elif f[0] == "GSM" and len(f) >= 7:
        out.update({"lac": f[3], "cell_id": f[4], "band": f[5], "rx_level": f[6]})
    elif f[0] == "WCDMA" and len(f) >= 7:
        out.update({"lac": f[3], "cell_id": f[4], "band": f[5], "uarfcn": f[6]})
        if len(f) >= 13:
            out.update({"ecio": f[10], "rscp": f[11]})
    return out


def parse_int_value(lines, prefix) -> int | None:
    ln = first(lines, prefix)
    if not ln:
        return None
    m = re.search(r"-?\d+", ln.split(":", 1)[1])
    return int(m.group()) if m else None


def parse_cbc(lines) -> float | None:
    ln = first(lines, "+CBC")
    if not ln:
        return None
    m = re.search(r"(\d+\.\d+)V", ln)
    if m:
        return float(m.group(1))
    m = re.search(r"(\d{4})", ln)
    return int(m.group(1)) / 1000 if m else None


def parse_cnum(lines) -> str:
    ln = first(lines, "+CNUM")
    if not ln:
        return ""
    f = _fields(ln)
    return f[1] if len(f) > 1 else ""


def parse_clip(line: str) -> str:
    m = re.search(r'\+CLIP:\s*"([^"]*)"', line)
    return m.group(1) if m else ""


def parse_cmti(line: str) -> int | None:
    m = re.search(r"\+CMTI:\s*\"?\w+\"?,\s*(\d+)", line)
    return int(m.group(1)) if m else None


def parse_cmgl(lines) -> list[tuple[int, str]]:
    """Return list of (index, pdu_hex) from AT+CMGL in PDU mode."""
    out = []
    idx = None
    for ln in lines:
        if ln.startswith("+CMGL:"):
            try:
                idx = int(_fields(ln)[0])
            except ValueError:
                idx = None
        elif idx is not None and re.fullmatch(r"[0-9A-Fa-f]+", ln):
            out.append((idx, ln))
            idx = None
    return out


def parse_cmgr(lines) -> str | None:
    for ln in lines:
        if re.fullmatch(r"[0-9A-Fa-f]{10,}", ln):
            return ln
    return None


CUSD_STATUS = {0: "", 1: "оператор ждёт ответа", 2: "сеанс завершён сетью", 3: "ответил другой клиент",
               4: "операция не поддерживается", 5: "сеть не ответила вовремя"}


def _ussd_text(raw: str, dcs: int | None) -> str:
    """The USSD answer: UCS2 (hex of UTF-16BE, dcs 72 / 0x48 — what Russian operators send) or plain text."""
    hexlike = bool(raw) and len(raw) % 4 == 0 and all(c in "0123456789ABCDEFabcdef" for c in raw)
    if hexlike and (dcs is None or dcs & 0x0C == 0x08 or dcs == 72):
        try:
            return bytes.fromhex(raw).decode("utf-16-be")
        except ValueError:
            pass
    return raw


def parse_cusd(line: str) -> dict:
    """+CUSD: <m>[,"<str>"[,<dcs>]] -> {status, text, more (the network waits for an answer), note}."""
    m = re.match(r'\+CUSD:\s*(\d+)(?:\s*,\s*"(.*)"(?:\s*,\s*(\d+))?)?', line.strip(), re.S)
    if not m:
        return {"status": None, "text": line, "more": False, "note": ""}
    code, raw, dcs = int(m.group(1)), m.group(2) or "", m.group(3)
    return {"status": code, "text": _ussd_text(raw, int(dcs) if dcs else None).strip(), "more": code == 1,
            "note": CUSD_STATUS.get(code, "")}
