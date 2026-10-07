"""Хезитации голоса — «Ммм...», «Секундочку...»: заполняют паузу, пока готовится ответ агента.

Набор принадлежит голосу из раздела «Голоса» (Yandex или Fish): строки в таблице voice_fillers, звук —
DATA_DIR/voice_fillers/<voice_id>/<id>.wav. Фразы можно добавлять и удалять; у голоса без набора стандартный
набор генерируется фоном (при сохранении голоса или агента, в крайнем случае в начале звонка).
Синтез: Fish — HTTP API (не занимает единственное realtime-соединение Kitta), Yandex — Realtime API.
"""
import asyncio
import io
import json
import logging
import random
import shutil
import wave

from . import config, db
from .audio import Resampler
from .agent import fish

log = logging.getLogger("fillers")

ROOT = config.DATA_DIR / "voice_fillers"
KINDS = ("short", "long")
DEFAULT_FILLERS = [
    # (текст, вид) — короткие маскируют ~0.5 с паузы, длинные почти всю
    ("Ммм...", "short"), ("Так...", "short"), ("Угу.", "short"), ("Ну...", "short"), ("Хм...", "short"),
    ("Так-так...", "short"), ("Секундочку...", "long"), ("Сейчас посмотрю.", "long"),
    ("Так, дайте подумать...", "long"), ("Минутку, уточняю.", "long"),
]

_jobs: dict[int, asyncio.Task] = {}
_errors: dict[int, str] = {}


def folder(voice_id: int):
    return ROOT / str(voice_id)


def wav_path(voice_id: int, filler_id: int):
    return folder(voice_id) / f"{filler_id}.wav"


def list_fillers(voice_id: int) -> list[dict]:
    rows = db.fetch_all("voice_fillers", "SELECT * FROM voice_fillers WHERE voice_id=? ORDER BY "
                        "CASE kind WHEN 'short' THEN 0 ELSE 1 END, id", (voice_id,))
    return [r for r in rows if wav_path(voice_id, r["id"]).exists()]


def counts() -> dict[int, int]:
    return dict(db.rows("SELECT voice_id, COUNT(*) FROM voice_fillers GROUP BY voice_id"))


def status(voice_id: int) -> str:
    """ready | generating | missing | error: …"""
    job = _jobs.get(voice_id)
    if job and not job.done():
        return "generating"
    if db.scalar("SELECT COUNT(*) FROM voice_fillers WHERE voice_id=?", (voice_id,)):
        return "ready"
    if voice_id in _errors:
        return "error: " + _errors[voice_id]
    return "missing"


# ---------------------------------------------------------------- synthesis

def _pcm_to_wav(pcm: bytes, rate: int) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    return buf.getvalue()


def _wav_info(data: bytes) -> tuple[bytes, int]:
    """(PCM, частота) из WAV — и нашего, и потокового от Kitta (длина в заголовке — заглушка)."""
    parsed = fish.parse_wav(data)
    if not parsed:
        raise fish.FishError("некорректный WAV")
    pcm, rate = parsed
    return pcm[: len(pcm) - len(pcm) % 2], rate


async def synthesize(voice: dict, text: str, kind: str = "filler") -> bytes:
    """WAV с фразой, сказанной этим голосом (kind — статья расходов в usage_log)."""
    s = db.get_settings()
    speed = float(voice.get("speed") or 1.0)
    if voice["engine"] == "fish":
        return await fish.synthesize(s, voice["voice"], text, voice.get("model") or "", speed,
                                     voice.get("language") or "ru", kind=kind)
    from .agent.realtime import synthesize_sample  # realtime imports this module
    pcm, rate = await synthesize_sample(s, voice["voice"], text, role=voice.get("role") or "", speed=speed, kind=kind)
    return _pcm_to_wav(pcm, rate)


