"""Combining marks laid over letters: strike-through, underline, stacked "Zalgo" marks.

Accents typed as separate marks are ordinary spelling ("é" may arrive as "e" plus an
acute), and phonetic notation uses rarer marks, so a mark is removed only from a
word that shows the trick: marks no alphabet spells with on a known English word,
on every letter of a word, or piled three deep.
One odd mark on one letter is not enough: phonetic notation writes "t͡s".
"""

import unicodedata
from collections.abc import Iterable
from functools import cache

from text_deobfuscate import scorer
from text_deobfuscate.transforms.base import CHUNK, Candidate, Transform
from text_deobfuscate.transforms.lookalike import WORD

# The blocks of marks that attach to letters of the Latin, Greek and Cyrillic alphabets.
BLOCKS = ((0x0300, 0x036F), (0x0483, 0x0489), (0x1AB0, 0x1AFF), (0x1DC0, 0x1DFF), (0x20D0, 0x20FF), (0xFE20, 0xFE2F))
# More marks than this on one letter is not spelling in any language.
MAX_STACK = 2


def is_mark(char: str) -> bool:
    return any(low <= ord(char) <= high for low, high in BLOCKS) and unicodedata.category(char) in ("Mn", "Me")


@cache
def spelling_marks() -> frozenset[str]:
    """Marks some alphabet spells with: those Unicode composes into a letter."""
    found: set[str] = set()
    for code in range(0xC0, 0x2000):
        char = chr(code)
        if char.isalpha():
            found.update(mark for mark in unicodedata.normalize("NFD", char)[1:] if is_mark(mark))
    return frozenset(found)


def strip(text: str) -> str:
    return "".join(char for char in text if not is_mark(char))


def clusters(chunk: str) -> list[tuple[str, str]]:
    """Each character of the chunk with the marks that follow it."""
    out: list[tuple[str, str]] = []
    for char in chunk:
        if is_mark(char) and out:
            out[-1] = (out[-1][0], out[-1][1] + char)
        else:
            out.append((char, ""))
    return out


class CombiningMarks(Transform):
    name = "combining-marks"
    level = "balanced"
    # The decision is made here, word by word; the scorer has nothing to add for one word.
    judged = False

    def propose(self, text: str) -> Iterable[Candidate]:
        if text.isascii():
            return
        spelling = spelling_marks()
        sure: list[Candidate] = []
        unsure: list[Candidate] = []
        for match in CHUNK.finditer(text):
            chunk = match.group()
            if not any(is_mark(char) for char in chunk):
                continue
            parts = clusters(chunk)
            odd = [any(mark not in spelling for mark in marks) for _, marks in parts]
            heavy = any(len(marks) > MAX_STACK for _, marks in parts)
            if not heavy and not any(odd):
                continue
            plain = strip(chunk)
            candidate = Candidate(match.start(), match.end(), plain)
            letters = [is_odd for (base, _), is_odd in zip(parts, odd) if base.isalpha()]
            words = [word.group() for word in WORD.finditer(plain)]
            known = bool(words) and all(len(word) > 1 and word.isascii() and scorer.is_word(word) for word in words)
            if heavy or (known and sum(letters) >= 2) or (len(letters) >= 3 and all(letters)):
                sure.append(candidate)
            elif all(base.isascii() for base, _ in parts):
                # A name or a one-letter word: follows the rest of the text.
                unsure.append(candidate)
        yield from sure
        if sure:
            yield from unsure
