"""More samples for the places the tool does worst, added after the first build.

Everything here comes from random streams of its own (see ``build.py``), so no earlier
row changes.

- ``carried``: an encoded sentence inside a message with a label, quotes or a signature.
  The older "partial" samples encode a run of words in the middle of a sentence; these
  encode a whole sentence and leave plain text around it, the way a pasted cipher
  usually arrives.
- ``accented``: accents written the other way round, on every vowel of a word.
- ``deep_stacks``: three layers, and more of the pairs that did worst.
- ``CATEGORIES``: clean sentences holding words that are other words when reversed,
  shifted or rotated, which the decoders must not touch.
"""

import unicodedata
from collections.abc import Callable, Iterator
from random import Random

from text_deobfuscate import resources
from evaluation import obfuscator

CARRIERS = (
    "Hi, the note says: {}",
    "Message: {}",
    'He wrote "{}" on the board.',
    "{} Please reply soon.",
    "FYI - {} (see attached)",
    "Subject: {}",
    "Re: {}\n\nThanks, Anna",
    "Here is the text again: {}\n\nCan you read it?",
    "Note to self: {}",
    "Check this out! {}",
    "> {}",
    "Password hint: {}",
    "She sent me this yesterday ({}) and I still do not get it.",
    "Translation needed:\n{}\nThanks in advance.",
    "[{}]",
    "Quote of the day - {}",
)
CARRIED_TRICKS = ("rot13", "rot47", "caesar", "atbash", "reverse", "word-reverse", "base32", "base64", "hex")
PER_CARRIED = 40

VOWELS = {
    "a": "áàäâãå", "e": "éèëêẽ", "i": "íìïîĩ", "o": "óòöôõ", "u": "úùüûũ", "y": "ýÿ",
    "A": "ÁÀÄÂÃ", "E": "ÉÈËÊ", "I": "ÍÌÏÎ", "O": "ÓÒÖÔÕ", "U": "ÚÙÜÛ",
    "c": "ç", "n": "ñ", "s": "š", "z": "ž",
}
ACCENTED = 120

DEEP_STACKS = (
    ("base64", "rot13", "base64"),
    ("zero-width", "base64", "rot13"),
    ("hex", "base64", "reverse"),
    ("url-percent", "html-entity", "base64"),
    ("zero-width", "leetspeak", "homoglyph"),
    ("rot13", "reverse", "base64"),
)
EXTRA_STACKS = (("homoglyph", "leetspeak"), ("reverse", "base64"), ("rot13", "leetspeak"), ("base64", "leetspeak"))
PER_STACK = 40


def carried(corpus: list[dict], rng: Random) -> Iterator[tuple[str, str, str, str, str, dict]]:
    """(category, mode, obfuscated, expected, trick, corpus row)."""
    pool = [row for row in corpus if 30 <= len(row["text"]) <= 130 and "\n" not in row["text"]]
    for trick in CARRIED_TRICKS:
        made = 0
        for row in rng.sample(pool, k=min(len(pool), PER_CARRIED * 4)):
            carrier = rng.choice(CARRIERS)
            encoded = obfuscator.apply(trick, row["text"], rng)
            if encoded == row["text"]:
                continue
            yield f"{trick} in-context", "partial", carrier.format(encoded), carrier.format(row["text"]), trick, row
            made += 1
            if made == PER_CARRIED:
                break


def accent_vowels(text: str, rng: Random) -> str:
    """Accent most of the vowels in some of the words, the way spam lookalike text does."""
    out = []
    for word in text.split(" "):
        if len(word) >= 3 and rng.random() < 0.45:
            share = rng.choice((0.6, 1.0))
            word = "".join(
                rng.choice(VOWELS[char]) if char in VOWELS and rng.random() < share else char for char in word
            )
        out.append(word)
    return " ".join(out)


def accented(corpus: list[dict], rng: Random) -> Iterator[tuple[str, str, str, str, str, dict]]:
    pool = [row for row in corpus if 30 <= len(row["text"]) <= 160 and row["text"].isascii()]
    made = 0
    for row in rng.sample(pool, k=min(len(pool), ACCENTED * 4)):
        text = accent_vowels(row["text"], rng)
        if text != row["text"] and unicodedata.normalize("NFC", text) == text:
            yield "accent-substitution", "whole", text, row["text"], "accent-substitution", row
            made += 1
            if made == ACCENTED:
                return


def deep_stacks(corpus: list[dict], rng: Random) -> Iterator[tuple[str, str, str, str, str, dict]]:
    pool = [row for row in corpus if len(row["text"]) <= 100]
    for stack in (*DEEP_STACKS, *EXTRA_STACKS):
        for row in rng.sample(pool, k=PER_STACK):
            yield "+".join(stack), "stacked", obfuscator.apply_stack(stack, row["text"], rng), row["text"], "|".join(stack), row


JOINERS = ((".", 8), ("-", 2), ("_", 2), ("*", 2), (",", 2))
JOINED = 120


