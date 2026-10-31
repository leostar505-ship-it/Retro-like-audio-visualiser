import math

import numpy as np
import pytest

from audiovis import colors
from audiovis.analysis import BANDS, Analyser
from audiovis.raster import Raster
from audiovis.screens import SCREEN_ORDER, SCREENS, screen_from_label, screen_label
from audiovis.visuals import BarsVisual, Look, RadialVisual, line, rect, ring


def lit(raster):
    return int((raster.px.max(axis=2) > 0).sum())


def active_analyser():
    an = Analyser()
    an.vals = np.linspace(1.0, 0.0, BANDS)
    an.bass_now = 0.6
    an.beat = True
    return an


def test_screen_table_has_the_html_presets_plus_larger_ones():
    labels = [screen_label(k) for k in SCREEN_ORDER]
    for expected in (
        "128x64 OLED (mono)",
        "128x64 (colour)",
        "160x128 TFT (colour)",
        "240x240 TFT (colour)",
        "320x240 TFT (colour)",
        "480x320 TFT (colour)",
    ):
        assert expected in labels
    assert SCREENS["oled"][3] is True
    assert screen_from_label("240x240 TFT (colour)") == "tft-240"
    assert screen_from_label("nonsense") == "full"


def test_rect_fills_exact_pixels_and_clips():
    r = Raster(16, 8)
    r.rect(2, 2, 5, 4, (255, 0, 0))
    assert lit(r) == 6
    assert tuple(r.px[2, 2]) == (255, 0, 0)
    r.clear()
    r.rect(-5, -5, 3, 3, (0, 255, 0))
    assert lit(r) == 9
    r.clear()
    r.rect(20, 20, 30, 30, (0, 255, 0))
    assert lit(r) == 0


def test_thin_rect_still_draws_one_pixel():
    r = Raster(16, 8)
    r.rect(4.0, 4.0, 4.0, 4.0, (1, 2, 3))
    assert lit(r) == 1


def test_line_is_continuous_for_any_angle():
    r = Raster(64, 64)
    for angle in range(0, 360, 15):
        r.clear()
        rad = np.radians(angle)
        cos_a = np.cos(rad)
        sin_a = np.sin(rad)
        r.line(32, 32, 32 + 25 * cos_a, 32 + 25 * sin_a, 1.0, (255, 255, 255))
        mask = r.px.max(axis=2) > 0
        if abs(cos_a) >= abs(sin_a):
            span = int(25 * abs(cos_a)) - 1
            start = 33 if cos_a > 0 else 31 - span
            counts = mask[:, start : start + span + 1].sum(axis=0)
        else:
            span = int(25 * abs(sin_a)) - 1
            start = 33 if sin_a > 0 else 31 - span
            counts = mask[start : start + span + 1, :].sum(axis=1)
        assert (counts >= 1).all()


def test_zero_length_line_draws_a_dot():
    r = Raster(16, 16)
    r.line(8, 8, 8, 8, 1.0, (255, 255, 255))
    assert lit(r) >= 1


def test_thicker_line_lights_more_pixels():
    thin = Raster(64, 64)
    thick = Raster(64, 64)
    thin.line(10, 32, 50, 32, 1.0, (255, 255, 255))
    thick.line(10, 32, 50, 32, 4.0, (255, 255, 255))
    assert lit(thick) > lit(thin) * 3


def test_ring_is_hollow_and_centered():
    r = Raster(64, 64)
    r.ring(32, 32, 20, 1.0, (255, 255, 255))
    assert tuple(r.px[32, 32]) == (0, 0, 0)
    assert r.px[32, 12].max() == 255 or r.px[32, 11].max() == 255
    assert 100 < lit(r) < 200


def test_mono_forces_white_and_drops_faint_alpha():
    r = Raster(32, 32, mono=True)
    prims = [
        rect(0, 0, 4, 4, (200, 10, 10)),
        ring(16, 16, 8, 1.0, (10, 10, 200), 1.0),
        ring(16, 16, 12, 1.0, (10, 10, 200), 0.2),
    ]
    r.render(prims)
    colours = {tuple(p) for p in r.px.reshape(-1, 3)}
    assert colours <= {(0, 0, 0), (255, 255, 255)}
    assert r.px[0, 0].tolist() == [255, 255, 255]
    far = np.hypot(*np.meshgrid(np.arange(32) + 0.5 - 16, np.arange(32) + 0.5 - 16))
    assert not (r.px.max(axis=2)[np.abs(far - 12) < 0.4] > 0).any()


