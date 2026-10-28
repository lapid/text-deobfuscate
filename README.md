# text-deobfuscate

Takes a text and returns the deobfuscated text, plus a record of which transforms were applied
and where.

```python
>>> from text_deobfuscate import deobfuscate
>>> deobfuscate("Pl&#101;ase confirm your acc&#111;unt").text
'Please confirm your account'
>>> deobfuscate("Cl1ck h3r3 to cla1m your pr1ze", strictness="balanced").text
'Click here to claim your prize'
```

**Status: version 0.x, an alpha, not yet released on PyPI.** The library and the command work,
thirty-two transforms are implemented and measured, and the numbers below say how far to trust
them: they are mostly from samples our own generators produced, so read "How well it works"
before relying on it.

## Installing

Not on PyPI yet, so install it from a clone:

```sh
git clone https://github.com/lapid/text-deobfuscate && cd text-deobfuscate
uv sync          # or: pip install .
```

It needs **Python 3.10 or newer** and has **no dependencies**.

## Using it

As a library. `deobfuscate()` returns the text and an ordered list of steps; each step says what
changed, where it sat in the text as it stood before that step, and how confident the engine was:

```python
from text_deobfuscate import deobfuscate

result = deobfuscate("Pl&#101;ase confirm your acc​ount")
result.text                       # 'Please confirm your account'
[step.transform for step in result.steps]        # ['zero-width', 'html-entity']
result.steps[0].start, result.steps[0].end       # 25, 33
```

As a command, with `--json` for the whole record:

```sh
$ text-deobfuscate "UGxlYXNlIHNlbmQgdGhlIHJlcG9ydCBiZWZvcmUgRnJpZGF5"
Please send the report before Friday

$ text-deobfuscate --strictness balanced "c o n f i r m   y o u r   a c c o u n t"
confirm your account

$ text-deobfuscate --json "Thx 4 ur msg"      # text plus steps, as JSON
```

It reads standard input when given no argument, so it pipes. Piped or redirected, it writes the
text and nothing else — no trailing newline is added, so `text-deobfuscate x > file` holds exactly the
text. A terminal gets a line ending, so the prompt does not land mid-sentence.

## Strictness

Three levels, because the tricks differ in how certain they are. `conservative` is the default.

| Level | Adds | Example |
|---|---|---|
| `conservative` | Encodings and escapes, invisible characters, styled and fullwidth letters, ciphers, reversal, Morse — things ordinary English does not contain | `UGxlYXNl…`, `&#101;`, `\141\142`, `ⓒⓞⓝⓕⓘⓡⓜ` |
| `balanced` | Ambiguous visual tricks: lookalike letters, added accents, overlaid marks, leetspeak, inserted separators | `раssword` with Cyrillic letters, `Cl1ck`, `c o n f i r m` |
| `aggressive` | A lower acceptance margin, plus informal writing from short lists: stretched words, texting shorthand, common misspellings, emoji for a word | `sooooo`, `l8r`, `recieve`, `📞 me` |

Below `aggressive`, informal writing comes back exactly as written.

## How it decides

**Changing clean text is treated as the worst mistake the tool can make.** Transforms only
*propose* rewrites; the engine applies one only when the result scores as more plausible English
than what it replaces, judged by a word list and a character four-gram table. Layered
obfuscation is decoded first and judged by what it finally turns into. URLs, paths, hashes and
other things that must not be touched are shielded. Nothing is ever executed — only decoded,
within size and depth limits.

