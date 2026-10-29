# Evaluation sets

Built by `evaluation/corpus.py` and `evaluation/build.py`; do not edit by hand. Described in
`docs/evaluation.md`.

**Do not read the `test` files to get ideas for rules.**

**Content note:** the sets hold real messages, so some contain profanity, crude or hateful talk and
scam text. They are kept on purpose, because phishing and injected instructions use such
language and the tool must be tested on it (`CODE_OF_CONDUCT.md`). Private details are masked.

## Files

- `corpus_<split>.jsonl`: 7,000 clean texts per split, with origin, credit, address and licence.
- `real_<split>.jsonl`: real text messages containing HTML entities, with the decoded text as
  the expected output (136 dev, 133 test).
- `<split>/clean.jsonl`: the corpus plus generated hard negatives. Must come back unchanged.
- `<split>/obfuscated.jsonl`: corpus texts obfuscated by our generator, plus the real messages.
- `<split>/deferred.jsonl`: the same, for the tricks version 1 does not undo (1,410 rows). Left
  out of a normal run: they can only score as out of scope, and undecodable text is the engine's
  slowest case, so they cost about a third of the run time for no reading.
  `python -m evaluation.run --deferred` includes them.

## Sources and licences

These files are **not** under the project's MIT licence. Every row carries its own `source`,
`url` and `licence` fields, and those govern that row.

| Origin | Texts per split | Licence | Credit |
|---|---|---|---|
| `wikipedia` | 2,000 | CC BY-SA 4.0 | The Wikipedia article at the row's `url`, and its authors |
| `wikinews` | 1,000 | CC BY 2.5; CC BY 4.0 for articles after 2024; public domain before 2005 | Wikinews, article at the row's `url` |
| `stack-exchange` | 1,500 | CC BY-SA 4.0, 3.0 or 2.5, as reported per post by the Stack Exchange API | The question at the row's `url`, by the author named in `source` |
| `sms` | 1,500, plus the real messages | CC BY 4.0 | Almeida, T. and Hidalgo, J. (2011). SMS Spam Collection. UCI Machine Learning Repository. https://doi.org/10.24432/C5CC84 |
| `books` | 1,000 | Public domain in the United States | Project Gutenberg editions of ten books published before 1929 |
| `generated` | 442 | MIT | This project |

Licence texts: https://creativecommons.org/licenses/by-sa/4.0/ ,
https://creativecommons.org/licenses/by-sa/3.0/ , https://creativecommons.org/licenses/by-sa/2.5/ ,
https://creativecommons.org/licenses/by/4.0/ , https://creativecommons.org/licenses/by/2.5/

## Changes made to the source text

- Documents were split into sentences and short runs of sentences; whitespace was collapsed.
  Wikipedia and Wikinews texts come from article introductions. Stack Exchange texts come from
  question bodies with markup removed and code blocks dropped. Only personal messages ("ham")
  were taken from the SMS collection.
- In `obfuscated.jsonl`, the `text` field is the source text altered by our obfuscator; the
  unaltered text is in `expected`. These altered rows are adaptations and stay under the licence
  of their source row (share-alike where that licence requires it).
- Wikipedia, Wikinews and Stack Exchange were sampled on 2026-10-08.