def join_characters(text: str, symbol: str) -> str:
    """Every word of more than one character written as its characters joined by the symbol."""
    return " ".join(symbol.join(word) if len(word) > 1 else word for word in text.split(" "))


def joined(corpus: list[dict], rng: Random) -> Iterator[tuple[str, str, str, str, str, dict]]:
    """A symbol between every character of every word, punctuation on the word included."""
    pool = [row for row in corpus if 30 <= len(row["text"]) <= 150 and "\n" not in row["text"] and "  " not in row["text"]]
    symbols = [symbol for symbol, weight in JOINERS for _ in range(weight)]
    made = 0
    for row in rng.sample(pool, k=min(len(pool), JOINED * 3)):
        symbol = rng.choice(symbols)
        yield f"separator every character ({symbol})", "whole", join_characters(row["text"], symbol), row["text"], "separator", row
        made += 1
        if made == JOINED:
            return


# --- clean sentences with words that look encoded ------------------------------------

def _pairs(shift: Callable[[str], str], *, minimum: int = 3) -> list[tuple[str, str]]:
    words = resources.words()
    return sorted(
        (word, other)
        for word in words
        if len(word) >= minimum and word.isascii() and word.isalpha() and word.islower() and (other := shift(word)) != word
        and other in words
    )


def _rot13(word: str) -> str:
    return word.translate(str.maketrans("abcdefghijklmnopqrstuvwxyz", "nopqrstuvwxyzabcdefghijklm"))


def _caesar3(word: str) -> str:
    return "".join(chr((ord(char) - 97 + 3) % 26 + 97) for char in word)


def _atbash(word: str) -> str:
    return "".join(chr(219 - ord(char)) for char in word)


COMMON = frozenset(
    "the of and to in is it you that he was for on are with as his they at be this have from or one had by word but not what all were we when your can said there use an each which she do how their if will up other about out many then them these so some her would make like him into time has look two more write go see number no way could people my than first water been call who oil its now find long down day did get come made may part".split()
)


def _templates(pairs: list[tuple[str, str]], frames: tuple[str, ...]) -> Callable[[Random], str]:
    # Prefer pairs where at least one word is common, so the sentence reads naturally.
    likely = [pair for pair in pairs if pair[0] in COMMON or pair[1] in COMMON] or pairs

    def make(rng: Random) -> str:
        first, second = rng.choice(likely)
        return rng.choice(frames).format(a=first, b=second)

    return make


FRAMES = (
    "Both {a} and {b} are listed in the dictionary.",
    "She wrote {a} on one card and {b} on the other.",
    "The words {a} and {b} appear twice in the poem.",
    "He said {a}, then he said {b}, and then he left.",
    "We talked about {a} and about {b} all afternoon.",
    "Is it {a} or {b}? Nobody in the office could tell.",
    "The teacher put {a} and {b} on the board.",
)
PALINDROMES = (
    "A man, a plan, a canal: Panama.", "Was it a car or a cat I saw?", "Never odd or even.", "Madam, in Eden I'm Adam.",
    "Step on no pets.", "Do geese see God?", "No lemon, no melon.", "Rise to vote, sir.", "Too hot to hoot.",
    "Mr. Owl ate my metal worm.", "Evil is a name of a foeman, as I live.", "Draw, O coward!", "Stressed desserts.",
)

ABBREVIATIONS = (
    "The U.S.A. and the U.K. signed it at 5 p.m. on Monday, e.g. in the morning.",
    "J.R.R. Tolkien and C.S. Lewis wrote about it, i.e. about myths.",
    "Version 1.2.3 replaced 1.2.2 on 2.0.1 of the schedule, as agreed.",
    "Countries: U.S.A, U.K, E.U, U.N and N.A.T.O all signed the text.",
    "U.S.A U.K E.U U.N N.A.T.O",
    "Dr. A.B. Smith met Ph.D. students at 3.30 p.m. in the U.S. office.",
    "Send it to a.b@example.com, c.d@example.org and e.f@example.net today.",
    "The values are 1.5, 2.5, 3.5 and 4.5 for the four samples shown.",
    "I.B.M. and A.T.&T. were listed beside H.P. in the old directory.",
)

CATEGORIES: dict[str, tuple[Callable[[Random], str], int]] = {
    "word-pairs-reversed": (_templates(_pairs(lambda w: w[::-1]), FRAMES), 40),
    "word-pairs-rot13": (_templates(_pairs(_rot13), FRAMES), 40),
    "word-pairs-caesar": (_templates(_pairs(_caesar3), FRAMES), 30),
    "word-pairs-atbash": (_templates(_pairs(_atbash), FRAMES), 30),
    "palindromes": (lambda rng: rng.choice(PALINDROMES), 13),
    "dotted-abbreviations": (lambda rng: rng.choice(ABBREVIATIONS), len(ABBREVIATIONS)),
}
