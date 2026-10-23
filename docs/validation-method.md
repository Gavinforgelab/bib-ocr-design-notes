# Validation Method: how the numbers were measured, and what they do not claim

> The pipeline quotes one headline measurement in public:
> a real race clip, processed end to end, with every sampled frame accounted for.
> This document is the audit trail for that claim.

## The setup

- **Source**: one continuous clip from a real 10K race, 36.5 s, 1080p at
  59.94 fps — 2,190 decoded frames in total.
- **Sampling**: every 0.1 s, i.e. one frame in six → **366 frames** enter the
  funnel. Nothing downstream sees more than that. The deadline for this pass
  is the next morning, not the next minute; sampling hard enough to catch a
  bib once matters more than decoding everything.
- **Environment**: a single laptop-class GPU. No datacenter, no cluster.

## The funnel

Every number below answers a different question. Keeping them separate is
the whole discipline.

```
2,190  frames decoded            — what the clip contains
  366  frames sampled             — what entered the funnel (1 in 6)
  205  person detections          — runners found; each one becomes an ROI attempt
  158  OCR candidates             — crops that produced a raw string
   98  validated reads            — strings that passed charset + geometry checks
    2  stable bib numbers         — tracks whose votes reached threshold
```

Note what these are *not*. There is no "bib detector" anywhere in this
funnel: 205 is the count of people a detector found, and the crop that
follows is computed from that person's keypoints (see
[decisions.md D2](decisions.md)). The count is printed so the arithmetic is
checkable, not because a bib detector exists to credit.

The public headline quotes 99.9% confidence on one read. That number is:

- **what the model said about one frame** — a confidence score
- and **not** what the pipeline gets right across the race — an accuracy
  score, which is a different measurement that needs labeled ground truth
  per frame and is not what this validation pass was for

Anyone quoting confidence as accuracy has skipped the last mile of honesty;
we would rather document the distinction than let the number travel.

## What was logged

Every sampled frame produced a row: frame index, timestamp, detections with
bounding boxes and confidence, the ROI each crop came from, raw OCR output,
normalized output, validation verdict, and per-call latency. Track-level
decisions were logged separately: when a track first received a bib
identity, when it changed, and what evidence accumulated.

Two counters per track, and they are not interchangeable. A runner is
**visible** in more frames than the runner is **readable** in: the main
subject here was on screen for 141 of the 176 samples in a 17.5 s window, and
the entire clip produced 98 validated reads across both tracks. Quoting 141 as
"frames of evidence" would be a track credited with reads it never made — the
same class of error as quoting a confidence score as an accuracy score, one
level down.

This is the part that outlived the run itself. When a number is questioned
weeks later, the answer is a query against the log, not a memory of the
afternoon.

## Why a two-read track is still published

One of the two published tracks carries **two** reads, which is below the
voting threshold on its own (`min_evidence=5` in
[`reference/frame_voting.py`](../reference/frame_voting.py)). It was published
anyway, and the reason is the part a frame-only view of this pipeline misses:

The candidate set is constrained **before** the crop is read, not after. The
event's timing system says which bib numbers were on course in that second, and
the pipeline matches footage to results within ±5 s. A read that agrees with a
bib the timing system already placed in that window is not a weakly supported
guess; it is a confirmation. Two frames that agree with an independent record
outrank twenty frames of self-agreement with nothing behind them.

That distinction is also why an unattended pipeline can publish a track a human
reviewer would have discarded — and why the raw vote count is the wrong number
to gate on in a system that has an external candidate list.

## Failure archiving

Frames where the funnel dropped information were archived **by failure
category** — no text found, low-resolution crop, unresolvable confusion —
not deleted. Two reasons:

1. Failure categories are the roadmap: each category points at a different
   defense (see [decisions.md D7](decisions.md)).
2. A validation pass that only keeps successes is marketing. The failed
   frame we kept visible — "not read, kept" — is the one that makes the
   rest of the numbers believable.

## Latency, framed honestly

The pass took ~110 s against a 36.5 s clip: about **three times the clip's
length**, not three times faster than realtime. Framed as throughput that
sounds weak; framed as an offline job that finishes overnight on a laptop,
it is more than the use case needs. State the constraint with the number,
or the reader will supply the wrong frame of reference themselves.

## The schema

`artifacts/validation-run.sample.json` holds the sanitized schema of the
measurement record — field names and structure identical to what the run
produced, values replaced with the public numbers above. The original
artifact contains filesystem paths and hardware identifiers and stays
private; the schema is what a reader needs to reproduce the *shape* of the
audit.
