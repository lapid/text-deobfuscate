"""Turns the hand-disguised sentences into evaluation samples.

Run ``python -m evaluation.human SHEET`` with the path of the sheet of sentences and their
disguised versions. It writes ``data/eval/human_<split>.jsonl``. Sentences are assigned to dev or test
by their number, so the test half can stay unread by whoever writes the rules.

Pass ``--project-sheet`` for the project's own sheet, whose two misplaced answers are corrected
(see ``MISPLACED``). Without it, every answer is taken as typed.
"""

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVAL = ROOT / "data" / "eval"
SPLITS = ("dev", "test")

# Answers typed under the wrong sentence in the project's own sheet, found by reading the dev half:
# answer number -> number of the sentence it actually disguises.
MISPLACED = {12: 11, 21: 20}


def pairs(sheet: Path) -> list[tuple[int, str, str]]:
    """(number, clean sentence, disguised sentence) for every answered line."""
    out = []
    number, clean = None, None
    for line in sheet.read_text(encoding="utf-8").splitlines():
        if match := re.match(r"(\d+): (.*)", line):
            number, clean = int(match.group(1)), match.group(2)
        elif line.startswith(">") and number is not None:
            # Leading and trailing spaces are not treated as part of the disguise.
            disguised = line[1:].strip()
            if disguised and disguised != clean:
                out.append((number, clean, disguised))
            number = None
    return out


def main(sheet: Path, project_sheet: bool = False) -> None:
    rows: dict[str, list[dict]] = {split: [] for split in SPLITS}
    clean_by_number = {
        int(number): clean
        for number, clean in re.findall(r"^(\d+): (.*)$", sheet.read_text(encoding="utf-8"), flags=re.MULTILINE)
    }
    for number, clean, disguised in pairs(sheet):
        if project_sheet and number in MISPLACED:
            clean = clean_by_number[MISPLACED[number]]
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
    arguments = [argument for argument in sys.argv[1:] if argument != "--project-sheet"]
    if len(arguments) != 1:
        sys.exit(__doc__)
    main(Path(arguments[0]), project_sheet="--project-sheet" in sys.argv)
