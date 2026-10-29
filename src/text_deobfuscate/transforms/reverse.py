import re
from collections.abc import Iterable

from text_deobfuscate import scorer
from text_deobfuscate.transforms.base import Candidate, Transform
from text_deobfuscate.transforms.runs import chunks, foreign_runs, reads_as_english


# A long unbroken token may be another encoding written backwards; base64 padding then comes first.
ENCODED = re.compile(r"(?<![A-Za-z0-9+/=_-])={0,2}(?=[A-Za-z0-9+/_-]*[a-z])(?=[A-Za-z0-9+/_-]*[A-Z0-9])[A-Za-z0-9+/_-]{16,}(?![A-Za-z0-9+/=_-])")


# How many words that read both ways may sit between two parts of one reversed run.
MAX_GAP = 2
# A run joined across such words rests on less, so it must be longer. With ten letters,
# two misspelt words around "is" ("waht is rael") read as English backwards by chance.
MIN_JOINED_LETTERS = 12
# A short text of few words can read as English backwards by chance: Spanish "No pasa nada" is
# "adan asap oN". The whole of a text is reversed only if it has this many words or letters.
SHORT_WORDS = 4
SHORT_LETTERS = 16


def each_word(span: str) -> str:
    """Every run of non-space characters reversed where it stands."""
    return " ".join(word[::-1] for word in span.split(" "))


STOPS = ".!?"


def written_word_by_word(span: str) -> bool:
    """Whether the span looks like each word reversed rather than the whole of it.

    Both readings give the same words, so the score cannot choose between them: one
    returns the words in order, the other in reverse order. Where the sentence's
    capital and full stop have landed does choose, and both ends have to agree.

    Reversed word by word, "ehT gniteem ... .roolf" keeps the capital at the end of
    its first word and the stop at the start of its last. Reversed as a whole, the
    text itself opens with the stop and closes with the capital.

    The stop decides it on its own, and more often than the capital does. Reversed
    word by word, the stop lands at the start of the **last** word (".roolf");
    reversed as a whole, it lands at the start of the **text**. So a span that does
    not open with a stop but whose last word does was reversed word by word.

    The capital is no help beside it. Requiring one as well ("ehT") missed every text
    that begins with a lowercase word, and reading either mark on its own took
    ".siraP ot devom eH" — "He moved to Paris." reversed whole — for word-reversed,
    because the original happened to end on a name.

    Two stricter rules were measured on dev and both rejected: demanding that
    punctuation support a reading before reversing anything cost 33 recoveries of
    plain reversed text, and declining whenever no stop appears at all destroyed the
    layered cases outright, since a reversed base64 string contains no stop.
    """
    words = span.split()
    stripped = span.strip()
    if len(words) < 2 or not stripped:
        return False
    return stripped[0] not in STOPS and words[-1][0] in STOPS


class Reverse(Transform):
    """Text written backwards: the whole of it, a run of words, or each word in place."""

    name = "reverse"
    # A short unknown word can read as English backwards by chance.
    min_letters = 10

    def propose(self, text: str) -> Iterable[Candidate]:
        for match in ENCODED.finditer(text):
            yield Candidate(match.start(), match.end(), match.group()[::-1])
        # Each word backwards with the words left in order. Reversing the whole text
        # recovers the letters but leaves the word order inverted, so this is proposed
        # as well. The two score alike, and the engine keeps the first of equal
        # proposals, so the one the punctuation points to is yielded first.
        if len(text.split()) < SHORT_WORDS and scorer.letter_count(text) < SHORT_LETTERS:
            return
        if " " in text and written_word_by_word(text):
            by_word = each_word(text)
            covered, total = scorer.word_coverage(by_word)
            if total and covered / total >= 0.6:
                yield Candidate(0, len(text), by_word)
        # Reversed text still contains the odd word that reads as English ("saw", "no"),
        # so the whole text is always tried; the engine keeps it only if it reads better.
        covered, total = scorer.word_coverage(text[::-1])
        whole = bool(total) and covered / total >= 0.6
        if whole:
            yield Candidate(0, len(text), text[::-1])
        found = chunks(text)
        runs = foreign_runs(found)
        # "no", "was" and "I" are words in both directions, and cut a reversed run in two.
        # The run across them is tried as well, unless the whole text may be reversed:
        # a run of nearly all of it would then win and leave the words at the ends behind.
        joined: list[tuple[int, int]] = []
        for first, last in [] if whole else runs:
            if joined and first - joined[-1][1] - 1 <= MAX_GAP and all(
                reads_as_english(chunk.text[::-1]) for chunk in found[joined[-1][1] + 1 : first]
            ):
                joined[-1] = (joined[-1][0], last)
            else:
                joined.append((first, last))
        for first, last in [*runs, *(run for run in joined if run not in runs)]:
            # A word that is English as it stands may sit inside the run, not at its ends.
            while first <= last and (found[first].plain or not reads_as_english(found[first].text[::-1])):
                first += 1
            while last >= first and (found[last].plain or not reads_as_english(found[last].text[::-1])):
                last -= 1
            if first > last:
                continue
            start, end = found[first].start, found[last].end
            span = text[start:end][::-1]
            if (first, last) not in runs and any(chunk.plain for chunk in found[first : last + 1]):
                if scorer.letter_count(span) < MIN_JOINED_LETTERS:
                    continue
            # The same run with each of its words reversed in place. Of two proposals
            # that score alike the engine keeps the first, so the reading the
            # punctuation points to goes first.
            readings = [span, each_word(text[start:end])]
            if written_word_by_word(text[start:end]):
                readings.reverse()
            for reading in readings:
                covered, total = scorer.word_coverage(reading)
                if total and covered / total >= 0.6:
                    yield Candidate(start, end, reading)
