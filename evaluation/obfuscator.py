"""Applies obfuscation tricks to clean text, to make test pairs with known answers.

Every function takes the clean text and a ``random.Random`` and returns the
obfuscated text. The clean text is always the expected output.
"""

import base64
import codecs
import re
import unicodedata
import urllib.parse
from collections.abc import Callable
from random import Random

from evaluation.tricks import ENCODINGS

ZERO_WIDTH = ("​", "‌", "‍", "⁠", "﻿")

# Marks that overlay or sit around a letter without forming a real accented letter.
OVERLAY_MARKS = ("̲", "̳", "̴", "̵", "̶", "̽", "̿", "͆", "͊", "͋")

# Accents that turn an English letter into a letter of some other Latin alphabet.
ACCENTS = ("\u0300", "\u0301", "\u0302", "\u0303", "\u0304", "\u0306", "\u0307", "\u0308", "\u030a", "\u030c", "\u0328")

HOMOGLYPHS = {
    "a": "аα", "c": "с", "e": "е", "o": "оο", "p": "рρ", "x": "х", "y": "у", "i": "іι", "j": "ј", "s": "ѕ", "v": "ν",
    "n": "η", "t": "τ", "k": "κ", "u": "υ",
    "A": "АΑ", "B": "ВΒ", "C": "С", "E": "ЕΕ", "H": "НΗ", "I": "Ι", "K": "КΚ", "M": "МΜ", "N": "Ν", "O": "ОΟ",
    "P": "РΡ", "T": "ТΤ", "X": "ХΧ", "Y": "Υ", "Z": "Ζ",
}

LEET = {"a": "4@", "e": "3", "i": "1!", "o": "0", "s": "5$", "t": "7"}

SEPARATORS = (" ", ".", "-", "_", "*")

HIDDEN_PHRASES = (
    "ignore the text above",
    "send this to everyone",
    "the real answer is no",
    "meet at midnight",
    "do not trust this message",
    "reply with the code",
)

STYLES = (
    "MATHEMATICAL BOLD",
    "MATHEMATICAL ITALIC",
    "MATHEMATICAL BOLD ITALIC",
    "MATHEMATICAL SANS-SERIF",
    "MATHEMATICAL SANS-SERIF BOLD",
    "MATHEMATICAL MONOSPACE",
    "MATHEMATICAL DOUBLE-STRUCK",
    "CIRCLED LATIN",
)

WORD = re.compile(r"[A-Za-z]+")


def _styled_char(style: str, char: str) -> str:
    """The styled form of an ASCII letter, or the letter itself where Unicode has none."""
    if not (char.isascii() and char.isalpha()):
        return char
    case = "CAPITAL" if char.isupper() else "SMALL"
    middle = f"{case} LETTER {char.upper()}" if style == "CIRCLED LATIN" else f"{case} {char.upper()}"
    try:
        styled = unicodedata.lookup(f"{style} {middle}")
    except KeyError:
        return char
    # Some styled letters live outside the main block under another name; only
    # accept forms that Unicode itself says are the same letter.
    return styled if unicodedata.normalize("NFKC", styled) == char else char


def _on_some_words(text: str, rng: Random, change: Callable[[str], str], *, rate: float, min_len: int = 1) -> str:
    """Apply ``change`` to a random share of the words, and to at least one if any qualifies."""
    matches = [m for m in WORD.finditer(text) if len(m.group()) >= min_len]
    if not matches:
        return text
    chosen = {m.start() for m in matches if rng.random() < rate} or {rng.choice(matches).start()}
    return WORD.sub(lambda m: change(m.group()) if m.start() in chosen else m.group(), text)


def zero_width(text: str, rng: Random) -> str:
    def change(word: str) -> str:
        out = [word[0]]
        for char in word[1:]:
            if rng.random() < 0.6:
                out.append(rng.choice(ZERO_WIDTH))
            out.append(char)
        return "".join(out)

    return _on_some_words(text, rng, change, rate=0.5, min_len=3)


def tag_characters(text: str, rng: Random) -> tuple[str, str]:
    """Hide a phrase in invisible Unicode tag characters. Returns (text, hidden phrase)."""
    phrase = rng.choice(HIDDEN_PHRASES)
    hidden = "".join(chr(0xE0000 + ord(char)) for char in phrase)
    words = text.split(" ")
    position = rng.randint(0, len(words))
    if position == 0:
        return hidden + text, phrase
    words[position - 1] += hidden
    return " ".join(words), phrase


