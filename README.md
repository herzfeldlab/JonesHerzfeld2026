# Waveform Curvature

Principled curation of singular spikes in extracellular recordings.

## Purpose

Deciding whether an extracellular event is a spike or an artifact is one of
the most basic, unavoidable steps in every spike sorting
pipeline, and it is currently solved by convention rather than
by principle. Most labs pick an amplitude threshold that "looks right,"
tune it by trial and error against a sorter's output, and accept
whatever spikes that threshold happens to miss.

This tool exists to give researchers a principled alternative: a way to
decide, for each candidate, whether it is or is not an action potential,
grounded in a truth about what an action potential actually is, rather
than in an arbitrary amplitude cutoff.


## The problem

Spike detection forces a tradeoff. Set your threshold high and you get
clean, obviously-spike-shaped candidates, but you miss real spikes that
happen to be smaller or partially overlapping. Set it low and you catch
those spikes, but you flood your sorter with noise crossings that were
never action potentials at all. Most pipelines resolve this by picking a
threshold that's higher than it should be, and quietly accepting the
missed spikes as a cost of doing business.

Waveform curvature is a way out of that tradeoff. It lets you set a low
detection threshold on purpose, catching everything that might be a
spike, and then curate that candidate pool with a second, independent
criterion: does the waveform actually look like a spike.

## The idea

An extracellular action potential has smooth, stereotyped temporal
dynamics: fast depolarization, fast repolarization, a coherent trajectory
from baseline through trough and back. Most artifacts do not possess
this trait.

That coherence is visible directly if you plot the waveform as a curve
(sample index against amplitude) and look at how sharply it bends.
Curvature is defined as:

```
curvature = 1 - mean(turn_angle) / pi
```

At each interior sample, the turn angle is the angle between the
incoming and outgoing step vectors of the waveform trajectory, computed
with a dot product. A straight run has a turn angle near 0 (curvature
near 1). A trajectory that keeps reversing on itself has a turn angle
near pi (curvature near 0). Real spikes sit in a consistent, separable
range because their dynamics are consistent; noise does not.

## Why this is a white-box solution

There's no model to train and no black box to trust. The score is a
closed-form geometric quantity computed directly from the waveform's
shape, so a threshold on it is a criterion you can state, defend, and
report: "candidates were kept if their trajectory through phase space
had a mean turn angle below X." Any researcher can look at the formula
and understand exactly why a given candidate was kept or dropped.

It's also cheap. It's a handful of numpy operations per waveform, with
no dependencies beyond numpy, and it drops into any pipeline as a
pre-sorting filter, independent of whatever sorter you use downstream.

## How the threshold is calibrated

The cutoff is not chosen by eye. It's calibrated directly from your own
recording's noise:

1. Pull a pool of noise snippets, windows that did not cross your
   detection threshold, from the same recording.
2. Score every noise snippet's curvature.
3. Set the cutoff at a chosen percentile of that noise distribution
   (for example, the 95th percentile of noise scores).
4. Keep only candidates whose curvature exceeds that cutoff.

Because the cutoff sits at a percentile of the noise distribution itself,
it comes with a concrete, interpretable guarantee: by construction, only
about `100 - percentile` percent of pure noise would pass the filter by
chance. That's a real false-positive rate you can report, not an
arbitrary number picked by eye. It also means the cutoff adapts
automatically to each recording, since noise characteristics drift
across sessions, probes, and preparations.

## Recommended detection threshold

Because curation happens after detection, you're free to lower your
detection threshold. We encourage researchers to do exactly that: choose
a relatively low detection threshold to maximize sensitivity (catch
every plausible spike, including small ones), and let curvature handle
specificity (reject the ones that don't have spike-like dynamics). This
decouples the two halves of the sensitivity/specificity tradeoff instead
of forcing one detection threshold to do both jobs at once.

## Install

```bash
pip install numpy
```

Then drop `waveform_curvature.py` into your project. It's a single file
with no other dependencies.

## End-to-end usage in a spike sorting workflow

The filter sits between detection and sorting:

```
raw recording -> low-threshold peak detection -> curvature curation -> sort survivors
```

### 1. Detect candidate peaks with a low threshold

Use whatever detector you already use (for example, spikeinterface's
`detect_peaks`, or your own threshold crossing detector), set
deliberately low so you don't miss real spikes.

### 2. Extract snippets

For each candidate, and for a separate pool of noise snippets (windows
where nothing crossed threshold, just background), cut out a
fixed-length waveform window around each peak, on the peak channel:

```python
# candidate_waveforms: (n_candidates, n_samples)
# noise_waveforms:     (n_noise, n_samples)
```

If your data is multi-channel, average over the peak channel and its
immediate neighbors first to get a clean 1-D waveform per snippet. Any
denoising you already do here is fine; curvature just needs a 1-D trace.

### 3. Score and calibrate a cutoff

```python
from waveform_curvature import calibrate_and_filter

keep, scores, threshold = calibrate_and_filter(
    candidate_waveforms,
    noise_waveforms,
    percentile=2.0,   # about 2% of noise passes by chance; lower is stricter
)
```

`keep` is a boolean mask over your candidates.

### 4. Filter and hand off to your sorter

```python
filtered_times = candidate_times[keep]
filtered_waveforms = candidate_waveforms[keep]

# now feed filtered_times / the corresponding recording segments
# into your spike sorter (Kilosort, Mountainsort, SpyKING Circus, etc.)
```

The sorter now only sees candidates that already have spike-like
dynamics, instead of every threshold crossing in the recording, even
though your detector was set to catch everything.

## Tuning

- `percentile` is the main knob. Lower values are stricter (fewer noise
  snippets sneak through, but you risk dropping some real low-curvature
  spikes). Start around 1 to 5 percent and adjust based on how your
  sorter's yield changes.
- Recompute the noise threshold per recording, or per session. Noise
  characteristics drift with the preparation and the probe, and the
  point of calibrating from noise is that the cutoff tracks that drift.

## API

```python
waveform_curvature(waveform, dt=1.0)
```
Curvature score for one `(n_samples,)` waveform, or an array of scores
for a `(n_candidates, n_samples)` batch.

```python
turn_angles(waveform, dt=1.0)
```
The raw per-point turn angles (radians) behind the score, if you want to
inspect them directly.

```python
calibrate_and_filter(candidate_waveforms, noise_waveforms, percentile=2.0, dt=1.0)
```
Scores both pools, sets a cutoff from the noise pool, and returns
`(keep, scores, threshold)`.

## License

MIT. See `LICENSE`.
