from audiovis import colors
from audiovis import settings as store


def test_loudness_gradient_goes_pink_to_red():
    quiet = colors.loudness_rgb(0.0)
    loud = colors.loudness_rgb(1.0)
    assert quiet[0] > 200 and quiet[2] > 100 and quiet[1] < 120
    assert loud[0] > 200 and loud[1] < 60 and loud[2] < 60


def test_loudness_gradient_passes_through_blue_and_green():
    blue = colors.loudness_rgb(0.4)
    green = colors.loudness_rgb(0.65)
    assert blue[2] > blue[0] and blue[2] > blue[1]
    assert green[1] > green[0] and green[1] > green[2]


def test_loudness_input_is_clamped():
    assert colors.loudness_rgb(-5) == colors.loudness_rgb(0)
    assert colors.loudness_rgb(9) == colors.loudness_rgb(1)


def test_parse_hex():
    assert colors.parse_hex("#00ffaa") == (0, 255, 170)
    assert colors.parse_hex("00FFAA") == (0, 255, 170)
    assert colors.parse_hex("#0fa") == (0, 255, 170)
    assert colors.parse_hex("#00ffa") is None
    assert colors.parse_hex("#gg0000") is None
    assert colors.parse_hex("") is None


def test_to_hex_roundtrip():
    assert colors.to_hex((255, 45, 149)) == "#ff2d95"
    assert colors.parse_hex(colors.to_hex((1, 2, 3))) == (1, 2, 3)


def test_blend_fades_to_black():
    assert colors.blend((200, 100, 50), 0.5) == (100, 50, 25)
    assert colors.blend((200, 100, 50), 0.0) == (0, 0, 0)


def test_bar_rgb_modes():
    fixed = (10, 20, 30)
    assert colors.bar_rgb(colors.MODE_FIXED, 3, 32, 0.9, 1.6, fixed) == fixed
    assert colors.bar_rgb(colors.MODE_RAINBOW, 0, 32, 0.9, 1.6, fixed) == colors.rainbow_rgb(0, 32)
    assert colors.bar_rgb(colors.MODE_LOUDNESS, 0, 32, 0.5, 2.0, fixed) == colors.loudness_rgb(1.0)


def test_settings_roundtrip(tmp_path):
    path = tmp_path / "settings.json"
    cfg = store.Settings(visual="bars", colour_mode=colors.MODE_FIXED, hex="#112233", sensitivity=2.2)
    store.save(cfg, path)
    loaded = store.load(path)
    assert loaded.visual == "bars"
    assert loaded.colour_mode == colors.MODE_FIXED
    assert loaded.hex == "#112233"
    assert loaded.sensitivity == 2.2


def test_settings_sanitise_bad_values(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text('{"visual": "nope", "colour_mode": 7, "hex": "zzz", "sensitivity": 99, "width": "x", "extra": 1}')
    loaded = store.load(path)
    assert loaded.visual == "radial"
    assert loaded.colour_mode == colors.MODE_LOUDNESS
    assert loaded.hex == store.DEFAULT_HEX
    assert loaded.sensitivity == 3.0
    assert loaded.width == 900


def test_settings_missing_or_corrupt_file(tmp_path):
    assert store.load(tmp_path / "missing.json").visual == "radial"
    bad = tmp_path / "bad.json"
    bad.write_text("not json")
    assert store.load(bad).visual == "radial"
