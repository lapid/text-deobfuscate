## What and why

<!-- One change per pull request. -->

## Checklist

- [ ] `uv run python -m unittest discover -s tests` passes
- [ ] `uv run python -m evaluation.gate` passes (or `--update` is in this commit, with the reason below)
- [ ] Clean texts changed did not rise at any level
- [ ] New transform or trick: samples, clean look-alikes, unit tests, and a row in `docs/taxonomy.md`
- [ ] No test-split rows read or used for tuning
- [ ] Anything committed is safe to publish and its licence allows it; no personal data

## What moved in the gate, and why
