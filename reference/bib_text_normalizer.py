"""Bib string normalization — the charset constraint and the confusables.

A race bib is a short, rule-bound string: one letter, four digits in the
common scheme (A0030). OCR does not know that. This module encodes what the
scheme makes knowable:

1. **Charset constraint** — anything outside [A-Z0-9] after cleanup is
   rejected before it can pollute voting.
2. **Position-aware confusion repair** — a leading `0` is almost certainly
   an `O`; an `O` in the digit block is almost certainly a `0`. Repairing
   positionally converts a chunk of raw OCR misses into valid reads without
   touching the model.

Reference implementation written for this repository; not the production
code. Dependencies: none beyond the standard library.
"""

from __future__ import annotations

import re

# Common scheme: one letter, four digits. Adjust per event as needed.
BIB_PATTERN = re.compile(r"^[A-Z]\d{4}$")

# First character must be a letter -> map likely digit misreads back.
_LEADING_TO_LETTER = str.maketrans({"0": "O", "1": "I", "8": "B", "5": "S", "2": "Z"})

# Characters 2..5 must be digits -> map likely letter misreads back.
_DIGIT_BLOCK_TO_DIGIT = str.maketrans(
    {"O": "0", "Q": "0", "D": "0", "U": "0", "I": "1", "L": "1", "B": "8", "S": "5", "Z": "2"}
)


def normalize_candidate(raw: str | None) -> str | None:
    """Turn a raw OCR string into a valid bib, or None if it cannot be.

    Returns the *repaired* candidate — the caller votes on these, so a
    repaired A0O30 and a clean A0030 land in the same bucket and the truth
    wins on volume instead of being split by a one-character misread.
    """
    if not raw:
        return None

    cleaned = re.sub(r"[^A-Za-z0-9]", "", raw).upper()
    if len(cleaned) != 5:
        return None

    repaired = cleaned[0].translate(_LEADING_TO_LETTER) + cleaned[1:].translate(
        _DIGIT_BLOCK_TO_DIGIT
    )

    return repaired if BIB_PATTERN.fullmatch(repaired) else None


if __name__ == "__main__":
    cases = [
        ("A0030", "A0030"),   # clean read
        ("A0O30", "A0030"),   # letter O misread in digit block
        ("a0030", "A0030"),   # case noise
        ("A-0030", "A0030"),  # separator noise
        ("80030", "B0030"),   # leading digit misread as letter slot
        ("A0O3O", "A0030"),   # two repairs at once
        ("A003", None),       # too short — reject, do not guess
        ("X00Y0", None),      # unrepairable
        ("", None),
        (None, None),
    ]
    for raw, expected in cases:
        got = normalize_candidate(raw)
        mark = "ok " if got == expected else "FAIL"
        print(f"{mark} {str(raw):>8} -> {str(got):>6} (expected {expected})")
    assert all(normalize_candidate(r) == e for r, e in cases), "self-test failed"
    print("all self-tests passed")
