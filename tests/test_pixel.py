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


def wave_an(freq, amp=0.6, n=2048):
    from audiovis.analysis import TARGET_RATE

    an = Analyser()
    t = np.arange(n) / TARGET_RATE
    an.wave = (amp * np.sin(2 * np.pi * freq * t)).astype(np.float32)
    an.vals = np.zeros(BANDS)
    return an


def wave_ys(smooth, sens=1.6, samples=None):
    from audiovis.visuals import WaveRadialVisual

    vis = WaveRadialVisual()
    an = wave_an(80)
    if samples is not None:
        an.wave = samples
    look = Look(colors.MODE_FIXED, (255, 0, 0), sens, 1.6, smooth)
    prims = []
    for _ in range(30):
        prims = vis.wave_prims(400, 300, 1 / 60, an, look, False)
    return np.array([p.b for p in prims]), prims


def test_waveform_follows_a_low_drone_and_is_centred():
    ys, prims = wave_ys(0.5)
    assert ys.max() - ys.min() > 20
    assert abs(ys.mean() - 150) < 15
    assert len(prims) > 10


def test_waveform_smoothness_removes_high_frequency_detail():
    from audiovis.analysis import TARGET_RATE

    t = np.arange(2048) / TARGET_RATE
    mix = (0.5 * np.sin(2 * np.pi * 70 * t) + 0.3 * np.sin(2 * np.pi * 2600 * t)).astype(np.float32)
    rough, _ = wave_ys(0.0, samples=mix)
    smooth, _ = wave_ys(1.0, samples=mix)
    assert np.abs(np.diff(smooth)).sum() < np.abs(np.diff(rough)).sum()


def test_waveform_is_flat_in_silence_and_sensitivity_scales_it():
    quiet, _ = wave_ys(0.5, samples=np.zeros(2048, dtype=np.float32))
    assert np.ptp(quiet) < 1.0
    low, _ = wave_ys(0.5, sens=0.05)
    high, _ = wave_ys(0.5, sens=3.0)
    assert np.ptp(low) < np.ptp(high)


def test_sensitivity_floor_shrinks_bars():
    def bar_extent(sens):
        an = active_analyser()
        an.vals = np.ones(BANDS)
        look = Look(colors.MODE_FIXED, (255, 0, 0), sens)
        prims = RadialVisual().frame(300, 300, 1 / 60, an, look, False)
        return max(p.c for p in prims if p.kind == "line") - 150

    assert bar_extent(0.05) < bar_extent(1.6)