async def add_filler(voice: dict, text: str, kind: str = "short") -> dict:
    text = text.strip()
    if not text:
        raise ValueError("пустой текст")
    data = await synthesize(voice, text)
    pcm, rate = _wav_info(data)
    row = db.insert("voice_fillers", {"voice_id": voice["id"], "text": text, "kind": kind if kind in KINDS else "short",
                                      "duration_ms": len(pcm) * 1000 // (2 * rate), "created_at": db.now()})
    folder(voice["id"]).mkdir(parents=True, exist_ok=True)
    wav_path(voice["id"], row["id"]).write_bytes(_pcm_to_wav(pcm, rate))  # a clean header with the real length
    return row


def delete_filler(voice_id: int, filler_id: int) -> bool:
    for p in folder(voice_id).glob(f"{filler_id}.*"):
        p.unlink()
    return db.execute("DELETE FROM voice_fillers WHERE id=? AND voice_id=?", (filler_id, voice_id)).rowcount > 0


def delete_voice(voice_id: int):
    db.execute("DELETE FROM voice_fillers WHERE voice_id=?", (voice_id,))
    shutil.rmtree(folder(voice_id), ignore_errors=True)


def _import_legacy(voice: dict) -> bool:
    """Заготовки Fish старого формата (DATA_DIR/fish_fillers/<voiceId>/) — перенести без повторного синтеза."""
    old = fish.FILLER_DIR / voice["voice"]
    manifest = old / "manifest.json"
    if voice["engine"] != "fish" or not manifest.exists():
        return False
    moved = 0
    for f in json.loads(manifest.read_text()):
        src = old / f"{f['id']}.wav"
        if not src.exists():
            continue
        pcm, rate = _wav_info(src.read_bytes())
        row = db.insert("voice_fillers", {"voice_id": voice["id"], "text": f["text"], "kind": f.get("kind", "short"),
                                          "duration_ms": len(pcm) * 1000 // (2 * rate), "created_at": db.now()})
        folder(voice["id"]).mkdir(parents=True, exist_ok=True)
        wav_path(voice["id"], row["id"]).write_bytes(_pcm_to_wav(pcm, rate))
        moved += 1
    return moved > 0


def migrate_legacy():
    """At startup: move the hesitations of the first version (per Fish voiceId) to the voices using them."""
    if not fish.FILLER_DIR.exists():
        return
    have = set(counts())
    for v in db.fetch_all("voices", "SELECT * FROM voices WHERE engine='fish'"):
        if v["id"] not in have and (fish.FILLER_DIR / v["voice"] / "manifest.json").exists():
            if _import_legacy(v):
                log.info("fillers of voice %s moved from %s", v["id"], fish.FILLER_DIR / v["voice"])


def ensure(voice: dict, force: bool = False) -> asyncio.Task | None:
    """Сгенерировать фоном набор заготовок голоса, если его нет (force — перегенерировать все фразы)."""
    vid = voice["id"]
    job = _jobs.get(vid)
    if job and not job.done():
        return job
    if not force and db.scalar("SELECT COUNT(*) FROM voice_fillers WHERE voice_id=?", (vid,)):
        return None
    if not force and _import_legacy(voice):
        return None

    async def run():
        try:
            if force:  # те же фразы заново (или стандартный набор, если список пуст)
                rows = db.fetch_all("voice_fillers", "SELECT * FROM voice_fillers WHERE voice_id=? ORDER BY id", (vid,))
                phrases = [(r["text"], r["kind"]) for r in rows] or DEFAULT_FILLERS
            else:
                phrases = DEFAULT_FILLERS
            sem = asyncio.Semaphore(3 if voice["engine"] == "fish" else 2)

            async def one(text, kind):
                async with sem:
                    try:
                        return await add_filler(voice, text, kind)
                    except Exception as e:  # noqa: BLE001
                        log.warning("filler %r for voice %s failed: %s", text, vid, e)
                        return None
            old = db.rows("SELECT id FROM voice_fillers WHERE voice_id=?", (vid,)) if force else []
            made = [r for r in await asyncio.gather(*(one(t, k) for t, k in phrases)) if r]
            if not made:
                raise RuntimeError("не удалось синтезировать ни одной фразы")
            for (fid,) in old:  # старые — только после успешной замены
                delete_filler(vid, fid)
            _errors.pop(vid, None)
            log.info("fillers for voice %s: %s", vid, len(made))
        except Exception as e:  # noqa: BLE001
            _errors[vid] = str(e) or type(e).__name__
            log.warning("fillers for voice %s failed: %s", vid, e)
            raise
    _jobs[vid] = asyncio.create_task(run())
    return _jobs[vid]


async def load_pcm(voice_id: int, rate: int) -> list[dict]:
    """Заготовки голоса в PCM16 `rate` Гц (пересэмплируются один раз, кэш рядом с wav)."""
    out = []
    for f in list_fillers(voice_id):
        cache = folder(voice_id) / f"{f['id']}.{rate}.pcm"
        if not cache.exists():
            pcm, src = _wav_info(wav_path(voice_id, f["id"]).read_bytes())
            data = await asyncio.to_thread(lambda: Resampler(src, rate).process(pcm) if src != rate else pcm)
            cache.write_bytes(data)
        out.append({**f, "pcm": cache.read_bytes()})
    return out


class FillerPicker:
    def __init__(self, items: list[dict], kind: str = "short"):
        self.items = items
        self.kind = kind
        self.last = None

    def pick(self) -> dict | None:
        pool = [f for f in self.items if self.kind in ("any", "") or f["kind"] == self.kind]
        if len(pool) > 1:
            pool = [f for f in pool if f["id"] != self.last]
        if not pool:
            return None
        f = random.choice(pool)
        self.last = f["id"]
        return f
