"""Version of the build shown under «Caller»: the release number + when its code last changed.

The stamp is the newest modification time of the app and web files (the deploy copies them with their times,
so the Pi shows the same build as the machine it was deployed from), e.g. «1.0.0 · 01.10.26 14:05».
"""
from datetime import datetime

from . import config

VERSION = "1.0.0"


def _stamp() -> str:
    files = [p for d in (config.BASE_DIR / "app", config.WEB_DIR) for p in d.rglob("*")
             if p.is_file() and p.suffix in {".py", ".js", ".css", ".html"} and "__pycache__" not in p.parts]
    newest = max((p.stat().st_mtime for p in files), default=0)
    return datetime.fromtimestamp(newest).strftime("%d.%m.%y %H:%M") if newest else ""


BUILD = _stamp()
FULL = f"{VERSION} · {BUILD}" if BUILD else VERSION
