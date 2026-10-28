"""Turns the hand-disguised sentences into evaluation samples.

Run ``python -m evaluation.human``. It reads ``data/human/to_disguise.txt`` (kept in the maintainer's private repository) and
writes ``data/eval/human_<split>.jsonl``. Sentences are assigned to dev or test
by their number, so the test half can stay unread by whoever writes the rules.
"""

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHEET = ROOT / "data" / "human" / "to_disguise.txt"
EVAL = ROOT / "data" / "eval"
SPLITS = ("dev", "test")

# Answers typed under the wrong sentence, found by reading the dev half:
# answer number -> number of the sentence it actually disguises.
MISPLACED = {12: 11, 21: 20}


def pairs() -> list[tuple[int, str, str]]:
    """(number, clean sentence, disguised sentence) for every answered line."""
    out = []
    number, clean = None, None
    for line in SHEET.read_text(encoding="utf-8").splitlines():
        if match := re.match(r"(\d+): (.*)", line):
            number, clean = int(match.group(1)), match.group(2)
        elif line.startswith(">") and number is not None:
            # Leading and trailing spaces are not treated as part of the disguise.
            disguised = line[1:].strip()
            if disguised and disguised != clean:
                out.append((number, clean, disguised))
            number = None
    return out


def main() -> None:
    rows: dict[str, list[dict]] = {split: [] for split in SPLITS}
    found_pairs = pairs()
    clean_by_number = dict(re.findall(r"^(\d+): (.*)$", SHEET.read_text(encoding="utf-8"), flags=re.M))
    for number, clean, disguised in found_pairs:
        if number in MISPLACED:
            clean = clean_by_number[str(MISPLACED[number])]
        split = SPLITS[hashlib.sha256(f"human-{number}".encode()).digest()[0] % 2]
        rows[split].append({
            "id": f"human-{number:03d}", "text": disguised, "expected": clean, "tricks": ["unknown"],
            "level": "balanced", "mode": "real", "category": "human-written", "origin": "human",
            "source": "written for this project", "url": "", "licence": "MIT", "split": split,
        })
    for split, found in rows.items():
        with (EVAL / f"human_{split}.jsonl").open("w", encoding="utf-8") as handle:
            for row in found:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"{split}: {len(found)} hand-disguised sentences")


if __name__ == "__main__":
    main()
