"""Runs a system over an evaluation split and prints the scores.

    python -m evaluation.run                      # the deobfuscator, all levels, dev split
    python -m evaluation.run --system identity    # a baseline
    python -m evaluation.run --detail             # add the per-category tables
    python -m evaluation.run --jobs 1             # one process, for honest timings

The test split is for reporting only: do not tune against it.
"""

import argparse
import json
import os
import statistics
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from evaluation import metrics, systems
from evaluation.tricks import LEVELS, NORMALISING

ROOT = Path(__file__).resolve().parent.parent
EVAL = ROOT / "data" / "eval"
LOCAL = ROOT / "data" / "local"


def load(split: str, deferred: bool = False, local: bool = True) -> list[dict]:
    """The committed sets, plus any local-only sets that have been built.

    ``deferred`` adds the samples of tricks version 1 does not undo; they are left
    out by default because they can only score as out of scope and are slow to run.
    ``local`` can be turned off to get only what is committed, which is the same
    everywhere; the local-only sets are built per machine and are not in the repository.
    """
    paths = [EVAL / split / "clean.jsonl", EVAL / split / "obfuscated.jsonl"]
    if local:
        paths += sorted(LOCAL.glob(f"*_{split}.jsonl"))
    if deferred:
        paths.append(EVAL / split / "deferred.jsonl")
    if (EVAL / f"human_{split}.jsonl").exists():
        paths.append(EVAL / f"human_{split}.jsonl")
    rows: list[dict] = []
    for path in paths:
        with path.open(encoding="utf-8") as handle:
            rows.extend(json.loads(line) for line in handle)
    return rows


def build(name: str, level: str) -> systems.System:
    return systems.ours(level) if name == "deobfuscate" else getattr(systems, name)


def one(system: systems.System, sample: dict) -> metrics.Outcome:
    started = time.perf_counter()
    output, transforms = system(sample["text"])
    seconds = time.perf_counter() - started
    rewritten = None
    if sample["tricks"] and output != sample["expected"]:
        again, used = system(sample["expected"])
        if again != sample["expected"] and set(used) <= NORMALISING:
            rewritten = again
    return metrics.Outcome(sample, output, transforms, system(output)[0], seconds, rewritten)


# A system is a closure and cannot be pickled, so each worker builds its own, once.
# The scorer's caches are per process and warm up separately in each.
_system: systems.System | None = None


def _start_worker(name: str, level: str) -> None:
    global _system
    _system = build(name, level)


def _one_in_worker(sample: dict) -> metrics.Outcome:
    assert _system is not None  # nosec B101
    return one(_system, sample)


def run(name: str, level: str, samples: list[dict], jobs: int = 1) -> list[metrics.Outcome]:
    """Scores every sample, over ``jobs`` processes. Texts are independent of each other.

    The outcomes come back in the order of ``samples`` whatever the number of processes,
    so every count and rate is identical. The per-text times are not: workers share the
    machine, so the slowest text reads slower under load than it does alone. Use
    ``--jobs 1`` when the timings are what is being measured.
    """
    if jobs == 1:
        system = build(name, level)
        return [one(system, sample) for sample in samples]
    with ProcessPoolExecutor(jobs, initializer=_start_worker, initargs=(name, level)) as pool:
        # The cost per text varies more than a hundredfold, so keep the chunks small
        # enough that one unlucky chunk cannot hold the whole run up at the end.
        return list(pool.map(_one_in_worker, samples, chunksize=32))


def pct(value: float | None) -> str:
    return "    n/a" if value is None else f"{value * 100:6.1f}%"


def tally(item: metrics.Tally) -> str:
    return f"{pct(item.rate)}  ({item.hits}/{item.total})"


