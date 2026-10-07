"""SIM7600 USB voice channel (/dev/ttyUSB4 after AT+CPCMREG=1).

The modem streams 8 kHz / 16-bit / mono PCM in both directions. We read frames
from the far end and write our audio paced at real time (20 ms per 320 bytes),
padding with silence when the agent is quiet. An optional background sound (city noise) is mixed into
what we send — never into what we read, so the speech recognition doesn't hear it.
"""
import logging
import threading
import time
import wave
from array import array

log = logging.getLogger("modem.audio")

RATE = 8000
FRAME_MS = 20
FRAME_BYTES = RATE * 2 * FRAME_MS // 1000  # 320
SILENCE = b"\x00" * FRAME_BYTES


class AudioPort:
    def __init__(self, port: str, on_frame, record: bool = False):
        self.port = port
        self.on_frame = on_frame
        self.record = record
        self._ser = None
        self._running = False
        self._buf = bytearray()
        self._lock = threading.Lock()
        self._vol = 1.0      # current playback volume (applied by the writer)
        self._target = 1.0   # volume the writer glides to, a little per frame
        self.rx = bytearray()
        self.tx = bytearray()
        # byte counters of the playback stream: everything ever queued / taken out (played or dropped);
        # `queued` after a play() marks where that audio ends — used to finish exactly the sounding sentence
        self.queued = 0
        self.played = 0
        # background sound: a loop of samples mixed under everything we send (see set_ambience)
        self._amb: array | None = None
        self._amb_pos = 0
        self._amb_gain = 0.0     # current level
        self._amb_target = 0.0   # level it glides to
        self._amb_step = 0.0     # gain change per sample

    def _open(self):
        import serial
        self._ser = serial.Serial(self.port, 115200, timeout=0.1)

    def start(self):
        self._open()
        self._running = True
        threading.Thread(target=self._reader, name="audio-rx", daemon=True).start()
        threading.Thread(target=self._writer, name="audio-tx", daemon=True).start()

    def stop(self):
        self._running = False
        time.sleep(0.05)
        if self._ser:
            try:
                self._ser.close()
            except Exception:
                pass
        self._ser = None

    # ------------------------------------------------------------ playback

    def play(self, pcm: bytes, max_ms: int | None = None):
        with self._lock:
            self._buf.extend(pcm)
            self.queued += len(pcm)
            if max_ms is not None:
                limit = RATE * 2 * max_ms // 1000
                if len(self._buf) > limit:  # live audio: drop the oldest part instead of lagging
                    self.played += len(self._buf) - limit
                    del self._buf[: len(self._buf) - limit]

    def clear(self):
        with self._lock:
            self.played += len(self._buf)
            self._buf.clear()

    def keep(self, nbytes: int, fade_ms: int = 0):
        """Keep only the next `nbytes` of queued audio (the rest is dropped); fade its last `fade_ms` to silence."""
        with self._lock:
            nbytes = max(0, min(nbytes, len(self._buf))) // 2 * 2
            dropped = len(self._buf) - nbytes
            head = self._buf[:nbytes]
            if fade_ms:
                n = min(nbytes, RATE * 2 * fade_ms // 1000) // 2 * 2
                tail = array("h")
                tail.frombytes(bytes(head[nbytes - n:]))
                for i in range(len(tail)):
                    tail[i] = int(tail[i] * (1 - (i + 1) / len(tail)))
                head[nbytes - n:] = tail.tobytes()
            self._buf = bytearray(head)
            self.played += dropped

    def set_volume(self, volume: float):
        """Glide the agent's volume (e.g. duck while the caller makes a short sound)."""
        self._target = max(0.0, min(1.0, volume))

    def fade_out(self, ms: int = 150):
        """Stop the agent smoothly: keep only `ms` of audio and ramp it down to silence."""
        self.keep(RATE * 2 * ms // 1000, fade_ms=ms)

    def set_ambience(self, samples: array | None, gain: float = 0.0, fade_ms: int = 1500):
        """Mix a looped background sound under our audio at `gain`, fading in from silence; None fades it out.
        Starts at a random place of the loop, so calls don't all sound the same."""
        import random
        if samples is not None and len(samples):
            if self._amb is not samples:
                self._amb, self._amb_pos, self._amb_gain = samples, random.randrange(len(samples)), 0.0
            self._amb_target = max(0.0, min(1.0, gain))
        else:
            self._amb_target = 0.0
        self._amb_step = abs(self._amb_target - self._amb_gain) / max(1, RATE * fade_ms // 1000)

    def _mix_ambience(self, frame: bytes) -> bytes:
        amb = self._amb
        if amb is None or (self._amb_gain == 0.0 and self._amb_target == 0.0):
            return frame
        x = array("h")
        x.frombytes(frame)
        g, target, step, pos, n = self._amb_gain, self._amb_target, self._amb_step or 1.0, self._amb_pos, len(amb)
        for i in range(len(x)):
            if g != target:
                g = min(target, g + step) if g < target else max(target, g - step)
            v = x[i] + int(amb[pos] * g)
            x[i] = 32767 if v > 32767 else -32768 if v < -32768 else v
            pos += 1
            if pos == n:
                pos = 0
        self._amb_gain, self._amb_pos = g, pos
        return x.tobytes()

    @property
    def pending_ms(self) -> int:
        return len(self._buf) * 1000 // (RATE * 2)

    # ------------------------------------------------------------ threads

    def _read_frame(self) -> bytes:
        return self._ser.read(FRAME_BYTES)

    def _write_frame(self, frame: bytes):
        self._ser.write(frame)

    def _reader(self):
        pending = b""
        while self._running:
            try:
                data = self._read_frame()
            except Exception as e:
                if self._running:
                    log.error("audio read error: %s", e)
                break
            if not data:
                continue
            pending += data
            while len(pending) >= FRAME_BYTES:
                frame, pending = pending[:FRAME_BYTES], pending[FRAME_BYTES:]
                if self.record:
                    self.rx.extend(frame)
                try:
                    self.on_frame(frame)
                except Exception:
                    log.exception("on_frame failed")

    def _apply_volume(self, frame: bytes) -> bytes:
        start, target = self._vol, self._target
        if start == target == 1.0:
            return frame
        end = target if abs(target - start) <= 0.25 else start + (0.25 if target > start else -0.25)
        x = array("h")
        x.frombytes(frame)
        n = len(x)
        for i in range(n):
            g = start + (end - start) * (i + 1) / n
            x[i] = int(x[i] * g)
        self._vol = end
        return x.tobytes()

    def _writer(self):
        next_t = time.monotonic()
        while self._running:
            with self._lock:
                frame = bytes(self._buf[:FRAME_BYTES])
                del self._buf[:FRAME_BYTES]
                self.played += len(frame)
            if len(frame) < FRAME_BYTES:
                frame += SILENCE[len(frame):]
            frame = self._mix_ambience(self._apply_volume(frame))  # the background isn't ducked with the agent
            try:
                self._write_frame(frame)
            except Exception as e:
                if self._running:
                    log.error("audio write error: %s", e)
                break
            if self.record:
                self.tx.extend(frame)
            next_t += FRAME_MS / 1000
            delay = next_t - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            elif delay < -0.2:
                next_t = time.monotonic()

    # ------------------------------------------------------------ recording

    def save_wav(self, path) -> bool:
        """Stereo WAV: left = caller, right = agent (with the background sound, if any)."""
        if not self.record or not (self.rx or self.tx):
            return False
        n = max(len(self.rx), len(self.tx)) // 2
        rx, tx = array("h"), array("h")
        rx.frombytes(bytes(self.rx[: n * 2]))
        tx.frombytes(bytes(self.tx[: n * 2]))
        rx.extend([0] * (n - len(rx)))
        tx.extend([0] * (n - len(tx)))
        out = array("h", bytes(n * 4))
        out[0::2] = rx
        out[1::2] = tx
        with wave.open(str(path), "wb") as w:
            w.setnchannels(2)
            w.setsampwidth(2)
            w.setframerate(RATE)
            w.writeframes(out.tobytes())
        return True


class MockAudioPort(AudioPort):
    """No hardware: the emulated 'caller' repeats what we send ~0.5 s later (echo test)."""

    def _open(self):
        from collections import deque
        self._echo = deque([SILENCE] * 25, maxlen=200)

    def _read_frame(self) -> bytes:
        time.sleep(FRAME_MS / 1000)
        # sleep() drifts a little slower than the paced writer; keep the echo delay ~0.5 s
        while len(self._echo) > 25:
            self._echo.popleft()
        return self._echo.popleft() if self._echo else SILENCE

    def _write_frame(self, frame: bytes):
        self._echo.append(frame)
