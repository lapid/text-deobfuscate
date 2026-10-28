"""Applies transforms until nothing more improves the text.

Transforms propose replacements; the engine decides. For each proposal it first
deobfuscates the replacement itself, so layered obfuscation is judged by what it
finally turns into, then applies the proposal only if that result reads more
like English than the text it replaces.
"""

from bisect import bisect_left
from dataclasses import dataclass

from text_deobfuscate import scorer
from text_deobfuscate.protect import merged, overlaps, protected_spans
from text_deobfuscate.transforms import ALL, Candidate, Transform
from text_deobfuscate.types import Step

LEVELS = ("conservative", "balanced", "aggressive")

# Longer inputs are returned unchanged.
MAX_INPUT_CHARS = 100_000
# How many layers deep a replacement may itself be deobfuscated.
MAX_DEPTH = 4
# How many replacements one text, or one layer of it, may receive.
MAX_STEPS = 200
# How many candidate replacements one text may have deobfuscated on its behalf.
# Judging a candidate means deobfuscating it first, in case it holds another layer, and
# enciphered text throws up candidates in bulk: a 55-word rot47 text produced 574 of
# them and took 700 ms, while the median text needs 2. Past this budget candidates are
# judged as they stand, so a deep stack inside an unusually productive text may go
# unread. Measured on dev: 29 texts of 18,109 reach the budget, and it costs one
# recovery of 18,109 -- a base64 string holding hex -- while the slowest text falls
# from 700-806 ms to 292-567 ms. Clean texts changed and made worse do not move.
MAX_LAYER_RUNS = 200
# How many characters one call may scan in total, summed over every pass and every layer.
# A pass reads the whole text, so a long text that keeps finding things to change would
# otherwise cost passes times length: 100,000 random characters ran past 35 seconds. A
# 5,000-character text can still make 800 passes, more than MAX_STEPS allows, so ordinary
# input never reaches this; a text of 100,000 characters gets about 40.
MAX_WORK_CHARS = 4_000_000


@dataclass(frozen=True, slots=True)
class Policy:
    """What it takes for a judged proposal to be accepted."""

    # The result must score at least this much as English (0 to 1).
    min_score: float
    # The result must beat what it replaces by at least this much.
    min_gain: float
    # The result must contain at least this many letters to be judged at all.
    min_letters: int


# Chosen by a sweep on the dev split (docs/evaluation.md, "Threshold sweep").
POLICIES = {
    "conservative": Policy(min_score=0.50, min_gain=0.30, min_letters=8),
    "balanced": Policy(min_score=0.50, min_gain=0.30, min_letters=8),
    "aggressive": Policy(min_score=0.45, min_gain=0.25, min_letters=6),
}


@dataclass(frozen=True, slots=True)
class Accepted:
    transform: Transform
    candidate: Candidate
    final: str
    inner_steps: tuple[Step, ...]
    confidence: float
    gain: float
    # Gain times the amount of text it was measured on. Proposals are ranked by
    # this, so a rewrite of the whole text beats the same rewrite of a part of it.
    weight: float


