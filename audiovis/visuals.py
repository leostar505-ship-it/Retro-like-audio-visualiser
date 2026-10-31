import math

from . import colors
from .analysis import BANDS


class Look:
    def __init__(self, mode, fixed, sensitivity):
        self.mode = mode
        self.fixed = fixed
        self.sensitivity = sensitivity


class RadialRenderer:
    def __init__(self, canvas):
        self.canvas = canvas
        self.bars = [canvas.create_line(0, 0, 0, 0, fill="#000000", width=1) for _ in range(BANDS * 2)]
        self.ring = canvas.create_oval(0, 0, 0, 0, outline="#000000", width=1, state="hidden")
        self.fills = [""] * (BANDS * 2)
        self.pulse = 0.0
        self.ring_r = 0.0
        self.ring_a = 0.0
        self.ring_v = 0.0
        self.size = 0.0

    def update(self, width, height, dt, an, look):
        c = self.canvas
        cx = width / 2.0
        cy = height / 2.0
        m = float(min(width, height))
        if m != self.size:
            self.size = m
            bar_width = max(1.0, m / 64.0)
            for item in self.bars:
                c.itemconfigure(item, width=bar_width)
            c.itemconfigure(self.ring, width=max(1.0, m / 128.0))
        self.pulse = max(self.pulse * 0.85 ** (dt * 60.0), an.bass_now)
        r0 = m * 0.2 + self.pulse * m * 0.08
        max_len = m * 0.28
        min_len = max(1.0, m / 64.0)
        for i in range(BANDS):
            length = an.vals[i] * max_len + min_len
            ang = (i + 0.5) / BANDS * math.pi - math.pi / 2.0
            cos_a = math.cos(ang)
            sin_a = math.sin(ang)
            y0 = cy + sin_a * r0
            y1 = cy + sin_a * (r0 + length)
            fill = colors.to_hex(
                colors.bar_rgb(look.mode, i, BANDS, an.vals[i], look.sensitivity, look.fixed)
            )
            for side in (0, 1):
                sign = 1.0 if side else -1.0
                idx = i * 2 + side
                c.coords(
                    self.bars[idx],
                    cx + sign * cos_a * r0,
                    y0,
                    cx + sign * cos_a * (r0 + length),
                    y1,
                )
                if self.fills[idx] != fill:
                    c.itemconfigure(self.bars[idx], fill=fill)
                    self.fills[idx] = fill
        if an.beat:
            self.ring_r = r0
            self.ring_a = 1.0
            self.ring_v = 0.5 + an.bass_now * look.sensitivity
        elif self.ring_a > 0.0:
            self.ring_r += m * 1.8 * dt
            self.ring_a -= 3.0 * dt
        if self.ring_a > 0.0:
            rgb = colors.blend(colors.ring_rgb(look.mode, self.ring_v, look.fixed), self.ring_a)
            r = self.ring_r
            c.coords(self.ring, cx - r, cy - r, cx + r, cy + r)
            c.itemconfigure(self.ring, outline=colors.to_hex(rgb), state="normal")
        else:
            c.itemconfigure(self.ring, state="hidden")


class BarsRenderer:
    def __init__(self, canvas):
        self.canvas = canvas
        self.bars = [canvas.create_rectangle(0, 0, 0, 0, fill="#000000", outline="") for _ in range(BANDS)]
        self.tops = [canvas.create_rectangle(0, 0, 0, 0, fill="#ffffff", outline="") for _ in range(BANDS)]
        self.bottoms = [canvas.create_rectangle(0, 0, 0, 0, fill="#ffffff", outline="") for _ in range(BANDS)]
        self.fills = [""] * BANDS
        self.peaks = [0.0] * BANDS

    def update(self, width, height, dt, an, look):
        c = self.canvas
        mid = height / 2.0
        bw = width / BANDS
        gap = bw * 0.12
        dot = max(2.0, height / 64.0)
        fall = height * 0.72 * dt
        for i in range(BANDS):
            h = an.vals[i] * (mid - 1.0)
            peak = max(h, self.peaks[i] - fall)
            self.peaks[i] = peak
            x0 = i * bw + gap
            x1 = (i + 1) * bw - gap
            c.coords(self.bars[i], x0, mid - h, x1, mid + h + 1.0)
            c.coords(self.tops[i], x0, mid - peak - dot - 1.0, x1, mid - peak - 1.0)
            c.coords(self.bottoms[i], x0, mid + peak + 1.0, x1, mid + peak + dot + 1.0)
            fill = colors.to_hex(
                colors.bar_rgb(look.mode, i, BANDS, an.vals[i], look.sensitivity, look.fixed)
            )
            if self.fills[i] != fill:
                c.itemconfigure(self.bars[i], fill=fill)
                self.fills[i] = fill


RENDERERS = {"radial": RadialRenderer, "bars": BarsRenderer}
