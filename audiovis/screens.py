SCREENS = {
    "full": ("Full window (smooth)", 0, 0, False),
    "oled": ("128x64 OLED (mono)", 128, 64, True),
    "oled-colour": ("128x64 (colour)", 128, 64, False),
    "tft-160": ("160x128 TFT (colour)", 160, 128, False),
    "tft-240": ("240x240 TFT (colour)", 240, 240, False),
    "tft-320": ("320x240 TFT (colour)", 320, 240, False),
    "tft-480": ("480x320 TFT (colour)", 480, 320, False),
}

SCREEN_ORDER = tuple(SCREENS)
DEFAULT_SCREEN = "full"


def screen_label(key):
    return SCREENS[key][0]


def screen_from_label(label):
    for key, value in SCREENS.items():
        if value[0] == label:
            return key
    return DEFAULT_SCREEN
