import json
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from .colors import MODE_LOUDNESS, MODES, parse_hex
from .screens import DEFAULT_SCREEN, SCREENS

VISUALS = ("radial", "bars")
DEFAULT_HEX = "#ff2d95"


@dataclass
class Settings:
    visual: str = "radial"
    screen: str = DEFAULT_SCREEN
    colour_mode: str = MODE_LOUDNESS
    hex: str = DEFAULT_HEX
    sensitivity: float = 1.6
    normalise: bool = True
    topmost: bool = False
    controls: bool = True
    device: str = ""
    width: int = 900
    height: int = 620

    def sanitise(self):
        if self.visual not in VISUALS:
            self.visual = "radial"
        if self.screen not in SCREENS:
            self.screen = DEFAULT_SCREEN
        if self.colour_mode not in MODES:
            self.colour_mode = MODE_LOUDNESS
        if not isinstance(self.hex, str) or parse_hex(self.hex) is None:
            self.hex = DEFAULT_HEX
        try:
            self.sensitivity = min(3.0, max(0.5, float(self.sensitivity)))
        except (TypeError, ValueError):
            self.sensitivity = 1.6
        self.normalise = bool(self.normalise)
        self.topmost = bool(self.topmost)
        self.controls = bool(self.controls)
        if not isinstance(self.device, str):
            self.device = ""
        try:
            self.width = min(4000, max(420, int(self.width)))
            self.height = min(3000, max(320, int(self.height)))
        except (TypeError, ValueError):
            self.width, self.height = 900, 620
        return self


def config_path():
    base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), ".config")
    return Path(base) / "AudioVisualiser" / "settings.json"


def load(path=None):
    target = Path(path) if path else config_path()
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return Settings().sanitise()
    if not isinstance(raw, dict):
        return Settings().sanitise()
    known = {f.name for f in fields(Settings)}
    values = {k: v for k, v in raw.items() if k in known}
    return Settings(**values).sanitise()


def save(settings, path=None):
    target = Path(path) if path else config_path()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")
    except OSError:
        pass
