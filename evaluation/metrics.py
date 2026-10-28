"""Scores a system's outputs against the evaluation sets."""

import statistics
from collections import defaultdict
from dataclasses import dataclass, field

from evaluation.tricks import NORMALISING, LEVELS, RECORDED_AS, in_scope

LENGTH_BUCKETS = (("under 20", 0, 20), ("20 to 59", 20, 60), ("60 to 149", 60, 150), ("150 and over", 150, 10**9))


def edit_distance(a: str, b: str) -> int:
    """Levenshtein distance, using Myers' bit-parallel algorithm."""
    if a == b:
        return 0
    if not a or not b:
        return len(a) or len(b)
    positions: dict[str, int] = {}
    for index, char in enumerate(a):
        positions[char] = positions.get(char, 0) | (1 << index)
    size = len(a)
    mask = (1 << size) - 1
    last = 1 << (size - 1)
    plus, minus, score = mask, 0, size
    for char in b:
        match = positions.get(char, 0)
        diagonal = match | minus
        horizontal = (((match & plus) + plus) ^ plus) | match
        plus_h = (minus | ~(horizontal | plus)) & mask
        minus_h = plus & horizontal
        if plus_h & last:
            score += 1
        elif minus_h & last:
            score -= 1
        plus_h = ((plus_h << 1) | 1) & mask
        minus_h = (minus_h << 1) & mask
        plus = (minus_h | ~(diagonal | plus_h)) & mask
        minus = plus_h & diagonal
    return score


def counts_at(sample: dict, level: str) -> bool:
    """Whether a deobfuscator at ``level`` is expected to recover this sample.

    Real samples do not say which tricks were used; they carry a level instead.
    """
    if "level" in sample:
        return LEVELS.index(sample["level"]) <= LEVELS.index(level)
    return in_scope(sample["tricks"], level)


INFORMAL_CATEGORIES = frozenset({"shorthand", "emoji"})
# Sources that were proofread: a shorthand or spelling step there is a mistake.
EDITED_ORIGINS = frozenset({"wikipedia", "wikinews", "books"})


def is_informal(sample: dict) -> bool:
    """Clean text of a kind that is normally written with shorthand, typos and emoji."""
    return sample.get("origin") == "sms" or sample.get("category") in INFORMAL_CATEGORIES


def same(a: str, b: str, sample: dict) -> bool:
    """Equality as the sample defines it: some sources supply lowercased answers."""
    return a.casefold() == b.casefold() if sample.get("caseless") else a == b


def length_bucket(text: str) -> str:
    for name, low, high in LENGTH_BUCKETS:
        if low <= len(text) < high:
            return name
    raise AssertionError("unreachable")


@dataclass
class Outcome:
    """What a system did with one sample."""

    sample: dict
    output: str
    transforms: list[str]
    second_pass: str
    seconds: float
    # The expected text as the system would rewrite it using only the transforms for
    # informal writing, if that differs. Answers from real messages keep their shorthand
    # ("u"), and a system that writes it out ("you") has still recovered the text.
    expected_rewritten: str | None = None


@dataclass
class Tally:
    total: int = 0
    hits: int = 0

    def add(self, hit: bool) -> None:
        self.total += 1
        self.hits += hit

    @property
    def rate(self) -> float | None:
        return self.hits / self.total if self.total else None


