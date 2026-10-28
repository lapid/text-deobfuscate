"""Lazy loaders for the data files shipped with the package."""

import math
from functools import cache
from importlib.resources import files

DATA = files("text_deobfuscate") / "data"


@cache
def words() -> frozenset[str]:
    return frozenset((DATA / "words.txt").read_text(encoding="utf-8").split("\n")) - {""}


@cache
def ngrams() -> tuple[dict[str, float], float, int]:
    """(log10 probability of each known n-gram, log10 probability for an unseen one, n)."""
    lines = (DATA / "ngrams.txt").read_text(encoding="utf-8").split("\n")
    total = int(lines[0].rsplit(" ", 1)[1])
    table = {}
    for line in lines[1:]:
        if line:
            gram, count = line.split("\t")
            table[gram] = math.log10(int(count) / total)
    return table, math.log10(0.5 / total), len(next(iter(table)))


@cache
def scripts() -> tuple[tuple[int, ...], tuple[int, ...], tuple[str, ...]]:
    """Parallel tuples of range starts, range ends and script names, sorted by start."""
    rows = [line.split(" ") for line in (DATA / "scripts.txt").read_text(encoding="utf-8").split("\n") if line]
    return (tuple(int(row[0], 16) for row in rows), tuple(int(row[1], 16) for row in rows), tuple(row[2] for row in rows))


@cache
def lookalikes() -> dict[str, str]:
    """Non-ASCII letter -> the ASCII letters Unicode says it can be mistaken for."""
    rows = [line.split("\t") for line in (DATA / "lookalikes.txt").read_text(encoding="utf-8").split("\n") if line]
    return {source: target for source, target in rows}