def styled_alphabet(text: str, rng: Random) -> str:
    style = rng.choice(STYLES)
    return "".join(_styled_char(style, char) for char in text)


def fullwidth(text: str, rng: Random) -> str:
    return "".join(chr(ord(char) + 0xFEE0) if "!" <= char <= "~" else char for char in text)


def html_entity(text: str, rng: Random) -> str:
    variant = rng.choice(("decimal", "hex", "mixed"))
    if variant == "decimal":
        return "".join(f"&#{ord(char)};" for char in text)
    if variant == "hex":
        return "".join(f"&#x{ord(char):x};" for char in text)
    named = {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}
    out = [named.get(char) or (f"&#{ord(char)};" if rng.random() < 0.4 else char) for char in text]
    if "".join(out) == text:
        out[0] = f"&#{ord(text[0])};"
    return "".join(out)


def url_percent(text: str, rng: Random) -> str:
    if rng.random() < 0.5:
        return urllib.parse.quote(text, safe="")
    return "".join(f"%{byte:02X}" for byte in text.encode())


def backslash_escape(text: str, rng: Random) -> str:
    if text.isascii() and rng.random() < 0.5:
        return "".join(f"\\x{ord(char):02x}" for char in text)
    return "".join(f"\\u{ord(char):04x}" if ord(char) < 0x10000 else f"\\U{ord(char):08x}" for char in text)


def base64_standard(text: str, rng: Random) -> str:
    return base64.b64encode(text.encode()).decode()


def base64_url(text: str, rng: Random) -> str:
    encoded = base64.urlsafe_b64encode(text.encode()).decode()
    return encoded.rstrip("=") if rng.random() < 0.5 else encoded


def hex_bytes(text: str, rng: Random) -> str:
    data = text.encode()
    variant = rng.choice(("plain", "upper", "spaced", "0x"))
    if variant == "plain":
        return data.hex()
    if variant == "upper":
        return data.hex().upper()
    if variant == "spaced":
        return " ".join(f"{byte:02x}" for byte in data)
    return " ".join(f"0x{byte:02x}" for byte in data)


def binary(text: str, rng: Random) -> str:
    return (" " if rng.random() < 0.7 else "").join(f"{byte:08b}" for byte in text.encode())


def decimal_codes(text: str, rng: Random) -> str:
    return rng.choice((" ", ", ", ",")).join(str(byte) for byte in text.encode())


def rot13(text: str, rng: Random) -> str:
    return codecs.encode(text, "rot13")


def caesar(text: str, rng: Random) -> str:
    shift = rng.choice([n for n in range(1, 26) if n != 13])

    def rotate(char: str) -> str:
        if "a" <= char <= "z":
            return chr((ord(char) - 97 + shift) % 26 + 97)
        if "A" <= char <= "Z":
            return chr((ord(char) - 65 + shift) % 26 + 65)
        return char

    return "".join(rotate(char) for char in text)


def reverse(text: str, rng: Random) -> str:
    return text[::-1]


def combining_marks(text: str, rng: Random) -> str:
    if rng.random() < 0.5:
        mark = rng.choice(("̶", "̲", "̵"))
        return _on_some_words(text, rng, lambda word: "".join(char + mark for char in word), rate=0.6)

    def stack(word: str) -> str:
        return "".join(char + "".join(rng.choice(OVERLAY_MARKS) for _ in range(rng.randint(1, 3))) for char in word)

    return _on_some_words(text, rng, stack, rate=0.6)


def homoglyph(text: str, rng: Random) -> str:
    def change(word: str) -> str:
        spots = [i for i, char in enumerate(word) if char in HOMOGLYPHS]
        if not spots:
            return word
        chosen = {i for i in spots if rng.random() < 0.6} or {rng.choice(spots)}
        return "".join(rng.choice(HOMOGLYPHS[char]) if i in chosen else char for i, char in enumerate(word))

    out = _on_some_words(text, rng, change, rate=0.5)
    return out if out != text else WORD.sub(lambda m: change(m.group()), text)


