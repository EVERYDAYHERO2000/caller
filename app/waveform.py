"""Peaks of a WAV for the UI player's waveform — a few hundred numbers instead of the whole file.

Recordings are stereo (left = the other person, right = the agent / you): the player draws the left channel up
and the right one down, so it shows who speaks when.
"""
import wave
from array import array
from functools import lru_cache
from pathlib import Path

BUCKETS = 800


@lru_cache(maxsize=64)
def _peaks(path: str, mtime: float, n: int) -> dict:
    with wave.open(path, "rb") as w:
        ch, width, rate, frames = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        if width != 2:
            raise ValueError("нужен 16-битный WAV")
        x = array("h")
        x.frombytes(w.readframes(frames))
    channels = []
    for c in range(min(ch, 2)):
        s = x[c::ch]  # slicing and min/max are C loops: a 5-minute call takes well under a second on the Pi
        size = max(1, -(-len(s) // n))
        channels.append([round(max(max(b), -min(b)) / 32768, 3) if (b := s[i:i + size]) else 0
                         for i in range(0, len(s), size)])
    return {"duration": round(frames / rate, 2), "channels": channels}


def peaks(path: Path, n: int = BUCKETS) -> dict:
    return _peaks(str(path), path.stat().st_mtime, max(50, min(n, 3000)))
