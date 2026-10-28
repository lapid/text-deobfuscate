# Samples

One JSON object per line:
`{"id", "text", "expected", "tricks", "source", "split", "notes"}`

- `expected` is the correct output. For a clean negative it equals `text`. It is `null` when the
  right answer is undecided.
- `tricks` lists the obfuscations in the order they must be undone, outermost first. Empty for
  clean text.
- `split` is `dev` or `test`. Never read `test` samples to get ideas for rules.

| File | Count | What | Licence |
|---|---|---|---|
| `obfuscated_self_written.jsonl` | 36 | One or more examples of each trick in scope, plus stacked and partial cases | MIT |
| `clean_negatives_self_written.jsonl` | 35 | Text that must come back unchanged | MIT |
| `sms_spam_collection.jsonl` | 10 | Real messages: shorthand negatives and real HTML entities | CC BY 4.0, see below |

These are seed samples for building and debugging. They are too few to measure anything, and
all are `dev` because the agent wrote or read every one. The measured sets come from the
generator and from sources sampled by script without being read (Phase 1).

`sms_spam_collection.jsonl` is taken from: Almeida, T. and Hidalgo, J. (2011). SMS Spam
Collection [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5CC84.
Licensed under CC BY 4.0. Texts are unmodified; the labels and notes are ours.
