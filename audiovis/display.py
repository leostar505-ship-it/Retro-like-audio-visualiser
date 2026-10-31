import math
import tkinter as tk

from . import colors
from .raster import Raster
from .screens import SCREENS

MAX_OUTPUT_PIXELS = 1300000


class SmoothDisplay:
    pixel = False

    def __init__(self, canvas):
        self.canvas = canvas
        self.pools = {"line": [], "rect": [], "ring": []}
        self.shown = {"line": 0, "rect": 0, "ring": 0}
        self.cache = {}

    def size(self, canvas_w, canvas_h):
        return canvas_w, canvas_h

    def _make(self, kind):
        c = self.canvas
        if kind == "line":
            return c.create_line(0, 0, 0, 0, fill="#000000", width=1)
        if kind == "rect":
            return c.create_rectangle(0, 0, 0, 0, fill="#000000", outline="")
        return c.create_oval(0, 0, 0, 0, outline="#000000", width=1)

    def draw(self, prims, canvas_w, canvas_h):
        c = self.canvas
        counts = {"line": 0, "rect": 0, "ring": 0}
        for p in prims:
            kind = p.kind
            pool = self.pools[kind]
            i = counts[kind]
            counts[kind] = i + 1
            if i == len(pool):
                pool.append(self._make(kind))
            item = pool[i]
            if i >= self.shown[kind]:
                c.itemconfigure(item, state="normal")
            rgb = colors.blend(p.rgb, p.alpha) if p.alpha < 1.0 else p.rgb
            fill = colors.to_hex(rgb)
            if kind == "ring":
                c.coords(item, p.a - p.c, p.b - p.c, p.a + p.c, p.b + p.c)
                key = (fill, p.w)
                if self.cache.get(item) != key:
                    c.itemconfigure(item, outline=fill, width=p.w)
                    self.cache[item] = key
            elif kind == "line":
                c.coords(item, p.a, p.b, p.c, p.d)
                key = (fill, p.w)
                if self.cache.get(item) != key:
                    c.itemconfigure(item, fill=fill, width=p.w)
                    self.cache[item] = key
            else:
                c.coords(item, p.a, p.b, p.c, p.d)
                if self.cache.get(item) != fill:
                    c.itemconfigure(item, fill=fill)
                    self.cache[item] = fill
        for kind, pool in self.pools.items():
            used = counts[kind]
            for j in range(used, self.shown[kind]):
                c.itemconfigure(pool[j], state="hidden")
            self.shown[kind] = used


class PixelDisplay:
    pixel = True

    def __init__(self, canvas, width, height, mono):
        self.canvas = canvas
        self.raster = Raster(width, height, mono)
        self.photo = None
        self.image_item = canvas.create_image(0, 0, anchor="center")
        self.frame_item = canvas.create_rectangle(0, 0, 0, 0, outline="#2a2a36", width=1)

    def size(self, canvas_w, canvas_h):
        return self.raster.w, self.raster.h

    def draw(self, prims, canvas_w, canvas_h):
        raster = self.raster
        raster.render(prims)
        fit = min(canvas_w // raster.w, canvas_h // raster.h)
        limit = int(math.sqrt(MAX_OUTPUT_PIXELS / (raster.w * raster.h)))
        scale = max(1, min(fit, limit))
        small = tk.PhotoImage(master=self.canvas, data=raster.ppm())
        self.photo = small.zoom(scale, scale) if scale > 1 else small
        cx = canvas_w / 2.0
        cy = canvas_h / 2.0
        half_w = raster.w * scale / 2.0
        half_h = raster.h * scale / 2.0
        self.canvas.itemconfigure(self.image_item, image=self.photo)
        self.canvas.coords(self.image_item, cx, cy)
        self.canvas.coords(self.frame_item, cx - half_w - 1, cy - half_h - 1, cx + half_w, cy + half_h)


def make_display(canvas, key):
    label, width, height, mono = SCREENS.get(key, SCREENS["full"])
    if width and height:
        return PixelDisplay(canvas, width, height, mono)
    return SmoothDisplay(canvas)
