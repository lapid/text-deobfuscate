"""Finds spans that must be left alone: addresses, paths and identifiers.

Inside these, things that look like obfuscation are part of the format: a
percent escape belongs in a URL, a backslash sequence in a file path, a long
run of hex digits in a hash.
"""

import re
from bisect import bisect_left

PATTERNS = (
    re.compile(r"\b(?:https?|ftp)://[^\s<>\"']+", re.IGNORECASE),
    re.compile(r"\bwww\.[^\s<>\"']+", re.IGNORECASE),
    re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b"),
    re.compile(r"(?<![\w])(?:[A-Za-z]:\\|\\\\)[^\s\"<>|]+"),
    re.compile(r"(?<![\w])(?:~|\.{1,2})?/(?:[\w.+-]+/)+[\w.+-]*"),
    re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.IGNORECASE),
    re.compile(r"(?<![0-9A-Za-z])(?:[0-9a-f]{32}|[0-9a-f]{40}|[0-9a-f]{56}|[0-9a-f]{64}|[0-9a-f]{96}|[0-9a-f]{128})(?![0-9A-Za-z])", re.IGNORECASE),
    # Not after "&": "&#115;" is an HTML entity, not a colour.
    re.compile(r"(?<![\w&])#(?:[0-9a-f]{3}|[0-9a-f]{6}|[0-9a-f]{8})\b", re.IGNORECASE),
)


def protected_spans(text: str) -> list[tuple[int, int]]:
    return sorted(match.span() for pattern in PATTERNS for match in pattern.finditer(text))


def merged(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """The same ground covered by sorted spans, with overlapping and touching ones joined."""
    out: list[tuple[int, int]] = []
    for start, end in sorted(spans):
        if out and start <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], end))
        else:
            out.append((start, end))
    return out


def overlaps(start: int, end: int, spans: list[tuple[int, int]]) -> bool:
    """Whether [start, end) touches any span. ``spans`` must be sorted and disjoint (see ``merged``)."""
    index = bisect_left(spans, (end, -1))
    return index > 0 and spans[index - 1][1] > start
