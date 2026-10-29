import re
from collections.abc import Iterable

from text_deobfuscate import scorer
from text_deobfuscate.transforms.base import Candidate, Transform
from text_deobfuscate.transforms.runs import Chunk, chunks, foreign_runs, reads_as_english

# A long unbroken token of letters and digits may be another encoding, rotated.
ENCODED = re.compile(
    r"(?<![A-Za-z0-9+/=_-])(?=[A-Za-z0-9+/_-]*[a-z])(?=[A-Za-z0-9+/_-]*[A-Z0-9])[A-Za-z0-9+/_-]{16,}={0,2}(?![A-Za-z0-9+/=_-])"
)
LOWER = "abcdefghijklmnopqrstuvwxyz"
ATBASH = str.maketrans(LOWER + LOWER.upper(), LOWER[::-1] + LOWER.upper()[::-1])


def table(shift: int) -> dict[int, int]:
    """Translation table that moves each letter ``shift`` places back through the alphabet."""
    moved = LOWER[-shift:] + LOWER[:-shift]
    return str.maketrans(LOWER + LOWER.upper(), moved + moved.upper())


class WholeTextCipher(Transform):
    """A cipher that rewrites every character the same way, wherever it stands.

    Rot47 and Atbash have no key and no variants, so there is nothing to search:
    the text, or a run of words that is not English, is simply put through the
    cipher and judged. Both are their own inverse, so clean text put through
    either becomes gibberish and is refused by the score.
    """

    # A short unknown word can turn into an English word by chance.
    min_letters = 10

    def convert(self, text: str) -> str:
        raise NotImplementedError

    def worth_proposing(self, span: str, converted: str) -> bool:
        """Whether the conversion of ``span`` is worth offering to the engine.

        Two guards that Caesar does not need. Rot47 moves punctuation and digits as
        well as letters, so converting English *destroys* its letters, and what is
        left can read as perfect English on a sample of two: "Teleiodes ... is a moth
        of the family Gelechiidae" enciphers to text whose only word-shaped token is a
        word, a coverage of 2 letters out of 2. Decoding is then judged against a
        clean text that scored badly for its Latin names, and enciphering it wins.

        So: the conversion may not lose letters, since deciphering reveals letters and
        enciphering buries them, and there must be enough of them for the share inside
        known words to mean anything. Atbash keeps every letter, so it passes the first
        test by equality.
        """
        if scorer.letter_count(converted) < scorer.letter_count(span):
            return False
        covered, total = scorer.word_coverage(converted)
        return total >= self.min_letters and covered / total >= 0.6

    def may_grow_over(self, chunk: Chunk) -> bool:
        """Whether a run may be extended over this neighbouring chunk.

        Only over a chunk that is no evidence of English on its own: it holds no
        word of more than one letter, as the scorer counts them, and it becomes an
        English word under the cipher. A chunk with a real word in it stops the run.
        """
        words = [token for token in scorer.TOKEN.findall(chunk.text) if len(token) > 1]
        if any(scorer.is_word(word) for word in words):
            return False
        return reads_as_english(self.convert(chunk.text))

    def propose(self, text: str) -> Iterable[Candidate]:
        found = chunks(text)
        runs = foreign_runs(found)
        if not runs:
            # Every word is English as it stands, so there is nothing enciphered here.
            # Checked before anything else: this is the common case, and converting and
            # scoring the whole text for it is the greater part of what these two cost.
            return
        # As in Caesar: the whole text is only worth converting when most of it is not
        # English. Text that already reads is not a cipher of something else.
        foreign = sum(found[i].letters for first, last in runs for i in range(first, last + 1))
        if foreign * 2 >= sum(chunk.letters for chunk in found):
            whole = self.convert(text)
            if self.worth_proposing(text, whole):
                yield Candidate(0, len(text), whole)
        for first, last in runs:
            # A name stays unknown under the cipher, so it cannot mark where a run ends.
            while first <= last and not reads_as_english(self.convert(found[first].text)):
                first += 1
            while last >= first and not reads_as_english(self.convert(found[last].text)):
                last -= 1
            if first > last:
                continue
            # Rot47 moves punctuation and digits as well as letters, so a short word
            # becomes a chunk with no letters in it at all ("@?" is "on"), or one whose
            # only English word is a stray capital ("@A6?" holds an "A"). A run cannot
            # start or end on the first, and the second looks like plain English, so
            # both are left behind. The run is grown outwards over them instead.
            while first > 0 and self.may_grow_over(found[first - 1]):
                first -= 1
            while last < len(found) - 1 and self.may_grow_over(found[last + 1]):
                last += 1
            start, end = found[first].start, found[last].end
            span = self.convert(text[start:end])
            if self.worth_proposing(text[start:end], span):
                yield Candidate(start, end, span)


