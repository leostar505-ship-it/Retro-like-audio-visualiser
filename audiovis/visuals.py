import math
from collections import namedtuple

from . import colors
from .analysis import BANDS

Prim = namedtuple("Prim", "kind a b c d w rgb alpha")


def line(x0, y0, x1, y1, width, rgb, alpha=1.0):
    return Prim("line", x0, y0, x1, y1, width, rgb, alpha)


def rect(x0, y0, x1, y1, rgb):
    return Prim("rect", x0, y0, x1, y1, 0.0, rgb, 1.0)


def ring(cx, cy, radius, width, rgb, alpha):
    return Prim("ring", cx, cy, radius, 0.0, width, rgb, alpha)


class Look:
    def __init__(self, mode, fixed, sensitivity):
        self.mode = mode
        self.fixed = fixed
        self.sensitivity = sensitivity


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
            ring_w = 1.0
        else:
            bar_w = max(1.0, m / 64.0)
            ring_w = max(1.0, m / 128.0)
        min_len = bar_w
        prims = []
        for i in range(BANDS):
            length = an.vals[i] * max_len + min_len
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
            self.ring_a -= 3.0 * dt
        if self.ring_a > 0.0:
            base = colors.ring_rgb(look.mode, self.ring_v, look.fixed)
            prims.append(ring(cx, cy, self.ring_r, ring_w, base, self.ring_a))
        return prims


class BarsVisual:
    def __init__(self):
        self.peaks = [0.0] * BANDS

    def frame(self, width, height, dt, an, look, pixel):
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
            h = an.vals[i] * (mid - 1.0)
            peak = max(h, self.peaks[i] - fall)
            self.peaks[i] = peak
            x0 = i * bw + offset
            x1 = x0 + bar_w
            rgb = colors.bar_rgb(look.mode, i, BANDS, an.vals[i], look.sensitivity, look.fixed)
            bars.append(rect(x0, mid - h, x1, mid + h + 1.0, rgb))
            tops.append(rect(x0, mid - peak - dot - 1.0, x1, mid - peak - 1.0, white))
            bottoms.append(rect(x0, mid + peak + 1.0, x1, mid + peak + dot + 1.0, white))
        return bars + tops + bottoms


VISUALS = {"radial": RadialVisual, "bars": BarsVisual}
