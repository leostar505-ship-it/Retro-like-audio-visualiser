import argparse
import sys
import time
import tkinter as tk
from tkinter import colorchooser, ttk

from . import __version__, colors
from . import settings as settings_store
from .analysis import Analyser
from .capture import AUTO_DEVICE, DemoSource, LoopbackCapture
from .visuals import RENDERERS, Look

BG = "#000000"
PANEL = "#15151d"
FIELD = "#22222e"
LINE = "#33334a"
TEXT = "#e8e8f0"
MUTED = "#99a0b0"

VISUAL_LABELS = {
    "radial": "Radial spectrum + bass ring",
    "bars": "Mirrored peak-hold bars",
}
MODE_LABELS = {
    colors.MODE_LOUDNESS: "Loudness gradient: pink to red",
    colors.MODE_FIXED: "Custom colour",
    colors.MODE_RAINBOW: "Rainbow by frequency",
}
SELFTEST_FRAMES = 90


def reverse_lookup(table, label, default):
    for key, value in table.items():
        if value == label:
            return key
    return default


class App:
    def __init__(self, root, source, cfg, selftest=False, persist=True):
        self.root = root
        self.source = source
        self.cfg = cfg
        self.selftest = selftest
        self.persist = persist
        self.exit_code = 0
        self.frames = 0
        self.fullscreen = False
        self.last = time.perf_counter()
        self.renderer = None
        self.after_id = None
        self.device_values = []
        self.analyser = Analyser(source.rate)
        self.analyser.normalise = cfg.normalise
        fixed = colors.parse_hex(cfg.hex) or colors.parse_hex(settings_store.DEFAULT_HEX)
        self.look = Look(cfg.colour_mode, fixed, cfg.sensitivity)
        self._build_ui()
        self._set_visual(cfg.visual)
        self._apply_controls_visibility()
        self.root.attributes("-topmost", cfg.topmost)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self._bind_keys()
        self.after_id = self.root.after(10, self.tick)

    def _style(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(".", background=PANEL, foreground=TEXT, fieldbackground=FIELD, bordercolor=LINE)
        style.configure("TFrame", background=PANEL)
        style.configure("TLabel", background=PANEL, foreground=MUTED)
        style.configure("Status.TLabel", background=PANEL, foreground=MUTED)
        style.configure("TCheckbutton", background=PANEL, foreground=TEXT)
        style.map("TCheckbutton", background=[("active", PANEL)])
        style.configure("TCombobox", fieldbackground=FIELD, background=FIELD, foreground=TEXT, arrowcolor=TEXT)
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", FIELD)],
            foreground=[("readonly", TEXT)],
            selectbackground=[("readonly", FIELD)],
            selectforeground=[("readonly", TEXT)],
        )
        style.configure("TButton", background=FIELD, foreground=TEXT, padding=(10, 4))
        style.map("TButton", background=[("active", LINE)])
        style.configure("TEntry", fieldbackground=FIELD, foreground=TEXT, insertcolor=TEXT)
        style.configure("Bad.TEntry", fieldbackground=FIELD, foreground="#ff6b6b", insertcolor=TEXT)
        style.configure("Horizontal.TScale", background=PANEL, troughcolor=FIELD)
        self.root.option_add("*TCombobox*Listbox.background", FIELD)
        self.root.option_add("*TCombobox*Listbox.foreground", TEXT)
        self.root.option_add("*TCombobox*Listbox.selectBackground", LINE)
        self.root.option_add("*TCombobox*Listbox.selectForeground", TEXT)

    def _build_ui(self):
        cfg = self.cfg
        self._style()
        self.controls = ttk.Frame(self.root, padding=(12, 10))
        row1 = ttk.Frame(self.controls)
        row1.pack(fill="x")
        row2 = ttk.Frame(self.controls)
        row2.pack(fill="x", pady=(8, 0))

        ttk.Label(row1, text="Visual").pack(side="left")
        self.visual_var = tk.StringVar(value=VISUAL_LABELS[cfg.visual])
        visual_box = ttk.Combobox(
            row1, textvariable=self.visual_var, values=list(VISUAL_LABELS.values()), state="readonly", width=26
        )
        visual_box.pack(side="left", padx=(6, 16))
        visual_box.bind("<<ComboboxSelected>>", self._on_visual)

        ttk.Label(row1, text="Colour").pack(side="left")
        self.mode_var = tk.StringVar(value=MODE_LABELS[cfg.colour_mode])
        mode_box = ttk.Combobox(
            row1, textvariable=self.mode_var, values=list(MODE_LABELS.values()), state="readonly", width=28
        )
        mode_box.pack(side="left", padx=(6, 8))
        mode_box.bind("<<ComboboxSelected>>", self._on_mode)

        self.swatch = tk.Button(
            row1, width=3, relief="flat", bd=0, bg=cfg.hex, activebackground=cfg.hex, command=self._pick_colour
        )
        self.swatch.pack(side="left", padx=(0, 6), ipady=2)
        self.hex_var = tk.StringVar(value=cfg.hex)
        self.hex_entry = ttk.Entry(row1, textvariable=self.hex_var, width=9)
        self.hex_entry.pack(side="left", padx=(0, 16))
        self.hex_var.trace_add("write", self._on_hex)

        ttk.Label(row2, text="Sensitivity").pack(side="left")
        self.sens = ttk.Scale(row2, from_=0.5, to=3.0, orient="horizontal", length=150, command=self._on_sens)
        self.sens.set(cfg.sensitivity)
        self.sens.pack(side="left", padx=(6, 16))

        self.norm_var = tk.BooleanVar(value=cfg.normalise)
        ttk.Checkbutton(row2, text="Normalise (react to changes)", variable=self.norm_var, command=self._on_norm).pack(
            side="left"
        )
        self.top_var = tk.BooleanVar(value=cfg.topmost)
        ttk.Checkbutton(row2, text="Always on top", variable=self.top_var, command=self._on_topmost).pack(
            side="left", padx=(14, 0)
        )

        row3 = ttk.Frame(self.controls)
        row3.pack(fill="x", pady=(8, 0))
        ttk.Label(row3, text="Audio").pack(side="left")
        self.device_var = tk.StringVar(value=cfg.device or AUTO_DEVICE)
        self.device_box = ttk.Combobox(row3, textvariable=self.device_var, values=[], state="readonly", width=34)
        self.device_box.pack(side="left", padx=(6, 8))
        self.device_box.bind("<<ComboboxSelected>>", self._on_device)
        ttk.Button(row3, text="Restart capture", command=self._restart_capture).pack(side="left")
        self.status = ttk.Label(row3, text="", style="Status.TLabel", anchor="w")
        self.status.pack(side="left", padx=(14, 0), fill="x", expand=True)

        self.canvas = tk.Canvas(self.root, bg=BG, highlightthickness=0, bd=0)
        self.canvas.pack(side="top", fill="both", expand=True)

    def _bind_keys(self):
        self.root.bind_all("<Key-h>", lambda e: self._shortcut(self.toggle_controls))
        self.root.bind_all("<Key-v>", lambda e: self._shortcut(self.cycle_visual))
        self.root.bind_all("<Key-r>", lambda e: self._shortcut(self._restart_capture))
        self.root.bind_all("<F11>", lambda e: self.toggle_fullscreen())
        self.root.bind_all("<Escape>", lambda e: self.leave_fullscreen())

    def _shortcut(self, action):
        focus = self.root.focus_get()
        if isinstance(focus, (ttk.Entry, tk.Entry)):
            return
        action()

    def _apply_controls_visibility(self):
        if self.cfg.controls:
            self.controls.pack(side="bottom", fill="x", before=self.canvas)
        else:
            self.controls.pack_forget()

    def toggle_controls(self):
        self.cfg.controls = not self.cfg.controls
        self._apply_controls_visibility()

    def toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        self.root.attributes("-fullscreen", self.fullscreen)

    def leave_fullscreen(self):
        if self.fullscreen:
            self.fullscreen = False
            self.root.attributes("-fullscreen", False)

    def cycle_visual(self):
        names = list(VISUAL_LABELS)
        nxt = names[(names.index(self.cfg.visual) + 1) % len(names)]
        self._set_visual(nxt)

    def _set_visual(self, name):
        self.canvas.delete("all")
        self.renderer = RENDERERS[name](self.canvas)
        self.cfg.visual = name
        self.visual_var.set(VISUAL_LABELS[name])

    def _on_visual(self, _event=None):
        self._set_visual(reverse_lookup(VISUAL_LABELS, self.visual_var.get(), "radial"))

    def _set_mode(self, mode):
        self.look.mode = mode
        self.cfg.colour_mode = mode
        self.mode_var.set(MODE_LABELS[mode])

    def _on_mode(self, _event=None):
        self._set_mode(reverse_lookup(MODE_LABELS, self.mode_var.get(), colors.MODE_LOUDNESS))

    def _on_hex(self, *_args):
        rgb = colors.parse_hex(self.hex_var.get())
        if rgb is None:
            self.hex_entry.configure(style="Bad.TEntry")
            return
        self.hex_entry.configure(style="TEntry")
        hex_text = colors.to_hex(rgb)
        self.look.fixed = rgb
        self.cfg.hex = hex_text
        self.swatch.configure(bg=hex_text, activebackground=hex_text)
        self._set_mode(colors.MODE_FIXED)

    def _pick_colour(self):
        chosen = colorchooser.askcolor(color=colors.to_hex(self.look.fixed), parent=self.root)
        if chosen and chosen[1]:
            self.hex_var.set(chosen[1])

    def _on_sens(self, value):
        self.look.sensitivity = float(value)
        self.cfg.sensitivity = float(value)

    def _on_norm(self):
        self.analyser.normalise = bool(self.norm_var.get())
        self.cfg.normalise = self.analyser.normalise

    def _on_topmost(self):
        self.cfg.topmost = bool(self.top_var.get())
        self.root.attributes("-topmost", self.cfg.topmost)

    def _on_device(self, _event=None):
        name = self.device_var.get()
        self.cfg.device = "" if name == AUTO_DEVICE else name
        self.source.select(name)

    def _restart_capture(self):
        self.source.restart()

    def _refresh_status(self):
        text = self.source.status
        if self.source.is_silent():
            text += " (no audio playing)"
        self.status.configure(text=text)
        values = self.source.devices()
        if values != self.device_values:
            self.device_values = values
            self.device_box.configure(values=values)
            if values and self.device_var.get() not in values:
                self.device_var.set(AUTO_DEVICE)

    def tick(self):
        started = time.perf_counter()
        dt = min(0.1, max(0.001, started - self.last))
        self.last = started
        self.analyser.set_rate(self.source.rate)
        self.analyser.update(self.source.latest(), dt, started)
        width = max(self.canvas.winfo_width(), 2)
        height = max(self.canvas.winfo_height(), 2)
        self.renderer.update(width, height, dt, self.analyser, self.look)
        self.frames += 1
        if self.frames % 20 == 1:
            self._refresh_status()
        if self.selftest and self.frames >= SELFTEST_FRAMES:
            healthy = self.analyser.bands.max() > 0.05 and len(self.canvas.find_all()) > 0
            self.exit_code = 0 if healthy else 1
            self.close()
            return
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        self.after_id = self.root.after(max(1, int(16 - elapsed_ms)), self.tick)

    def close(self):
        if self.after_id is not None:
            self.root.after_cancel(self.after_id)
            self.after_id = None
        if self.persist:
            if not self.fullscreen and self.root.state() == "normal":
                self.cfg.width = self.root.winfo_width()
                self.cfg.height = self.root.winfo_height()
            settings_store.save(self.cfg.sanitise())
        self.source.close()
        self.root.destroy()


def enable_dpi_awareness():
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass


def main(argv=None):
    parser = argparse.ArgumentParser(prog="AudioVisualiser")
    parser.add_argument("--demo", action="store_true", help="use synthetic audio instead of the system output")
    parser.add_argument("--selftest", action="store_true", help="run a short headless-friendly check and exit")
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args(argv)

    demo = args.demo or args.selftest
    cfg = settings_store.Settings().sanitise() if args.selftest else settings_store.load()
    source = DemoSource() if demo else LoopbackCapture()

    enable_dpi_awareness()
    root = tk.Tk()
    root.title("Audio Visualiser")
    root.configure(bg=BG)
    root.geometry("%dx%d" % (cfg.width, cfg.height))
    root.minsize(520, 340)
    app = App(root, source, cfg, selftest=args.selftest, persist=not args.selftest)
    if not demo:
        source.start()
    root.mainloop()
    return app.exit_code