def accent_substitution(text: str, rng: Random) -> str:
    """Swap letters for accented forms, as real phishing mail does."""

    def change(word: str) -> str:
        out = []
        for char in word:
            accented = unicodedata.normalize("NFC", char + rng.choice(ACCENTS))
            out.append(accented if len(accented) == 1 and rng.random() < 0.35 else char)
        return "".join(out)

    for _ in range(10):
        out = _on_some_words(text, rng, change, rate=0.6)
        if out != text:
            return out
    return text


def leetspeak(text: str, rng: Random) -> str:
    def change(word: str) -> str:
        spots = [i for i, char in enumerate(word) if char.lower() in LEET]
        if not spots:
            return word
        chosen = {i for i in spots if rng.random() < 0.7} or {rng.choice(spots)}
        return "".join(rng.choice(LEET[char.lower()]) if i in chosen else char for i, char in enumerate(word))

    out = _on_some_words(text, rng, change, rate=0.6, min_len=4)
    return out if out != text else WORD.sub(lambda m: change(m.group()), text)


def separator(text: str, rng: Random) -> str:
    sep = rng.choice(SEPARATORS)
    if sep == " " and rng.random() < 0.5:
        # Whole text spaced out, with a wider gap marking the original word breaks.
        return "   ".join(" ".join(word) for word in text.split(" "))
    return _on_some_words(text, rng, sep.join, rate=0.4, min_len=4)


def repeated_chars(text: str, rng: Random) -> str:
    def change(word: str) -> str:
        spots = [i for i, char in enumerate(word) if char in "aeiouAEIOU"] or list(range(len(word)))
        chosen = set(rng.sample(spots, k=min(len(spots), rng.randint(1, 2))))
        return "".join(char * rng.randint(3, 5) if i in chosen else char for i, char in enumerate(word))

    return _on_some_words(text, rng, change, rate=0.4, min_len=3)


# The generator's own lists. The deobfuscator has separate, shorter ones, so that
# these samples measure what it misses as well as what it knows.
SHORTHAND = {
    "you": ("u",), "your": ("ur",), "are": ("r",), "for": ("4",), "to": ("2",), "later": ("l8r",),
    "great": ("gr8",), "before": ("b4",), "please": ("pls", "plz"), "thanks": ("thx", "thnx", "tnx"),
    "tomorrow": ("tmrw", "2moro", "2mrw"), "tonight": ("2nite",), "today": ("2day",), "people": ("ppl",),
    "because": ("bc", "cuz", "coz"), "message": ("msg",), "text": ("txt",), "about": ("abt",),
    "though": ("tho",), "through": ("thru",), "love": ("luv",), "night": ("nite",), "see": ("c",),
    "be": ("b",), "someone": ("sum1", "some1"), "anyone": ("any1",), "everyone": ("every1",),
    "forever": ("4ever",), "wait": ("w8",), "mate": ("m8",), "and": ("n",), "have": ("hv",),
    "with": ("w/",), "what": ("wat", "wot"), "good": ("gd",),
    "weekend": ("wknd",), "really": ("rly",), "know": ("kno",), "from": ("frm",), "just": ("jst",),
    "birthday": ("bday",), "why": ("y",), "okay": ("k",), "tonite": ("2nite",), "between": ("btwn",),
    "without": ("w/o",), "something": ("sth", "smth"), "probably": ("prob", "prolly"), "would": ("wud",),
    "could": ("cud",), "should": ("shud",), "going": ("goin",), "little": ("lil",), "enough": ("enuf",),
}
COMMON_MISSPELLINGS = {
    "receive": "recieve", "definitely": "definately", "separate": "seperate", "until": "untill",
    "which": "wich", "because": "becuase", "their": "thier", "believe": "beleive",
    "government": "goverment", "tomorrow": "tommorow", "beginning": "begining", "different": "diffrent",
    "friend": "freind", "really": "realy", "address": "adress", "business": "buisness",
    "calendar": "calender", "necessary": "neccessary", "occurred": "occured", "the": "teh",
    "and": "adn", "with": "wiht", "that": "taht", "about": "abuot", "people": "poeple",
    "would": "woudl", "should": "shoudl", "weird": "wierd", "known": "konwn", "first": "frist",
    "other": "ohter", "between": "bewteen", "another": "antoher", "there": "tehre", "after": "afetr",
    "national": "natoinal", "several": "severall", "following": "folowing", "including": "inculding",
    "however": "howver", "during": "durring", "important": "importnat", "although": "allthough",
}
KEYBOARD_ROWS = ("qwertyuiop", "asdfghjkl", "zxcvbnm")
EMOJI_WORDS = {
    "love": "❤️", "heart": "❤️", "fire": "🔥", "money": "💰", "phone": "📱", "call": "📞", "email": "📧",
    "house": "🏠", "home": "🏠", "car": "🚗", "gift": "🎁", "key": "🔑", "world": "🌍", "sun": "☀️",
    "moon": "🌙", "star": "⭐", "dog": "🐶", "cat": "🐱", "book": "📖", "books": "📚", "computer": "💻",
    "birthday": "🎂", "cake": "🍰", "medicine": "💊", "coffee": "☕", "pizza": "🍕", "beer": "🍺",
    "bank": "🏦", "eyes": "👀", "music": "🎵", "rain": "🌧️", "snow": "❄️", "tree": "🌳", "flower": "🌸",
    "fish": "🐟", "bird": "🐦", "horse": "🐴", "king": "👑", "school": "🏫", "hospital": "🏥",
    "church": "⛪", "plane": "✈️", "train": "🚆", "ship": "🚢", "bus": "🚌", "water": "💧", "city": "🏙️",
    "mountain": "⛰️", "baby": "👶", "police": "👮", "camera": "📷", "film": "🎬", "football": "⚽",
    "game": "🎮", "letter": "✉️", "idea": "💡", "time": "⏰", "wine": "🍷", "island": "🏝️", "bridge": "🌉",
}


