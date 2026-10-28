"""Letters repeated inside a word: "heeellooo", "freeee".

English has no letter three times in a row, so a run of three or more is cut to
two or to one, whichever spells a known word. People also stretch a word on
purpose ("sooooo good", "Hmmm"), which looks the same; that is why this runs only
at the ``aggressive`` level. Stretching for effect falls mostly on one short word,
so a short word is cut back only when another word in the text is stretched too.
A word that is not known either way (a name) needs two.
"""

import re
from collections.abc import Iterable
from itertools import product

from text_deobfuscate import resources, scorer
from text_deobfuscate.transforms.base import Candidate, Transform

WORD = re.compile(r"(?<![\w'’])[A-Za-z]+(?:['’][A-Za-z]+)?(?![\w'’])")
RUN = re.compile(r"([A-Za-z])\1{2,}", re.IGNORECASE)
MIN_WORD = 3
# A stretched word this long is cut back even when it is the only one in the text.
LONG_WORD = 5
MAX_RUNS = 4
EVIDENCE_FOR_NAME = 2


def is_plain_word(word: str) -> bool:
    """A known word that is not only an abbreviation; "don't" counts through "don't" itself."""
    known = resources.words()
    word = word.replace("’", "'")
    return word.lower() in known or (not word.isupper() and word.capitalize() in known)


def collapse(word: str) -> str | None:
    """The word with its stretched letters cut back, if that spells a known word."""
    runs = list(RUN.finditer(word))
    if not runs or len(runs) > MAX_RUNS:
        return None
    found: list[str] = []
    for lengths in product((2, 1), repeat=len(runs)):
        parts, position = [], 0
        for run, length in zip(runs, lengths):
            parts.append(word[position : run.start()] + run.group()[:length])
            position = run.end()
        plain = "".join(parts) + word[position:]
        if len(plain) >= MIN_WORD and is_plain_word(plain):
            found.append(plain)
    # Several readings ("theee" is "thee" or "the"): the commoner letter pattern wins.
    return max(found, key=lambda plain: scorer.ngram_fit(plain) or float("-inf"), default=None)


class RepeatedChars(Transform):
    name = "repeated-chars"
    level = "aggressive"
    # The decision is made here, word by word; the scorer has nothing to add for one word.
    judged = False

    def propose(self, text: str) -> Iterable[Candidate]:
        found = []
        names = []
        for match in WORD.finditer(text):
            word = match.group()
            if len(word) <= MIN_WORD or scorer.is_word(word) or not RUN.search(word):
                continue
            plain = collapse(word)
            if plain is not None:
                found.append(Candidate(match.start(), match.end(), plain))
            elif not word.isupper():
                names.append(Candidate(match.start(), match.end(), RUN.sub(lambda run: run.group()[0], word)))
        alone = len(found) == 1
        yield from (candidate for candidate in found if not alone or len(candidate.replacement) >= LONG_WORD)
        if len(found) >= EVIDENCE_FOR_NAME:
            yield from names
