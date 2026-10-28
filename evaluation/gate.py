"""Checks that a change has not made the deobfuscator worse than the recorded baseline.

    python -m evaluation.gate              # pass or fail against evaluation/baseline.json
    python -m evaluation.gate --update     # record the current numbers as the baseline

This is the regression check the project has been running by hand: clean texts changed
may not rise, and no trick may recover fewer samples than before. It runs on the
committed sets only, never the local-only real-world set, so it gives the same answer
on every machine and in continuous integration.

A deliberate trade-off is made by updating the baseline in the same commit as the
change, with the reason in the commit message. The gate's job is to make that a decision
rather than an accident.
"""

import argparse
import json
import os
import sys
from pathlib import Path

from evaluation import metrics, run
from evaluation.tricks import LEVELS

BASELINE = Path(__file__).resolve().parent / "baseline.json"


def measure(split: str, jobs: int) -> dict:
    """The numbers the gate watches, at every level."""
    samples = run.load(split, local=False)
    levels = {}
    for level in LEVELS:
        report = metrics.score(run.run("deobfuscate", level, samples, jobs), level)
        levels[level] = {
            "clean_changed": report.false_change.hits,
            "clean_total": report.false_change.total,
            "recovered": report.recovered.hits,
            "recovered_total": report.recovered.total,
            "made_worse": report.made_worse.hits,
            "idempotent": report.idempotent.hits,
            "idempotent_total": report.idempotent.total,
            "by_trick": {f"{mode} {category}": [item.hits, item.total]
                         for (mode, category), item in sorted(report.recovered_by_category.items())},
        }
    return {"split": split, "samples": len(samples), "levels": levels}


def compare(old: dict, new: dict) -> tuple[list[str], list[str]]:
    """Regressions and improvements, as lines of text."""
    bad: list[str] = []
    good: list[str] = []
    if old["samples"] != new["samples"]:
        bad.append(f"the sets changed size: {old['samples']} samples recorded, {new['samples']} now. "
                   f"Rebuild means a new baseline; check it by hand and pass --update")
        return bad, good
    for level in LEVELS:
        was, now = old["levels"][level], new["levels"][level]
        if now["clean_changed"] > was["clean_changed"]:
            bad.append(f"{level}: clean texts changed rose from {was['clean_changed']} to {now['clean_changed']} "
                       f"of {now['clean_total']}. This is the measure that matters most")
        elif now["clean_changed"] < was["clean_changed"]:
            good.append(f"{level}: clean texts changed fell from {was['clean_changed']} to {now['clean_changed']}")
        if now["recovered"] < was["recovered"]:
            bad.append(f"{level}: recovered fell from {was['recovered']} to {now['recovered']} "
                       f"of {now['recovered_total']}")
        elif now["recovered"] > was["recovered"]:
            good.append(f"{level}: recovered rose from {was['recovered']} to {now['recovered']}")
        if now["made_worse"] > was["made_worse"]:
            bad.append(f"{level}: made worse rose from {was['made_worse']} to {now['made_worse']}")
        if now["idempotent"] < was["idempotent"]:
            bad.append(f"{level}: {was['idempotent'] - now['idempotent']} more texts change again when "
                       f"the tool is run twice over its own output")
        for trick, (hits, total) in now["by_trick"].items():
            before = was["by_trick"].get(trick)
            if before is None:
                good.append(f"{level}: {trick} is new to the sets, {hits}/{total}")
            elif hits < before[0]:
                bad.append(f"{level}: {trick} recovered {hits}/{total}, was {before[0]}/{before[1]}")
            elif hits > before[0]:
                good.append(f"{level}: {trick} recovered {hits}/{total}, was {before[0]}/{before[1]}")
        for trick in was["by_trick"]:
            if trick not in now["by_trick"]:
                bad.append(f"{level}: {trick} has no samples any more; it used to recover "
                           f"{was['by_trick'][trick][0]}/{was['by_trick'][trick][1]}")
    return bad, good


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--split", choices=("dev", "test"), default="dev")
    parser.add_argument("--update", action="store_true", help="record the current numbers as the baseline")
    parser.add_argument("--jobs", type=int, default=0, help="processes to score over (default: one per core)")
    args = parser.parse_args()

    jobs = max(1, args.jobs or (getattr(os, "process_cpu_count", os.cpu_count))() or 1)
    print(f"Scoring the committed {args.split} sets at all three levels over {jobs} processes...")
    new = measure(args.split, jobs)

    if args.update or not BASELINE.exists():
        BASELINE.write_text(json.dumps(new, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"Baseline written to {BASELINE.name}. Say in the commit message why it moved.")
        return

    old = json.loads(BASELINE.read_text(encoding="utf-8"))
    if old["split"] != new["split"]:
        print(f"The baseline is for the {old['split']} split, not {new['split']}.")
        sys.exit(2)
    bad, good = compare(old, new)
    for line in good:
        print(f"  better  {line}")
    for line in bad:
        print(f"  WORSE   {line}")
    if bad:
        print(f"\nFailed: {len(bad)} regression(s). Keep the change only if the owner wants the trade-off, "
              f"and then run --update in the same commit.")
        sys.exit(1)
    if good:
        print(f"\nPassed, with {len(good)} improvement(s). Run --update to record them, "
              f"so that the next change cannot give them back unnoticed.")
    else:
        print("\nPassed; nothing moved.")


if __name__ == "__main__":
    main()
