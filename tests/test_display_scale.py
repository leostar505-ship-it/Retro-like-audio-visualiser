import math

import pytest

from audiovis.display import MAX_OUTPUT_PIXELS
from audiovis.screens import SCREENS


@pytest.mark.parametrize("key", [k for k in SCREENS if SCREENS[k][1]])
def test_scale_cap_keeps_output_small_enough(key):
    _, w, h, _ = SCREENS[key]
    limit = max(1, int(math.sqrt(MAX_OUTPUT_PIXELS / (w * h))))
    assert limit >= 1
    if limit > 1:
        assert (w * limit) * (h * limit) <= MAX_OUTPUT_PIXELS
