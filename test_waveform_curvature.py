import numpy as np
import pytest

import waveform_curvature as wc


def reference(wf, delay=2, dim=25):
    # the loop version used in experiments/
    n = len(wf)
    span = (dim - 1) * delay
    start = max(0, (n - span) // 2)
    T = n - span - start
    emb = np.column_stack([wf[start + i * delay:start + i * delay + T] for i in range(dim)])
    dv = np.diff(emb, axis=0)
    u = dv / np.linalg.norm(dv, axis=1)[:, None]
    ang = np.arccos(np.clip((u[:-1] * u[1:]).sum(1), -1, 1))
    return 1 - ang.mean() / np.pi


def test_matches_reference():
    x = np.random.default_rng(0).normal(size=(20, 90))
    expected = [reference(w) for w in x]
    np.testing.assert_allclose(wc.waveform_curvature(x, delay=2, dim=25), expected, atol=1e-12)


def test_batch_matches_single():
    x = np.random.default_rng(1).normal(size=(10, 40))
    single = [wc.waveform_curvature(w) for w in x]
    np.testing.assert_allclose(wc.waveform_curvature(x, chunk=3), single)


def test_scale_invariant():
    w = np.random.default_rng(2).normal(size=40)
    assert wc.waveform_curvature(w) == pytest.approx(wc.waveform_curvature(25 * w))


def test_flat_waveform_is_nan():
    assert np.isnan(wc.waveform_curvature(np.zeros(40)))


def test_false_positive_rate():
    noise = np.random.default_rng(3).normal(size=(20000, 40))
    _, _, thr = wc.calibrate_and_filter(noise[:10000], noise[:10000], percentile=5)
    rate = np.mean(wc.waveform_curvature(noise[10000:]) > thr)
    assert rate == pytest.approx(0.05, abs=0.01)


def test_nan_never_kept():
    noise = np.random.default_rng(4).normal(size=(500, 40))
    keep, scores, _ = wc.calibrate_and_filter(np.zeros((1, 40)), noise)
    assert np.isnan(scores[0]) and not keep[0]


def test_bad_input():
    with pytest.raises(ValueError):
        wc.calibrate_and_filter(np.zeros((3, 40)), np.zeros((3, 50)))
    with pytest.raises(ValueError):
        wc.calibrate_and_filter(np.zeros((3, 40)), np.ones((3, 40)), percentile=0)
