"""Morse code: letters as dots and dashes, separated by spaces."""

import re
from collections.abc import Iterable

from text_deobfuscate.transforms.base import Candidate, Transform

CODES = {
    ".-": "a", "-...": "b", "-.-.": "c", "-..": "d", ".": "e", "..-.": "f", "--.": "g", "....": "h", "..": "i",
    ".---": "j", "-.-": "k", ".-..": "l", "--": "m", "-.": "n", "---": "o", ".--.": "p", "--.-": "q", ".-.": "r",
    "...": "s", "-": "t", "..-": "u", "...-": "v", ".--": "w", "-..-": "x", "-.--": "y", "--..": "z",
    "-----": "0", ".----": "1", "..---": "2", "...--": "3", "....-": "4", ".....": "5", "-....": "6",
    "--...": "7", "---..": "8", "----.": "9", ".-.-.-": ".", "--..--": ",", "..--..": "?", ".----.": "'",
    "-.-.--": "!", "-..-.": "/", "-.--.": "(", "-.--.-": ")", ".-...": "&", "---...": ":", "-.-.-.": ";",
    "-...-": "=", ".-.-.": "+", "-....-": "-", ".-..-.": '"', ".--.-.": "@",
}

# Written as text, the dot and dash are "." and "-" in ASCII, the middle dot and minus
# sign in the typographic form the ITU prints, and the underscore where a hyphen would
# be read as punctuation. En and em dashes turn up where an editor has "improved" a hyphen.
MARKS = str.maketrans({"·": ".", "•": ".", "−": "-", "–": "-", "—": "-", "_": "-"})
MARK = r".\-_·•−–—"
SEPARATOR = r" \t\n|/"
# A stretch of nothing but marks and the characters that separate them.
RUN = re.compile(rf"[{MARK}][{MARK}{SEPARATOR}]*[{MARK}]")

# Two conventions share the slash, and the same run can be read either way.
# Usually a single space parts letters and a slash, a pipe or a wider gap parts words.
# But the slash is also written between letters, with a double slash between words.
# A line break parts words however the slash is used: a long message is written out
# one word to a line.
WIDE = r"\s*\n\s*|\s{2,}"
BREAKS = {
    "words": (re.compile(rf"\s*(?:\|\|?|//?)\s*|{WIDE}"), re.compile(r"\s+")),
    "letters": (re.compile(rf"\s*(?:\|\|?|//)\s*|{WIDE}"), re.compile(r"[\s/]+")),
}


def decode(run: str, slash: str = "words") -> str | None:
    """The text a Morse run stands for, or None if any group is not a code.

    ``slash`` says which convention to read the run under. A line break inside a run
    is read as a word break, so a Morse message split over lines comes back as one line.
    """
    word_break, letter_break = BREAKS[slash]
    words: list[str] = []
    for word in word_break.split(run.translate(MARKS).strip()):
        letters = [CODES.get(group) for group in letter_break.split(word) if group]
        if not letters or any(letter is None for letter in letters):
            return None
        words.append("".join(letters))
    return " ".join(words) or None


class Morse(Transform):
    """Dots and dashes for letters. Capitals are not written in Morse and cannot come back.

    Ordinary writing holds runs of dots and dashes too: an ellipsis, a rule under a
    heading, a command's "--option", a row of underscores, a markdown table's dashes
    and pipes. Those decode to a letter or two at most, which the minimum on letters
    refuses; anything longer has to read as English.

    Where a run can be read under either slash convention, both readings are proposed
    and the score chooses. The wrong one runs the words together, which scores worse.
    A double slash settles it, though: it parts words where the single slash parts
    letters, and means nothing at all under the other convention. Without that hint the
    engine picked letter-by-letter words and the separator transform then glued them
    back together, which left "sockets ?" with the mark adrift.
    """

    name = "morse"
    min_letters = 10
    # A rule of dashes or a dotted leader can sit inside a path or an address.
    ignores_protection = True

    def propose(self, text: str) -> Iterable[Candidate]:
        for match in RUN.finditer(text):
            seen = set()
            # Of two readings that score alike the engine keeps the first.
            readings = ("letters", "words") if "//" in match.group() else ("words", "letters")
            for slash in readings:
                if slash == "letters" and "/" not in match.group():
                    continue
                decoded = decode(match.group(), slash)
                if decoded and decoded not in seen:
                    seen.add(decoded)
                    yield Candidate(match.start(), match.end(), decoded)
