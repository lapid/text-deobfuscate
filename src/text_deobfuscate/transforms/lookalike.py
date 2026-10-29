"""Letters swapped for look-alikes: from other alphabets, or with accents added.

Both tricks are decided one word at a time. A word is rewritten when it is not
English as written and its plain-letter reading is, or when the rest of the
text shows the same trick clearly enough that a name or typo should follow suit.
"""

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from itertools import islice, product

from text_deobfuscate import resources, scorer
from text_deobfuscate.scripts import script_of
from text_deobfuscate.transforms.base import Candidate, Transform
from text_deobfuscate.transforms.leet import read as read_leet

# Letters of any alphabet, with apostrophes allowed inside.
# Symbols that stand for a letter only when written inside a word ("¢ard", "confi¡rm").
SYMBOLS = {"¢": "c", "₫": "d", "∨": "v", "¡": "i"}
# Letters of any alphabet, with apostrophes allowed inside. "¡" opens a Spanish
# sentence, so it counts only after a letter.
WORD = re.compile(r"(?:[^\W\d_]|[¢₫∨]|(?<=[^\W\d_])¡)+(?:['’][^\W\d_]+)*")
CYRILLIC_VARIANT = re.compile(r"(CYRILLIC (?:SMALL|CAPITAL) LETTER \w+) WITH ")
# "ꜰʀᴇᴇ ᴘʀɪᴢᴇ", which real phishing mail uses. Unicode files the small capitals as Latin
# letters, so they take the same path as an accent, but they are a look-alike alphabet
# and are recorded as one. Only the recorded name differs; the decision is the same.
SMALL_CAPITAL = "LATIN LETTER SMALL CAPITAL "
LATIN_NAME = re.compile(
    r"LATIN (?:SMALL|CAPITAL) LETTER (?:SCRIPT )?([A-Z])(?: WITH .+)?$|LATIN LETTER SMALL CAPITAL ([A-Z])$"
)

# Look-alikes used in real phishing mail that Unicode's table does not list,
# because the resemblance is loose. Found in the dev half of the BitCore set.
LOOSE = {
    "τ": "t", "η": "n", "κ": "k", "ᴨ": "n", "ң": "h", "п": "n", "ʍ": "m", "β": "b", "ŉ": "n", "ҥ": "h", "к": "k",
    "ω": "w", "ĸ": "k", "Ƿ": "p", "щ": "w", "ᚱ": "r", "ժ": "d", "в": "b", "μ": "u", "н": "h", "Ի": "r", "қ": "k",
    "џ": "u", "Ա": "u", "м": "m", "т": "t", "г": "r", "ш": "w", "ρ": "p", "ν": "v", "χ": "x", "ε": "e", "σ": "o",
    "ᴦ": "r",
}
# Letters seen standing for more than one plain letter, or for another one than
# Unicode lists. Found in the dev half of the hand-disguised sentences. The first
# reading that gives a known word is used.
SEVERAL = {
    "þ": "pb", "ϸ": "pb", "ɕ": "cg", "ө": "eo", "ԑ": "se", "ғ": "fr", "ſ": "fs", "ϱ": "pe",
    "ƅ": "b", "ϝ": "f", "ϵ": "e", "ς": "c", "ϛ": "c", "ɥ": "u", "ʘ": "o", "µ": "u",
    "ե": "t", "ր": "n", "թ": "p", "և": "u", "Ւ": "t", "υ": "uv",
}
# English words that are normally written with accents. They are correct as they stand, so no
# level rewrites them: "résumé" is not a disguise of "resume". Lower case. A lone "à" is left
# out on purpose: real phishing mail writes it for "a" (14 of 3,000 real dev rows).
ACCENTED_ENGLISH = frozenset("""
    abbé attaché blasé cafés café château châteaux cliché clichéd clichés communiqué consommé coup crème
    débâcle débutante décor déjà dénouement détente divorcée élan élite émigré entrée entrées exposé façade
    fête fiancé fiancée fiancés flambé gruyère habitué jalapeño jalapeños mêlée matinée naïf naïve naïvely naïveté
    outré papier passé pâté pâtés piñata piñatas protégé protégée protégés raison résumé résumés risqué roué
    rôle sauté séance señor señora señorita smörgåsbord soirée soupçon touché über voilà
""".split())
# Unicode files every upright stroke under "l". Which letter is meant depends on the word.
STROKES = frozenset("lIi")
MAX_READINGS = 32


