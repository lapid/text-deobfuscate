"""Finds stretches of text that are not English as they stand.

Shared by the transforms that rewrite letters in place (Caesar shifts,
reversal): they look for runs of words that are not English, and check whether
their rewrite turns those words into English.
"""

from dataclasses import dataclass

from text_deobfuscate import scorer
from text_deobfuscate.transforms.base import CHUNK


@dataclass(frozen=True, slots=True)
class Chunk:
    start: int
    end: int
    text: str
    # Letters in the chunk, and whether any of its words is English as it stands.
    letters: int
    plain: bool


def chunks(text: str) -> list[Chunk]:
    out = []
    for match in CHUNK.finditer(text):
        tokens = scorer.TOKEN.findall(match.group())
        out.append(Chunk(match.start(), match.end(), match.group(), sum(map(len, tokens)),
                         any(scorer.is_word(token) for token in tokens)))
    return out


def foreign_runs(found: list[Chunk]) -> list[tuple[int, int]]:
    """Index ranges (first, last inclusive) of runs of chunks that are not English.

    Chunks without letters (numbers, punctuation) may sit inside a run but
    cannot start or end one.
    """
    runs = []
    first = last = None
    for index, chunk in enumerate([*found, None]):
        if chunk is not None and not chunk.plain:
            if chunk.letters:
                first = index if first is None else first
                last = index
            continue
        if first is not None:
            runs.append((first, last))
        first = last = None
    return runs


def reads_as_english(text: str) -> bool:
    """Whether a rewritten chunk contains an English word."""
    return any(scorer.is_word(token) for token in scorer.TOKEN.findall(text))