class Engine:
    def __init__(self, level: str, transforms: tuple[Transform, ...] = ALL) -> None:
        self.policy = POLICIES[level]
        self.layer_runs = 0
        self.work_left = MAX_WORK_CHARS
        limit = LEVELS.index(level)
        self.transforms = tuple(t for t in transforms if LEVELS.index(t.level) <= limit)
        # Verdicts depend only on the transform and the two texts, and the same
        # proposals come up again after every accepted step.
        self.verdicts: dict[tuple[str, str, str], Accepted | None] = {}

    def run(self, text: str, depth: int = 0) -> tuple[str, tuple[Step, ...]]:
        if len(text) > MAX_INPUT_CHARS:
            return text, ()
        if depth == 0:
            self.layer_runs = 0
            self.work_left = MAX_WORK_CHARS
        steps: list[Step] = []
        for _ in range(MAX_STEPS):
            accepted = self.best_proposals(text, depth)
            if not accepted:
                break
            # Applied left to right; ``moved`` is how far earlier ones have shifted the rest.
            moved = 0
            for best in accepted:
                candidate = best.candidate
                start, end = candidate.start + moved, candidate.end + moved
                steps.append(Step(best.transform.name, start, end, text[start:end], candidate.replacement,
                                  round(best.confidence, 3), candidate.hidden))
                # Inner steps were found on the replacement alone; move them to where it now sits.
                steps.extend(Step(s.transform, s.start + start, s.end + start, s.before, s.after, s.confidence, s.hidden)
                             for s in best.inner_steps)
                text = text[:start] + best.final + text[end:]
                moved += len(best.final) - (end - start)
        return text, tuple(steps)

    def best_proposals(self, text: str, depth: int) -> list[Accepted]:
        """The proposals to apply next, in text order; empty when nothing is left to do."""
        if self.work_left <= 0:
            return []
        self.work_left -= len(text)
        protected = merged(protected_spans(text))
        # Certain transforms go first, until none applies. Judged transforms then
        # see text free of invisible characters and escapes, which would otherwise
        # break words apart and mislead them.
        # Last of all, and only on the whole text, come the transforms that rewrite
        # informal writing. A decoded fragment can be a single letter of a longer
        # word, and must not be read as shorthand on its own.
        for judged, late in ((False, False), (True, False), (False, True)):
            if late and depth:
                continue
            best: Accepted | None = None
            winner: Transform | None = None
            proposed: list[tuple[Transform, list[Accepted]]] = []
            for transform in self.transforms:
                if transform.judged != judged or transform.late != late:
                    continue
                verdicts = []
                for candidate in transform.propose(text):
                    before = text[candidate.start : candidate.end]
                    if candidate.replacement == before:
                        continue
                    if not transform.ignores_protection and overlaps(candidate.start, candidate.end, protected):
                        continue
                    verdict = self.judge(transform, candidate, before, depth)
                    if verdict is not None:
                        verdicts.append(verdict)
                top = max(verdicts, key=lambda verdict: verdict.weight, default=None)
                if top is not None and (best is None or top.weight > best.weight):
                    best, winner = top, transform
                proposed.append((transform, verdicts))
            if best is None:
                continue
            if judged:
                return [best]
            # A certain transform decided on the text as a whole, so everything it
            # proposed is applied at once. One at a time, the words applied first
            # would no longer be there as evidence for the rest. The same holds for
            # the other transforms of its group.
            together = [verdict for transform, verdicts in proposed for verdict in verdicts
                        if transform is winner or (winner.group and transform.group == winner.group)]
            # Heaviest first; one is kept if it overlaps none already kept. The kept ones are
            # disjoint, so only the neighbours on either side of its start need a look.
            kept: list[Accepted] = []
            starts: list[int] = []
            for verdict in sorted(together, key=lambda verdict: (-verdict.weight, verdict.candidate.start)):
                start, end = verdict.candidate.start, verdict.candidate.end
                index = bisect_left(starts, start)
                if index > 0 and kept[index - 1].candidate.end > start:
                    continue
                if index < len(kept) and kept[index].candidate.start < end:
                    continue
                kept.insert(index, verdict)
                starts.insert(index, start)
            return kept
        return []

    def judge(self, transform: Transform, candidate: Candidate, before: str, depth: int) -> Accepted | None:
        key = (transform.name, before, candidate.replacement)
        if key not in self.verdicts:
            self.verdicts[key] = self.decide(transform, candidate, before, depth)
        found = self.verdicts[key]
        # The cached verdict was reached for the same texts, possibly at another position.
        return None if found is None else Accepted(found.transform, candidate, found.final, found.inner_steps,
                                                   found.confidence, found.gain, found.weight)

    def decide(self, transform: Transform, candidate: Candidate, before: str, depth: int) -> Accepted | None:
        final, inner_steps = candidate.replacement, ()
        if depth < MAX_DEPTH and self.layer_runs < MAX_LAYER_RUNS:
            self.layer_runs += 1
            final, inner_steps = self.run(candidate.replacement, depth + 1)
        if not transform.judged:
            return Accepted(transform, candidate, final, inner_steps, 1.0, 1.0, float(len(before)))
        if scorer.letter_count(final) < max(self.policy.min_letters, transform.min_letters):
            return None
        after_score = scorer.english_score(final)
        gain = after_score - scorer.english_score(before)
        if after_score < self.policy.min_score or gain < self.policy.min_gain:
            return None
        return Accepted(transform, candidate, final, inner_steps, after_score, gain, gain * scorer.letter_count(final))