def readings(char: str) -> tuple[list[str], str] | None:
    """Plain letters a character may stand for, and whether it is "accent" or "foreign".

    None if it has no plain reading.
    """
    base = unicodedata.normalize("NFD", char)[0]
    if char in SYMBOLS:
        return [SYMBOLS[char]], "foreign"
    if several := SEVERAL.get(base):
        return list(several), "accent" if script_of(base) == "Latin" else "foreign"
    if unicodedata.category(char) == "Nl":
        # Roman numerals that have their own character: "ⅼ", "ⅴ", "ⅿ".
        folded = unicodedata.normalize("NFKC", char)
        return ([folded], "foreign") if len(folded) == 1 and folded.isascii() else None
    if base.isascii():
        found, kind = (base, "accent") if base.isalpha() else (None, "")
    else:
        strict = resources.lookalikes()
        found = strict.get(char) or strict.get(base) or LOOSE.get(char) or LOOSE.get(base)
        if found is None and (named := LATIN_NAME.match(unicodedata.name(base, ""))):
            found = (named.group(1) or named.group(2)).lower()
        if found is None and (variant := CYRILLIC_VARIANT.match(unicodedata.name(base, ""))):
            # "ӷ", "ҫ", "ҟ": a Cyrillic letter with a hook or stroke reads as the letter without.
            without = readings(unicodedata.lookup(variant.group(1)))
            found = without[0][0].lower() if without else None
        if found == "rn":
            found = "m"
        # Small capitals are Latin by script but are a look-alike alphabet, not an accent
        # on a letter, and the accent rules ask for evidence they can never supply: an
        # accent counts as evidence only when it is an odd one sitting on a plain letter,
        # which a small capital is not. A wholly small-capitals text went unread.
        if unicodedata.name(char, "").startswith(SMALL_CAPITAL):
            kind = "foreign"
        else:
            kind = "accent" if script_of(base) == "Latin" else "foreign"
    if not found or len(found) != 1:
        # Ligatures such as "œ" are ordinary spelling, not a disguise.
        return None
    if found in STROKES:
        # Capitals are read as "I" first, small letters as "i" or "l" as listed.
        first = "I" if char.isupper() else found.lower()
        return [first, "i" if first == "l" else "l"], kind
    if char.isupper() and found.islower():
        found = found.upper()
    return [found], kind


@dataclass(frozen=True, slots=True)
class Reading:
    start: int
    end: int
    plain: str
    # The plain reading is a known English word.
    known: bool
    # The word contains letters of another alphabet / only accents on Latin letters.
    foreign: bool
    # Every letter is from another alphabet, so it could be a real foreign word.
    wholly_foreign: bool
    # Its accents are ones English and its neighbours do not use (as in "yōũr"),
    # sitting on plain letters. Such a word is suspicious on its own.
    odd_accents: bool
    # It uses a symbol or a Roman numeral for a letter. Only a known word is rewritten.
    symbols: bool = False
    # It is written in small capitals, a look-alike alphabet Unicode files as Latin.
    small_caps: bool = False


# What may sit next to the word inside one leetspeak token.
LEET_TOKEN = re.compile(r"(?:[^\W_]|[@$!])+")


def known_with_digits(match: re.Match) -> bool:
    """Whether the word is part of a token that also uses digits for letters ("аcc0unt")

    and the token is a known word once both tricks are read.
    """
    text = match.string
    for token in LEET_TOKEN.finditer(text, max(0, match.start() - 40), match.end() + 40):
        if token.start() <= match.start() and match.end() <= token.end():
            break
    else:
        return False
    chunk = token.group().rstrip("!")
    if chunk == match.group():
        return False
    plain = []
    for char in chunk:
        if char.isascii():
            plain.append(char)
        elif (found := readings(char)) is not None:
            plain.append(found[0][0])
        else:
            return False
    found = read_leet("".join(plain))
    return found is not None and found[1]


def read_word(match: re.Match) -> Reading | None:
    """The plain-letter reading of a word with non-ASCII letters, if it has one."""
    word = match.group()
    options: list[list[str]] = []
    kinds: set[str] = set()
    for char in word:
        if char.isascii() or char == "’":
            options.append([char])
            continue
        found = readings(char)
        if found is None:
            return None
        options.append(found[0])
        kinds.add(found[1])
    if not kinds:
        return None
    if word[0] == "µ":
        # The unit prefix: "µm", "µg".
        return None
    symbols = [char for char in word if char in SYMBOLS or unicodedata.category(char) == "Nl"]
    if symbols and len(word) - len(symbols) < 2:
        # A real Roman numeral, or a currency sign beside a letter.
        return None
    plain = "".join(choice[0] for choice in options)
    known = False
    for combo in islice(product(*options), MAX_READINGS):
        if scorer.is_word("".join(combo)):
            plain, known = "".join(combo), True
            break
    if not known:
        known = known_with_digits(match)
    letters = [char for char in word if char.isalpha()]
    return Reading(
        match.start(), match.end(), plain, known, "foreign" in kinds,
        all(not char.isascii() and script_of(unicodedata.normalize("NFD", char)[0]) != "Latin" for char in letters),
        all(unicodedata.normalize("NFD", char)[0].isascii() for char in word) and any(ord(char) > 0xFF for char in word),
        bool(symbols),
        any(unicodedata.name(char, "").startswith(SMALL_CAPITAL) for char in word),
    )


