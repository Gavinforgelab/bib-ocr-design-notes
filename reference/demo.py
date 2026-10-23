"""Synthetic end-to-end run: pose-prior ROI -> normalization -> voting.

Clone-and-verify demo. No GPU, no model, no downloads, no footage — the
runner is generated, the "OCR" is a deterministic noise model around one
true bib string, and the geometry is the real code from
roi_from_keypoints.py.

    python demo.py            (from reference/, needs numpy only)

What to watch in the output:

1. ROI angle follows the runner's lean frame by frame — the crop is
   computed from anatomy, so it never needs retraining.
2. The funnel shrinks the way the real one did: frames -> reads -> valid
   reads -> one stable conclusion.
3. Confused reads (A0O30) land in the same bucket as clean ones — repair
   feeds voting, and volume picks the truth.

Reference implementation written for this repository; not the production
code.
"""

from __future__ import annotations

import math

import numpy as np

from bib_text_normalizer import normalize_candidate
from frame_voting import conclude_track
from roi_from_keypoints import torso_roi

# --- the synthetic race -----------------------------------------------------

FRAMES = 40                 # 4.0 s at 0.1 s sampling
VISIBLE_FROM = 10           # runner enters pose range
READABLE_FROM = 14          # bib close enough for "OCR"
TRUE_BIB = "A0030"
CONFUSABLES = ["A0O30", "A0080"]  # what a sloppy read looks like, pre-normalization

rng = np.random.default_rng(2026)  # fixed seed: this demo re-runs identically


def synthetic_pose(frame: int) -> np.ndarray | None:
    """One runner approaching, then leaning into the finish tape."""
    if frame < VISIBLE_FROM:
        return None
    t = (frame - VISIBLE_FROM) / (FRAMES - VISIBLE_FROM)
    lean = math.radians(28 * t)  # forward lean grows to the tape
    cx = 900 + 120 * t           # drifting across frame, camera follows
    cy = 640 + 60 * t
    shoulder_w, torso_h = 78.0, 190.0

    kp = np.zeros((17, 3))
    kp[:, 2] = 0.9
    # shoulders along the (rotated) shoulder line, hips below along the axis
    axis = np.array([math.sin(lean), math.cos(lean)])
    perp = np.array([math.cos(lean), -math.sin(lean)])
    mid_sh = np.array([cx, cy])
    kp[5, :2] = mid_sh - perp * shoulder_w / 2
    kp[6, :2] = mid_sh + perp * shoulder_w / 2
    kp[11, :2] = mid_sh + axis * torso_h - perp * shoulder_w * 0.3
    kp[12, :2] = mid_sh + axis * torso_h + perp * shoulder_w * 0.3
    return kp


def synthetic_ocr(frame: int) -> str | None:
    """Deterministic noise model standing in for the OCR stage."""
    if frame < READABLE_FROM or frame % 7 == 3:  # some frames simply miss
        return None
    if rng.random() < 0.15:
        return CONFUSABLES[rng.integers(0, len(CONFUSABLES))]
    return TRUE_BIB


# --- the run ----------------------------------------------------------------

reads: list[tuple[int, str, float]] = []
track_frames = 0
angles: list[float] = []

for frame in range(FRAMES):
    kp = synthetic_pose(frame)
    if kp is None:
        continue
    track_frames += 1

    roi = torso_roi(kp)
    assert roi is not None
    angles.append(roi.angle_deg)

    raw = synthetic_ocr(frame)
    bib = normalize_candidate(raw)
    if bib is not None:
        reads.append((frame, bib, 0.85))

result = conclude_track(reads, first_seen_frame=VISIBLE_FROM, last_seen_frame=FRAMES - 1)

print(f"frames sampled        : {FRAMES}")
print(f"frames on track       : {track_frames}")
print(f"valid reads           : {len(reads)}")
print(f"ROI angle span        : {min(angles):.1f}..{max(angles):.1f} deg (follows the lean)")
print()
assert result is not None
print(
    f"conclusion: bib={result.bib}  evidence={result.evidence_count}/{result.track_frame_count} "
    f"frames  contested={result.contested}"
)
assert result.bib == TRUE_BIB and not result.contested
print("\nthe confused reads joined the clean ones; volume picked the truth.")