def _on_listed_words(text: str, rng: Random, table: dict, rate: float) -> str:
    """Swap a random share of the words found in ``table``, and at least one if any is there."""
    matches = [m for m in WORD.finditer(text) if m.group().lower() in table]
    if not matches:
        return text
    chosen = {m.start() for m in matches if rng.random() < rate} or {rng.choice(matches).start()}

    def change(match: re.Match) -> str:
        if match.start() not in chosen:
            return match.group()
        options = table[match.group().lower()]
        return options if isinstance(options, str) else rng.choice(options)

    return WORD.sub(change, text)


def shorthand(text: str, rng: Random) -> str:
    return _on_listed_words(text, rng, SHORTHAND, rate=0.7)


def emoji_word(text: str, rng: Random) -> str:
    return _on_listed_words(text, rng, EMOJI_WORDS, rate=0.7)


def _typo(word: str, rng: Random) -> str:
    """One slip of the fingers: two letters swapped, one doubled, dropped, or a neighbouring key."""
    spot = rng.randint(1, len(word) - 2)
    kind = rng.choice(("swap", "swap", "double", "drop", "neighbour"))
    if kind == "swap":
        return word[:spot] + word[spot + 1] + word[spot] + word[spot + 2 :]
    if kind == "double":
        return word[:spot] + word[spot] + word[spot:]
    if kind == "drop":
        return word[:spot] + word[spot + 1 :]
    for row in KEYBOARD_ROWS:
        at = row.find(word[spot].lower())
        if at >= 0:
            return word[:spot] + row[at - 1 if at else 1] + word[spot + 1 :]
    return word


def misspelling(text: str, rng: Random) -> str:
    def change(word: str) -> str:
        if word.lower() in COMMON_MISSPELLINGS:
            return COMMON_MISSPELLINGS[word.lower()]
        return _typo(word, rng) if len(word) >= 5 and word.islower() else word

    listed = [m for m in WORD.finditer(text) if m.group().lower() in COMMON_MISSPELLINGS]
    if listed and rng.random() < 0.5:
        return _on_listed_words(text, rng, COMMON_MISSPELLINGS, rate=0.7)
    return _on_some_words(text, rng, change, rate=0.2, min_len=5)


# Tricks from the coverage survey.

RLO, PDF = "‮", "‬"
BIDI_MARKS = ("‎", "‏")
# Brackets are drawn mirrored inside right-to-left text.
MIRRORED = str.maketrans("()[]{}<>", ")(][}{><")
OTHER_INVISIBLE = ("ㅤ", "ᅟ", "ᅠ", "ﾠ", "឴", "឵", "᠋", "᠌", "᠍", "᠏")