@dataclass
class Report:
    # Clean set: a "hit" is a text that was changed. Lower is better.
    false_change: Tally = field(default_factory=Tally)
    # Clean informal texts (text messages, shorthand, emoji) changed only by the
    # transforms that rewrite informal writing. That is what those transforms are for,
    # so these are counted here and not as false changes.
    normalised: Tally = field(default_factory=Tally)
    false_change_by_category: dict[str, Tally] = field(default_factory=lambda: defaultdict(Tally))
    false_change_by_length: dict[str, Tally] = field(default_factory=lambda: defaultdict(Tally))
    false_change_by_origin: dict[str, Tally] = field(default_factory=lambda: defaultdict(Tally))
    # Obfuscated set, samples the strictness level is expected to handle.
    # Recovery ignores capitals: a capital hidden by a disguise is often not recoverable,
    # and a reader loses nothing by it. ``recovered_with_capitals`` is the strict count.
    recovered: Tally = field(default_factory=Tally)
    recovered_with_capitals: Tally = field(default_factory=Tally)
    recovered_by_category: dict[tuple[str, str], Tally] = field(default_factory=lambda: defaultdict(Tally))
    recovered_by_length: dict[str, Tally] = field(default_factory=lambda: defaultdict(Tally))
    recovered_by_mode: dict[str, Tally] = field(default_factory=lambda: defaultdict(Tally))
    recovered_by_origin: dict[str, Tally] = field(default_factory=lambda: defaultdict(Tally))
    made_worse: Tally = field(default_factory=Tally)
    error_by_origin: dict[str, list[tuple[float, float]]] = field(default_factory=lambda: defaultdict(list))
    error_rate_before: list[float] = field(default_factory=list)
    error_rate_after: list[float] = field(default_factory=list)
    # Obfuscated set, samples above the strictness level: leaving them alone is acceptable.
    out_of_scope_recovered: Tally = field(default_factory=Tally)
    out_of_scope_made_worse: Tally = field(default_factory=Tally)
    # Step record against the tricks actually used, over both sets.
    transform_true: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    transform_false: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    transform_missed: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    idempotent: Tally = field(default_factory=Tally)
    seconds: list[float] = field(default_factory=list)

    def precision(self, transform: str) -> float | None:
        found = self.transform_true[transform] + self.transform_false[transform]
        return self.transform_true[transform] / found if found else None

    def recall(self, transform: str) -> float | None:
        wanted = self.transform_true[transform] + self.transform_missed[transform]
        return self.transform_true[transform] / wanted if wanted else None

    def mean_error_rate(self, after: bool) -> float | None:
        values = self.error_rate_after if after else self.error_rate_before
        return statistics.fmean(values) if values else None


def score(outcomes: list[Outcome], level: str) -> Report:
    report = Report()
    for outcome in outcomes:
        sample = outcome.sample
        text, expected, tricks = sample["text"], sample["expected"], sample["tricks"]
        report.seconds.append(outcome.seconds)
        report.idempotent.add(outcome.second_pass == outcome.output)

        expected_here = counts_at(sample, level)
        if tricks != ["unknown"]:
            gold, found = {RECORDED_AS.get(trick, trick) for trick in tricks}, set(outcome.transforms)
            for name in gold & found:
                report.transform_true[name] += 1
            for name in found - gold:
                # Real informal text has shorthand and typos of its own; rewriting them is not a wrong step.
                if not (name in NORMALISING and sample.get("origin") not in EDITED_ORIGINS):
                    report.transform_false[name] += 1
            if expected_here:
                for name in gold - found:
                    report.transform_missed[name] += 1

        if not tricks:
            changed = not same(outcome.output, expected, sample)
            if is_informal(sample):
                rewritten = changed and set(outcome.transforms) <= NORMALISING
                report.normalised.add(rewritten)
                changed = changed and not rewritten
            report.false_change.add(changed)
            report.false_change_by_category[sample["category"]].add(changed)
            report.false_change_by_length[length_bucket(expected)].add(changed)
            report.false_change_by_origin[sample.get("origin", "unknown")].add(changed)
            continue

        fold = str.casefold
        exact = fold(outcome.output) == fold(expected)
        if not exact and outcome.expected_rewritten is not None:
            exact = fold(outcome.output) == fold(outcome.expected_rewritten)
            expected = outcome.expected_rewritten if exact else expected
        before = edit_distance(fold(text), fold(expected))
        after = 0 if exact else edit_distance(fold(outcome.output), fold(expected))
        if after and outcome.expected_rewritten is not None:
            after = min(after, edit_distance(fold(outcome.output), fold(outcome.expected_rewritten)))
        if not expected_here:
            report.out_of_scope_recovered.add(exact)
            report.out_of_scope_made_worse.add(after > before)
            continue
        report.recovered.add(exact)
        report.recovered_with_capitals.add(same(outcome.output, expected, sample))
        report.recovered_by_category[(sample["mode"], sample["category"])].add(exact)
        report.recovered_by_length[length_bucket(expected)].add(exact)
        report.recovered_by_mode[sample["mode"]].add(exact)
        report.recovered_by_origin[sample.get("origin", "unknown")].add(exact)
        report.made_worse.add(after > before)
        scale = max(len(expected), 1)
        # Capped at 1: an encoding can be many times longer than the text it hides.
        report.error_rate_before.append(min(before / scale, 1.0))
        report.error_rate_after.append(min(after / scale, 1.0))
        report.error_by_origin[sample.get("origin", "unknown")].append((min(before / scale, 1.0), min(after / scale, 1.0)))
    return report
