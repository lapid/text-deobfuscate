"""Builds evaluation sets that may be used locally but not committed.

Run ``python -m evaluation.local_sets``. Output goes to ``data/local/``, which
git ignores. ``evaluation.run`` picks these sets up when they are present.

BitCore: real sentences from phishing emails, disguised by their senders, with
the restored text supplied by the dataset's authors. No licence is stated for
it, so only the download script lives in this repository.
"""

import hashlib
import json
from pathlib import Path

from evaluation import sources

LOCAL = Path(__file__).resolve().parent.parent / "data" / "local"
SPLITS = ("dev", "test")
PER_SPLIT = 3000

# The first rows of the dataset were looked at while writing this module, so
# they may only ever be development data.
SEEN_ROWS = 100


def build() -> dict[str, list[dict]]:
    rows = sources.fetch_bitcore()
    seen_labels = {row["label"] for row in rows[:SEEN_ROWS]}
    out: dict[str, list[dict]] = {split: [] for split in SPLITS}
    taken: set[str] = set()
    # Ordered by a hash so the sample taken from each split is arbitrary but repeatable.
    for row in sorted(rows, key=lambda row: hashlib.sha256(row["id"].encode()).hexdigest()):
        text, label = row["text"], row["label"]
        if not text.strip() or text in taken:
            continue
        taken.add(text)
        # The same sentence was sent many times with different disguises. Splitting
        # on the restored text keeps every version of a sentence in one split.
        split = "dev" if label in seen_labels else SPLITS[hashlib.sha256(label.encode()).digest()[0] % 2]
        disguised = text.casefold() != label.casefold()
        out[split].append({
            "id": f"bitcore-{row['id']}", "text": text, "expected": label if disguised else text,
            "tricks": ["unknown"] if disguised else [], "level": "balanced",
            "mode": "real" if disguised else "clean", "category": "real-visual" if disguised else "prose",
            "origin": "bitcore", "caseless": True, "source": "BitCore (Lee et al., 2025)",
            "url": "https://huggingface.co/datasets/AutoML/bitcore", "licence": "none stated", "split": split,
        })
    return {split: found[:PER_SPLIT] for split, found in out.items()}


def main() -> None:
    LOCAL.mkdir(parents=True, exist_ok=True)
    for split, rows in build().items():
        with (LOCAL / f"bitcore_{split}.jsonl").open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        disguised = sum(row["mode"] == "real" for row in rows)
        print(f"{split}: {disguised} disguised and {len(rows) - disguised} undisguised BitCore sentences")


if __name__ == "__main__":
    main()
