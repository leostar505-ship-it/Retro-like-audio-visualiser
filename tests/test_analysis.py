import math

import numpy as np

from audiovis.analysis import (
    BANDS,
    FFT_SIZE,
    TARGET_RATE,
    Analyser,
    band_edges,
    decimation_factor,
)


def sine(freq, rate=TARGET_RATE, amp=0.5, n=FFT_SIZE):
    t = np.arange(n) / rate
    return (amp * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def settle(an, samples, frames=20, start=0.0, dt=1 / 60):
    now = start
    for _ in range(frames):
        now += dt
        an.update(samples, dt, now)
    return now


def test_band_edges_are_monotonic_and_in_range():
    for rate in (44100, 48000):
        lo, hi = band_edges(rate)
        assert len(lo) == BANDS and len(hi) == BANDS
        assert np.all(hi > lo)
        assert np.all(lo[1:] >= hi[:-1])
        assert hi.max() <= FFT_SIZE // 2


def test_decimation_factor():
    assert decimation_factor(44100) == 1
    assert decimation_factor(48000) == 1
    assert decimation_factor(96000) == 2
    assert decimation_factor(88200) == 2
    assert decimation_factor(192000) == 4


def test_tone_lights_the_matching_band():
    an = Analyser(TARGET_RATE)
    settle(an, sine(1000))
    expected = int(BANDS * math.log(1000 / 40.0) / math.log(16000 / 40.0))
    assert abs(int(an.bands.argmax()) - expected) <= 1
    assert an.bands.max() > 0.5


def test_silence_stays_quiet():
    an = Analyser(TARGET_RATE)
    settle(an, np.zeros(FFT_SIZE, dtype=np.float32))
    assert an.bands.max() == 0.0
    assert an.vals.max() == 0.0
    assert not an.beat


def test_normalise_suppresses_steady_sound():
    an = Analyser(TARGET_RATE)
    tone = sine(1000)
    settle(an, tone, frames=400)
    assert an.vals.max() < 0.15
    an.normalise = False
    settle(an, tone, frames=5, start=10.0)
    assert an.vals.max() > 0.5


def test_beat_fires_on_bass_hit_after_quiet():
    an = Analyser(TARGET_RATE)
    now = settle(an, np.zeros(FFT_SIZE, dtype=np.float32), frames=30)
    now += 1 / 60
    an.update(sine(60, amp=0.9), 1 / 60, now)
    assert an.beat


def test_beat_does_not_fire_continuously_on_steady_bass():
    an = Analyser(TARGET_RATE)
    now = settle(an, np.zeros(FFT_SIZE, dtype=np.float32), frames=30)
    bass = sine(60, amp=0.9)
    beats = 0
    for _ in range(240):
        now += 1 / 60
        an.update(bass, 1 / 60, now)
        beats += int(an.beat)
    assert beats <= 3


def test_rate_change_rebuilds_edges():
    an = Analyser(TARGET_RATE)
    an.set_rate(44100)
    assert an.rate == 44100
    assert np.array_equal(an.hi, band_edges(44100)[1])
    assert np.array_equal(an.lo, band_edges(44100)[0])


def bass_mix(amp):
    return sum(sine(f, amp=amp) for f in (45, 60, 80, 100, 130))


def count_beats(ring_sens):
    an = Analyser(TARGET_RATE)
    an.ring_sens = ring_sens
    now = settle(an, bass_mix(0.0005), frames=150)
    beats = 0
    for _ in range(60):
        now += 1 / 60
        an.update(bass_mix(0.002), 1 / 60, now)
        beats += int(an.beat)
    return beats


def test_higher_ring_sensitivity_fires_on_smaller_bass_jumps():
    low = count_beats(0.5)
    mid = count_beats(1.0)
    high = count_beats(3.0)
    assert low == 0
    assert high > mid >= low
