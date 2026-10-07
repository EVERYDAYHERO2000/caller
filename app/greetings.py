"""Первая фраза агента, синтезированная заранее — пока идёт дозвон или звонит входящий.

После ответа она звучит сразу, без ожидания модели и синтеза. Звук кэшируется по голосу и тексту
(DATA_DIR/greetings/<voice_id>/<hash>.wav): приветствие без имени и с частыми именами синтезируется один раз.
Fish-агент синтезирует её через своё realtime-соединение, которое всё равно открывается до набора
(быстрее HTTP: звук идёт потоком); запасной путь и голоса Yandex — как у хезитаций (HTTP / Realtime API).
"""
import asyncio
import hashlib
import json
import logging
import re

from . import config, fillers
from .audio import Resampler

log = logging.getLogger("greetings")

ROOT = config.DATA_DIR / "greetings"
KEEP = 200  # файлов на голос; старые (по времени использования) удаляются


def render(template: str, variables: dict) -> str:
    """Шаблон первой фразы: неизвестная переменная убирается вместе с лишней пунктуацией —
    «Здравствуйте, {{contact_name}}!» без имени становится «Здравствуйте!»."""
    text = re.sub(r"\{\{\s*(\w+)\s*\}\}", lambda m: str(variables.get(m.group(1)) or ""), template or "")
    text = re.sub(r"\s*,\s*(?=[,.!?…])", "", text)        # «Здравствуйте, !» -> «Здравствуйте!»
    text = re.sub(r"^[\s,]+", "", text)
    text = re.sub(r"\s+([,.!?…])", r"\1", text)
    text = re.sub(r"\s{2,}", " ", text).strip()
    return text[:1].upper() + text[1:]


def _path(voice: dict, text: str):
    sound = {k: voice.get(k) for k in ("engine", "voice", "model", "speed", "role", "language")}
    digest = hashlib.sha1(json.dumps([sound, text], ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:20]
    return ROOT / str(voice["id"]) / f"{digest}.wav"


def _prune(folder):
    files = sorted(folder.glob("*.wav"), key=lambda p: p.stat().st_mtime, reverse=True)
    for p in files[KEEP:]:
        p.unlink(missing_ok=True)


def cached(voice: dict, text: str) -> bytes | None:
    """WAV of this phrase in this voice, if it was synthesized before."""
    path = _path(voice, text)
    if not path.exists():
        return None
    path.touch()  # recently used — kept by _prune
    return path.read_bytes()


def store(voice: dict, text: str, pcm: bytes, rate: int) -> bytes:
    """Save a synthesized phrase (PCM16 mono) to the cache; returns the WAV."""
    data = fillers._pcm_to_wav(pcm[: len(pcm) // 2 * 2], rate)
    path = _path(voice, text)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    _prune(path.parent)
    return data


async def to_rate(data: bytes, rate: int) -> bytes:
    raw, src = fillers._wav_info(data)
    if src == rate:
        return raw
    return await asyncio.to_thread(lambda: Resampler(src, rate).process(raw))


async def pcm(voice: dict, text: str, rate: int) -> bytes:
    """PCM16 `rate` Гц с фразой этим голосом — из кэша или синтезом по HTTP."""
    data = cached(voice, text)
    if data is None:
        data = await fillers.synthesize(voice, text, kind="greeting")
        _, src = fillers._wav_info(data)
        data = store(voice, text, fillers._wav_info(data)[0], src)
        log.info("greeting for voice %s synthesized over HTTP: %r", voice["id"], text)
    return await to_rate(data, rate)


def forget(voice_id: int):
    """Голос изменился или удалён — его приветствия больше не годятся."""
    import shutil
    shutil.rmtree(ROOT / str(voice_id), ignore_errors=True)
