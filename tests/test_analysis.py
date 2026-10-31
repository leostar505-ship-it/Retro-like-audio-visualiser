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


def kick_track(seconds=8.0, period=0.4, rate=TARGET_RATE):
    n = int(seconds * rate)
    t = np.arange(n) / rate
    x = 0.12 * np.sin(2 * np.pi * 55 * t) + 0.08 * np.sin(2 * np.pi * 220 * t) + 0.05 * np.sin(2 * np.pi * 880 * t)
    kicks = []
    k = 0.5
    while k < seconds - 0.3:
        kicks.append(k)
        s = int(k * rate)
        m = int(0.18 * rate)
        tt = np.arange(m) / rate
        freq = 55 + 90 * np.exp(-tt * 40)
        x[s : s + m] += 0.5 * np.sin(2 * np.pi * np.cumsum(freq) / rate) * np.exp(-tt * 14)
        x[s : s + 240] += 0.3 * np.random.default_rng(1).standard_normal(240) * np.exp(-np.arange(240) / 60.0)
        k += period
    return x.astype(np.float32), kicks


def beats_for(x, ring_sens=1.6):
    an = Analyser(TARGET_RATE)
    an.ring_sens = ring_sens
    out = []
    hop = TARGET_RATE // 60
    for pos in range(FFT_SIZE, len(x), hop):
        an.update(x[pos - FFT_SIZE : pos], 1 / 60, pos / TARGET_RATE)
        if an.beat:
            out.append(pos / TARGET_RATE)
    return np.array(out)


def test_kicks_over_a_loud_sustained_mix_register():
    x, kicks = kick_track()
    beats = beats_for(x)
    hit = sum(1 for k in kicks if len(beats) and np.min(np.abs(beats - k - 0.02)) < 0.09)
    assert hit >= 0.75 * len(kicks)
    assert len(beats) <= 1.7 * len(kicks)


def test_higher_ring_sensitivity_fires_more_often():
    x, _ = kick_track()
    assert len(beats_for(x, 8.0)) >= len(beats_for(x, 1.6)) >= len(beats_for(x, 0.5))


def test_no_beats_in_silence_or_a_pure_steady_tone():
    assert len(beats_for(np.zeros(TARGET_RATE * 3, dtype=np.float32))) == 0
    t = np.arange(TARGET_RATE * 4) / TARGET_RATE
    assert len(beats_for((0.4 * np.sin(2 * np.pi * 80 * t)).astype(np.float32))) <= 1


def test_drone_tracks_the_strongest_tone_and_resists_flicker():
    an = Analyser(TARGET_RATE)
    strong = sine(220, amp=0.5) + sine(660, amp=0.2)
    now = settle(an, strong, frames=40)
    assert abs(an.drone_hz - 220) < 6
    near_tie = sine(220, amp=0.5) + sine(660, amp=0.55)
    settle(an, near_tie, frames=30, start=now)
    assert abs(an.drone_hz - 220) < 6
    dominant = sine(660, amp=0.6) + sine(220, amp=0.1)
    settle(an, dominant, frames=40, start=now + 1.0)
    assert abs(an.drone_hz - 660) < 10


def test_bass_mode_reacts_far_less_to_a_mid_frequency_click_than_kick_mode():
    n = TARGET_RATE * 4
    t = np.arange(n) / TARGET_RATE
    x = (0.1 * np.sin(2 * np.pi * 55 * t)).astype(np.float32)
    burst_t = np.arange(2400) / TARGET_RATE
    burst = (0.6 * np.sin(2 * np.pi * 500 * burst_t) * np.exp(-burst_t * 60.0)).astype(np.float32)
    for k in (1.0, 1.6, 2.2, 2.8, 3.4):
        s = int(k * TARGET_RATE)
        x[s : s + len(burst)] += burst

    def peak_flux(trigger):
        an = Analyser(TARGET_RATE)
        an.set_trigger(trigger)
        peak = 0.0
        for pos in range(FFT_SIZE, len(x), TARGET_RATE // 60):
            an.update(x[pos - FFT_SIZE : pos], 1 / 60, pos / TARGET_RATE)
            peak = max(peak, an.flux)
        return peak

    assert peak_flux("kick") > 3.0 * peak_flux("bass")


def test_set_trigger_ignores_unknown_names():
    an = Analyser(TARGET_RATE)
    an.set_trigger("nope")
    assert an.trigger == "kick"
    an.set_trigger("bass")
    assert an.trigger == "bass"
