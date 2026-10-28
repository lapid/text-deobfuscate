"""Score a set of obfuscated texts that lives outside the repository, and print aggregates only.

    uv run python -m evaluation.external /path/to/set.tsv

The file is tab-separated with the columns ``original_text``, ``type_of_obfuscation`` and
``obfuscated_text``. It is read in place and never copied; no text is printed. Use it for sets
the project must not keep, such as the owner's outside and unseen sets. Recovery is measured
exactly and ignoring capitals; "changed" is the share of texts the tool altered.
"""

import argparse
import csv
from collections import defaultdict
from multiprocessing import Pool
from pathlib import Path

from text_deobfuscate import deobfuscate

LEVELS = ("conservative", "balanced", "aggressive")


def work(args: tuple[str, str, str]) -> tuple[bool, bool, bool]:
    obfuscated, original, level = args
    out = deobfuscate(obfuscated, strictness=level).text
    return out == original, out.casefold() == original.casefold(), out != obfuscated


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("path", type=Path)
    parser.add_argument("--level", choices=LEVELS, help="one level only")
    args = parser.parse_args()
    csv.field_size_limit(10**9)
    with args.path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t", quoting=csv.QUOTE_NONE))
    print(len(rows), "rows")
    for level in [args.level] if args.level else LEVELS:
        with Pool() as pool:
            results = pool.map(work, [(r["obfuscated_text"], r["original_text"], level) for r in rows], chunksize=20)
        table: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0, 0])
        for row, (exact, folded, changed) in zip(rows, results):
            cell = table[row["type_of_obfuscation"]]
            cell[0] += 1
            cell[1] += exact
            cell[2] += folded
            cell[3] += changed
        print(f"\n== {level}: type  n  exact%  ignoring-case%  changed%")
        total = [0, 0, 0, 0]
        for kind, cell in sorted(table.items()):
            print(f"{kind:28s}{cell[0]:5d} {100 * cell[1] / cell[0]:6.1f} {100 * cell[2] / cell[0]:6.1f} {100 * cell[3] / cell[0]:6.1f}")
            total = [a + b for a, b in zip(total, cell)]
        print(f"{'ALL':28s}{total[0]:5d} {100 * total[1] / total[0]:6.1f} {100 * total[2] / total[0]:6.1f} {100 * total[3] / total[0]:6.1f}")


if __name__ == "__main__":
    main()