def decide(text: str, loose: bool = False) -> list[tuple[Reading, str]]:
    """The words to rewrite, each with the name of the trick.

    ``loose`` also rewrites a lone word with everyday accents, and a lone "a" or "I"
    in another alphabet, when the plain reading is English. That catches more real
    disguises and also changes some correct foreign spellings.
    """
    plain_words: list[str] = []
    found: list[tuple[Reading, str]] = []
    unreadable_foreign = 0
    for match in WORD.finditer(text):
        word = match.group()
        if word.isascii():
            plain_words.append(word)
            continue
        if scorer.is_word(word) or word.lower() in ACCENTED_ENGLISH:
            continue
        reading = read_word(match)
        if reading is None or (reading.wholly_foreign and not reading.known):
            if all(script_of(char) != "Latin" for char in word if char.isalpha()):
                unreadable_foreign += 1
        if reading is not None:
            found.append((reading, word))
    if not found:
        return []

    # The text must be English around the suspicious words, or have no plain words at all.
    multi = [word for word in plain_words if len(word) > 1]
    # The loose rules act on less evidence, so they ask for more English around it.
    needed = 0.7 if loose else 0.5
    english = sum(scorer.is_word(word) for word in multi)
    # Disguised words that read as English count too; a text may have few plain words left.
    readable = [reading for reading, word in found if len(word) > 1]
    english += sum(reading.known for reading in readable)
    if multi and english < (len(multi) + len(readable)) * needed:
        return decide(text) if loose else []

    def strong(item: tuple[Reading, str]) -> bool:
        return item[0].known and len(item[1]) > 1

    # How clearly the text shows each trick: words that become English once read plainly.
    foreign_evidence = sum(strong(item) and item[0].foreign for item in found)
    odd_accent_evidence = sum(
        strong(item) and not item[0].foreign and item[0].odd_accents and item[1][0].islower() for item in found
    )
    # Capitalised words are left out: two Vietnamese names ("Trần", "Hồ") read as English words.
    evidence = foreign_evidence + odd_accent_evidence
    # A text in another language has words in its alphabet that have no English reading.
    another_language = unreadable_foreign >= max(1, foreign_evidence)

    out = []
    for reading, word in found:
        if reading.foreign:
            if reading.wholly_foreign and len(word) == 1:
                # "a" and "I" written in another alphabet; too little to act on alone.
                ok = reading.known and (foreign_evidence >= 1 or loose) and not another_language
            elif reading.wholly_foreign:
                ok = not another_language and (reading.known or foreign_evidence >= 2)
            else:
                ok = reading.known or foreign_evidence >= 1
            name = "homoglyph"
        else:
            if reading.known and reading.odd_accents:
                ok = word[0].islower() or evidence >= 1
            elif reading.known:
                # Everyday accents ("café", "à") and letters such as "ł" are normal
                # spelling unless the text shows the trick elsewhere.
                ok = evidence >= 1 and (len(word) > 1 or evidence >= 2)
                ok = ok or (loose and len(word) > 1 and word[0].islower())
            else:
                ok = evidence >= 3
            name = "homoglyph" if reading.small_caps else "accent-substitution"
        if reading.symbols and not reading.known:
            ok = False
        if ok and reading.plain != word:
            out.append((reading, name))
    return out


class Lookalike(Transform):
    # The decision is made here, word by word; the scorer has nothing to add for one word.
    judged = False
    # Both tricks are decided together, each word counting as evidence for the others.
    group = "lookalike"

    def __init__(self, name: str, level: str = "balanced", loose: bool = False) -> None:
        self.name = name
        self.level = level
        self.loose = loose

    def propose(self, text: str) -> Iterable[Candidate]:
        if text.isascii():
            return
        for reading, name in decide(text, self.loose):
            if name == self.name:
                yield Candidate(reading.start, reading.end, reading.plain)
