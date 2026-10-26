"""Waveform curvature (v1)"""
import numpy as np

__version__ = "0.1.0"
__all__ = ["waveform_curvature", "turn_angles", "calibrate_and_filter"]


def _embed(x, delay, dim):
    n = x.shape[1]
    dim = max(2, n // 4) if dim is None else dim
    span = (dim - 1) * delay
    start = max(0, (n - span) // 2)
    T = n - span - start
    if T < 3:
        return None
    idx = start + delay * np.arange(dim)
    return np.stack([x[:, i:i + T] for i in idx], axis=-1)


def _angles(x, delay, dim):
    emb = _embed(x, delay, dim)
    if emb is None:
        return np.full((len(x), 0), np.nan)
    step = np.diff(emb, axis=1)
    norm = np.linalg.norm(step, axis=2)
    ok = norm > 1e-10
    unit = step / np.where(ok, norm, 1.0)[..., None]
    cos = np.clip((unit[:, :-1] * unit[:, 1:]).sum(-1), -1.0, 1.0)
    return np.where(ok[:, :-1] & ok[:, 1:], np.arccos(cos), np.nan)


def _prep(waveform):
    x = np.asarray(waveform, dtype=float)
    if x.ndim not in (1, 2):
        raise ValueError("waveform must be (n_samples,) or (n_waveforms, n_samples)")
    return np.atleast_2d(x), x.ndim == 1


def turn_angles(waveform, delay=2, dim=None):
    """Per-point turn angles in radians (NaN where undefined)."""
    x, single = _prep(waveform)
    out = _angles(x, delay, dim)
    return out[0] if single else out


def waveform_curvature(waveform, delay=2, dim=None, chunk=4096):
    """Curvature, 1 - mean(turn_angle) / pi. Higher means smoother.

    Takes one waveform or a (n_waveforms, n_samples) batch. `dim` defaults to
    n_samples // 4. Returns NaN if the score is undefined.
    """
    x, single = _prep(waveform)
    scores = np.empty(len(x))
    for i in range(0, len(x), chunk):
        ang = _angles(x[i:i + chunk], delay, dim)
        n = np.isfinite(ang).sum(axis=1)
        mean = np.nansum(ang, axis=1) / np.maximum(n, 1)
        s = 1.0 - mean / np.pi
        s[n < 2] = np.nan
        scores[i:i + chunk] = s
    return scores[0] if single else scores


def calibrate_and_filter(candidate_waveforms, noise_waveforms, percentile=2.0, delay=2, dim=None):
    """Keep candidates whose curvature beats a cutoff set from noise.

    `percentile` is the share of pure noise (in %) allowed to pass; lower is
    stricter. Returns (keep, scores, threshold).
    """
    cand = np.atleast_2d(candidate_waveforms)
    noise = np.atleast_2d(noise_waveforms)
    if cand.shape[1] != noise.shape[1]:
        raise ValueError("candidate and noise waveforms must have the same length")
    if not 0 < percentile < 100:
        raise ValueError("percentile must be between 0 and 100")
    noise_scores = waveform_curvature(noise, delay, dim)
    noise_scores = noise_scores[np.isfinite(noise_scores)]
    if noise_scores.size == 0:
        raise ValueError("noise waveforms have no defined curvature")
    threshold = float(np.percentile(noise_scores, 100 - percentile))
    scores = waveform_curvature(cand, delay, dim)
    keep = np.isfinite(scores) & (scores > threshold)
    return keep, scores, threshold
