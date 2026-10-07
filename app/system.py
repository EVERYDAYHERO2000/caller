"""The host (Raspberry Pi): health for the «Система» dashboard and power-saving settings.

Linux /proc and /sys are read directly (no psutil on the Pi); on other systems (development on a laptop)
whatever is unavailable is None. A sample (CPU, temperature, memory) is taken every 10 s and the last hour
is kept for the charts. Changing power saving needs root: it goes through deploy/caller-sys via a narrow
sudo rule installed by deploy/install.sh.
"""
import asyncio
import logging
import os
import platform
import shutil
import socket
import subprocess
import sys
import time
from collections import deque
from pathlib import Path

from . import config, db

log = logging.getLogger("system")

HELPER = config.BASE_DIR / "deploy" / "caller-sys"
SAMPLE_SEC = 10
HISTORY = 360  # one hour
STARTED = time.time()
GOVERNORS_PATH = Path("/sys/devices/system/cpu/cpu0/cpufreq")


def _read(path, default=None):
    try:
        return Path(path).read_text().strip()
    except OSError:
        return default


def _run(*cmd, timeout=5) -> str | None:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip() if r.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


# ---------------------------------------------------------------- readings

def _cpu_times():
    line = _read("/proc/stat", "").split("\n")[0].split()
    if not line or line[0] != "cpu":
        return None
    vals = list(map(int, line[1:]))
    idle = vals[3] + (vals[4] if len(vals) > 4 else 0)
    return sum(vals), idle


def temperature() -> float | None:
    v = _read("/sys/class/thermal/thermal_zone0/temp")
    return round(int(v) / 1000, 1) if v and v.lstrip("-").isdigit() else None


def memory() -> dict:
    info = {}
    for line in _read("/proc/meminfo", "").splitlines():
        k, _, rest = line.partition(":")
        info[k] = int(rest.split()[0]) * 1024 if rest.split() else 0
    if not info:
        return {}
    total, avail = info.get("MemTotal", 0), info.get("MemAvailable", 0)
    return {"total": total, "used": total - avail, "available": avail,
            "swap_total": info.get("SwapTotal", 0), "swap_used": info.get("SwapTotal", 0) - info.get("SwapFree", 0)}


# vcgencmd get_throttled bits: https://www.raspberrypi.com/documentation/computers/os.html#get_throttled
THROTTLE_BITS = {0: "under_voltage", 1: "freq_capped", 2: "throttled", 3: "soft_temp_limit",
                 16: "under_voltage_occurred", 17: "freq_capped_occurred", 18: "throttled_occurred",
                 19: "soft_temp_limit_occurred"}


def throttled() -> dict | None:
    out = _run("vcgencmd", "get_throttled")
    if not out or "=" not in out:
        return None
    value = int(out.split("=")[1], 16)
    return {"raw": hex(value), **{name: bool(value & (1 << bit)) for bit, name in THROTTLE_BITS.items()}}


def _unescape(s: str) -> str:
    """iw prints non-ASCII SSID bytes as \\xHH escapes — back to UTF-8 text."""
    if "\\x" not in s:
        return s
    try:
        return s.encode("latin-1", "backslashreplace").decode("unicode_escape").encode("latin-1").decode("utf-8")
    except (UnicodeError, ValueError):
        return s


def wifi() -> dict:
    iface = "wlan0"
    out = {"interface": iface}
    link = _run("/usr/sbin/iw", "dev", iface, "link") or _run("iw", "dev", iface, "link") or ""
    for line in link.splitlines():
        line = line.strip()
        if line.startswith("SSID:"):
            out["ssid"] = _unescape(line[5:].strip())
        elif line.startswith("signal:"):
            out["signal_dbm"] = int(line.split()[1])
        elif line.startswith("tx bitrate:"):
            out["bitrate"] = " ".join(line.split()[2:4])
    ps = _run("/usr/sbin/iw", "dev", iface, "get", "power_save") or _run("iw", "dev", iface, "get", "power_save")
    out["power_save"] = None if not ps else ps.split(":")[-1].strip() == "on"
    return out


def ip_address() -> str | None:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.0.2.1", 9))  # no packet is sent
            return s.getsockname()[0]
    except OSError:
        return None


def governor() -> dict:
    return {"current": _read(GOVERNORS_PATH / "scaling_governor"),
            "available": (_read(GOVERNORS_PATH / "scaling_available_governors") or "").split()}


