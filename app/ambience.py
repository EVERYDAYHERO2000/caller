"""Background sound of an agent call — city noise under the agent's voice that also fills the pauses while the
answer is being synthesized.

It is mixed only into what goes to the modem (TX), so the person hears it and the recording has it (right
channel), but the speech recognition never does: Yandex gets the caller's audio (RX) only.

The sounds are 8 kHz mono WAVs in app/sounds/ambience, normalized to about -26 LUFS (made from mp3 with ffmpeg:
highpass 150, lowpass 3400, loudnorm I=-26). The level in a call is `ambience.volume` on top of that.
"""
import logging
import random
import wave
from array import array
from functools import lru_cache
from pathlib import Path

from . import db

log = logging.getLogger("ambience")

DIR = Path(__file__).resolve().parent / "sounds" / "ambience"
RATE = 8000
SEAM_S = 2  # the loop's end is crossfaded into its start

CATALOG = [
    {"id": "street", "name": "Городская улица"},
    {"id": "city", "name": "Шум улицы города"},
    {"id": "sidewalk", "name": "На тротуаре"},
    {"id": "intersection", "name": "Перекрёсток"},
    {"id": "cars", "name": "Шум машин"},
    {"id": "wet", "name": "Мокрая улица в центре"},
    {"id": "winter", "name": "Зимний трафик"},
    {"id": "construction", "name": "Крыша парковки, стройка вдали"},
]
RANDOM = "random"


def sounds() -> list[dict]:
    return [s for s in CATALOG if (DIR / f"{s['id']}.wav").exists()]


def path(sound_id: str) -> Path | None:
    p = DIR / f"{sound_id}.wav"
    return p if sound_id in {s["id"] for s in CATALOG} and p.exists() else None


def resolve(choice: str | None) -> str:
    """'' = none, 'random' = any of the sounds, otherwise the sound id (unknown ones → none)."""
    choice = (choice or "").strip()
    if choice == RANDOM:
        ids = [s["id"] for s in sounds()]
        return random.choice(ids) if ids else ""
    return choice if path(choice) else ""


@lru_cache(maxsize=2)
def loop(sound_id: str) -> array:
    """The sound as a seamless loop of 16-bit samples: its last SEAM_S fade into its first ones."""
    with wave.open(str(path(sound_id)), "rb") as w:
        if w.getnchannels() != 1 or w.getsampwidth() != 2 or w.getframerate() != RATE:
            raise ValueError(f"{sound_id}: нужен WAV 8 кГц, 16 бит, моно")
        x = array("h")
        x.frombytes(w.readframes(w.getnframes()))
    f = min(SEAM_S * RATE, len(x) // 4)
    n = len(x)
    out = x[f:]  # starts where the fade-in of the head ends, so out[-1] → out[0] continues the sound
    for i in range(f):
        k = i / f
        out[n - 2 * f + i] = int(x[n - f + i] * (1 - k) + x[i] * k)  # out[n-2f+i] was x[n-f+i]
    return out


def for_call(choice: str | None) -> tuple[str, array | None, float]:
    """(sound id, loop, gain) for a call; (`''`, None, 0) when there is no background."""
    sound_id = resolve(choice)
    if not sound_id:
        return "", None, 0.0
    try:
        return sound_id, loop(sound_id), max(0.0, min(1.0, float(db.setting("ambience.volume", 0.3))))
    except Exception as e:  # noqa: BLE001
        log.warning("background sound %s: %s", sound_id, e)
        return "", None, 0.0
