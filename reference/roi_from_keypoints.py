"""Torso ROI from pose keypoints — the reference geometry.

The idea this file demonstrates (see docs/decisions.md D2): race rules pin
the bib to the torso, and the torso is exactly the region bounded by the
shoulder and hip keypoints of any pretrained pose model. The crop is
computed from anatomy, not learned from labels.

The geometry consumes exactly four anchors — left/right shoulder, left/right
hip — so it is decoupled from any model's keypoint topology through
KEYPOINT_TOPOLOGIES below. COCO-17 (RTMPose & friends) and MediaPipe-33
(BlazePose lineage) both map; adding a third family is one dict entry. See
docs/pose-prior.md for the lineage and why MediaPipe was vetoed despite its
clean license.

Dependencies: numpy only. No model, no weights, no images — the caller
supplies keypoints and, if it wants pixels, warps its own crop with the
returned rectangle (cv2.getRectSubPix + cv2.getRotationMatrix2D is the
usual pair in production).

Reference implementation written for this repository; not the production
code.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

# Anchor indices per keypoint topology. Any model family that can name
# these four anchors plugs in; the geometry never changes.
KEYPOINT_TOPOLOGIES: dict[str, dict[str, int]] = {
    "coco17": {"left_shoulder": 5, "right_shoulder": 6, "left_hip": 11, "right_hip": 12},
    "mediapipe33": {"left_shoulder": 11, "right_shoulder": 12, "left_hip": 23, "right_hip": 24},
}


@dataclass(frozen=True)
class TorsoROI:
    """A rotated rectangle in image coordinates, ready to crop with."""

    cx: float          # center x
    cy: float          # center y
    width: float       # crop width  (across the torso)
    height: float      # crop height (shoulder line -> hip line)
    angle_deg: float   # torso axis tilt; 0 = upright runner
    corners: np.ndarray  # 4x2 polygon, for sanity-drawing on a frame


def torso_roi(
    keypoints: np.ndarray,
    width_factor: float = 1.3,
    top_padding: float = 0.15,
    min_confidence: float = 0.3,
    topology: str | dict[str, int] = "coco17",
) -> TorsoROI | None:
    """Compute the bib-bearing torso ROI from one pose estimate.

    keypoints: (N, 3) array of [x, y, confidence]; N must cover the topology.
    topology: a KEYPOINT_TOPOLOGIES name, or a custom {"left_shoulder": i, ...}
        dict — pass the indices your model actually emits.
    width_factor: torso width = shoulder-to-shoulder distance * this. A bib
        is usually wider than the skeleton line, and OCR wants margin.
    top_padding: lift the top edge above the shoulder line by this fraction
        of torso height, so the top of the bib is never clipped.
    min_confidence: below this on any of the four anchors, refuse to guess —
        a made-up ROI is worse than no ROI (the caller widens or skips).

    Returns None when the four anchor keypoints are not trustworthy.
    """
    idx = KEYPOINT_TOPOLOGIES[topology] if isinstance(topology, str) else topology
    anchors = [idx["left_shoulder"], idx["right_shoulder"], idx["left_hip"], idx["right_hip"]]

    pts = np.asarray(keypoints, dtype=float)
    if pts.shape[0] <= max(anchors):
        return None
    if any(pts[i][2] < min_confidence for i in anchors):
        return None

    ls, rs, lh, rh = pts[anchors[0]][:2], pts[anchors[1]][:2], pts[anchors[2]][:2], pts[anchors[3]][:2]

    shoulder_mid = (ls + rs) / 2.0
    hip_mid = (lh + rh) / 2.0

    # Torso axis: shoulder line -> hip line. The angle is what lets the crop
    # follow a sprinting runner's forward lean instead of assuming upright.
    # Image y grows downward, so "upright" (axis pointing at +y) is 0 deg.
    axis = hip_mid - shoulder_mid
    torso_height = float(np.linalg.norm(axis))
    if torso_height < 1e-6:
        return None
    angle_deg = math.degrees(math.atan2(axis[0], axis[1]))  # 0 = upright

    shoulder_width = float(np.linalg.norm(rs - ls))
    width = shoulder_width * width_factor
    height = torso_height * (1.0 + top_padding)

    # Open the padding above the shoulder line (bib top margin), not below
    # the hips: shift the center back along the axis by half the padding.
    unit = axis / torso_height
    center = shoulder_mid + axis * 0.5 - unit * (top_padding * torso_height / 2.0)

    # Corners of the rotated rectangle, for drawing / clipping checks.
    # Matches the angle convention above: local (across, along) -> image.
    hw, hh = width / 2.0, height / 2.0
    rad = math.radians(angle_deg)
    cos_a, sin_a = math.cos(rad), math.sin(rad)
    local = np.array([[-hw, -hh], [hw, -hh], [hw, hh], [-hw, hh]])
    rot = np.array([[cos_a, sin_a], [-sin_a, cos_a]])
    corners = local @ rot.T + center

    return TorsoROI(
        cx=float(center[0]),
        cy=float(center[1]),
        width=width,
        height=height,
        angle_deg=angle_deg,
        corners=corners,
    )


if __name__ == "__main__":
    # The same synthetic runner expressed twice: once in COCO-17 topology,
    # once in MediaPipe-33. The point to watch: identical ROI — the geometry
    # is topology-blind. A second pose shows the crop following a lean.
    up = {"left_shoulder": (860, 620), "right_shoulder": (940, 620),
          "left_hip": (875, 810), "right_hip": (925, 810)}

    def build(topology: str) -> np.ndarray:
        idx = KEYPOINT_TOPOLOGIES[topology]
        n = 17 if topology == "coco17" else 33
        kp = np.zeros((n, 3))
        kp[:, 2] = 0.9
        for name, (x, y) in up.items():
            kp[idx[name]] = [x, y, 0.95]
        return kp

    coco = torso_roi(build("coco17"), topology="coco17")
    mp = torso_roi(build("mediapipe33"), topology="mediapipe33")
    assert coco is not None and mp is not None
    assert all(abs(getattr(coco, f) - getattr(mp, f)) < 1e-9 for f in ("cx", "cy", "width", "height", "angle_deg"))
    print(
        f"same pose, two topologies -> identical ROI: "
        f"center=({coco.cx:.1f},{coco.cy:.1f}) size=({coco.width:.1f}x{coco.height:.1f}) "
        f"angle={coco.angle_deg:.2f}deg"
    )

    # Lean: hips shift forward; angle and center follow, width stays tied to
    # the shoulders. No retraining, no pose assumptions.
    lean_pts = dict(up, left_hip=(925, 790), right_hip=(960, 805))
    kp = np.zeros((17, 3))
    kp[:, 2] = 0.9
    for name, (x, y) in lean_pts.items():
        kp[KEYPOINT_TOPOLOGIES["coco17"][name]] = [x, y, 0.95]
    lean = torso_roi(kp)
    assert lean is not None
    print(
        f"leaning pose            -> center=({lean.cx:.1f},{lean.cy:.1f}) "
        f"angle={lean.angle_deg:.2f}deg top_edge_y={lean.cy - lean.height / 2:.1f}"
    )
    assert abs(coco.angle_deg) < 1e-6 and 0 < lean.angle_deg < 30  # upright is zero, not 180
