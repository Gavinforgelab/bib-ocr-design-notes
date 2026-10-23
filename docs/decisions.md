# Decision Log: one entry per component

> ADR-style: for each choice — the context, the options considered, the veto,
> and the consequence we live with. The license constraints behind these
> choices are detailed in [license-analysis.md](license-analysis.md).
>
> **Scope of the first person.** D1–D5, D7 and the validation method are the
> author's selection and engineering decisions. D6 covers the training runs,
> which were joint work with the team's vision lead. Nothing in this
> log claims the model architecture.

---

## D1 · Object detection → YOLOX (Apache-2.0)

**Context.** Runners must be found in every sampled frame. The default
instinct — and the default of every tutorial — is the Ultralytics stack.

**Options.** Ultralytics YOLOv8/11 (AGPL-3.0) · YOLOX (Apache-2.0) · RT-DETR
(Apache-2.0) · no detector at all (D2 makes this partly true).

**Decision.** YOLOX where a detector is needed. Anchor-free, comparable
capability, and a license that never attaches to the product.

**Veto.** Ultralytics: AGPL-3.0, weights included. A capable architecture is
not worth a root-level legal dependency.

**Consequence.** No one-click CLI. Training discipline (hyperparameters,
seeds, data versioning) is managed by hand instead of by framework magic —
see D6, which was joint work with the vision lead.

---

## D2 · ROI localization → pose keypoints, not a trained bib detector

**Context.** OCR needs a tight crop around the bib. The obvious path is
labeling a few thousand bib boxes and training a detector.

**Decision.** A pretrained pose model provides shoulder and hip keypoints;
race rules pin the bib to the torso; the torso is exactly the keypoint-
bounded region. The crop is computed, not learned
([geometry in `reference/roi_from_keypoints.py`](../reference/roi_from_keypoints.py);
lineage, paradigm trade-offs and topology mapping in
[pose-prior.md](pose-prior.md)).

**Veto.** The custom detector: annotation budget, retraining every time a
race changes kit color, and a model that knows bibs but not bodies.

**Consequence.** Zero annotation, zero training, full generalization across
events. Bonus: the full keypoint set is available downstream for
re-identification when multiple cameras must agree on the same athlete.
Cost: when the pose model errs, the ROI errs with it — see D7 defenses.

---

## D2.1 · Pose model → RTMPose/RTMO (MediaPipe evaluated, vetoed)

**Context.** D2 needs a keypoint source. The options split on lineage and
deployment target: the HRNet → MMPose → RTMPose server-grade line, and the
BlazePose → MediaPipe on-device line. Details in
[pose-prior.md](pose-prior.md).

**Decision.** RTMPose/RTMO (Apache-2.0, MMPose), top-down: one full-
resolution refinement crop per detected runner.

**Veto.** MediaPipe Pose — and explicitly **not** on license grounds: it is
Apache-2.0 and legally clean. It lost on engineering: bundled models are
quantized for phones and browsers, tuned for a single subject, and our
hostile regime is small runners (30–80 px tall) in dense groups — exactly
where device-class accuracy gives out. Top-down crops at
server resolution are the correct tool for the back of the pack.

**Consequence.** Higher per-frame compute than an on-device model, and a
stronger accuracy floor where it matters. Also the honest note in the
decision table: at least one row here was vetoed for engineering reasons
while perfectly legal — the license analysis set the boundary, not the
whole strategy.

---

## D3 · Text recognition → PaddleOCR (Apache-2.0)

**Context.** The crop contains one short string: one letter, four digits.

**Decision.** PaddleOCR end to end (text detection finds the string inside
the ROI, recognition reads it), with the character set constrained to
`A-Z0-9` and confusable characters repaired post-hoc
([`reference/bib_text_normalizer.py`](../reference/bib_text_normalizer.py)).

**Veto.** Commercial cloud OCR: per-call cost at video sampling rates does
not survive a finance review, and every frame leaves the building.

**Consequence.** O/0, 8/B confusions are a data problem, handled in
normalization and voting — not a model problem to retrain away.

---

## D4 · Multi-object tracking → ByteTrack (MIT)

**Context.** One runner appears in dozens of frames. The output that matters
is not "a bib was read somewhere" but "bib A0030 was visible from 15.9 s to
33.4 s across 141 frames".

**Decision.** ByteTrack. Its defining trick — associating low-score
detection boxes instead of discarding them — keeps partially occluded
runners attached to their track, which is exactly the finish-line situation.

**Veto.** DeepSORT: the older standard, but its identity model leans harder
on appearance features, and ByteTrack's low-score association covers our
occlusion pattern better.

**Consequence.** Every OCR result aggregates per track, so voting (D7) has a
natural home and the decision log has a natural shape: one line per
track-level conclusion, not per frame.

---

## D5 · Fallback → a VLM used sparingly (Qwen2.5-VL, Apache-2.0)

**Context.** A small residue of frames defeats the funnel: the bib is at a
leg-slash angle (some trail events pin it low), an arm crosses it, or the
vote splits between two confusable readings.

**Decision.** Route only low-confidence, vote-splitting, or geometrically
implausible cases to a VLM for a second read.

**Veto.** Running the VLM on every frame: cost per frame is orders of
magnitude above OCR, for a job OCR already does on 95%+ of frames.

**Consequence.** The expensive model is the arbiter, not the worker. Cost
scales with the error rate, not the frame rate.

---

## D6 · Training & experiments → local GPU for real runs, cloud quotas for drafts

**Context.** YOLOX needs hands-on configuration; hyperparameter sweeps and
first-pass experiments benefit from free cloud GPUs (Kaggle/Colab queues).

**Decision.** Prototype and sweep on free cloud quotas; anything that
produces an artifact worth keeping runs locally with fixed seeds and
versioned data.

**Consequence.** Reproducibility: every published number can be re-derived.
The measurements quoted in public are measurements that survive being
re-run.

---

## D7 · Rejected and defended: known failure modes

| Failure | Defense |
|---|---|
| Pose keypoint drift drags the ROI off the bib | Run text detection inside the ROI as a sanity check; widen and retry when no text appears |
| Frame-to-frame ROI jitter degrades OCR | Temporal smoothing along the track before voting |
| O/0, 8/B confusions survive OCR | Post-hoc normalization + multi-frame voting + D5 arbitration |
| Unreproducible experiments | D6: fixed seeds, versioned data, local runs for anything quoted in public |

---

## D0 · The one that was never an option: background subtraction

Fixed-camera pipelines often skip detection entirely: model the background,
diff the frames, keep the moving blobs. It is cheap, classic, and was vetoed
on one fact — **the camera moves**. Field cameras follow the race; the
background never stands still long enough to model. Every component above
was chosen to be indifferent to camera motion.
