import time

import numpy as np

from audiovis import capture
from audiovis.capture import DemoSource, LoopbackCapture, RingBuffer


def test_ring_buffer_keeps_latest_samples():
    buf = RingBuffer(size=8)
    buf.push(np.arange(5, dtype=np.float32))
    buf.push(np.arange(5, 10, dtype=np.float32))
    assert buf.latest().tolist() == [2, 3, 4, 5, 6, 7, 8, 9]


def test_ring_buffer_returns_zeros_when_stale():
    buf = RingBuffer(size=8, stale_after=0.05)
    buf.push(np.ones(8, dtype=np.float32))
    assert buf.latest().sum() == 8
    time.sleep(0.1)
    assert buf.latest().sum() == 0


def test_ring_buffer_age_before_any_data():
    assert RingBuffer(size=8).age() == float("inf")


def test_stereo_downmix_and_decimation_carry():
    cap = LoopbackCapture()
    cap.buffer = RingBuffer(size=8)
    cap._channels = 2
    cap._factor = 2
    left = np.array([1, 3, 5, 7, 9], dtype=np.float32)
    right = np.array([3, 5, 7, 9, 11], dtype=np.float32)
    interleaved = np.empty(10, dtype=np.float32)
    interleaved[0::2] = left
    interleaved[1::2] = right
    cap._push(interleaved)
    assert cap.buffer.data[-2:].tolist() == [3.0, 7.0]
    assert cap._carry.tolist() == [10.0]
    cap._push(np.array([20, 20], dtype=np.float32))
    assert cap.buffer.data[-1] == 15.0


def test_demo_source_produces_signal():
    src = DemoSource()
    time.sleep(0.05)
    data = src.latest()
    assert data.shape == (capture.FFT_SIZE,)
    assert np.abs(data).max() > 0.01
