# Evaluating a bib-reading pipeline

> Written for the person buying this work rather than doing it. If a vendor
> quotes you "99% accuracy" on bib recognition, this is the page that tells
> you which question to ask next — and how to run the test yourself in an
> afternoon without a labeling team.

The point of this document is not to make our numbers look good. It is that
the metrics most vendors quote are the ones that are easy to produce and hard
to falsify, and the four that actually decide whether a race day works are
none of them.

## The four numbers that matter

| Metric | Definition | What it decides |
|---|---|---|
| **Read rate** | tracks with a published bib ÷ tracks the tracker saw | Did every finisher get a clip? |
| **Read correctness** | published bibs that match ground truth ÷ published bibs | Does a buyer get someone else's video? |
| **Identity stability** | 1 − (tracks whose bib changed after publication ÷ published tracks) | Would the athlete notice? |
| **Cost per footage hour** | GPU wall seconds ÷ footage seconds, at production sampling | Does the model work at race scale? |

Report all four together or none. Read rate alone rewards a system that
publishes guesses; correctness alone rewards a system that publishes nothing;
stability is invisible in any single-frame measurement; and cost is what turns
a demo into an invoice.

## What is not a metric

- **A confidence score.** `0.9999` is what a model said about one read. It is
  not the share of athletes you got right, and the two can differ by twenty
  points. Ask for the denominator.
- **mAP on a public bib dataset.** It measures a model on somebody else's
  photographs. Your venue has your lighting, your bib stock, your camera
  height and your back-of-the-pack density.
- **"99% accuracy."** Without a denominator this sentence means "we measured
  something". Ask: 99% of what, over how many runners, on which footage, and
  was the failure counted per frame or per athlete?
- **A pretty sample clip.** Ten hand-picked finishers prove the pipeline can
  work. They do not tell you the failure rate, which is the number you are
  buying.

## Building ground truth without a labeling team

You do not need per-frame labels. You need two things the event already has:

1. **The start list.** It bounds the candidate set to the runners who were on
   course — which is a large part of the problem solved for free. Bib `A0498`
   cannot appear in a 10K if nobody ran under that number.
2. **Fifty athletes read by eye.** From the entry list and the finish footage,
   an operator can write down fifty bib numbers and the second each crossed.
   That is half a day of work and it yields every metric above except cost.

Label **per track**, not per frame. Per-frame labels measure the pipeline's
agreement with itself; per-track labels measure whether the athlete gets their
video.

## Three traps in your own test

- **Sampling interval.** At 1 s per sample a runner is on screen for two
  frames; at 0.1 s, twenty. A coarse interval inflates the read rate on the
  runners you do catch and silently loses the ones you do not. State the
  interval in the report or the number is not comparable.
- **The easy half.** Split results by position. Back-of-pack runners are
  smaller, more occluded and more often in a crowd. A single aggregate number
  hides a pipeline that is fine at the front and useless at the back — and the
  back of the pack paid for their video too.
- **Deleting failures.** A validation pass that keeps only the frames it read
  is a highlight reel. Ask for the failure set, categorised. The categories
  are where the next month of work is.

## How this repository's numbers read under that lens

Published from one 36.5 s clip, 1080p, sampled at 0.1 s:

| | |
|---|---|
| Tracks seen | 2 subjects with a stable identity |
| Published bibs | 2, neither contested |
| Read rate | 2 of 2 — over a two-track sample, which is not a rate, it is an anecdote |
| Read correctness | not measured: no labelled ground truth was built for this pass |
| Stability | no bib changed after publication, over two tracks |
| Cost | 110 s of laptop GPU for 36.5 s of footage ≈ 3× the clip length, offline |

Two of the four numbers are effectively missing, and that is the honest state of
a feasibility pass: it establishes that the loop closes end to end, not that it
is production-grade on your footage. Anyone who hands you four confident
numbers from a single clip is quoting the two easy ones twice.

## A trial that settles it in one day

1. Send **ten minutes of your worst footage** — backlight, rain, a crowded
   finish, the far camera. Not the good one.
2. Send **twenty bib numbers you already know** ran, and the second each
   crossed.
3. Ask for: read rate, correctness, stability, cost per footage hour, and the
   failure categories with counts.

Ten minutes and twenty numbers is enough to tell a working pipeline from a
demo. It is also small enough that nobody has to sign anything to find out.
