"""Tests for the reference geometry and the two rules built on it.

The `__main__` blocks under `reference/` are demonstrations: they print what
they prove and assert it in passing. This file is the check that runs on every
push, and it exists because a repository whose thesis is engineering discipline
should not be the one place where "it works on my laptop" is the test plan.

    python -m pytest -q          (from the repository root)

Dependencies: numpy and pytest. No model, no weights, no images.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "reference"
sys.path.insert(0, str(REFERENCE))

from bib_text_normalizer import normalize_candidate  # noqa: E402
from frame_voting import conclude_track  # noqa: E402
from roi_from_keypoints import KEYPOINT_TOPOLOGIES, torso_roi  # noqa: E402

# An upright runner: shoulders at y=620, hips at y=810, 80 px apart.
UPRIGHT = {
    "left_shoulder": (860.0, 620.0),
    "right_shoulder": (940.0, 620.0),
    "left_hip": (875.0, 810.0),
    "right_hip": (925.0, 810.0),
}


def pose(topology: str = "coco17", **overrides: tuple[float, float]) -> np.ndarray:
    """A keypoint array in the requested topology, confidence 0.9 everywhere."""
    idx = KEYPOINT_TOPOLOGIES[topology]
    size = max(idx.values()) + 1
    kp = np.zeros((size, 3))
    kp[:, 2] = 0.9
    for name, (x, y) in {**UPRIGHT, **overrides}.items():
        kp[idx[name]] = [x, y, 0.95]
    return kp


# --- the geometry -----------------------------------------------------------


@pytest.mark.parametrize("topology", ["coco17", "mediapipe33"])
def test_topology_does_not_change_the_roi(topology: str) -> None:
    """The four anchors are the whole contract: same pose, same crop.

    This is what makes the prior portable across model families, and it is the
    claim `docs/pose-prior.md` makes about swapping topologies being a one-line
    change. If this test ever fails, that document is wrong.
    """
    coco = torso_roi(pose("coco17"))
    other = torso_roi(pose(topology), topology=topology)
    assert coco is not None and other is not None
    for field in ("cx", "cy", "width", "height", "angle_deg"):
        assert getattr(coco, field) == pytest.approx(getattr(other, field))


def test_upright_runner_has_zero_angle() -> None:
    """0 deg is upright, not 180. Image y grows downward, so the torso axis
    points at +y and atan2(0, +h) is zero."""
    roi = torso_roi(pose())
    assert roi is not None
    assert roi.angle_deg == pytest.approx(0.0, abs=1e-9)


def test_a_lean_rotates_the_crop_but_not_its_width() -> None:
    """Hips forward of the shoulders: angle grows, width still follows the
    shoulders. This is the property the pose prior is sold on - the crop
    follows the body instead of assuming a vertical rectangle."""
    upright = torso_roi(pose())
    lean = torso_roi(pose(left_hip=(925.0, 790.0), right_hip=(960.0, 805.0)))
    assert upright is not None and lean is not None
    assert 0 < lean.angle_deg < 30
    assert lean.width == pytest.approx(upright.width)


def test_the_top_edge_clears_the_shoulder_line_by_the_padding() -> None:
    """The bib is pinned at the top of the torso, so the crop opens upward.
    Guarding the arithmetic here because an off-by-one-half in the offset is
    invisible in a rendered crop and clips the first row of digits."""
    padding = 0.15
    torso_h = 190.0
    roi = torso_roi(pose(), top_padding=padding)
    assert roi is not None
    assert roi.height == pytest.approx(torso_h * (1 + padding))
    top_edge = roi.cy - roi.height / 2
    assert top_edge == pytest.approx(620.0 - padding * torso_h)


def test_low_confidence_anchor_refuses_to_guess() -> None:
    """A hallucinated hip joint makes a confidently wrong crop, which makes
    garbage OCR, which the vote then has to un-believe. Cheaper to skip the
    frame."""
    kp = pose()
    kp[KEYPOINT_TOPOLOGIES["coco17"]["left_hip"]][2] = 0.1
    assert torso_roi(kp, min_confidence=0.3) is None
    # And the gate is a parameter, not a constant buried in the function.
    assert torso_roi(kp, min_confidence=0.05) is not None


def test_degenerate_input_returns_none_instead_of_nan() -> None:
    """Shoulders and hips at the same point: no axis, no crop. Returning a
    zero-size box here would push a NaN centre into the crop call."""
    flat = pose(left_hip=(900.0, 620.0), right_hip=(900.0, 620.0))
    assert torso_roi(flat) is None
    too_short = np.zeros((12, 3))
    too_short[:, 2] = 0.9
    assert torso_roi(too_short) is None  # COCO hip index 12 is out of range


# --- the charset rule -------------------------------------------------------

NORMALIZE_CASES = [
    ("A0030", "A0030"),   # clean read
    ("A0O30", "A0030"),   # letter O in the digit block
    ("a0030", "A0030"),   # case noise
    ("A-0030", "A0030"),  # separator noise
    ("80030", "B0030"),   # leading digit read into the letter slot
    ("A0O3O", "A0030"),   # two repairs at once
    ("A003", None),       # too short: reject, do not guess
    ("X00Y0", None),      # unrepairable
    ("", None),
    (None, None),
]


@pytest.mark.parametrize(("raw", "expected"), NORMALIZE_CASES)
def test_normalization_table(raw: str | None, expected: str | None) -> None:
    assert normalize_candidate(raw) == expected


def test_repair_is_idempotent() -> None:
    """The caller votes on repaired strings, so re-repairing must not move a
    candidate into a different bucket - that would split a track's evidence."""
    for raw, expected in NORMALIZE_CASES:
        if expected is None:
            continue
        assert normalize_candidate(expected) == expected


