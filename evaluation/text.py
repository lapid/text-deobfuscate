"""Plain-text helpers for building the corpus: sentence splitting and HTML to text."""

import re
from html.parser import HTMLParser

# A full stop after one of these does not end a sentence.
ABBREVIATIONS = frozenset(
    "mr mrs ms dr prof st sr jr vs etc inc ltd co corp gen col lt sgt capt rev hon mt no vol fig ca approx est "
    "e.g i.e a.m p.m u.s u.k a.k.a jan feb mar apr jun jul aug sep sept oct nov dec".split()
)

BOUNDARY = re.compile(r"([.!?]+[\"”’')\]]*)\s+(?=[\"“‘'(\[]?[A-Z0-9])")


def split_sentences(paragraph: str) -> list[str]:
    """Split a paragraph into sentences. Imperfect by design; a fragment is still clean text."""
    out: list[str] = []
    start = 0
    for match in BOUNDARY.finditer(paragraph):
        before = paragraph[start : match.start()]
        last_word = before.rsplit(None, 1)[-1].lower().lstrip("(\"“'") if before.strip() else ""
        if match.group(1).startswith(".") and (last_word in ABBREVIATIONS or len(last_word) == 1):
            continue
        out.append(paragraph[start : match.end()].strip())
        start = match.end()
    tail = paragraph[start:].strip()
    if tail:
        out.append(tail)
    return out


class _Paragraphs(HTMLParser):
    BLOCKS = frozenset({"p", "li", "h1", "h2", "h3", "h4", "blockquote", "div", "br"})
    SKIPPED = frozenset({"pre", "script", "style"})

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.paragraphs: list[str] = []
        self.current: list[str] = []
        self.skipping = 0

    def flush(self) -> None:
        text = " ".join("".join(self.current).split())
        if text:
            self.paragraphs.append(text)
        self.current = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in self.SKIPPED:
            self.skipping += 1
        if tag in self.BLOCKS:
            self.flush()

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIPPED and self.skipping:
            self.skipping -= 1
        if tag in self.BLOCKS:
            self.flush()

    def handle_data(self, data: str) -> None:
        if not self.skipping:
            self.current.append(data)


def html_paragraphs(markup: str) -> list[str]:
    """Paragraphs of visible text. Code blocks are dropped; inline code is kept."""
    parser = _Paragraphs()
    parser.feed(markup)
    parser.close()
    parser.flush()
    return parser.paragraphs