def test_colour_alpha_blends_toward_black():
    r = Raster(8, 8)
    r.render([rect(0, 0, 8, 8, (200, 100, 50))] + [ring(4, 4, 2, 1.0, (200, 100, 50), 0.5)])
    assert (r.px == np.array([200, 100, 50])).all(axis=2).sum() >= 1
    assert (r.px == np.array([100, 50, 25])).all(axis=2).sum() >= 1


def test_ppm_header_and_size():
    r = Raster(6, 4)
    data = r.ppm()
    assert data.startswith(b"P6\n6 4\n255\n")
    assert len(data) == len(b"P6\n6 4\n255\n") + 6 * 4 * 3


@pytest.mark.parametrize("visual_cls", [RadialVisual, BarsVisual])
@pytest.mark.parametrize("key", [k for k in SCREEN_ORDER if SCREENS[k][1]])
@pytest.mark.parametrize("mode", [colors.MODE_LOUDNESS, colors.MODE_FIXED, colors.MODE_RAINBOW])
def test_every_visual_renders_on_every_preset(visual_cls, key, mode):
    _, w, h, mono = SCREENS[key]
    raster = Raster(w, h, mono)
    visual = visual_cls()
    look = Look(mode, (0, 255, 170), 1.6)
    an = active_analyser()
    for _ in range(5):
        prims = visual.frame(w, h, 1 / 60, an, look, True)
        raster.render(prims)
        an.beat = False
    assert lit(raster) > 50
    if mono:
        assert {tuple(p) for p in raster.px.reshape(-1, 3)} <= {(0, 0, 0), (255, 255, 255)}


def test_smooth_mode_geometry_scales_with_window():
    visual = RadialVisual()
    look = Look(colors.MODE_LOUDNESS, (255, 0, 0), 1.6)
    an = active_analyser()
    small = visual.frame(400, 300, 1 / 60, an, look, False)
    big = visual.frame(1600, 1200, 1 / 60, an, look, False)
    assert max(p.w for p in big if p.kind == "line") > max(p.w for p in small if p.kind == "line")


def test_radial_emits_two_lines_per_band_and_ring_on_beat():
    visual = RadialVisual()
    look = Look(colors.MODE_LOUDNESS, (255, 0, 0), 1.6)
    an = active_analyser()
    prims = visual.frame(128, 64, 1 / 60, an, look, True)
    assert sum(1 for p in prims if p.kind == "line") == BANDS * 2
    assert sum(1 for p in prims if p.kind == "ring") == 1
    an.beat = False
    for _ in range(40):
        prims = visual.frame(128, 64, 1 / 60, an, look, True)
    assert sum(1 for p in prims if p.kind == "ring") == 0


def test_bars_emit_bar_and_two_peak_rects_per_band():
    visual = BarsVisual()
    look = Look(colors.MODE_LOUDNESS, (255, 0, 0), 1.6)
    prims = visual.frame(128, 64, 1 / 60, active_analyser(), look, True)
    assert len(prims) == BANDS * 3
    assert all(p.kind == "rect" for p in prims)


def test_peak_dots_fall_over_time():
    visual = BarsVisual()
    look = Look(colors.MODE_LOUDNESS, (255, 0, 0), 1.6)
    an = active_analyser()
    visual.frame(128, 64, 1 / 60, an, look, True)
    start = visual.peaks[0]
    an.vals = np.zeros(BANDS)
    for _ in range(10):
        visual.frame(128, 64, 1 / 60, an, look, True)
    assert 0 < visual.peaks[0] < start


def test_ring_slider_makes_ring_thicker_in_pixel_mode():
    from audiovis.visuals import Look, RadialVisual

    def ring_width(ring):
        an = active_analyser()
        an.beat = True
        look = Look("loudness", (255, 45, 149), 1.6, ring)
        prims = RadialVisual().frame(240, 240, 1 / 60, an, look, True)
        return [p.w for p in prims if p.kind == "ring"][0]

    assert ring_width(3.0) > ring_width(0.5)


def drone_an(hz, mag=0.1):
    an = Analyser()
    an.drone_hz = hz
    an.drone_mag = mag
    an.vals = np.zeros(BANDS)
    return an


def run_wave(hz, smooth=0.5, sens=1.6, mag=0.1, mode=colors.MODE_FIXED, frames=40, width=600, height=400):
    from audiovis.visuals import WaveRadialVisual

    vis = WaveRadialVisual()
    an = drone_an(hz, mag)
    look = Look(mode, (255, 0, 0), sens, 1.6, smooth)
    prims = []
    for _ in range(frames):
        prims = vis.wave_prims(width, height, 1 / 60, an, look, False)
    return prims