def bidi_control(text: str, rng: Random) -> str:
    """Text stored in one order and shown in another (Trojan Source), or bidi marks inside words."""
    kind = rng.choice(("words", "span", "marks"))
    if kind == "words":
        # Each chosen word is stored backwards inside a right-to-left override, so it displays the right way round.
        return _on_some_words(text, rng, lambda word: RLO + word[::-1] + PDF, rate=0.5, min_len=3)
    if kind == "span":
        return RLO + text[::-1].translate(MIRRORED) + PDF

    def change(word: str) -> str:
        spot = rng.randint(1, len(word) - 1)
        return word[:spot] + rng.choice(BIDI_MARKS) + word[spot:]

    return _on_some_words(text, rng, change, rate=0.5, min_len=3)


def control_chars(text: str, rng: Random) -> str:
    """A stray letter followed by a backspace or delete character, which hides it (Bad Characters)."""

    def change(word: str) -> str:
        spot = rng.randint(1, len(word) - 1)
        return word[:spot] + rng.choice("abcdefghijklmnopqrstuvwxyz") + rng.choice("\b\x7f") + word[spot:]

    return _on_some_words(text, rng, change, rate=0.4, min_len=3)


def other_invisible(text: str, rng: Random) -> str:
    """Characters Unicode marks as ignorable that are not zero-width spaces: Hangul fillers and others."""

    def change(word: str) -> str:
        spot = rng.randint(1, len(word) - 1)
        return word[:spot] + rng.choice(OTHER_INVISIBLE) + word[spot:]

    return _on_some_words(text, rng, change, rate=0.5, min_len=3)


def variation_selector(text: str, rng: Random) -> tuple[str, str]:
    """Hide a phrase in variation selectors, one byte each, after a visible character (Butler, 2025).

    Returns (text, hidden phrase).
    """
    phrase = rng.choice(HIDDEN_PHRASES)
    hidden = "".join(chr(0xFE00 + byte) if byte < 16 else chr(0xE0100 + byte - 16) for byte in phrase.encode())
    if rng.random() < 0.5:
        return f"{text} \U0001f60a{hidden}", phrase
    words = text.split(" ")
    position = rng.randrange(len(words))
    words[position] += hidden
    return " ".join(words), phrase


def _soft_breaks(pieces: list[str], rng: Random) -> str:
    """Join encoded pieces into lines of at most 76 characters, ending each with "=" (RFC 2045)."""
    width = rng.choice((40, 60, 76))
    lines, line = [], ""
    for piece in pieces:
        if len(line) + len(piece) > width - 1:
            lines.append(line + "=")
            line = ""
        line += piece
    return "\n".join([*lines, line])


def quoted_printable(text: str, rng: Random) -> str:
    share = rng.choice((1.0, 0.5))
    pieces = [f"={byte:02X}" if byte in b"=" or byte > 126 or rng.random() < share else chr(byte) for byte in text.encode()]
    return _soft_breaks(pieces, rng) if rng.random() < 0.5 else "".join(pieces)


def _utf8_pieces(text: str, size: int) -> list[bytes]:
    """The text's UTF-8 bytes in pieces of at most ``size``, never splitting a character."""
    pieces, piece = [], b""
    for char in text:
        encoded = char.encode()
        if piece and len(piece) + len(encoded) > size:
            pieces.append(piece)
            piece = b""
        piece += encoded
    return [*pieces, piece] if piece else pieces


def mime_word(text: str, rng: Random) -> str:
    """MIME encoded words, as in an email subject line (RFC 2047)."""
    charset = rng.choice(("UTF-8", "utf-8"))
    if rng.random() < 0.5:
        return " ".join(f"=?{charset}?B?{base64.b64encode(piece).decode()}?=" for piece in _utf8_pieces(text, 45))

    def q(piece: bytes) -> str:
        return "".join("_" if byte == 32 else chr(byte) if chr(byte).isalnum() and byte < 128 else f"={byte:02X}" for byte in piece)

    return " ".join(f"=?{charset}?Q?{q(piece)}?=" for piece in _utf8_pieces(text, 30))


def base32(text: str, rng: Random) -> str:
    encoded = base64.b32encode(text.encode()).decode()
    return encoded.rstrip("=") if rng.random() < 0.3 else encoded


