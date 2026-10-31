import math

import numpy as np

FFT_SIZE = 2048
BANDS = 32
MIN_DB = -100.0
MAX_DB = -30.0
SMOOTHING = 0.55
F_MIN = 40.0
F_MAX = 16000.0
BASS_BANDS = 5
TARGET_RATE = 48000


def decimation_factor(rate):
    return max(1, int(math.floor(rate / TARGET_RATE + 0.5)))


def band_edges(sample_rate, fft_size=FFT_SIZE, bands=BANDS):
    bin_count = fft_size // 2
    nyq = sample_rate / 2.0
    lo = []
    hi = []
    prev = 1
    for i in range(bands):
        f0 = F_MIN * (F_MAX / F_MIN) ** (i / bands)
        f1 = F_MIN * (F_MAX / F_MIN) ** ((i + 1) / bands)
        a = max(prev, int(math.floor(f0 / nyq * bin_count + 0.5)))
        b = max(a + 1, int(math.floor(f1 / nyq * bin_count + 0.5)))
        a = min(a, bin_count)
        b = min(b, bin_count)
        lo.append(a)
        hi.append(b)
        prev = b
    return np.array(lo, dtype=np.int64), np.array(hi, dtype=np.int64)


def blackman(n):
    k = np.arange(n) / n
    window = 0.42 - 0.5 * np.cos(2.0 * np.pi * k) + 0.08 * np.cos(4.0 * np.pi * k)
    return window.astype(np.float32)


class Analyser:
    def __init__(self, sample_rate=TARGET_RATE):
        self.window = blackman(FFT_SIZE)
        self.smoothed = np.zeros(FFT_SIZE // 2)
        self.avg = np.zeros(BANDS)
        self.bands = np.zeros(BANDS)
        self.vals = np.zeros(BANDS)
        self.bass_avg = 0.0
        self.bass_now = 0.0
        self.level = 0.0
        self.beat = False
        self.last_beat = -1e9
        self.normalise = True
        self.ring_sens = 1.0
        self.rate = 0
        self.lo = None
        self.hi = None
        self.width = None
        self.set_rate(sample_rate)

    def set_rate(self, sample_rate):
        if sample_rate == self.rate:
            return
        self.rate = sample_rate
        self.lo, self.hi = band_edges(sample_rate)
        self.width = np.maximum(self.hi - self.lo, 1)

    def update(self, samples, dt, now):
        dt = min(max(dt, 1e-3), 0.1)
        steps = dt * 60.0
        spectrum = np.abs(np.fft.rfft(samples * self.window))[: FFT_SIZE // 2] / FFT_SIZE
        k = SMOOTHING**steps
        self.smoothed = k * self.smoothed + (1.0 - k) * spectrum
        db = 20.0 * np.log10(np.maximum(self.smoothed, 1e-10))
        norm = np.clip((db - MIN_DB) / (MAX_DB - MIN_DB), 0.0, 1.0)
        cumulative = np.concatenate(([0.0], np.cumsum(norm)))
        self.bands = (cumulative[self.hi] - cumulative[self.lo]) / self.width
        self.avg += (self.bands - self.avg) * (1.0 - 0.985**steps)
        if self.normalise:
            self.vals = np.clip((self.bands - self.avg * 0.95) * 2.5, 0.0, 1.0)
        else:
            self.vals = self.bands.copy()
        self.level = float(self.bands.mean())
        bass = float(self.bands[:BASS_BANDS].mean())
        self.bass_now = float(self.vals[:BASS_BANDS].mean())
        self.beat = False
        gain = max(0.25, float(self.ring_sens))
        if bass > self.bass_avg * (1.0 + 0.35 / gain) + 0.04 / gain and now - self.last_beat > 0.13:
            self.beat = True
            self.last_beat = now
        keep = 0.95**steps
        self.bass_avg = self.bass_avg * keep + bass * (1.0 - keep)