def count_crossings(prims, cy):
    ys = np.array([p.b for p in prims] + [prims[-1].d]) - cy
    return int(np.sum(np.signbit(ys[1:]) != np.signbit(ys[:-1])))


def test_waveform_is_one_clean_sine_whose_cycles_grow_with_frequency():
    low = run_wave(82.0)
    high = run_wave(1200.0)
    assert count_crossings(high, 200) > count_crossings(low, 200)
    assert count_crossings(low, 200) >= 2
    ys = np.array([p.b for p in low])
    assert abs(ys.mean() - 200) < 15
    assert np.ptp(ys) > 20


def test_waveform_is_flat_when_there_is_no_tone_and_sensitivity_scales_it():
    quiet = run_wave(100.0, mag=0.0, frames=60)
    assert np.ptp([p.b for p in quiet]) < 1.0
    low = run_wave(100.0, sens=0.05)
    high = run_wave(100.0, sens=3.0)
    assert np.ptp([p.b for p in low]) < np.ptp([p.b for p in high])


def test_smoothness_slows_frequency_changes():
    from audiovis.visuals import WaveRadialVisual

    def settle(smooth):
        vis = WaveRadialVisual()
        look = Look(colors.MODE_FIXED, (255, 0, 0), 1.6, 1.6, smooth)
        for _ in range(30):
            vis.wave_prims(600, 400, 1 / 60, drone_an(100.0), look, False)
        for _ in range(5):
            vis.wave_prims(600, 400, 1 / 60, drone_an(1600.0), look, False)
        return vis.log_f

    assert settle(0.0) > settle(1.0)


def test_sensitivity_floor_shrinks_bars():
    def bar_extent(sens):
        an = active_analyser()
        an.vals = np.ones(BANDS)
        look = Look(colors.MODE_FIXED, (255, 0, 0), sens)
        prims = RadialVisual().frame(300, 300, 1 / 60, an, look, False)
        return max(p.c for p in prims if p.kind == "line") - 150

    assert bar_extent(0.05) < bar_extent(1.6)


def test_rainbow_waveform_red_middle_pink_at_circle_edge_back_to_red_at_ends():
    prims = run_wave(100.0, mode=colors.MODE_RAINBOW, width=600, height=400)
    cross = 400 * 0.2
    mid = min(prims, key=lambda p: abs((p.a + p.c) / 2 - 300))
    at_circle = min(prims, key=lambda p: abs(abs((p.a + p.c) / 2 - 300) - cross))
    end = min(prims, key=lambda p: (p.a + p.c) / 2)
    assert mid.rgb[0] > 200 and mid.rgb[1] < 90 and mid.rgb[2] < 90
    assert at_circle.rgb[0] > 200 and at_circle.rgb[2] > 100 and at_circle.rgb[1] < 110
    assert end.rgb[0] > 200 and end.rgb[1] < 110 and end.rgb[2] < 110


def test_rainbow_radial_bars_match_waveform_gradient_by_horizontal_position():
    an = active_analyser()
    an.vals = np.ones(BANDS)
    look = Look(colors.MODE_RAINBOW, (255, 0, 0), 1.6)
    prims = RadialVisual().frame(600, 600, 1 / 60, an, look, False)
    segs = [p for p in prims if p.kind == "line"]
    assert len(segs) > 64 * 2
    cx = 300.0

    def dx(p):
        return abs((p.a + p.c) / 2 - cx)

    centre = min(segs, key=dx)
    side = max(segs, key=dx)
    assert centre.rgb != side.rgb
    assert centre.rgb[0] > centre.rgb[1] and centre.rgb[0] > centre.rgb[2]
    assert side.rgb == colors.wave_rgb(dx(side), 600 * 0.2, 300.0)


def test_rainbow_ring_is_not_one_flat_colour():
    an = active_analyser()
    an.beat = True
    look = Look(colors.MODE_RAINBOW, (255, 0, 0), 1.6)
    prims = RadialVisual().frame(600, 600, 1 / 60, an, look, False)
    colours = {p.rgb for p in prims if p.kind == "line" and p.alpha == 1.0 and p.w > 0}
    assert len(colours) > 3


def test_wave_only_visual_draws_just_the_waveform():
    from audiovis.visuals import WaveVisual

    an = active_analyser()
    an.beat = True
    look = Look(colors.MODE_RAINBOW, (255, 0, 0), 1.6)
    prims = WaveVisual().frame(600, 400, 1 / 60, an, look, False)
    assert prims and all(p.kind == "line" for p in prims)
    xs = [p.a for p in prims] + [p.c for p in prims]
    assert min(xs) < 5 and max(xs) > 590
    assert all(abs(p.b - 200) < 80 and abs(p.d - 200) < 80 for p in prims)