def octal_escape(text: str, rng: Random) -> str:
    """Bytes as a backslash and octal digits, in the four notations that occur in real code.

    ``padded`` is C and printf; ``minimal`` drops the leading zeros, so a space is
    ``\\40``; ``zero`` is the JavaScript form with ``\\0`` in front; ``mixed`` writes some
    of the bytes as hex, which obfuscated scripts do to break up the pattern.
    """
    data = text.encode()
    match rng.choice(("padded", "minimal", "zero", "mixed")):
        case "padded":
            return "".join(f"\\{byte:03o}" for byte in data)
        case "minimal":
            return "".join(f"\\{byte:o}" for byte in data)
        case "zero":
            return "".join(f"\\0{byte:03o}" for byte in data)
    # Every third byte in hex, so that a short text still holds both notations.
    return "".join(f"\\x{byte:02x}" if index % 3 == 0 else f"\\{byte:03o}" for index, byte in enumerate(data))


def rot47(text: str, rng: Random) -> str:
    return "".join(chr(33 + (ord(char) - 33 + 47) % 94) if "!" <= char <= "~" else char for char in text)


def atbash(text: str, rng: Random) -> str:
    def flip(char: str) -> str:
        if "a" <= char <= "z":
            return chr(219 - ord(char))
        if "A" <= char <= "Z":
            return chr(155 - ord(char))
        return char

    return "".join(flip(char) for char in text)


MORSE = {
    "a": ".-", "b": "-...", "c": "-.-.", "d": "-..", "e": ".", "f": "..-.", "g": "--.", "h": "....", "i": "..",
    "j": ".---", "k": "-.-", "l": ".-..", "m": "--", "n": "-.", "o": "---", "p": ".--.", "q": "--.-", "r": ".-.",
    "s": "...", "t": "-", "u": "..-", "v": "...-", "w": ".--", "x": "-..-", "y": "-.--", "z": "--..",
    "0": "-----", "1": ".----", "2": "..---", "3": "...--", "4": "....-", "5": ".....", "6": "-....", "7": "--...",
    "8": "---..", "9": "----.", ".": ".-.-.-", ",": "--..--", "?": "..--..", "'": ".----.", "!": "-.-.--",
    "/": "-..-.", "(": "-.--.", ")": "-.--.-", "&": ".-...", ":": "---...", ";": "-.-.-.", "=": "-...-",
    "+": ".-.-.", "-": "-....-", '"': ".-..-.", "@": ".--.-.",
}


# How Morse is written down when it is written as text. Letters are nearly always
# parted by a single space and words by a slash or a wider gap, but the slash is also
# used between letters, with a double slash between words. The dot and dash are "." and
# "-" in ASCII, "·" and "−" in the typographic form the ITU prints, and the
# underscore stands in for the dash where a hyphen would be read as punctuation.
MORSE_GAPS = ((" ", " / "), (" ", "   "), (" ", "/"), (" ", " | "), (" ", "\n"), ("/", "//"))
MORSE_MARKS = ((".", "-"), (".", "_"), ("·", "−"))


def morse(text: str, rng: Random) -> str:
    """Morse code, in one of the ways it is written as text. Loses capitals.

    Text with a character Morse has no code for is returned unchanged.
    """
    words = text.lower().split()
    if not words or any(char not in MORSE for word in words for char in word):
        return text
    letter_gap, word_gap = rng.choice(MORSE_GAPS)
    dot, dash = rng.choice(MORSE_MARKS)
    marks = str.maketrans({".": dot, "-": dash})
    return word_gap.join(letter_gap.join(MORSE[char].translate(marks) for char in word) for word in words)


def word_reverse(text: str, rng: Random) -> str:
    """Each word written backwards, the words left in order (FlipAttack's second mode)."""
    return " ".join(word[::-1] for word in text.split(" "))


def _letters_as(text: str, first_capital: int) -> str:
    """Letters replaced by the capital-only symbol alphabet that starts at ``first_capital``."""
    return "".join(chr(first_capital + ord(char.upper()) - 65) if char.isascii() and char.isalpha() else char for char in text)


def squared_letters(text: str, rng: Random) -> str:
    """Negative circled, negative squared or squared capitals: 🅒, 🅲, 🄲."""
    return _letters_as(text, rng.choice((0x1F150, 0x1F170, 0x1F130)))


