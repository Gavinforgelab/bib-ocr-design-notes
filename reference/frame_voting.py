"""Per-track multi-frame voting — the stabilizer idea in its smallest form.

One runner is visible in dozens of frames; OCR reads a subset of them, and
some reads are wrong. The unit of output that matters is not a frame read
but a *track conclusion*: which bib this track is, when it first and last
appeared, and how much evidence stands behind that.

Three rules do the work:

1. **Volume beats confidence** — a bib read correctly in 20 mediocre frames
   is more believable than one spectacular frame. Evidence count is the
   primary signal; per-read confidence is the tiebreaker.
2. **Agreement ratio gates acceptance** — a track where the winning bib
   barely outvotes its runner-up is not stable, it is contested. Those go
   to arbitration (the VLM slot in production) instead of being published.
3. **Absence is data** — first/last seen timestamps come from the track,
   not from the reads, so a bib read at frames 3 and 40 still reports the
   full visibility window the tracker observed.

Reference implementation written for this repository; not the production
code. Dependencies: none beyond the standard library.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass


@dataclass(frozen=True)
class TrackConclusion:
    bib: str
    first_seen_frame: int
    last_seen_frame: int
    evidence_count: int          # frames that voted for the winning bib
    track_frame_count: int       # frames the tracker saw, reads or not
    mean_confidence: float
    contested: bool              # winner did not clear agree_ratio


def conclude_track(
    reads: list[tuple[int, str, float]],
    first_seen_frame: int,
    last_seen_frame: int,
    min_evidence: int = 5,
    agree_ratio: float = 0.6,
) -> TrackConclusion | None:
    """reads: (frame_index, normalized_bib, confidence) — already normalized.

    Returns None when there is not enough evidence to say anything. Returns
    a contested TrackConclusion (contested=True) when evidence exists but
    disagrees too much — the caller decides whether to arbitrate or drop.
    """
    if not reads:
        return None

    counts = Counter(bib for _, bib, _ in reads)
    bib, votes = counts.most_common(1)[0]

    if votes < min_evidence:
        return None

    confs = [c for _, b, c in reads if b == bib]
    runner_up = counts.most_common(2)[1][1] if len(counts) > 1 else 0

    return TrackConclusion(
        bib=bib,
        first_seen_frame=first_seen_frame,
        last_seen_frame=last_seen_frame,
        evidence_count=votes,
        track_frame_count=last_seen_frame - first_seen_frame + 1,
        mean_confidence=sum(confs) / len(confs),
        contested=(votes / len(reads)) < agree_ratio or (votes - runner_up) < min_evidence,
    )


if __name__ == "__main__":
    # A track across 40 frames with 14 usable reads: two are misreads of the
    # same bib (already normalized to a *different* string), the rest agree.
    reads = [(i, "A0030", 0.9) for i in range(16, 30, 1)]
    reads += [(18, "A0830", 0.7), (24, "A0080", 0.7)]  # confusions, normalized form
    reads += [(35, "A0030", 0.95)]  # stragglers past the dense block

    result = conclude_track(reads, first_seen_frame=10, last_seen_frame=38)
    assert result is not None and not result.contested
    print(
        f"bib={result.bib} evidence={result.evidence_count}/{result.track_frame_count} frames "
        f"conf={result.mean_confidence:.3f} contested={result.contested}"
    )

    # A contested track: split evidence must not be published as-is.
    split = [(i, "A0030", 0.8) for i in range(5)] + [(i, "A0830", 0.8) for i in range(5, 10)]
    contested = conclude_track(split, first_seen_frame=0, last_seen_frame=9)
    assert contested is not None and contested.contested
    print(f"split vote -> bib={contested.bib} contested={contested.contested} (route to arbitration)")

    # Too little evidence says nothing at all.
    assert conclude_track(reads[:2], first_seen_frame=16, last_seen_frame=17) is None
    print("sparse track -> None (say nothing rather than guess)")
