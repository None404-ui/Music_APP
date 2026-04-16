"""Пятизонный графический эквалайзер (peaking biquads, Robert Bristow-Johnson)."""

from __future__ import annotations

import math
from typing import Sequence

# Центры полос, Гц (типичный 5-band)
BAND_CENTER_HZ: tuple[float, ...] = (100.0, 330.0, 1000.0, 3300.0, 10000.0)
DEFAULT_Q = 1.4142135623730951

# id -> кортеж усилений (дБ) по полосам снизу вверх
EQ_PRESET_GAINS_DB: dict[str, tuple[float, ...]] = {
    "flat": (0.0, 0.0, 0.0, 0.0, 0.0),
    "bass": (7.0, 4.5, 2.0, 0.0, 0.0),
    "treble": (0.0, 0.0, 1.5, 5.0, 7.5),
    "rock": (5.5, 3.0, -2.0, 2.5, 5.0),
    "vocal": (-2.0, -1.5, 4.0, 5.0, 2.0),
    "electronic": (6.0, 3.5, 0.5, 3.0, 5.5),
    "warm": (4.0, 3.0, 1.0, -1.0, -2.0),
}


class Biquad:
    __slots__ = ("b0", "b1", "b2", "a1", "a2", "x1", "x2", "y1", "y2")

    def __init__(self) -> None:
        self.identity()
        self.reset()

    def identity(self) -> None:
        self.b0, self.b1, self.b2 = 1.0, 0.0, 0.0
        self.a1, self.a2 = 0.0, 0.0

    def reset(self) -> None:
        self.x1 = self.x2 = self.y1 = self.y2 = 0.0

    def set_peaking(self, sample_rate: float, fc: float, gain_db: float, q: float) -> None:
        if abs(gain_db) < 1e-4:
            self.identity()
            self.reset()
            return
        sr = max(8000.0, float(sample_rate))
        f0 = min(max(20.0, fc), 0.45 * sr)
        w0 = 2.0 * math.pi * f0 / sr
        cosw0 = math.cos(w0)
        sinw0 = math.sin(w0)
        alpha = sinw0 / (2.0 * max(0.05, q))
        # Амплитуда на центральной частоте (cookbook)
        a_lin = math.sqrt(10.0 ** (gain_db / 20.0))
        b0 = 1.0 + alpha * a_lin
        b1 = -2.0 * cosw0
        b2 = 1.0 - alpha * a_lin
        a0 = 1.0 + alpha / a_lin
        a1 = -2.0 * cosw0
        a2 = 1.0 - alpha / a_lin
        inv = 1.0 / a0
        self.b0, self.b1, self.b2 = b0 * inv, b1 * inv, b2 * inv
        self.a1, self.a2 = a1 * inv, a2 * inv

    def process(self, x: float) -> float:
        y = self.b0 * x + self.b1 * self.x1 + self.b2 * self.x2 - self.a1 * self.y1 - self.a2 * self.y2
        self.x2, self.x1 = self.x1, x
        self.y2, self.y1 = self.y1, y
        return y


class GraphicEQProcessor:
    """Серия peaking-фильтров на канал; коэффициенты общие, состояние — отдельно."""

    def __init__(self, channel_count: int = 2) -> None:
        self._ch = max(1, int(channel_count))
        self._fs = 44100.0
        self._gains_db = [0.0] * len(BAND_CENTER_HZ)
        self._chains: list[list[Biquad]] = [
            [Biquad() for _ in range(len(BAND_CENTER_HZ))] for _ in range(self._ch)
        ]
        self._recalc_coeffs()

    def set_sample_rate(self, sample_rate: float) -> None:
        fs = float(sample_rate)
        if abs(fs - self._fs) < 1.0:
            return
        self._fs = fs
        self._recalc_coeffs()

    def set_gains_db(self, gains: Sequence[float]) -> None:
        n = len(BAND_CENTER_HZ)
        g = [0.0] * n
        for i in range(n):
            try:
                g[i] = float(gains[i])
            except (IndexError, TypeError, ValueError):
                g[i] = 0.0
            g[i] = max(-12.0, min(12.0, g[i]))
        if g == self._gains_db:
            return
        self._gains_db = g
        self._recalc_coeffs()

    def gains_db(self) -> list[float]:
        return list(self._gains_db)

    def _recalc_coeffs(self) -> None:
        for ch in range(self._ch):
            for i, bq in enumerate(self._chains[ch]):
                bq.set_peaking(self._fs, BAND_CENTER_HZ[i], self._gains_db[i], DEFAULT_Q)

    def reset(self) -> None:
        for ch in self._chains:
            for bq in ch:
                bq.reset()

    def process_sample(self, x: float, channel: int) -> float:
        c = channel % self._ch
        y = x
        for bq in self._chains[c]:
            y = bq.process(y)
        return y
