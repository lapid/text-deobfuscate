"""Letters and digits written in decorative Unicode forms."""

import re
import unicodedata
from collections.abc import Iterable

from text_deobfuscate.scripts import scripts_in
from text_deobfuscate.transforms.base import CHUNK, Candidate, Transform

# Mathematical alphanumerics, circled letters, squared letters.
STYLED_RANGES = ((0x1D400, 0x1D7FF), (0x24B6, 0x24E9), (0x1F130, 0x1F149))
# Letterlike symbols such as the italic h, which fill gaps in the mathematical
# alphabets. On their own they are ordinary symbols, so they never count as evidence.
LETTERLIKE = (0x2100, 0x214F)
FULLWIDTH = (0xFF01, 0xFF5E)
# The fullwidth form of the space; it sits between fullwidth words.
IDEOGRAPHIC_SPACE = "\u3000"
# Fullwidth forms are normal in these scripts.
EAST_ASIAN = frozenset({"Han", "Hiragana", "Katakana", "Hangul", "Bopomofo"})


def plain(char: str) -> str | None:
    """The ASCII letter or digit a decorative character stands for, if any."""
    folded = unicodedata.normalize("NFKC", char)
    return folded if len(folded) == 1 and folded.isascii() and folded.isalnum() else None


def is_styled(char: str) -> bool:
    return any(low <= ord(char) <= high for low, high in STYLED_RANGES) and plain(char) is not None


def is_letterlike(char: str) -> bool:
    return LETTERLIKE[0] <= ord(char) <= LETTERLIKE[1] and plain(char) is not None


class StyledAlphabet(Transform):
    name = "styled-alphabet"
    judged = False

    def propose(self, text: str) -> Iterable[Candidate]:
        """Runs of neighbouring words written in styled letters.

        A run needs two styled letters. One on its own is usually a maths variable.
        """
        run: list[re.Match[str]] = []
        for match in [*CHUNK.finditer(text), None]:
            if match is not None and any(is_styled(char) for char in match.group()):
                run.append(match)
                continue
            if run:
                start, end = run[0].start(), run[-1].end()
                span = text[start:end]
                if sum(is_styled(char) for char in span) >= 2:
                    folded = "".join((plain(char) or char) if is_styled(char) or is_letterlike(char) else char for char in span)
                    yield Candidate(start, end, folded)
            run = []


def is_fullwidth(char: str) -> bool:
    return FULLWIDTH[0] <= ord(char) <= FULLWIDTH[1]


def narrow(char: str) -> str:
    if is_fullwidth(char):
        return chr(ord(char) - 0xFEE0)
    return " " if char == IDEOGRAPHIC_SPACE else char


class Fullwidth(Transform):
    name = "fullwidth"
    judged = False

    def propose(self, text: str) -> Iterable[Candidate]:
        """Runs of neighbouring words containing fullwidth characters.

        A run needs a fullwidth letter or digit. Fullwidth punctuation alone is
        a typing habit, not a disguise.
        """
        if scripts_in(text) & EAST_ASIAN:
            return
        run: list[re.Match[str]] = []
        for match in [*CHUNK.finditer(text), None]:
            if match is not None and any(is_fullwidth(char) for char in match.group()):
                run.append(match)
                continue
            if run:
                start, end = run[0].start(), run[-1].end()
                span = text[start:end]
                if any(is_fullwidth(char) and plain(char) for char in span):
                    yield Candidate(start, end, "".join(map(narrow, span)))
            run = []
