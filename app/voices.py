"""Голоса: стартовый набор голосов Fish Audio при подключении ключа.

Библиотека Fish — тысячи голосов, поэтому в «Голоса» добавляются только 50 русских (совместимых с потоковой
моделью), остальные находятся поиском при создании голоса. Загрузка выполняется один раз для каждого ключа:
при сохранении нового ключа и при старте, если для текущего ключа её ещё не было.
"""
import asyncio
import hashlib
import logging

import aiohttp

from . import db
from .agent import fish

log = logging.getLogger("voices")

IMPORT_COUNT = 50
IMPORT_LANGUAGE = "ru"

_task: asyncio.Task | None = None
_state = {"running": False, "error": "", "added": 0, "finished_at": None}


def _key_mark(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()[:12]


def status() -> dict:
    return {**_state, "has_key": bool(db.setting("fish.api_key")),
            "imported": db.setting("fish.voices_imported", "") == _key_mark(db.setting("fish.api_key", ""))}


def start_import(force: bool = False) -> bool:
    """Добавить 50 русских голосов Fish, если для текущего ключа их ещё не добавляли (или force)."""
    global _task
    key = db.setting("fish.api_key", "")
    if not key or (_task and not _task.done()):
        return False
    if not force and db.setting("fish.voices_imported", "") == _key_mark(key):
        return False
    _task = asyncio.create_task(_import(key))
    return True


async def _import(key: str):
    _state.update(running=True, error="", added=0)
    try:
        s = db.get_settings()
        url = (s.get("fish.api_url") or fish.DEFAULT_API_URL) + "/v3/voices"
        known = {r[0] for r in db.rows("SELECT voice FROM voices WHERE engine='fish'")}
        ts, new = db.now(), []
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as http:
            page = 1
            while len(new) < IMPORT_COUNT and page <= 5:
                params = {"page": page, "pageSize": 100, "language": IMPORT_LANGUAGE}
                async with http.get(url, headers=fish._auth(s), params=params) as r:
                    if r.status != 200:
                        raise fish.FishError(f"Fish Audio: {r.status} {(await r.text())[:200]}")
                    data = await r.json()
                for v in data.get("items", []):
                    vid = v.get("voiceId")
                    if (len(new) >= IMPORT_COUNT or not vid or vid in known or v.get("isPersonal")
                            or fish.DEFAULT_MODEL not in (v.get("modelIds") or [])):
                        continue
                    known.add(vid)
                    new.append({"name": (v.get("name") or vid).strip()[:120], "engine": "fish", "voice": vid,
                                "description": (v.get("description") or "").strip()[:500], "source": "library",
                                "language": v.get("primaryLanguage") or IMPORT_LANGUAGE, "speed": 1.0,
                                "created_at": ts, "updated_at": ts})
                if page >= int(data.get("totalPages") or 1):
                    break
                page += 1
        db.insert_many("voices", new)
        db.set_settings({"fish.voices_imported": _key_mark(key)})
        _state.update(added=len(new), finished_at=db.now())
        log.info("fish voices imported: %s", len(new))
    except Exception as e:  # noqa: BLE001
        _state["error"] = str(e) or type(e).__name__
        log.warning("fish voices import failed: %s", e)
    finally:
        _state["running"] = False
