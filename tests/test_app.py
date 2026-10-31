import time

import pytest

from audiovis.capture import DemoSource
from audiovis.settings import Settings


def make_root():
    tk = pytest.importorskip("tkinter")
    try:
        return tk.Tk()
    except tk.TclError:
        pytest.skip("no display available")


def pump(root, seconds):
    end = time.time() + seconds
    while time.time() < end:
        root.update()
        time.sleep(0.005)


@pytest.mark.parametrize("visual", ["radial_wave", "radial", "bars"])
@pytest.mark.parametrize("mode", ["loudness", "custom", "rainbow"])
def test_app_renders_each_visual_and_colour_mode(visual, mode):
    from audiovis.app import App

    root = make_root()
    root.geometry("800x500")
    cfg = Settings(visual=visual, colour_mode=mode).sanitise()
    app = App(root, DemoSource(), cfg, persist=False)
    pump(root, 0.8)
    assert app.frames > 5
    assert len(app.canvas.find_all()) > 0
    assert app.analyser.bands.max() > 0.05
    app.close()


@pytest.mark.parametrize("screen", ["full", "oled", "oled-colour", "tft-160", "tft-240", "tft-320", "tft-480"])
@pytest.mark.parametrize("visual", ["radial_wave", "radial", "bars"])
def test_app_renders_every_screen_preset(screen, visual):
    from audiovis.app import App

    root = make_root()
    root.geometry("900x560")
    cfg = Settings(visual=visual, screen=screen).sanitise()
    app = App(root, DemoSource(), cfg, persist=False)
    pump(root, 0.7)
    assert app.frames > 3
    assert app.display.pixel == (screen != "full")
    assert len(app.canvas.find_all()) > 0
    app.close()


def test_screen_can_be_changed_while_running():
    from audiovis.app import App
    from audiovis.screens import SCREEN_ORDER

    root = make_root()
    root.geometry("900x560")
    cfg = Settings().sanitise()
    app = App(root, DemoSource(), cfg, persist=False)
    pump(root, 0.2)
    seen = set()
    for _ in range(len(SCREEN_ORDER) + 1):
        app.cycle_screen()
        pump(root, 0.15)
        seen.add(cfg.screen)
    assert seen == set(SCREEN_ORDER)
    assert cfg.screen == SCREEN_ORDER[1]
    app.close()


def test_hex_entry_switches_to_custom_colour():
    from audiovis.app import App

    root = make_root()
    cfg = Settings().sanitise()
    app = App(root, DemoSource(), cfg, persist=False)
    app.hex_var.set("#00ffaa")
    pump(root, 0.2)
    assert app.look.mode == "custom"
    assert app.look.fixed == (0, 255, 170)
    app.hex_var.set("#zzz")
    pump(root, 0.1)
    assert app.look.fixed == (0, 255, 170)
    app.close()


def test_visual_cycle_and_controls_toggle():
    from audiovis.app import App

    root = make_root()
    cfg = Settings().sanitise()
    app = App(root, DemoSource(), cfg, persist=False)
    pump(root, 0.2)
    app.cycle_visual()
    assert cfg.visual == "radial"
    app.cycle_visual()
    assert cfg.visual == "bars"
    app.cycle_visual()
    assert cfg.visual == "radial_wave"
    app.toggle_controls()
    assert cfg.controls is False
    app.toggle_controls()
    assert cfg.controls is True
    pump(root, 0.2)
    app.close()
