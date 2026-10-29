# Contributing

Thank you for helping. This project undoes text obfuscation and tells you what it did. Its first
rule is that **it must not change clean text**, so every contribution is judged against that.

By contributing you agree that your code is released under the MIT licence (see `LICENSE`).

## Before you start

- Read `README.md` for what the tool does and does not do, and `docs/taxonomy.md` for the list of
  tricks and what is out of scope (code obfuscation, languages other than English, wrong-encoding
  damage such as `Ã©`).
- Open an issue before a large change, or a new transform, so we can agree it is in scope.
- Python 3.10 or newer. The tool has no dependencies. Development uses [uv](https://docs.astral.sh/uv/).

## Running things

```
uv run python -m unittest discover -s tests     # unit tests
uv run python -m evaluation.gate                # the regression gate (exit code 1 on a regression)
uv run python -m evaluation.run --detail        # the full evaluation, with per-category tables
uv run text-deobfuscate --json "some text"           # try it
```

A pull request must pass both the unit tests and the gate. CI runs them.

## The gate, and the clean-text rule

`evaluation/gate.py` scores the committed development sets at every strictness level and compares
with `evaluation/baseline.json`. It fails if

- **clean texts changed** rises at any level (the measure that matters most), or
- recovery falls in any category, or a text that used to come back right now comes back worse.

If a change is a deliberate trade-off, run `uv run python -m evaluation.gate --update` in the same
commit and explain the reason in the pull request. Do not update the baseline to hide a regression.

## Adding a transform

`docs/architecture.md` ("Adding a transform") has the interface. In short:

1. A transform proposes candidate rewrites; the engine accepts one only when a plausibility score
   improves. Give it a guard that keeps ordinary text alone.
2. Use the trick name from `evaluation/tricks.py`; add it there with its strictness level.
3. **Samples are required.** Add a generator in `evaluation/obfuscator.py`, with several different
   shapes of the trick (not one shape with different words in it), and clean look-alike texts in
   `evaluation/negatives.py` that must not be changed. Rebuild the sets with
   `uv run python -m evaluation.build`.
4. Add unit tests, including text that must stay as it is. `CoverageTest` fails if a trick has no
   test that recovers it.
5. Run the gate. Record anything that moved, and why, in the pull request.
6. Add a row to `docs/taxonomy.md`.

## Data and licences

- Everything committed must be safe to publish and have a licence that allows redistribution.
- Evaluation rows from third-party sources keep their own licence and credit (`data/eval/README.md`).
  The `data/eval` files are **not** under the MIT licence.
- Do not commit samples with personal data (names with addresses, phone numbers, email addresses
  of private people); mask them. Real profanity, crude or hateful language in phishing, spam or injection
  text is fine as data, with its source and licence, kept to what the sample needs and only in the
  data files; do not write abusive text yourself, and see
  `CODE_OF_CONDUCT.md`. Do not commit data whose licence you have not checked.
- Do not copy another deobfuscation tool's code or data into the tool. Standard-library codecs
  and word-list or n-gram resources are fine.

## The test split

`data/eval/test/` is kept for a final judgement. Do not read it to get ideas for rules, and do not
tune against it. Develop against the dev sets.

## Pull requests

- Keep a pull request to one change.
- One maintainer must approve before it is merged.
- Fill in the checklist in the pull request template.
