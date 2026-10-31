import math
from collections import namedtuple

import numpy as np

from . import colors
from .analysis import BANDS

Prim = namedtuple("Prim", "kind a b c d w rgb alpha")


def line(x0, y0, x1, y1, width, rgb, alpha=1.0):
    return Prim("line", x0, y0, x1, y1, width, rgb, alpha)


def rect(x0, y0, x1, y1, rgb):
    return Prim("rect", x0, y0, x1, y1, 0.0, rgb, 1.0)


def ring(cx, cy, radius, width, rgb, alpha):
    return Prim("ring", cx, cy, radius, 0.0, width, rgb, alpha)


def height_gain(look):
    return max(0.0, look.sensitivity) / 1.6


class Look:
    def __init__(self, mode, fixed, sensitivity, ring=1.0, smooth=0.5):
        self.smooth = smooth
        self.mode = mode
        self.fixed = fixed
        self.sensitivity = sensitivity
        self.ring = ring


class RadialVisual:
    def __init__(self):
        self.pulse = 0.0
        self.ring_r = 0.0
        self.ring_a = 0.0
        self.ring_v = 0.0

    def frame(self, width, height, dt, an, look, pixel):
        cx = width / 2.0
        cy = height / 2.0
        m = float(min(width, height))
        self.pulse = max(self.pulse * 0.85 ** (dt * 60.0), an.bass_now)
        r0 = m * 0.2 + self.pulse * m * 0.08
        max_len = m * 0.28
        if pixel:
            bar_w = max(1.0, float(round(m / 64.0)))
            ring_w = max(1.0, float(round(min(look.ring, 3.0))))
        else:
            bar_w = max(1.0, m / 64.0)
            ring_w = max(1.0, m / 128.0) * (0.6 + 0.4 * min(look.ring, 3.0))
        min_len = bar_w
        gain = height_gain(look)
        prims = []
        for i in range(BANDS):
            length = min(1.0, an.vals[i] * gain) * max_len + min_len
            ang = (i + 0.5) / BANDS * math.pi - math.pi / 2.0
            cos_a = math.cos(ang)
            sin_a = math.sin(ang)
            y0 = cy + sin_a * r0
            y1 = cy + sin_a * (r0 + length)
            rgb = colors.bar_rgb(look.mode, i, BANDS, an.vals[i], look.sensitivity, look.fixed)
            prims.append(line(cx - cos_a * r0, y0, cx - cos_a * (r0 + length), y1, bar_w, rgb))
            prims.append(line(cx + cos_a * r0, y0, cx + cos_a * (r0 + length), y1, bar_w, rgb))
        if an.beat:
            self.ring_r = r0
            self.ring_a = 1.0
            self.ring_v = 0.5 + an.bass_now * look.sensitivity
        elif self.ring_a > 0.0:
            self.ring_r += m * 1.8 * dt
            self.ring_a -= 3.0 * dt / math.sqrt(max(0.25, look.ring))
        if self.ring_a > 0.0:
            base = colors.ring_rgb(look.mode, self.ring_v, look.fixed)
            prims.append(ring(cx, cy, self.ring_r, ring_w, base, self.ring_a))
        return prims


class BarsVisual:
    def __init__(self):
        self.peaks = [0.0] * BANDS

    def frame(self, width, height, dt, an, look, pixel):
        gain = height_gain(look)
        mid = height / 2.0
        bw = width / BANDS
        fall = height * 0.72 * dt
        if pixel:
            bar_w = max(1.0, bw - 1.0)
            dot = max(1.0, float(round(height / 100.0)))
        else:
            bar_w = bw * 0.76
            dot = max(2.0, height / 64.0)
        offset = 0.0 if pixel else bw * 0.12
        bars = []
        tops = []
        bottoms = []
        white = (255, 255, 255)
        for i in range(BANDS):
            h = min(1.0, an.vals[i] * gain) * (mid - 1.0)
            peak = max(h, self.peaks[i] - fall)
            self.peaks[i] = peak
            x0 = i * bw + offset
            x1 = x0 + bar_w
            rgb = colors.bar_rgb(look.mode, i, BANDS, an.vals[i], look.sensitivity, look.fixed)
            bars.append(rect(x0, mid - h, x1, mid + h + 1.0, rgb))
            tops.append(rect(x0, mid - peak - dot - 1.0, x1, mid - peak - 1.0, white))
            bottoms.append(rect(x0, mid + peak + 1.0, x1, mid + peak + dot + 1.0, white))
        return bars + tops + bottoms


class WaveRadialVisual(RadialVisual):
    def __init__(self):
        super().__init__()
        self.line = None
        self.peak = 0.02

    def wave_prims(self, width, height, dt, an, look, pixel):
        n = int(min(128, max(16, width // 4)))
        samples = np.asarray(an.wave, dtype=np.float32)
        edges = np.linspace(0, len(samples), n + 1).astype(int)
        sums = np.add.reduceat(samples, edges[:-1])
        pts = sums / np.maximum(np.diff(edges), 1)
        smooth = min(1.0, max(0.0, look.smooth))
        half = int(round(smooth * smooth * 12.0))
        if half > 0:
            padded = np.pad(pts, half, mode="edge")
            pts = np.convolve(padded, np.ones(2 * half + 1) / (2 * half + 1), mode="valid")
        if self.line is None or len(self.line) != n:
            self.line = pts.copy()
        keep = (smooth * 0.9) ** (min(max(dt, 1e-3), 0.1) * 60.0)
        self.line = keep * self.line + (1.0 - keep) * pts
        top = float(np.max(np.abs(self.line)))
        self.peak = max(top, self.peak * 0.995 ** (min(max(dt, 1e-3), 0.1) * 60.0), 0.02)
        scaled = self.line / self.peak
        m = float(min(width, height))
        amp = m * 0.16 * min(height_gain(look), 2.0)
        cy = height / 2.0
        stroke = 1.0 if pixel else max(1.5, m / 200.0)
        prims = []
        for i in range(n - 1):
            x0 = i / (n - 1) * (width - 1)
            x1 = (i + 1) / (n - 1) * (width - 1)
            y0 = cy - float(scaled[i]) * amp
            y1 = cy - float(scaled[i + 1]) * amp
            rgb = colors.bar_rgb(look.mode, i, n - 1, abs(float(scaled[i])), look.sensitivity, look.fixed)
            prims.append(line(x0, y0, x1, y1, stroke, rgb))
        return prims

    def frame(self, width, height, dt, an, look, pixel):
        wave = self.wave_prims(width, height, dt, an, look, pixel)
        return wave + super().frame(width, height, dt, an, look, pixel)


VISUALS = {"radial_wave": WaveRadialVisual, "radial": RadialVisual, "bars": BarsVisual}