def _process() -> dict:
    rss = None
    for line in _read(f"/proc/{os.getpid()}/status", "").splitlines():
        if line.startswith("VmRSS:"):
            rss = int(line.split()[1]) * 1024
    return {"pid": os.getpid(), "rss": rss, "uptime": round(time.time() - STARTED), "python": platform.python_version()}


def _os_name() -> str:
    for line in _read("/etc/os-release", "").splitlines():
        if line.startswith("PRETTY_NAME="):
            return line.split("=", 1)[1].strip('"')
    return f"{platform.system()} {platform.release()}"


# ---------------------------------------------------------------- monitor

class Monitor:
    def __init__(self):
        self.history: deque = deque(maxlen=HISTORY)
        self.cpu = None
        self._prev = None
        self._task: asyncio.Task | None = None

    def start(self):
        self._task = asyncio.create_task(self._loop())

    async def stop(self):
        if self._task:
            self._task.cancel()

    def _sample(self):
        now = _cpu_times()
        if now and self._prev:
            total, idle = now[0] - self._prev[0], now[1] - self._prev[1]
            self.cpu = round(100 * (1 - idle / total), 1) if total > 0 else None
        self._prev = now
        mem = memory()
        self.history.append({"t": int(time.time()), "cpu": self.cpu, "temp": temperature(),
                             "mem": round(100 * mem["used"] / mem["total"], 1) if mem.get("total") else None})

    async def _loop(self):
        while True:
            try:
                self._sample()
            except Exception as e:  # noqa: BLE001
                log.debug("system sample failed: %s", e)
            await asyncio.sleep(SAMPLE_SEC)


monitor = Monitor()


def info() -> dict:
    disk = shutil.disk_usage(config.DATA_DIR)
    load = os.getloadavg() if hasattr(os, "getloadavg") else None
    freq = _read(GOVERNORS_PATH / "scaling_cur_freq")
    uptime = _read("/proc/uptime")
    return {
        "hostname": socket.gethostname(),
        "model": (_read("/proc/device-tree/model") or platform.machine()).strip("\x00"),
        "os": _os_name(), "kernel": platform.release(), "arch": platform.machine(),
        "uptime": int(float(uptime.split()[0])) if uptime else None,
        "cpu": {"percent": monitor.cpu, "cores": os.cpu_count(), "load": [round(x, 2) for x in load] if load else None,
                "freq_mhz": int(freq) // 1000 if freq and freq.isdigit() else None, "governor": governor()},
        "temperature": temperature(),
        "throttled": throttled(),
        "memory": memory(),
        "disk": {"total": disk.total, "used": disk.used, "free": disk.free, "path": str(config.DATA_DIR)},
        "network": {"ip": ip_address(), "wifi": wifi()},
        "process": _process(),
        "power": power_settings(),
        "helper": HELPER.exists() and sys.platform.startswith("linux"),
        "history": list(monitor.history),
    }


# ---------------------------------------------------------------- power saving

def power_settings() -> dict:
    return {"wifi_powersave": wifi().get("power_save"), "cpu_governor": governor()["current"],
            "governors": governor()["available"]}


async def _helper(*args) -> None:
    if not HELPER.exists() or not sys.platform.startswith("linux"):
        raise RuntimeError("Настройка доступна только на Raspberry Pi (Linux)")
    proc = await asyncio.create_subprocess_exec("sudo", "-n", str(HELPER), *args,
                                                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    out, err = await asyncio.wait_for(proc.communicate(), 20)
    if proc.returncode:
        raise RuntimeError((err or out).decode(errors="replace").strip() or f"caller-sys: код {proc.returncode}")


async def set_power(wifi_powersave: bool | None = None, cpu_governor: str | None = None) -> dict:
    if wifi_powersave is not None:
        await _helper("wifi-powersave", "on" if wifi_powersave else "off")
        db.set_settings({"system.wifi_powersave": wifi_powersave})
    if cpu_governor:
        if cpu_governor not in governor()["available"]:
            raise RuntimeError(f"неизвестный режим процессора: {cpu_governor}")
        await _helper("governor", cpu_governor)
        db.set_settings({"system.cpu_governor": cpu_governor})
    return power_settings()


async def apply_saved():
    """At startup: the CPU governor resets on reboot — re-apply the chosen one (Wi-Fi keeps its own setting)."""
    gov = db.setting("system.cpu_governor", "")
    if gov and gov != governor()["current"]:
        try:
            await _helper("governor", gov)
            log.info("cpu governor set to %s", gov)
        except Exception as e:  # noqa: BLE001
            log.warning("cpu governor not applied: %s", e)
