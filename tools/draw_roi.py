"""Render `docs/img/roi-geometry.svg` from the geometry in `reference/`.

The figure is generated from the same `torso_roi()` the pipeline uses, so it
cannot drift from the code: `tests/test_reference.py` recomputes this module's
geometry and compares it against the numbers embedded in the committed SVG.

What it draws: a synthetic skeleton at three lean angles — upright, mid-stride,
and leaning into the tape — with the torso ROI on top of it and the bib
rectangle the ROI is there to contain. No footage, no athletes, no
photographs. The runner is arithmetic.

    python tools/draw_roi.py        (writes docs/img/roi-geometry.svg)
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "reference"))

from roi_from_keypoints import torso_roi  # noqa: E402

OUT = ROOT / "docs" / "img" / "roi-geometry.svg"

# Panel geometry, in image pixels. y grows downward.
PANEL_W = 320
HEIGHT = 352
TORSO_H = 118.0
SHOULDER_W = 62.0
SHOULDER_Y = 74.0

# The three poses. The angle is the only thing that changes; nothing else is
# tuned per panel, which is the point the figure is making.
POSES = [
    (0.0, "upright"),
    (14.0, "mid-stride"),
    (27.0, "into the tape"),
]

INK = "#1f2937"
FURNITURE = "#9aa4b2"
BIB = "#111827"
ROI_FILL = "#f59e0b"
ROI_STROKE = "#b45309"
CAPTION = "#111827"
MUTED = "#6b7280"


def pose(lean_deg: float, cx: float) -> dict[str, object]:
    """A synthetic runner at one lean angle, in absolute image coordinates."""
    lean = math.radians(lean_deg)
    axis = np.array([math.sin(lean), math.cos(lean)])
    perp = np.array([math.cos(lean), -math.sin(lean)])
    sm = np.array([cx, SHOULDER_Y])

    ls = sm - perp * SHOULDER_W / 2
    rs = sm + perp * SHOULDER_W / 2
    lh = sm + axis * TORSO_H - perp * SHOULDER_W * 0.3
    rh = sm + axis * TORSO_H + perp * SHOULDER_W * 0.3

    kp = np.zeros((17, 3))
    kp[:, 2] = 0.9
    kp[5, :2], kp[6, :2] = ls, rs
    kp[11, :2], kp[12, :2] = lh, rh
    roi = torso_roi(kp)
    assert roi is not None

    # The bib sits where the rules put it: on the chest, centred on the axis,
    # wider than it is tall because that is the shape of a printed bib.
    bib_w, bib_h = roi.width * 0.62, roi.height * 0.26
    bib_c = sm + axis * (TORSO_H * 0.34)
    hw, hh = bib_w / 2, bib_h / 2
    rad = math.radians(roi.angle_deg)
    rot = np.array([[math.cos(rad), math.sin(rad)], [-math.sin(rad), math.cos(rad)]])
    bib = np.array([[-hw, -hh], [hw, -hh], [hw, hh], [-hw, hh]]) @ rot.T + bib_c

    # Head clears the ROI's top edge, which sits 0.15 of torso height above the
    # shoulder line. Drawing it inside the rectangle read as a bug in the crop.
    head = sm - axis * (0.15 * TORSO_H + 18)

    return {
        "roi": roi,
        "ls": ls, "rs": rs, "lh": lh, "rh": rh,
        "sm": sm, "hip_mid": (lh + rh) / 2, "head": head, "bib": bib,
        "bib_c": bib_c, "bib_angle": roi.angle_deg,
    }


def pts(points: np.ndarray) -> str:
    return " ".join(f"{p[0]:.1f},{p[1]:.1f}" for p in points)


def panel(index: int, lean: float, title: str) -> str:
    cx = index * PANEL_W + PANEL_W / 2
    p = pose(lean, cx)
    roi = p["roi"]

    # Legs hang from the hip anchors, not from the midpoint: a stick figure
    # whose legs sprout from one point reads as a coat rack.
    legs = []
    for hip, sign in ((p["lh"], -1), (p["rh"], 1)):
        knee = hip + np.array([sign * 13, 46])
        foot = knee + np.array([sign * 7, 38])
        legs.append(f'<polyline points="{pts(np.array([hip, knee, foot]))}" />')

    anchors = "".join(
        f'<circle cx="{q[0]:.1f}" cy="{q[1]:.1f}" r="3.4" />'
        for q in (p["ls"], p["rs"], p["lh"], p["rh"])
    )

    return (
        f'<g data-angle="{roi.angle_deg:.2f}" data-roi-w="{roi.width:.2f}" '
        f'data-roi-h="{roi.height:.2f}">'
        # ROI first: it is the claim, and it should sit under the evidence.
        f'<polygon class="roi" points="{pts(roi.corners)}" />'
        f'<g class="furniture">{"".join(legs)}'
        # A neck, not a floating head: the ROI's top padding lifts it above the
        # shoulder line, so without this the head reads as a stray circle.
        f'<polyline points="{pts(np.array([p["sm"], p["head"]]))}" />'
        f'<circle cx="{p["head"][0]:.1f}" cy="{p["head"][1]:.1f}" r="14" /></g>'
        f'<polygon class="bib" points="{pts(p["bib"])}" />'
        f'<text class="bibtext" transform="rotate({p["bib_angle"]:.2f} '
        f'{p["bib_c"][0]:.1f} {p["bib_c"][1]:.1f})" x="{p["bib_c"][0]:.1f}" '
        f'y="{p["bib_c"][1] + 2.6:.1f}">A0030</text>'
        # The two lines the four anchors define, plus the sides.
        f'<g class="skeleton">'
        f'<polyline points="{pts(np.array([p["ls"], p["rs"]]))}" />'
        f'<polyline points="{pts(np.array([p["lh"], p["rh"]]))}" />'
        f'<polyline points="{pts(np.array([p["ls"], p["lh"]]))}" />'
        f'<polyline points="{pts(np.array([p["rs"], p["rh"]]))}" /></g>'
        # Anchors last, so nothing covers them.
        f'<g class="anchors">{anchors}</g>'
        f'<text class="cap" x="{cx:.0f}" y="298" text-anchor="middle">{title}</text>'
        f'<text class="sub" x="{cx:.0f}" y="315" text-anchor="middle">'
        f"ROI {roi.angle_deg:.0f}\u00b0</text>"
        f"</g>"
    )


def build_svg() -> str:
    panels = "".join(panel(i, lean, title) for i, (lean, title) in enumerate(POSES))
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="960" height="{HEIGHT}" \
viewBox="0 0 960 {HEIGHT}" role="img" \
aria-label="Three synthetic runners at increasing lean. The same four keypoints \
bound a torso rectangle in each; the rectangle rotates with the shoulder-to-hip \
line and still contains the bib.">
<style>
  .roi {{ fill: {ROI_FILL}; fill-opacity: 0.12; stroke: {ROI_STROKE}; stroke-width: 1.5; }}
  .skeleton polyline {{ fill: none; stroke: {INK}; stroke-width: 2; stroke-linecap: round; }}
  .furniture polyline, .furniture circle {{ fill: none; stroke: {FURNITURE}; stroke-width: 2; stroke-linecap: round; }}
  .bib {{ fill: {BIB}; }}
  .bibtext {{ fill: #ffffff; font: 600 7.5px ui-monospace, Menlo, monospace;
             letter-spacing: 0.08em; text-anchor: middle; }}
  .anchors circle {{ fill: {INK}; }}
  .cap {{ fill: {CAPTION}; font: 500 11px ui-monospace, Menlo, monospace; letter-spacing: 0.09em; }}
  .sub {{ fill: {MUTED}; font: 10px ui-monospace, Menlo, monospace; letter-spacing: 0.04em; }}
  .foot {{ fill: {MUTED}; font: 10px ui-monospace, Menlo, monospace; letter-spacing: 0.03em; }}
</style>
<rect width="960" height="{HEIGHT}" fill="#ffffff" />
{panels}
<text class="foot" x="{PANEL_W / 2:.0f}" y="342" text-anchor="middle">\
amber = torso ROI, computed from the four anchors</text>
<text class="foot" x="{PANEL_W * 1.5:.0f}" y="342" text-anchor="middle">\
black = the bib it has to contain</text>
<text class="foot" x="{PANEL_W * 2.5:.0f}" y="342" text-anchor="middle">\
nothing here was trained on a bib</text>
</svg>
"""


if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(build_svg())
    print(f"wrote {OUT.relative_to(ROOT)}")
