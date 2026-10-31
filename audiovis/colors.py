import colorsys

MODE_LOUDNESS = "loudness"
MODE_FIXED = "custom"
MODE_RAINBOW = "rainbow"
MODES = (MODE_LOUDNESS, MODE_FIXED, MODE_RAINBOW)

HEX_DIGITS = set("0123456789abcdefABCDEF")


def clamp01(value):
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def hsl_to_rgb(h, s, l):
    r, g, b = colorsys.hls_to_rgb((h % 360.0) / 360.0, l / 100.0, s / 100.0)
    return (int(round(r * 255)), int(round(g * 255)), int(round(b * 255)))


def loudness_rgb(value):
    v = clamp01(value)
    return hsl_to_rgb(330.0 * (1.0 - v), 95.0, 52.0 + v * 8.0)


def rainbow_rgb(index, count):
    return hsl_to_rgb(index / count * 300.0, 90.0, 55.0)


def wave_rgb(dx, crossing, half):
    d = abs(dx)
    if d <= crossing:
        hue = 330.0 * (d / max(crossing, 1e-6)) ** 1.7
    else:
        hue = 330.0 + 30.0 * min(1.0, (d - crossing) / max(0.3 * (half - crossing), 1e-6))
    return hsl_to_rgb(hue, 90.0, 55.0)


RING_RAINBOW = hsl_to_rgb(190.0, 90.0, 60.0)


def blend(rgb, alpha):
    a = clamp01(alpha)
    return (int(rgb[0] * a), int(rgb[1] * a), int(rgb[2] * a))


def to_hex(rgb):
    return "#%02x%02x%02x" % (rgb[0], rgb[1], rgb[2])


def parse_hex(text):
    t = text.strip().lstrip("#")
    if len(t) == 3 and all(c in HEX_DIGITS for c in t):
        t = "".join(c * 2 for c in t)
    if len(t) != 6 or any(c not in HEX_DIGITS for c in t):
        return None
    return (int(t[0:2], 16), int(t[2:4], 16), int(t[4:6], 16))


def bar_rgb(mode, index, count, value, sensitivity, fixed):
    if mode == MODE_FIXED:
        return fixed
    if mode == MODE_RAINBOW:
        return rainbow_rgb(index, count)
    return loudness_rgb(value * sensitivity)


def ring_rgb(mode, scaled_value, fixed):
    if mode == MODE_FIXED:
        return fixed
    if mode == MODE_RAINBOW:
        return RING_RAINBOW
    return loudness_rgb(scaled_value)
