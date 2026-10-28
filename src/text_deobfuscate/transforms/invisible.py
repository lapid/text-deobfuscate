"""Invisible characters: ones slipped inside words, and ones carrying hidden text."""

import re
import unicodedata
from collections.abc import Iterable

from text_deobfuscate.scripts import SHARED, script_of
from text_deobfuscate.transforms.base import CHUNK, Candidate, Transform

# Zero-width space, non-joiner, joiner, word joiner, byte-order mark, soft
# hyphen, Mongolian vowel separator, and the invisible maths operators.
INVISIBLE = frozenset("\u200b\u200c\u200d\u2060\ufeff\u00ad\u180e\u2061\u2062\u2063\u2064")
JOINERS = frozenset("\u200c\u200d")
TAGS = re.compile("[\U000e0020-\U000e007e]+\U000e007f?")
BLACK_FLAG = "\U0001f3f4"


def needs_it(char: str) -> bool:
    """Whether a neighbouring character can legitimately need an invisible one.

    Several non-Latin scripts use joiners to shape letters or mark word breaks,
    and emoji sequences are built with them.
    """
    if not char:
        return False
    if script_of(char) not in SHARED | {"Latin"}:
        return True
    return unicodedata.category(char) in ("So", "Sk") or char == "\ufe0f"


class ZeroWidth(Transform):
    name = "zero-width"
    judged = False

    def propose(self, text: str) -> Iterable[Candidate]:
        for match in CHUNK.finditer(text):
            chunk = match.group()
            if not any(char in INVISIBLE for char in chunk):
                continue
            visible = [char for char in chunk if char not in INVISIBLE]
            kept, seen = [], 0
            for char in chunk:
                if char not in INVISIBLE:
                    kept.append(char)
                    seen += 1
                    continue
                before = visible[seen - 1] if seen else ""
                after = visible[seen] if seen < len(visible) else ""
                if needs_it(before) or needs_it(after):
                    kept.append(char)
            cleaned = "".join(kept)
            if cleaned != chunk:
                yield Candidate(match.start(), match.end(), cleaned)


class TagCharacters(Transform):
    """Removes text hidden in Unicode tag characters and reports what it said."""

    name = "tag-characters"
    judged = False
    # Hidden text is removed wherever it sits, including on the end of a URL.
    ignores_protection = True

    def propose(self, text: str) -> Iterable[Candidate]:
        for match in TAGS.finditer(text):
            # A black flag followed by tags is a real emoji (regional flags).
            if match.start() and text[match.start() - 1] == BLACK_FLAG:
                continue
            hidden = "".join(chr(ord(char) - 0xE0000) for char in match.group() if char != "\U000e007f")
            yield Candidate(match.start(), match.end(), "", hidden=hidden)
