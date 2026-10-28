"""Separators put between the letters of a word: "f r e e", "c.l.i.c.k", "f-r-e-e".

Decided one run at a time. Letters are joined only when they then spell known
English words. Initials and abbreviations ("J. R. R.", "U.S.A", "W.H.O") do not:
they are either not words, or known only in capitals, and are left alone.
"""

import re
from collections.abc import Iterable

from text_deobfuscate import resources, scorer
from text_deobfuscate.transforms.base import Candidate, Transform

SYMBOLS = ".-_*,"
SYMBOL_RUNS = tuple(
    re.compile(rf"(?<![\w{re.escape(symbol)}])[A-Za-z](?:{re.escape(symbol)}[A-Za-z]){{2,}}(?!\w)(?!{re.escape(symbol)}\w)")
    for symbol in SYMBOLS
)
SPACED_RUN = re.compile(r"(?<![\w'’.])(?:[A-Za-z] ){3,}[A-Za-z](?![\w'’])")
# A whole text written one character at a time, with wider gaps between the words.
SPACED_TEXT = re.compile(r"\S(?: \S)*(?: {2,}\S(?: \S)*)+")
ONE_LETTER_WORDS = frozenset("aI")
MIN_WORD = 3
MIN_COVERAGE = 0.5
# No word is longer; also keeps a run of thousands of letters from costing the square of its length.
LONGEST_WORD = 40
MIN_GROUPS = 3
# Runs rewritten outright that a run must have beside it when its letters are not a
# known word (a name). "_" and "*" are not used between letters in ordinary writing.
EVIDENCE_FOR_NAME = {"_": 1, "*": 1, ".": 2, "-": 2, ",": 2}


WORD_TOKEN = re.compile(r"\S+")
# A text separated character by character needs this many such words, and nearly every
# word of more than one character must be one.
MIN_SEPARATED = 4
MIN_SEPARATED_SHARE = 0.9


def separated_tokens(text: str, symbol: str) -> list[Candidate]:
    """Every word written as its characters joined by ``symbol`` ("d.o.n.'.t"), if the text is that kind.

    Punctuation sitting on a word is separated with it ("S.o.," is "So,"), and a full stop at the
    end of a sentence ends up as "..". Words of one character stay as they are, so a text
    in which almost every longer word has the shape is plainly written this way.
    """
    found = []
    longer = 0
    for match in WORD_TOKEN.finditer(text):
        token = match.group()
        if len(token) < 2:
            continue
        longer += 1
        if len(token) % 2 == 1 and len(token) >= 3 and set(token[1::2]) == {symbol}:
            found.append(Candidate(match.start(), match.end(), token[::2]))
    letters = sum(any(char.isalpha() for char in candidate.replacement) for candidate in found)
    # A list of initialisms ("U.S.A U.K E.U") is all capitals; written words are not.
    lower = sum(any(char.islower() for char in candidate.replacement) for candidate in found)
    if letters < MIN_SEPARATED or lower < MIN_SEPARATED or len(found) < MIN_SEPARATED_SHARE * longer:
        return []
    return found


def is_plain_word(word: str) -> bool:
    """A known word that is not only an abbreviation: "free" and "John", not "USA"."""
    known = resources.words()
    return len(word) >= MIN_WORD and (word.lower() in known or (not word.isupper() and word.capitalize() in known))


def split_words(letters: str) -> list[str] | None:
    """The fewest known words the letters spell in order, or None.

    A run can hold several words ("f r e e g i f t"), or begin or end with an
    ordinary one-letter word ("a f r e e").
    """
    size = len(letters)
    count = [0] + [-1] * size          # fewest words that spell letters[:end]; -1 if none
    cut = [0] * (size + 1)             # where the last word of that best split begins
    for end in range(1, size + 1):
        for start in range(max(0, end - LONGEST_WORD), end):
            if count[start] < 0:
                continue
            piece = letters[start:end]
            if not (is_plain_word(piece) or piece in ONE_LETTER_WORDS):
                continue
            if count[end] < 0 or count[start] + 1 < count[end]:
                count[end], cut[end] = count[start] + 1, start
    if count[size] < 0:
        return None
    words = []
    end = size
    while end > 0:
        words.append(letters[cut[end] : end])
        end = cut[end]
    words.reverse()
    if all(len(word) == 1 for word in words):
        return None
    return words


class Separator(Transform):
    name = "separator"
    level = "balanced"
    # The decision is made here, run by run; the scorer has nothing to add for one word.
    judged = False

    def propose(self, text: str) -> Iterable[Candidate]:
        whole = SPACED_TEXT.fullmatch(text.strip())
        # Spaced-out capitals are how headings are set ("C H A P T E R   O N E").
        if whole and not text.isupper():
            groups = re.split(r" {2,}", text.strip())
            joined = " ".join(group.replace(" ", "") for group in groups)
            covered, total = scorer.word_coverage(joined)
            if len(groups) >= MIN_GROUPS and total and covered >= total * MIN_COVERAGE:
                start = len(text) - len(text.lstrip())
                yield Candidate(start, start + len(text.strip()), joined)
                return
        for symbol in SYMBOLS:
            if symbol in text and (every := separated_tokens(text, symbol)):
                yield from every
                return
        strong: list[Candidate] = []
        weak: list[Candidate] = []
        names: list[tuple[int, Candidate]] = []
        for symbol, pattern in zip(SYMBOLS, SYMBOL_RUNS):
            for match in pattern.finditer(text):
                word = match.group()[::2]
                candidate = Candidate(match.start(), match.end(), word)
                if not is_plain_word(word):
                    if len(word) > MIN_WORD and not word.isupper():
                        names.append((EVIDENCE_FOR_NAME[symbol], candidate))
                elif word.isupper() or (symbol == "." and text[match.end() : match.end() + 1] == "."):
                    # Abbreviations are written in capitals, or with a dot after every letter ("a.k.a.").
                    weak.append(candidate)
                else:
                    strong.append(candidate)
        for match in SPACED_RUN.finditer(text):
            letters = match.group()[::2]
            words = split_words(letters)
            if words is not None:
                (weak if letters.isupper() else strong).append(Candidate(match.start(), match.end(), " ".join(words)))
        yield from strong
        if strong:
            yield from weak
        yield from (candidate for needed, candidate in names if len(strong) >= needed)
