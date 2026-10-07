"""Bootstrap configuration (environment variables).

Everything else (modem ports, Yandex credentials, call behaviour) lives in the
database `settings` table and is editable from the UI / API.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("CALLER_DATA_DIR", BASE_DIR / "data"))
DB_PATH = Path(os.environ.get("CALLER_DB", DATA_DIR / "caller.db"))
RECORDINGS_DIR = DATA_DIR / "recordings"
WEB_DIR = BASE_DIR / "web"

HOST = os.environ.get("CALLER_HOST", "0.0.0.0")
PORT = int(os.environ.get("CALLER_PORT", "8080"))
LOG_LEVEL = os.environ.get("CALLER_LOG_LEVEL", "INFO").upper()

# HTTPS listener (browsers only allow microphone access over HTTPS). 0 disables it.
# A self-signed certificate is generated in DATA_DIR/tls on first start unless paths are given.
SSL_PORT = int(os.environ.get("CALLER_SSL_PORT", "8443"))
SSL_CERT = Path(os.environ.get("CALLER_SSL_CERT", DATA_DIR / "tls" / "cert.pem"))
SSL_KEY = Path(os.environ.get("CALLER_SSL_KEY", DATA_DIR / "tls" / "key.pem"))

# CALLER_MOCK=1 — run without hardware (emulated modem), useful for UI development.
MOCK = os.environ.get("CALLER_MOCK", "0") == "1"

DATA_DIR.mkdir(parents=True, exist_ok=True)
RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
