"""Tiny pure-python PCM16 helpers (no numpy needed on the Pi)."""
import math
from array import array


class Resampler:
    """Streaming linear-interpolation resampler for mono PCM16 LE.

    Keeps state between chunks so there are no clicks at chunk boundaries.
    When downsampling, a one-pole low-pass filter reduces aliasing.
    """

    def __init__(self, src_rate: int, dst_rate: int):
        self.src = src_rate
        self.dst = dst_rate
        self.step = src_rate / dst_rate
        self.pos = 0.0
        self.prev = 0
        self.lp = 0.0
        self.alpha = None
        if dst_rate < src_rate:
            fc = dst_rate / 2 * 0.9
            self.alpha = 1 - math.exp(-2 * math.pi * fc / src_rate)

    def process(self, pcm: bytes) -> bytes:
        if self.src == self.dst or not pcm:
            return pcm
        x = array("h")
        x.frombytes(pcm[: len(pcm) - len(pcm) % 2])
        n = len(x)
        if not n:
            return b""
        if self.alpha is not None:
            a, y = self.alpha, self.lp
            for i in range(n):
                y += a * (x[i] - y)
                x[i] = int(y)
            self.lp = y
        out = array("h")
        p, step, prev = self.pos, self.step, self.prev
        while p < n - 1:
            i = math.floor(p)
            frac = p - i
            s0 = prev if i < 0 else x[i]
            s1 = x[i + 1]
            out.append(int(s0 + (s1 - s0) * frac))
            p += step
        self.pos = p - n
        self.prev = x[-1]
        return out.tobytes()


def apply_gain(pcm: bytes, gain: float) -> bytes:
    if gain == 1.0 or not pcm:
        return pcm
    x = array("h")
    x.frombytes(pcm)
    for i in range(len(x)):
        v = int(x[i] * gain)
        x[i] = 32767 if v > 32767 else (-32768 if v < -32768 else v)
    return x.tobytes()
