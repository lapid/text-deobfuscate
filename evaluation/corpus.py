"""Builds the clean text corpus from the downloaded sources.

Run ``python -m evaluation.corpus``. It writes, per split, in ``data/eval/``:

- ``corpus_<split>.jsonl``: clean texts with their origin, credit and licence.
- ``real_<split>.jsonl``: real messages that contain HTML entities, with the
  decoded text as the expected output.

Dev and test never share a document: books are assigned by title, everything
else by a hash of its address or text.
"""

import hashlib
import html
import json
import re
from pathlib import Path
from random import Random

from evaluation import sources
from evaluation.text import split_sentences

EVAL = Path(__file__).resolve().parent.parent / "data" / "eval"
SPLITS = ("dev", "test")
SEED = 20261008

# origin -> (texts per split, most texts taken from one document)
QUOTAS = {"books": (1000, 200), "wikipedia": (2000, 4), "wikinews": (1000, 5), "stack-exchange": (1500, 3), "sms": (1500, 1)}

# Characters whose presence makes "this text is clean" doubtful: invisible
# characters outside emoji and non-Latin shaping, and control characters.
DOUBTFUL = re.compile("[​⁠﻿­\U000e0000-\U000e007f\x00-\x08\x0b-\x1f\x7f-\x9f]")


def split_of(key: str) -> str:
    return SPLITS[hashlib.sha256(key.encode()).digest()[0] % 2]


def units(doc: dict, rng: Random) -> list[str]:
    """Single sentences, plus some runs of two or three, for a spread of lengths."""
    out: list[str] = []
    for para in doc["paragraphs"]:
        found = [s for s in split_sentences(para) if 8 <= len(s) <= 300 and len(s.split()) >= 2]
        out.extend(found)
        for size in (2, 3):
            if len(found) >= size and rng.random() < 0.3:
                start = rng.randint(0, len(found) - size)
                out.append(" ".join(found[start : start + size]))
    return sorted(set(out))


def documents(split: str) -> dict[str, list[dict]]:
    by_url = {
        "wikipedia": sources.fetch_wikipedia(),
        "wikinews": sources.fetch_wikinews(),
        "stack-exchange": sources.fetch_stack_exchange(),
    }
    docs = {origin: [doc for doc in found if split_of(doc["url"]) == split] for origin, found in by_url.items()}
    docs["books"] = sources.fetch_books(split)
    return docs


def sms_messages(split: str) -> list[dict]:
    """One entry per distinct message. Chain messages differ only in spacing or case."""
    seen: dict[str, dict] = {}
    for doc in sources.fetch_sms():
        key = re.sub(r"[^a-z0-9]", "", doc["text"].lower())
        if key and key not in seen:
            seen[key] = doc
    return [doc for key, doc in sorted(seen.items()) if split_of(key) == split]


def build(split: str, taken: set[str]) -> tuple[list[dict], list[dict], dict[str, int]]:
    """``taken`` holds texts already used by another split; they are not used again."""
    rng = Random(f"{SEED}-{split}")
    corpus: list[dict] = []
    dropped: dict[str, int] = {}

    def keep(origin: str, texts: list[str], doc: dict) -> list[dict]:
        clean = [text for text in texts if not DOUBTFUL.search(text) and text not in taken]
        dropped[origin] = dropped.get(origin, 0) + len(texts) - len(clean)
        return [{"text": text, "origin": origin, "source": doc["source"], "url": doc["url"], "licence": doc["licence"]}
                for text in clean]

    for origin, docs in documents(split).items():
        quota, per_doc = QUOTAS[origin]
        pool: list[dict] = []
        for doc in docs:
            found = keep(origin, units(doc, rng), doc)
            pool.extend(rng.sample(found, k=min(len(found), per_doc)))
        corpus.extend(rng.sample(pool, k=min(len(pool), quota)))

    real: list[dict] = []
    messages: list[dict] = []
    for doc in sms_messages(split):
        decoded = html.unescape(doc["text"])
        if decoded != doc["text"]:
            real.append({"text": doc["text"], "expected": decoded, "tricks": ["html-entity"], "origin": "sms",
                         "source": doc["source"], "url": doc["url"], "licence": doc["licence"]})
        else:
            messages.extend(keep("sms", [doc["text"]], doc))
    corpus.extend(rng.sample(messages, k=min(len(messages), QUOTAS["sms"][0])))

    rng.shuffle(corpus)
    # Masked last, so the choice of rows stays what it was.
    for row in (*corpus, *real):
        if row["origin"] == "sms":
            for field in ("text", "expected"):
                if field in row:
                    row[field] = sources.mask_private(row[field])
    return corpus, real, dropped


def write(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> None:
    EVAL.mkdir(parents=True, exist_ok=True)
    taken: set[str] = set()
    for split in SPLITS:
        corpus, real, dropped = build(split, taken)
        taken.update(row["text"] for row in corpus)
        write(EVAL / f"corpus_{split}.jsonl", corpus)
        write(EVAL / f"real_{split}.jsonl", real)
        counts = {origin: sum(row["origin"] == origin for row in corpus) for origin in QUOTAS}
        print(f"{split}: {len(corpus)} clean texts {counts}; {len(real)} real entity messages; dropped as doubtful or repeated {dropped}")


if __name__ == "__main__":
    main()
