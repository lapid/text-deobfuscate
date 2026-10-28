"""The transforms the engine runs, in no particular order."""

from text_deobfuscate.transforms.base import Candidate, Transform
from text_deobfuscate.transforms.base64 import Base32, Base64
from text_deobfuscate.transforms.bytes import Binary, DecimalCodes, Hex
from text_deobfuscate.transforms.caesar import Atbash, Caesar, Rot47
from text_deobfuscate.transforms.emoji import EmojiWord
from text_deobfuscate.transforms.escapes import BackslashEscape, HtmlEntity, OctalEscape, UrlPercent
from text_deobfuscate.transforms.invisible import TagCharacters, ZeroWidth
from text_deobfuscate.transforms.leet import Leetspeak
from text_deobfuscate.transforms.lookalike import Lookalike
from text_deobfuscate.transforms.mail import MimeWord, QuotedPrintable
from text_deobfuscate.transforms.marks import CombiningMarks
from text_deobfuscate.transforms.misspelling import Misspelling
from text_deobfuscate.transforms.morse import Morse
from text_deobfuscate.transforms.repeated import RepeatedChars
from text_deobfuscate.transforms.reverse import Reverse
from text_deobfuscate.transforms.separator import Separator
from text_deobfuscate.transforms.shorthand import Shorthand
from text_deobfuscate.transforms.styled import Fullwidth, StyledAlphabet

ALL: tuple[Transform, ...] = (
    ZeroWidth(),
    TagCharacters(),
    StyledAlphabet(),
    Fullwidth(),
    HtmlEntity(),
    UrlPercent(),
    BackslashEscape(),
    OctalEscape(),
    QuotedPrintable(),
    MimeWord(),
    CombiningMarks(),
    Leetspeak(),
    Separator(),
    RepeatedChars(),
    Shorthand(),
    Misspelling(),
    EmojiWord(),
    Lookalike("homoglyph"),
    Lookalike("accent-substitution"),
    Lookalike("homoglyph", level="aggressive", loose=True),
    Lookalike("accent-substitution", level="aggressive", loose=True),
    Base64(),
    Base32(),
    Morse(),
    Rot47(),
    Atbash(),
    Hex(),
    Binary(),
    DecimalCodes(),
    Caesar("rot13", (13,), encoded_tokens=True),
    Caesar("caesar", tuple(shift for shift in range(1, 26) if shift != 13)),
    Reverse(),
)

__all__ = ["ALL", "Candidate", "Transform"]