def print_report(title: str, report: metrics.Report, detail: bool, jobs: int = 1) -> None:
    print(f"\n=== {title} ===")
    print(f"Clean texts changed (lower is better)   {tally(report.false_change)}")
    print(f"Informal clean texts rewritten on purpose {tally(report.normalised)}")
    print(f"Obfuscated texts recovered              {tally(report.recovered)}")
    print(f"  with every capital letter right       {tally(report.recovered_with_capitals)}")
    print(f"Obfuscated texts made worse             {tally(report.made_worse)}")
    print(f"Mean character error, before -> after   {pct(report.mean_error_rate(False))} -> {pct(report.mean_error_rate(True))}")
    print(f"Above this level: recovered / worse     {tally(report.out_of_scope_recovered)} / {tally(report.out_of_scope_made_worse)}")
    print(f"Same result when run twice              {tally(report.idempotent)}")
    millis = sorted(second * 1000 for second in report.seconds)
    shared = f"   (measured over {jobs} processes sharing the machine; --jobs 1 to time it properly)" if jobs > 1 else ""
    print(f"Time per text, median / 95th / max      {statistics.median(millis):.3f} / {millis[int(len(millis) * 0.95)]:.3f} / {millis[-1]:.3f} ms{shared}")

    print("\nBy text length          clean changed          recovered")
    for name, _, _ in metrics.LENGTH_BUCKETS:
        print(f"  {name:<20}  {tally(report.false_change_by_length[name]):<21}  {tally(report.recovered_by_length[name])}")
    print("\nBy kind of sample       recovered")
    for mode in ("whole", "partial", "stacked", "real"):
        print(f"  {mode:<20}  {tally(report.recovered_by_mode[mode])}")
    print("\nBy origin of the text   clean changed          recovered              character error, before -> after")
    for origin in sorted(set(report.false_change_by_origin) | set(report.recovered_by_origin)):
        errors = report.error_by_origin[origin]
        change = f"{pct(statistics.fmean(b for b, _ in errors))} -> {pct(statistics.fmean(a for _, a in errors))}" if errors else ""
        print(f"  {origin:<20}  {tally(report.false_change_by_origin[origin]):<21}  {tally(report.recovered_by_origin[origin]):<21}  {change}")
    if not detail:
        return

    print("\nClean texts changed, by category")
    for category, item in sorted(report.false_change_by_category.items()):
        print(f"  {category:<28}  {tally(item)}")
    print("\nRecovered, by trick")
    for (mode, category), item in sorted(report.recovered_by_category.items()):
        print(f"  {mode:<8} {category:<28}  {tally(item)}")
    names = sorted(set(report.transform_true) | set(report.transform_false) | set(report.transform_missed))
    print("\nStep record against tricks used    precision   recall")
    for name in names:
        print(f"  {name:<28}  {pct(report.precision(name))}    {pct(report.recall(name))}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--split", choices=("dev", "test"), default="dev")
    parser.add_argument("--system", choices=("deobfuscate", "identity", "nfkc"), default="deobfuscate")
    parser.add_argument("--level", choices=LEVELS, action="append", help="strictness level; repeat for several (default: all)")
    parser.add_argument("--detail", action="store_true", help="also print per-category tables")
    parser.add_argument("--deferred", action="store_true",
                        help="also run the samples of tricks version 1 does not undo (slow; they score as out of scope)")
    parser.add_argument("--jobs", type=int, default=0,
                        help="processes to score over (default: one per core; 1 for honest per-text timings)")
    args = parser.parse_args()

    samples = load(args.split, args.deferred)
    jobs = max(1, min(args.jobs or (getattr(os, "process_cpu_count", os.cpu_count))() or 1, len(samples)))
    if not any(LOCAL.glob(f"*_{args.split}.jsonl")):
        print("Note: no local-only sets found; run `python -m evaluation.local_sets` to add the real-world samples.")
    for level in args.level or LEVELS:
        report = metrics.score(run(args.system, level, samples, jobs), level)
        print_report(f"{args.system}, scored at {level}, {args.split} split ({len(samples)} texts)",
                     report, args.detail, jobs)


if __name__ == "__main__":
    main()