class Rot47(WholeTextCipher):
    """Every printable ASCII character moved 47 places on, punctuation included."""

    name = "rot47"

    def convert(self, text: str) -> str:
        return "".join(chr(33 + (ord(char) - 33 + 47) % 94) if "!" <= char <= "~" else char for char in text)


class Atbash(WholeTextCipher):
    """The alphabet reversed: "a" for "z", "b" for "y"."""

    name = "atbash"

    def convert(self, text: str) -> str:
        return text.translate(ATBASH)


class Lazy:
    """``reads[i]``, worked out the first time it is asked for.

    Most checks stop at the first chunk that fails, so a long text of random characters never
    has all of its chunks read under every shift.
    """

    def __init__(self, compute) -> None:
        self.compute = compute
        self.known: dict[int, bool] = {}

    def __getitem__(self, index: int) -> bool:
        if index not in self.known:
            self.known[index] = self.compute(index)
        return self.known[index]


class Caesar(Transform):
    """Letters shifted along the alphabet. Rot13 is the shift by 13."""

    # A short unknown word can turn into an English word under some shift by chance.
    min_letters = 10

    def __init__(self, name: str, shifts: tuple[int, ...], encoded_tokens: bool = False) -> None:
        self.name = name
        self.tables = [table(shift) for shift in shifts]
        self.encoded_tokens = encoded_tokens

    def propose(self, text: str) -> Iterable[Candidate]:
        if self.encoded_tokens:
            for match in ENCODED.finditer(text):
                yield Candidate(match.start(), match.end(), match.group().translate(self.tables[0]))

        found = chunks(text)
        runs = foreign_runs(found)
        if not runs:
            return
        # When most of the text is not English, the whole of it may be shifted,
        # including stray words that happen to read as English either way.
        foreign = sum(found[i].letters for first, last in runs for i in range(first, last + 1))
        mostly_foreign = foreign * 2 >= sum(chunk.letters for chunk in found)
        for moved in self.tables:
            if mostly_foreign:
                whole = text.translate(moved)
                covered, total = scorer.word_coverage(whole)
                if total and covered / total >= 0.6:
                    yield Candidate(0, len(text), whole)
            english = Lazy(lambda i, moved=moved: reads_as_english(found[i].text.translate(moved)))
            # Shifted text can contain words that are also English as they stand
            # ("or" for "be"). Join runs that have only such words between them.
            joined: list[list[int]] = []
            for first, last in runs:
                if joined and all(english[i] or not found[i].letters for i in range(joined[-1][1] + 1, first)):
                    joined[-1][1] = last
                else:
                    joined.append([first, last])
            for first, last in joined:
                # Names stay unknown under any shift, so they cannot mark where a run ends.
                while first <= last and not english[first]:
                    first += 1
                while last >= first and not english[last]:
                    last -= 1
                if first > last:
                    continue
                outside = (i for i in range(len(found)) if (i < first or i > last) and found[i].letters)
                if all(english[i] or not found[i].plain for i in outside):
                    # Everything else fits the same shift: the whole text was shifted.
                    start, end = 0, len(text)
                else:
                    start, end = found[first].start, found[last].end
                span = text[start:end].translate(moved)
                letters = [char for char in span if char.isalpha()]
                if sum(not char.isascii() for char in letters) * 10 > len(letters):
                    # Shifting moves plain letters only. A phrase full of accented letters
                    # is another language ("Quánguó Nánzǐ"), not shifted English.
                    continue
                covered, total = scorer.word_coverage(span)
                if total and covered / total >= 0.6:
                    yield Candidate(start, end, span)
