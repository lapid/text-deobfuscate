# The plausibility scorer

`scorer.english_score(text)` returns 0 for text with no sign of English and 1 for text that
reads as English. The engine accepts a proposal only when this score rises enough.

## Signals

- **Word coverage:** the share of letters that sit inside known English words. The word list is
  SCOWL up to size 60 (91,796 entries, possessives handled separately).
- **Letter-sequence fit:** the mean log probability of each four-letter window, over lowercase
  letters and spaces, against counts from twenty public-domain books (33,812 four-letter
  sequences kept, from 16 million counted). None of those books is in the evaluation corpus.

The score is the mean of the two, with the fit rescaled so that typical wrong decodes map to 0
and typical English to 1.

## Experiment: which signal? (2026-10-08, dev split)

2,500 clean dev texts against five kinds of wrong text made from them: rot13, reversed, a
random Caesar shift, the base64 string itself, and random bytes read as text. The number is the
chance that a clean text outscores a wrong one (1.000 is perfect separation, 0.5 is a coin toss).

| Text length | Word coverage | Sequence fit | Both |
|---|---|---|---|
| Under 20 characters | 0.929 to 0.956 | 0.946 to 0.962 | 0.951 to 0.962 |
| 20 to 59 | 0.992 to 0.999 | 0.997 to 1.000 | 0.998 to 1.000 |
| 60 and over | 1.000 | 1.000 | 1.000 |

Ranges are across the five kinds of wrong text.

- From 20 characters up, either signal separates almost perfectly.
- Under 20 characters neither is reliable. This is why the policy requires a minimum number of
  letters before a proposal is judged at all.
- The sequence fit is slightly ahead, and the combination is never worse, so both are used.
- Clean text is not uniform. Median word coverage is 1.00 for books, news and Stack Exchange,
  but 0.92 to 0.93 for Wikipedia and text messages, where names and shorthand are common. A
  threshold that demands near-perfect coverage would reject real English.

## What this experiment does not show

It covers wrong decodes of whole texts, which are the easy case. It says nothing yet about
single-word decisions such as leetspeak or lookalike letters, where there is one word of
evidence. Those depend mainly on `is_word`, and will be measured when those transforms exist.