Details in [`docs/architecture.md`](https://github.com/lapid/text-deobfuscate/blob/master/docs/architecture.md) and [`docs/scorer.md`](https://github.com/lapid/text-deobfuscate/blob/master/docs/scorer.md).

## How well it works

**Read this first.** Most samples were made by our own obfuscation generators, so they test the
decoders against the people who wrote them. The independent evidence is smaller: 3,000 real
phishing sentences, 25 sentences disguised by hand, and sets made by someone else's generator
(below). The development sets have been run and tuned against many times, and the test split was
used up in October 2026. Treat every figure as an upper bound for text you have not seen.

Recovery means the text came back exactly, ignoring capital letters; clean texts changed is
measured strictly. The tool is judged first on **not changing clean text**.

**Development sets, thirty-two transforms (2026-10-27):** 7,806 clean texts, about 9,500
obfuscated ones, and the 3,000 real phishing sentences (kept outside the repository).

| Level | Clean texts changed | Recovered | Made worse | Real phishing | Hand-disguised |
|---|---|---|---|---|---|
| `conservative` | 0.01% (1 of 7,806) | 89.4% (5,277 of 5,905) | 1.2% | — | — |
| `balanced` | 0.01% (1 of 7,806) | 88.2% (10,296 of 11,680) | 0.6% | 90.8% | 15 of 25 |
| `aggressive` | 0.31% (24 of 7,806) | 86.8% (10,868 of 12,520) | 0.7% | 94.4% | 17 of 25 |

Each level is scored on the samples it is meant to undo, so the denominators differ and the rows
are not comparable with each other. Adding transforms or harder samples lowers a total without
anything getting worse; judge a trick by its own row in
[`docs/evaluation.md`](https://github.com/lapid/text-deobfuscate/blob/master/docs/evaluation.md).

**Sets made by someone else's generator, scored at `balanced`.** The first is 6,000 rows kept
outside the repository; we tuned against it, so it is optimistic. The second is 3,000 fresh rows
from unused text of the same source and generator: new rows, but the same style of obfuscation.
Neither tests a different author's habits.

| Trick | Tuned set | Fresh rows |
|---|---|---|
| base64, ROT13, zero-width, spacing | 99–100% | 100% |
| fullwidth, reversal | 96–99% | 98.5–99.6% |
| homoglyph | 96.5% | 97.8% |
| a symbol between every character | 99.8% | 99.3% |
| leetspeak | 59.7% | 57.5% |
| alternating capitals | 0% (99.8% ignoring capitals) | 0% (100%) |
| dropped vowels | 0% | 0% |
| **all rows** | **77.3%** | **77.5%** |

Alternating capitals come back in lower case: the tool does not restore capitals. Dropped
vowels are informal writing, out of scope by design.

**Where it does worst** (development sets, `balanced`): a disguised sentence inside plain text is
the weakest case. Reverse in context recovers 2.5%, ROT47 15%, per-word reversal 17.5%, Atbash
45%, Caesar 58%, ROT13 70%. Leetspeak with every letter replaced recovers 66% of whole texts;
accent substitution 62–71%. Encodings that fill a whole text (base64, hex, base32, escapes) are
above 90%.

**Time:** the median text takes about 2 ms and the 95th percentile about 15 ms. The slowest
inputs are long and hostile: 100,000 random printable characters take about 14 seconds, and
everything else tested at that size takes under 5. One call scans at most four million characters.

**The test split** was run once, on 2026-10-12, for twenty-three transforms. It showed clean
texts changed at 3, 13 and 38 of 7,442 for the three levels. Reading the 13 at `balanced` on
2026-10-27 led to fixes for leetspeak on names and numbers (`P-51's`, `S4C`, `tty1`), and 5
remain, so the split no longer measures anything independently.

## Known limits

Honest list; each is measured and logged.

- **Clean texts changed was higher on test than on dev** (13 against 1 at `balanced`). Reading the
  13 showed leetspeak applied to names and numbers; that is fixed, and 5 remain, which are
  arguably correct changes. The unseen text of a real user may still be changed in ways our
  samples do not show: report it.
- **Hand-disguised sentences did not carry over** from dev (15 of 25) to test (5 of 22). Human
  disguises vary more than generated ones.
- **Most of the evidence comes from generators we wrote or tuned against.** See the top of
  "How well it works".
- **Leetspeak** is about 58% exact on someone else's generator. Lone `1` and `4` in lightly
  disguised text need a second disguised word nearby, and the wider table (`8`, `9`, `2`) is weak.
- **Time and size:** inputs over 100,000 characters are returned unchanged; 100,000 random
  printable characters take about 14 seconds.
- **A text reversed word by word cannot be told from a wholly reversed one** unless a full stop
  settles it, so 51 of 210 such samples come back with the words in the wrong order. 44 of those
  are still perfectly legible; this is a limit of the ambiguity, not a bug to fix.
- **A lone disguised word** with everyday accents, or a lone Greek "a", is left alone at
  `balanced`: one word is not enough evidence.
- **A capital hidden behind a leetspeak digit is lost** (`Cl1ck` → `click`). Recovery is measured
  ignoring capitals for this reason.
- **Shifted or reversed words inside otherwise clean text** recover poorly.
- **A short text in another language whose words all read as English backwards** is reversed
  ("No pasa nada").
- **No recogniser yet for key-like tokens or code**, so a ticket code in base32 may be decoded.
- **English only.** Other languages and scripts pass through unchanged, by design.
- **Deferred to version 2:** bidirectional controls, variation-selector payloads, Punycode, part
  of Unicode's invisible characters, and some styled ranges. Samples for them exist and are
  excluded from a normal run.
- **Wrong-encoding damage** (`Ã©` for `é`) is out of scope and comes back unchanged.
- Code obfuscation is out of scope.

## Testing and the regression gate

```sh
uv run python -m unittest discover -s tests   # 122 unit tests
uv run python -m evaluation.gate              # the regression gate: pass or fail
uv run python -m evaluation.run --detail      # the full report, per category and per trick
```

The gate scores the committed sets at all three levels and fails if clean texts changed rises, if
any trick recovers fewer samples than before, or if the output stops settling when the tool is run
over its own output. A deliberate trade-off is made by passing `--update` in the same commit and
giving the reason in the commit message. More in
[`docs/evaluation.md`](https://github.com/lapid/text-deobfuscate/blob/master/docs/evaluation.md).

## Documentation

- [`docs/taxonomy.md`](https://github.com/lapid/text-deobfuscate/blob/master/docs/taxonomy.md): every trick, its level, its main guard, and what is out of scope.
- [`docs/architecture.md`](https://github.com/lapid/text-deobfuscate/blob/master/docs/architecture.md): how it works inside, and how to add a transform.
- [`docs/scorer.md`](https://github.com/lapid/text-deobfuscate/blob/master/docs/scorer.md): the plausibility scorer and the experiment behind it.
- [`docs/evaluation.md`](https://github.com/lapid/text-deobfuscate/blob/master/docs/evaluation.md): the sets, the measures, and every baseline number.

Contributions go through a pull request: the tests and the gate must pass, and a new transform
comes with samples. The false-change rate on the clean set may not rise.

## Licence

MIT for our own code and data; see [`LICENSE`](https://github.com/lapid/text-deobfuscate/blob/master/LICENSE). Third-party data keeps its own licence,
with its source and terms recorded beside it in [`data/`](https://github.com/lapid/text-deobfuscate/tree/master/data/) and
[`src/text_deobfuscate/data/NOTICE.md`](https://github.com/lapid/text-deobfuscate/blob/master/src/text_deobfuscate/data/NOTICE.md).