def regional_indicator(text: str, rng: Random) -> str:
    """Regional indicator symbols, the letters flags are made of: 🇨🇱🇮🇨🇰."""
    return _letters_as(text, 0x1F1E6)


def _superscript_letters() -> dict[str, str]:
    table: dict[str, str] = {}
    for code in (*range(0x2B0, 0x2E5), *range(0x1D2C, 0x1DC0), *range(0x2070, 0x20A0), *range(0x10780, 0x107BB)):
        char = chr(code)
        name = unicodedata.name(char, "")
        folded = unicodedata.normalize("NFKC", char)
        if ("MODIFIER LETTER SMALL" in name or "SUPERSCRIPT LATIN SMALL" in name) and len(folded) == 1 and "a" <= folded <= "z":
            table.setdefault(folded, char)
    return table


SUPERSCRIPT = _superscript_letters()


def superscript(text: str, rng: Random) -> str:
    """Small superscript letters, as text generators make them: ᶜˡⁱᶜᵏ. Loses capitals."""
    return "".join(SUPERSCRIPT.get(char.lower(), char) if char.isascii() else char for char in text)


TRICKS: dict[str, Callable[[str, Random], str]] = {
    "zero-width": zero_width,
    "styled-alphabet": styled_alphabet,
    "fullwidth": fullwidth,
    "html-entity": html_entity,
    "url-percent": url_percent,
    "backslash-escape": backslash_escape,
    "base64": base64_standard,
    "base64url": base64_url,
    "hex": hex_bytes,
    "binary": binary,
    "decimal-codes": decimal_codes,
    "rot13": rot13,
    "caesar": caesar,
    "reverse": reverse,
    "combining-marks": combining_marks,
    "homoglyph": homoglyph,
    "accent-substitution": accent_substitution,
    "leetspeak": leetspeak,
    "separator": separator,
    "repeated-chars": repeated_chars,
    "shorthand": shorthand,
    "misspelling": misspelling,
    "emoji-word": emoji_word,
    "bidi-control": bidi_control,
    "control-chars": control_chars,
    "other-invisible": other_invisible,
    "quoted-printable": quoted_printable,
    "mime-word": mime_word,
    "base32": base32,
    "octal-escape": octal_escape,
    "rot47": rot47,
    "atbash": atbash,
    "morse": morse,
    "word-reverse": word_reverse,
    "squared-letters": squared_letters,
    "regional-indicator": regional_indicator,
    "superscript": superscript,
}

# Layered recipes, outermost trick first. The innermost is applied first.
STACKS = (
    ("base64", "base64"),
    ("rot13", "base64"),
    ("hex", "base64"),
    ("base64", "hex"),
    ("reverse", "base64"),
    ("base64", "reverse"),
    ("url-percent", "html-entity"),
    ("base64", "leetspeak"),
    ("base64", "homoglyph"),
    ("rot13", "leetspeak"),
    ("zero-width", "base64"),
    ("zero-width", "homoglyph"),
    ("zero-width", "leetspeak"),
    ("styled-alphabet", "leetspeak"),
    ("homoglyph", "leetspeak"),
    ("homoglyph", "accent-substitution"),
)


def apply(trick: str, text: str, rng: Random) -> str:
    """Obfuscate the whole text with one trick."""
    return TRICKS[trick](text, rng)


def apply_stack(stack: tuple[str, ...], text: str, rng: Random) -> str:
    for trick in reversed(stack):
        text = TRICKS[trick](text, rng)
    return text


def apply_partial(trick: str, text: str, rng: Random) -> str | None:
    """Obfuscate one run of words inside the text. None if the text is too short for it."""
    words = text.split(" ")
    need_words, need_chars = (3, 12) if trick in ENCODINGS else (1, 4)
    for _ in range(20):
        size = rng.randint(need_words, max(need_words, min(6, len(words) - 1)))
        if size >= len(words):
            return None
        start = rng.randint(0, len(words) - size)
        span = " ".join(words[start : start + size])
        if len(span) < need_chars:
            continue
        changed = TRICKS[trick](span, rng)
        if changed != span:
            return " ".join([*words[:start], changed, *words[start + size :]])
    return None
