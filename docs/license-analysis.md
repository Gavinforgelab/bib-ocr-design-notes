# License Analysis: why the default detector was not an option

> A reading of the licenses as they shipped in 2026, for one specific
> deployment: a closed-source commercial SaaS that processes video on its own
> servers. This is engineering due diligence, not legal advice — check your
> own deployment.

## The constraint

The bib-recognition pipeline runs inside a closed-source commercial product.
Users interact with it over a network; they never receive a binary. Two
properties of the license question follow directly:

1. Distribution-style analysis ("we only ship the model on our servers") is
   the wrong frame. What matters is the network-use clause.
2. Whatever license attaches to the chosen components attaches to the
   product's legal exposure, not just to a research prototype.

## What AGPL-3.0 changes compared to GPL

The GNU Affero General Public License is GPL v3 plus one clause, and that
clause is the whole story for a SaaS deployment.

- **GPL**: copyleft obligations trigger on *distribution*. Run a modified
  version on your own server and hand nothing out, and the license asks
  nothing of you.
- **AGPL §13 (network use)**: if users interact with a modified version
  *over a network*, you must offer them the corresponding source. There is
  no "we only run it on our servers" exit — the clause was written to close
  exactly that gap.

For a pipeline embedded in a closed SaaS, choosing an AGPL component means
the complete Corresponding Source of the combined work has to be made
available to the people using it over the network — which, in practice,
means the product, not just the component.

The distinction worth being precise about: §13 obliges you to *offer the
source to those users*, not to publish it to the world. In a closed product
that difference is academic — the users are the customers, and the offer is
the obligation — but stating it correctly matters, because the sloppy version
of this paragraph ("you must open-source everything") is the version that gets
quoted back at you by someone who knows the license better than you do.

## The weights question (the part people get wrong)

The common workaround attempt is: "AGPL covers the *code*, so I'll train my
own model and ship only the weights."

The upstream project's own licensing position closes this door:

- The training/fine-tuning pipeline is AGPL code; a model produced by it is
  generally treated as covered by the same terms.
- The upstream FAQ states this explicitly: fine-tuned weights, weights
  trained from scratch with the framework, and private deployments do not
  escape the obligation. The stated remedy is the same fork in the road:
  open-source everything or buy the enterprise license.

We treated the weights as infected and moved on. Even under a favorable
reading, the residual risk would sit on the exact artifact that makes the
product work — the worst possible place to carry a "probably fine".

That is a decision, not a finding. Whether weights are a derivative work of
the code that produced them is genuinely contested, and reasonable lawyers
land on both sides. What is not contested is who carries the downside if the
optimistic reading is wrong, and a small team cannot. Where the position is
argued, this document takes the conservative branch and says so, so that a
reader can see which sentences are law and which are risk appetite.

## Enforcement is not theoretical

The upstream vendor actively monitors compliance and has a commercial
licensing operation built on that enforcement. A small closed team is not
invisible to this, and "we didn't know" is not a defense that survives a
public GitHub history. Any pipeline whose value proposition is "closed by
design" cannot have an AGPL root.

## The three legal exits

| Exit | What it costs | Why we did not take it |
|---|---|---|
| **Open-source the whole product** | The entire codebase becomes AGPL | The product's value is the closed loop: recording, matching, delivery, paywall |
| **Enterprise license** | Annual fee, quote-based, per project/org | Real money for capability that permissively-licensed components provide for free |
| **Rebuild on permissive components** | Engineering time to re-validate | The only exit that keeps both the code and the money |

## The replacement stack, license by license

| Component | Project | License | Note |
|---|---|---|---|
| Object detection | YOLOX | Apache-2.0 | Anchor-free YOLO-family detector; the capability we needed, none of the terms we feared |
| Pose estimation | RTMPose / RTMO (MMPose) | Apache-2.0 | Pretrained only in our deployment |
| Text recognition | PaddleOCR | Apache-2.0 | Detection + recognition in one package |
| Tracking | ByteTrack | MIT | Official implementation |
| Fallback VLM | Qwen2.5-VL | Apache-2.0 | Arbitration use only |

No component in the chain is copyleft. No component's output artifact
(weights, crops, read strings) carries obligations back into the product.

## The part that is easy to miss

The license decision had to be made **before** training anything. Had we
fine-tuned the convenient framework first and audited later, the trained
weights would already be an AGPL-attached asset sunk into the product — and
the "swap the detector" exit would have meant throwing away real work. Due
diligence at selection time cost an afternoon; due diligence after training
costs a model.
