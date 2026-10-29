"""Builds the evaluation sets from the clean corpus.

Run ``python -m evaluation.build``. Output, per split, in ``data/eval/<split>/``:

- ``clean.jsonl``: text that must come back unchanged.
- ``obfuscated.jsonl``: obfuscated text with the clean original as ``expected``,
  plus the real messages from ``real_<split>.jsonl``.

Everything is derived from a fixed seed, so rebuilding gives identical files.
"""

import json
from pathlib import Path
from random import Random

from evaluation import leet_context, more_samples, negatives, obfuscator, other_languages
from evaluation.tricks import DEFERRED, NORMALISING, SURVEY, TRICK_LEVEL

ROOT = Path(__file__).resolve().parent.parent
EVAL = ROOT / "data" / "eval"
SPLITS = ("dev", "test")
SEED = 20261008

WHOLE_PER_TRICK = 150
PARTIAL_PER_TRICK = 60
PER_STACK = 50

# Encodings that grow the text several times over are made from shorter sources.
BULKY = {"binary", "decimal-codes", "html-entity", "backslash-escape"}


def write(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


CREDIT = ("origin", "source", "url", "licence")
OURS = {"origin": "generated", "source": "generated", "url": "", "licence": "MIT"}


def read(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle]


def clean_rows(split: str, corpus: list[dict], rng: Random) -> list[dict]:
    rows = [{"category": "prose", **row} for row in corpus]
    rows += [{"category": category, "text": text, **OURS} for category, text in negatives.generate(rng)]
    # Added with the coverage survey, from a stream of their own so earlier rows are unchanged.
    later = Random(f"{SEED}-{split}-survey-clean")
    rows += [{"category": category, "text": text, **OURS} for category, text in negatives.generate(later, negatives.LATER_CATEGORIES)]
    # Digit look-alikes of function words, from their own stream for the same reason.
    context = Random(f"{SEED}-{split}-leet-context-clean")
    rows += [{"category": category, "text": text, **OURS} for category, text in negatives.generate(context, leet_context.CATEGORIES)]
    # Words that look encoded, for the decoders that did worst.
    words = Random(f"{SEED}-{split}-more-clean")
    rows += [{"category": category, "text": text, **OURS} for category, text in negatives.generate(words, more_samples.CATEGORIES)]
    # Short phrases in other languages and English with accents, again from a stream of their own.
    languages = Random(f"{SEED}-{split}-other-languages-clean")
    rows += [{"category": category, "text": text, **OURS} for category, text in negatives.generate(languages, other_languages.categories(split))]
    return [
        {"id": f"{split}-clean-{n:05d}", "text": row["text"], "expected": row["text"], "tricks": [], "mode": "clean",
         "category": row["category"], **{key: row[key] for key in CREDIT}, "split": split}
        for n, row in enumerate(rows, 1)
    ]


def obfuscated_rows(split: str, corpus: list[dict], real: list[dict], rng: Random) -> list[dict]:
    rows: list[dict] = []

    def add(text: str, expected: str, tricks: list[str], mode: str, credit: dict, **extra: str) -> None:
        if text == expected:
            return
        rows.append({"id": f"{split}-obf-{len(rows) + 1:05d}", "text": text, "expected": expected, "tricks": tricks,
                     "mode": mode, "category": "+".join(tricks), **{key: credit[key] for key in CREDIT},
                     "split": split, **extra})

    def sources(count: int, *, short: bool = False) -> list[dict]:
        pool = [row for row in corpus if len(row["text"]) <= 120] if short else corpus
        return rng.sample(pool, k=count)

    def single(trick: str, rng: Random) -> None:
        for row in rng.sample(corpus, k=WHOLE_PER_TRICK * 6):
            if sum(sample["category"] == trick and sample["mode"] == "whole" for sample in rows[-WHOLE_PER_TRICK:]) == WHOLE_PER_TRICK:
                break
            add(obfuscator.apply(trick, row["text"], rng), row["text"], [trick], "whole", row)
        made = 0
        for row in rng.sample(corpus, k=PARTIAL_PER_TRICK * 6):
            if made == PARTIAL_PER_TRICK:
                break
            text = obfuscator.apply_partial(trick, row["text"], rng)
            if text is not None:
                add(text, row["text"], [trick], "partial", row)
                made += 1

    for trick in TRICK_LEVEL:
        if trick in NORMALISING or trick in SURVEY:
            continue
        if trick == "tag-characters":
            for row in sources(WHOLE_PER_TRICK):
                text, hidden = obfuscator.tag_characters(row["text"], rng)
                add(text, row["text"], [trick], "whole", row, hidden=hidden)
            continue
        for row in sources(WHOLE_PER_TRICK, short=trick in BULKY):
            add(obfuscator.apply(trick, row["text"], rng), row["text"], [trick], "whole", row)
        made = 0
        for row in sources(PARTIAL_PER_TRICK * 6):
            if made == PARTIAL_PER_TRICK:
                break
            text = obfuscator.apply_partial(trick, row["text"], rng)
            if text is not None:
                add(text, row["text"], [trick], "partial", row)
                made += 1

    for stack in obfuscator.STACKS:
        for row in sources(PER_STACK, short=True):
            add(obfuscator.apply_stack(stack, row["text"], rng), row["text"], list(stack), "stacked", row)

    # Real messages, not produced by our obfuscator.
    for row in real:
        add(row["text"], row["expected"], row["tricks"], "real", row)

    # Added after the sets were first built. They come last and draw from their own
    # random stream, so every earlier row is unchanged.
    later = Random(f"{SEED}-{split}-normalising")
    for trick in sorted(NORMALISING):
        single(trick, later)

    # Added from the coverage survey, after everything above; one stream per trick,
    # so adding another later leaves these unchanged.
    for trick in SURVEY:
        stream = Random(f"{SEED}-{split}-survey-{trick}")
        if trick == "variation-selector":
            for row in stream.sample(corpus, k=WHOLE_PER_TRICK):
                text, hidden = obfuscator.variation_selector(row["text"], stream)
                add(text, row["text"], [trick], "whole", row, hidden=hidden)
            continue
        single(trick, stream)

    # Leetspeak function words, whole and inside clean text, and numbers kept beside them.
    context = Random(f"{SEED}-{split}-leet-context")
    for category, mode, text, expected, row in leet_context.positives(corpus, context):
        add(text, expected, ["leetspeak"], mode, row or OURS, category=category)

    # More of what did worst: encodings with text around them, accents on vowels, deeper stacks.
    more = Random(f"{SEED}-{split}-more")
    for make in (more_samples.carried, more_samples.accented, more_samples.deep_stacks, more_samples.joined):
        for category, mode, text, expected, tricks, row in make(corpus, more):
            add(text, expected, tricks.split("|"), mode, row, category=category)

    # Full leetspeak, the plain 1337 style (added after the outside set showed it dominates).
    for category, mode, text, expected, row in leet_context.full_positives(corpus, Random(f"{SEED}-{split}-leet-full")):
        add(text, expected, ["leetspeak"], mode, row or OURS, category=category)
    return rows


def main() -> None:
    for split in SPLITS:
        corpus = read(EVAL / f"corpus_{split}.jsonl")
        rng = Random(f"{SEED}-{split}")
        clean = clean_rows(split, corpus, rng)
        rows = obfuscated_rows(split, corpus, read(EVAL / f"real_{split}.jsonl"), rng)
        # Samples of tricks version 1 does not undo go to their own file. They can only
        # be scored as out of scope, and undecodable text is the slowest case for the
        # engine, so running them costs about a third of the time for no reading.
        # ``evaluation.run --deferred`` puts them back.
        deferred = [row for row in rows if any(trick in DEFERRED for trick in row["tricks"])]
        obfuscated = [row for row in rows if row not in deferred]
        write(EVAL / split / "clean.jsonl", clean)
        write(EVAL / split / "obfuscated.jsonl", obfuscated)
        write(EVAL / split / "deferred.jsonl", deferred)
        print(f"{split}: {len(clean)} clean, {len(obfuscated)} obfuscated, {len(deferred)} deferred")


if __name__ == "__main__":
    main()
