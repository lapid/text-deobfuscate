"""Leetspeak: digits and symbols standing for the letters they resemble ("fr33", "p@ssw0rd").

Decided one token at a time. A token is rewritten only when reading its digits and
symbols as letters gives a known English word. Shorthand that uses a digit for its
sound ("l8r", "b4", "2day", "4" for "for") is not leetspeak and has no such reading.
Short tokens and tokens shaped like a word with a number attached ("test5", "h1")
are rewritten only when the text shows the trick elsewhere.
"""

import re
from bisect import bisect_left, bisect_right
from collections.abc import Iterable
from itertools import islice, product

from text_deobfuscate import resources, scorer
from text_deobfuscate.transforms.base import Candidate, Transform

# Only resemblances by shape. "8" and "2" are left out: they are used for their sound.
READINGS = {"0": "o", "1": "il", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s", "!": "i"}
TOKEN = re.compile(r"(?<![\w@$.,])[A-Za-z0-9@$!]+(?:['’][A-Za-z0-9]+)?(?![\w@$])")
# An amount of money, a number with a unit or an ending, a word or code with a number attached.
PRICE = re.compile(r"\$\d[\d.,]*(?:[kKmMbB]|bn|mm)?")
NUMBER_FIRST = re.compile(r"(\d+)([A-Za-z]+)")
NUMBER_LAST = re.compile(r"([A-Za-z]+)(\d+)")
UNITS = frozenset(
    "st nd rd th s am pm k m g h d x b bn kg km cm mm ml mg px ms hr hrs min mins sec gb mb kb tb hz mph up".split()
)
# Two small letters and a doubled "3" or "0", the commonest doubled letters: "fr33", "tr33".
DOUBLED_LAST = re.compile(r"[a-z]{2}(?:33|00)")
# "4" and "2" before a word are shorthand for "for" and "to" ("4my", "2go").
SOUND_FIRST = re.compile(r"[24]([A-Za-z]+)")
SENTENCE_START = re.compile(r"(?:^|[.!?]\s+|\n\s*)[\"'“‘(]?$")
MAX_READINGS = 32
# Words of evidence needed before a short or number-shaped token is rewritten,
# and before a token is rewritten whose reading is not a known word (a name).
EVIDENCE_FOR_WEAK = 1
EVIDENCE_FOR_UNKNOWN = 2
MIN_STRONG_LENGTH = 4
ACRONYM_LENGTH = 4
SHOUTING = 0.6
# Function words that leetspeak writers keep disguising ("h1", "1s", "4n", "@s"). Two letters
# are too few to judge alone, and "1s", "4m" and "w3" read as a unit or a model elsewhere, so
# they are read only where the text already shows the trick in at least this many longer words.
STOPWORDS = frozenset("a i is it in if as an am at on or so we he me be hi oh no go do to".split())
EVIDENCE_FOR_STOPWORD = 2
# Disguised words in one text before whole numbers in it may be words too ("15", "734").
EVIDENCE_FOR_DIGITS = 4
# How far (in characters) a longer disguised word may sit from a short one and still count.
EVIDENCE_WINDOW = 90
# Or this many in the whole text.
EVIDENCE_FOR_TEXT = 4
# The words in front of which a short token is a unit or a quantity, not a function word:
# "took 1s", "under 1s", "every 1s".
UNIT_CONTEXT = frozenset(
    "in for every took take takes within about under over per of after than around wait waits lasts last was were is are be been has had have".split()
)
# "4" and "@" for the article "a", read only beside disguised text (see ``article``).
LONE_ARTICLE = frozenset({"4", "@"})
COUNTED = frozenset("page step chapter no number level room item row figure section line part tab".split())
MONTHS = frozenset("january february march april may june july august september october november december".split())
UNIT_WORDS = frozenset("mph kph rpm pm am hour hours minute minutes second seconds day days week weeks month months year years".split())
BEFORE_I = frozenset("and but so when if hey hi oh then because that think".split())
AFTER_I = frozenset(
    "am was will have had can could would do did think want need love like hope know see got get just really never always "
    "agree feel wonder assume believe mean guess suppose wish doubt prefer understand thought said saw may might must "
    "shall should also already still often usually sometimes cant dont wont couldnt wouldnt shouldnt didnt hate".split()
)
PER_UNITS = {"hours": {"day", "week"}, "days": {"week", "month"}, "times": {"day", "week", "month", "year"}, "weeks": {"month", "year"}}
MAX_LOOKBACK = 80


class Previous:
    """The word in front of a position, with the interface of a regex match on ``(\\S+)``."""

    __slots__ = ("word", "position")

    def __init__(self, word: str, position: int) -> None:
        self.word, self.position = word, position

    def group(self, _: int = 1) -> str:
        return self.word

    def start(self, _: int = 1) -> int:
        return self.position


def previous_word(text: str, end: int) -> Previous | None:
    """The last run of non-space characters before ``end``, looking back at most ``MAX_LOOKBACK``
    characters, so a long text costs no more per word than a short one."""
    stop = end
    floor = max(0, end - MAX_LOOKBACK)
    while stop > floor and text[stop - 1].isspace():
        stop -= 1
    start = stop
    while start > floor and not text[start - 1].isspace():
        start -= 1
    return Previous(text[start:stop], start) if stop > start else None


def sentence_start(text: str, position: int) -> bool:
    """Whether ``position`` begins a sentence: after a full stop, a line break, or the start."""
    return bool(SENTENCE_START.search(text[max(0, position - MAX_LOOKBACK) : position]))
EDGE = ".,;:()[]\"'“”‘’"
# After a lone "@" these make it the word "at" or an address, not the article.
NOT_ARTICLE_NEXT = frozenset("u ur ya and or of in on is are to for with by from as at but".split())
AFTER_AT = frozenset("the my our your his her their home work noon night midnight school least last first once all any this that these those it us you me him them one".split())
NEXT_WORD = re.compile(r"\s+([A-Za-z0-9@$!]+)")
HEX = re.compile(r"[0-9a-fA-F]+")


# A number with a plural or possessive: "1990's", "P-51's", "Measure 114's".
# Words that stand in front of an amount: "about 70", "over 15".
BEFORE_NUMBER = frozenset("about around over under approximately nearly almost than only just some roughly of by".split())
ENDINGS = frozenset(("nd", "st", "rd", "th", "ll"))
# Words after which a lone "1" is a quantity: "take 1 tablet", "only 1", "with 1".
TAKES_QUANTITY = BEFORE_NUMBER | frozenset(
    "take takes took give gave buy bought order add use used send bring eat ate drink pick has have had need want get got "
    "for with in on at to from per than each every one no".split()
)
ORDINAL = {"st": "1", "nd": "2", "rd": "3"}
NUMBER_PLURAL = re.compile(r"\d+['’]s")


def read(token: str) -> tuple[str, bool] | None:
    """The token with digits and symbols read as letters, and whether that is a known word.

    None if some character has no reading as a letter.
    """
    options = [READINGS.get(char, char) if not char.isalpha() else char for char in token]
    if any(not choice[0].isalpha() and choice[0] not in "'’" for choice in options):
        return None
    letters = [char for char in token if char.isalpha()]
    upper = len(letters) >= 2 and all(char.isupper() for char in letters)
    for combo in islice(product(*options), MAX_READINGS):
        word = "".join(combo)
        if scorer.is_word(word):
            known = resources.words()
            if not token[0].isalpha() and word not in known and word.capitalize() in known:
                # Only known as a name: "@pril".
                word = word.capitalize()
            return (word.upper() if upper else word), True
    word = "".join(choice[0] for choice in options)
    return (word.upper() if upper else word), False


def is_acronym(token: str) -> bool:
    """Short capitals with a digit: "S4C", "1DOL", usually a name or an acronym."""
    letters = [char for char in token if char.isalpha()]
    return len(token) <= ACRONYM_LENGTH and len(letters) >= 2 and all(char.isupper() for char in letters)


def is_weak(token: str) -> bool:
    """Too short, or shaped like something that is normally written with a number."""
    if len(token) == 3 and token[0].isalpha() and token[2].isalpha():
        # "y0u", "n0w": the digit sits inside the word.
        return False
    if len(token) < MIN_STRONG_LENGTH or not any(char.isalpha() for char in token):
        return True
    inside = token.strip("@$!")
    if inside.isalpha():
        # A symbol only at the edge: "@mark" is a handle, "print$" a share name.
        return True
    if DOUBLED_LAST.fullmatch(token):
        return False
    if match := NUMBER_LAST.fullmatch(token):
        return scorer.is_word(match.group(1))
    if match := NUMBER_FIRST.fullmatch(token):
        return len(match.group(2)) <= 2 or scorer.is_word(match.group(2))
    return False


class Leetspeak(Transform):
    name = "leetspeak"
    level = "balanced"
    # The decision is made here, word by word; the scorer has nothing to add for one word.
    judged = False

    def propose(self, text: str) -> Iterable[Candidate]:
        strong: list[Candidate] = []
        weak: list[Candidate] = []
        unknown: list[Candidate] = []
        stop: list[Candidate] = []
        letters = [char for char in text if char.isalpha()]
        # In a text written in capitals the short capitals are just the trick.
        shouting = sum(char.isupper() for char in letters) > SHOUTING * len(letters)
        lone: list[Candidate] = []
        digits: list[Candidate] = []
        short: list[Candidate] = []
        for match in TOKEN.finditer(text):
            # A "!" at the end is punctuation.
            token = match.group().rstrip("!")
            start = match.start()
            if token in LONE_ARTICLE or token == "1":
                lone.append(Candidate(start, start + 1, token))
                continue
            if token.isdigit() and 2 <= len(token) <= 5 and not match.group().endswith("!"):
                digits.append(Candidate(start, start + len(token), token))
                continue
            if token.isalpha() or token.isdigit() or not token or PRICE.fullmatch(token) or NUMBER_PLURAL.fullmatch(token):
                continue
            if len(token) <= 2 and not token.lstrip("@").isalpha() and (stopword := self.stopword(token)):
                if not token[0].isalpha() and sentence_start(text, start):
                    stopword = stopword.capitalize()
                stop.append(Candidate(start, start + len(token), stopword))
                continue
            number_first = NUMBER_FIRST.fullmatch(token)
            if number_first and number_first.group(2).lower() in UNITS and self.is_unit(number_first):
                # "541d" is "said" in a text full of the trick, a duration anywhere else.
                if len(token) >= 3 and token[0] != "0" and token[0].isdigit() and (found := read(token)) and found[1]:
                    short.append(Candidate(start, start + len(token), found[0]))
                continue
            number_last = NUMBER_LAST.fullmatch(token)
            model_like = bool(number_last and len(number_last.group(1)) <= 2 and not DOUBLED_LAST.fullmatch(token))
            if model_like and not self.digit_ending(token):
                # A model or a grade: "G5", "M14", "b4". In a text that is plainly disguised,
                # two digits that read as letters make a word ("w45", "g07").
                tail = number_last.group(2)
                if (len(tail) >= 2 or len(token) >= 3) and all(char in READINGS for char in tail) and (found := read(token)) and found[1] and (token[0].islower() or sentence_start(text, start)):
                    short.append(Candidate(start, start + len(token), found[0]))
                continue
            sound_first = SOUND_FIRST.fullmatch(token)
            if sound_first and scorer.is_word(sound_first.group(1)) and sound_first.group(1).lower() not in ENDINGS:
                continue
            found = read(token)
            if found is None:
                continue
            plain, known = found
            if not token[0].isalpha() and sentence_start(text, start):
                plain = plain[0].upper() + plain[1:]
            candidate = Candidate(start, start + len(token), plain)
            if is_weak(token) or (known and model_like) or (known and is_acronym(token) and not shouting):
                if known:
                    weak.append(candidate)
            elif known:
                strong.append(candidate)
            else:
                unknown.append(candidate)
        yield from strong
        # Words already in plain form ("patty's") are no evidence of the trick.
        shown = sum(text[c.start : c.end] != c.replacement for c in strong)
        if shown >= EVIDENCE_FOR_WEAK:
            yield from weak
        if shown >= EVIDENCE_FOR_UNKNOWN:
            yield from unknown
        # Longer words that show the trick, near the short ones: known words, and names
        # with several digits or symbols inside them ("n!gro71b!al1$").
        marks = [c.start for c in strong if text[c.start : c.end] != c.replacement]
        if shown >= EVIDENCE_FOR_WEAK:
            marks += [c.start for c in weak]
        if shown >= EVIDENCE_FOR_UNKNOWN:
            # Words that read as a word only with their digits, in a text that already shows the trick.
            marks += [c.start for c in short]
        marks += [c.start for c in unknown if self.dense(text[c.start : c.end], c.replacement)]
        marks.sort()
        # Words read so far, by position; one dict for the whole text, so a long text stays linear.
        known = {c.start: c for c in (*strong, *weak)}
        for candidate in stop:
            if self.enough(marks, candidate) and not self.unit_context(text, candidate, known):
                known[candidate.start] = candidate
                yield candidate
        if len(marks) >= EVIDENCE_FOR_DIGITS:
            yield from short
            for candidate in digits:
                word = self.number_word(text, candidate, known)
                if word:
                    if sentence_start(text, candidate.start):
                        word = word.capitalize()
                    known[candidate.start] = Candidate(candidate.start, candidate.end, word)
                    yield known[candidate.start]
        for candidate in lone:
            if self.enough(marks, candidate):
                word = self.lone_word(text, candidate, known, len(marks) >= EVIDENCE_FOR_DIGITS)
                if word:
                    yield Candidate(candidate.start, candidate.end, word)

    @staticmethod
    def is_unit(match: re.Match) -> bool:
        """"2nd", "21st", "5h": a number with its unit or ending. "4nd" fits none."""
        number, suffix = match.group(1), match.group(2).lower()
        if suffix in ORDINAL:
            return number.endswith(ORDINAL[suffix]) and not number.endswith("1" + ORDINAL[suffix])
        return True

    def number_word(self, text: str, candidate: Candidate, decoded: dict) -> str | None:
        """What a whole number stands for in a text that is plainly disguised ("15" is "is", "734" is "tea")."""
        token = candidate.replacement
        following = NEXT_WORD.match(text, candidate.end)
        ahead = (following.group(1) if following else "").lower()
        if ahead in UNIT_WORDS or ahead in MONTHS or text[candidate.end : candidate.end + 1] == "%":
            return None
        if following and following.start(1) in decoded:
            ahead = decoded[following.start(1)].replacement.lower()
        if ahead.isalpha() and (ahead == "percent" or ahead.endswith("s") and not ahead.endswith(("ss", "us", "is"))):
            # "15 finalists", "70 percent": a count.
            return None
        before = previous_word(text, candidate.start)
        if before and before.group(1).strip(EDGE).lower() in BEFORE_NUMBER:
            return None
        if len(token) == 2:
            word = self.stopword(token)
            if word and not self.unit_context(text, Candidate(candidate.start, candidate.end, word), decoded):
                return word
            return None
        found = read(token)
        if found is None or not found[1] or len(set(token)) < 2 or set(token) <= {"0", "1"}:
            # "100", "101": a number, whatever it reads as.
            return None
        return found[0]

    @staticmethod
    def enough(marks: list[int], candidate: Candidate) -> bool:
        """Longer disguised words near the token, or so many in the text that it is plainly the trick.

        ``marks`` is sorted.
        """
        near = bisect_right(marks, candidate.start + EVIDENCE_WINDOW) - bisect_left(marks, candidate.start - EVIDENCE_WINDOW)
        return near >= EVIDENCE_FOR_STOPWORD or len(marks) >= EVIDENCE_FOR_TEXT

    @staticmethod
    def dense(token: str, plain: str) -> bool:
        """A token with at least two digits or symbols among at least three letters, reading as
        a word-shaped name with a vowel, and not a hex string."""
        symbols = sum(not char.isalpha() for char in token)
        return (
            symbols >= 2
            and len(token) - symbols >= 3
            and any(vowel in plain.lower() for vowel in "aeiouy")
            and not HEX.fullmatch(token)
        )

    @staticmethod
    def digit_ending(token: str) -> bool:
        """A word ending in several digits that all read as letters, and the word is known ("th47")."""
        match = NUMBER_LAST.fullmatch(token)
        if not match or len(token) < MIN_STRONG_LENGTH or len(match.group(2)) < 2 or any(char not in READINGS for char in match.group(2)):
            return False
        found = read(token)
        return found is not None and found[1]

    @staticmethod
    def stopword(token: str) -> str | None:
        """The function word a short disguised token stands for, with its first capital kept."""
        if token.startswith("@") and token[1:].isalpha():
            # A handle.
            return None
        found = read(token)
        if found is None or found[0].lower() not in STOPWORDS or not found[1]:
            return None
        word = found[0].lower()
        return word.capitalize() if token[0].isupper() else word

    @staticmethod
    def unit_context(text: str, candidate: Candidate, decoded: dict) -> bool:
        """Whether the word before the token makes it a unit or quantity ("took 1s", "in 1s")."""
        before = previous_word(text, candidate.start)
        if before is None:
            return False
        previous = before.group(1).strip(EDGE)
        word = candidate.replacement.lower()
        if before.start(1) in decoded:
            previous = decoded[before.start(1)].replacement
        elif previous == "1" and word == "am":
            # "1 4m": the pronoun, then "am".
            return False
        if previous.isdigit():
            # "5 1s" is a duration, "Room 4 1s" is not; "10 7o 3" is neither.
            if word not in {"is", "as", "am"}:
                return False
            earlier = previous_word(text, before.start(1))
            if earlier is None:
                return True
            noun = decoded[earlier.start(1)].replacement if earlier.start(1) in decoded else earlier.group(1).strip(EDGE)
            return noun.lower() not in COUNTED
        return previous.lower() in UNIT_CONTEXT and word in {"is", "as", "am"}

    @staticmethod
    def lone_word(text: str, candidate: Candidate, decoded: dict, dense: bool = False) -> str | None:
        """What a lone "4", "@" or "1" stands for in front of disguised text, if the words around fit."""
        before = previous_word(text, candidate.start)
        previous = before.group(1).strip(EDGE).lower() if before else ""
        if before and before.start(1) in decoded:
            previous = decoded[before.start(1)].replacement.lower()
        following = NEXT_WORD.match(text, candidate.end)
        if following is None:
            return None
        ahead = decoded[following.start(1)].replacement if following.start(1) in decoded else following.group(1)
        ahead_low = ahead.strip(EDGE).lower()
        if not ahead_low.isalpha():
            return None
        if candidate.replacement == "1":
            opens = before is None or sentence_start(text, candidate.start) or previous in BEFORE_I
            verb = ahead_low in AFTER_I or (ahead_low.endswith(("ed", "ly")) and scorer.is_word(ahead_low))
            if dense and not (previous.isdigit() or previous in COUNTED or previous in MONTHS or previous in TAKES_QUANTITY):
                # In a text full of the trick the pronoun may stand in front of any word that is
                # no unit, month or plural noun, unless the word before it asks for a quantity.
                opens = True
                verb = verb or (
                    scorer.is_word(ahead_low)
                    and ahead_low not in UNIT_WORDS
                    and ahead_low not in MONTHS
                    and not (ahead_low.endswith("s") and not ahead_low.endswith(("ss", "us", "is")))
                )
            return "I" if opens and verb else None
        if previous in COUNTED or previous.isdigit() or previous in MONTHS:
            return None
        if previous in PER_UNITS and ahead_low in PER_UNITS[previous]:
            # "two hours 4 day": a rate.
            return "a"
        if ahead_low in UNIT_WORDS or ahead_low in MONTHS or (ahead_low.endswith("s") and not ahead_low.endswith(("ss", "us", "is"))):
            return None
        # A lone "4" or "@" in a text that is plainly disguised, in front of a singular word,
        # is the article. Not before a pronoun or a function word ("4 you", "@ the").
        if ahead_low in AFTER_AT or ahead_low in NOT_ARTICLE_NEXT or len(ahead_low) < 2:
            return None
        return "a"