# --- the voting rule --------------------------------------------------------


def dense_track() -> list[tuple[int, str, float]]:
    reads = [(i, "A0030", 0.9) for i in range(16, 30)]
    reads += [(18, "A0830", 0.7), (24, "A0080", 0.7)]  # confusions
    reads += [(35, "A0030", 0.95)]  # stragglers past the dense block
    return reads


def test_volume_beats_a_single_confident_frame() -> None:
    result = conclude_track(dense_track(), first_seen_frame=10, last_seen_frame=38)
    assert result is not None
    assert result.bib == "A0030"
    assert result.evidence_count == 15
    assert not result.contested


def test_the_visibility_window_comes_from_the_track_not_the_reads() -> None:
    """`Absence is data`: a bib read at frames 16 and 35 still reports the
    window the tracker observed. Two counters, deliberately - a track can be
    visible for 29 frames and readable in 17 of them, and collapsing the two
    into one number loses the difference."""
    result = conclude_track(dense_track(), first_seen_frame=10, last_seen_frame=38)
    assert result is not None
    assert result.track_frame_count == 29
    assert result.evidence_count < result.track_frame_count


def test_split_evidence_is_flagged_not_published_as_truth() -> None:
    split = [(i, "A0030", 0.8) for i in range(5)]
    split += [(i, "A0830", 0.8) for i in range(5, 10)]
    result = conclude_track(split, first_seen_frame=0, last_seen_frame=9)
    assert result is not None
    assert result.contested


def test_too_little_evidence_says_nothing() -> None:
    assert conclude_track(dense_track()[:2], first_seen_frame=16, last_seen_frame=17) is None
    assert conclude_track([], first_seen_frame=0, last_seen_frame=0) is None


# --- the promise the README makes ------------------------------------------


def test_reference_stays_dependency_free() -> None:
    """The README promises NumPy and nothing else, which is what lets a reader
    clone this without a GPU, a download, or a model. Enforced rather than
    advertised: importing the three modules must not drag in a framework."""
    heavy = [m for m in ("torch", "cv2", "paddle", "onnxruntime") if m in sys.modules]
    assert not heavy, f"reference/ pulled in {heavy}"


def test_the_committed_figure_is_the_geometry() -> None:
    """`docs/img/roi-geometry.svg` is generated, not drawn.

    The README's first image is the argument the whole repository makes, so it
    is the last thing that should be allowed to drift from the code. This
    asserts the committed file is byte-identical to what the generator emits
    today: change the geometry, and the figure has to be re-rendered or CI
    goes red.
    """
    sys.path.insert(0, str(ROOT / "tools"))
    import draw_roi

    committed = (ROOT / "docs" / "img" / "roi-geometry.svg").read_text()
    assert committed.splitlines() == draw_roi.build_svg().splitlines()

    # And the numbers the figure prints are the numbers the geometry returns.
    angles = [float(a) for a in re.findall(r'data-angle="([\d.]+)"', committed)]
    assert len(angles) == len(draw_roi.POSES)
    for (lean, _), printed in zip(draw_roi.POSES, angles):
        roi = draw_roi.pose(lean, 0.0)["roi"]
        assert printed == pytest.approx(roi.angle_deg, abs=0.01)


def test_the_demo_is_deterministic() -> None:
    """The README tells a reader to clone and run. A fixed seed is what makes
    that reproducible; this pins the seed by comparing two runs, not by
    comparing against a stored transcript that would need updating forever."""
    runs = [
        subprocess.run(
            [sys.executable, str(REFERENCE / "demo.py")],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        for _ in range(2)
    ]
    assert runs[0] == runs[1]
    assert "bib=A0030" in runs[0]
    assert "contested=False" in runs[0]
