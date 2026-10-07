"""Users, password hashing (PBKDF2) and login sessions."""
import hashlib
import hmac
import secrets
import time

from . import db

DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "admin"
SESSION_TTL = 30 * 24 * 3600
COOKIE = "caller_session"
_ITERATIONS = 120_000  # ~0.3 s on a Raspberry Pi 3


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), _ITERATIONS).hex()
    return f"pbkdf2_sha256${_ITERATIONS}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iterations, salt, digest = stored.split("$")
        calc = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(iterations)).hex()
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(calc, digest)


def ensure_default_user():
    if not db.scalar("SELECT COUNT(*) FROM users"):
        ts = db.now()
        db.execute("INSERT INTO users(username, password_hash, is_default, created_at, updated_at) "
                   "VALUES(?,?,1,?,?)", (DEFAULT_USERNAME, hash_password(DEFAULT_PASSWORD), ts, ts))


def authenticate(username: str, password: str) -> dict | None:
    user = db.fetch_one("users", "SELECT * FROM users WHERE username=?", (username.strip(),))
    if user and verify_password(password, user["password_hash"]):
        return user
    return None


def create_session(user_id: int, ip: str = "") -> str:
    token = secrets.token_urlsafe(32)
    db.execute("DELETE FROM sessions WHERE expires_at < ?", (time.time(),))
    db.execute("INSERT INTO sessions(token, user_id, created_at, expires_at, ip) VALUES(?,?,?,?,?)",
               (token, user_id, db.now(), time.time() + SESSION_TTL, ip))
    return token


def session_user(token: str) -> dict | None:
    if not token:
        return None
    return db.fetch_one(
        "users",
        "SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token=? AND s.expires_at > ?",
        (token, time.time()))


def delete_session(token: str):
    db.execute("DELETE FROM sessions WHERE token=?", (token,))


def change_credentials(user_id: int, new_password: str, new_username: str | None, keep_token: str):
    data = {"password_hash": hash_password(new_password), "is_default": 0, "updated_at": db.now()}
    if new_username:
        data["username"] = new_username.strip()
    sets = ", ".join(f"{k}=?" for k in data)
    db.execute(f"UPDATE users SET {sets} WHERE id=?", (*data.values(), user_id))
    # log out every other browser
    db.execute("DELETE FROM sessions WHERE user_id=? AND token<>?", (user_id, keep_token))


def public_user(user: dict) -> dict:
    return {"id": user["id"], "username": user["username"], "default_password": bool(user.get("is_default"))}
