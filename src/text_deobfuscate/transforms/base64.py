import base64
import binascii
import re
from collections.abc import Iterable

from text_deobfuscate.transforms.base import Candidate, Transform, is_readable

# A run of base64 characters that is not part of a longer word-like run.
TOKEN = re.compile(r"(?<![A-Za-z0-9+/=_-])[A-Za-z0-9+/_-]{16,}={0,2}(?![A-Za-z0-9+/=_-])")
URL_SAFE = str.maketrans("-_", "+/")

# Base32's alphabet is capitals and the digits 2 to 7, padded to a multiple of eight.
BASE32_TOKEN = re.compile(r"(?<![A-Za-z0-9=])[A-Z2-7]{16,}={0,6}(?![A-Za-z0-9=])")


class Base64(Transform):
    name = "base64"

    def propose(self, text: str) -> Iterable[Candidate]:
        for match in TOKEN.finditer(text):
            token = match.group()
            # Both alphabets in one token is not base64.
            if ("-" in token or "_" in token) and ("+" in token or "/" in token):
                continue
            body = token.rstrip("=").translate(URL_SAFE)
            if len(body) % 4 == 1:
                continue
            try:
                decoded = base64.b64decode(body + "=" * (-len(body) % 4), validate=True).decode("utf-8")
            except (binascii.Error, UnicodeDecodeError):
                continue
            if decoded and is_readable(decoded):
                yield Candidate(match.start(), match.end(), decoded)


class Base32(Transform):
    """Text in base32.

    Its alphabet is capitals and six digits, which is also what licence keys, ticket
    codes and reference numbers look like, so it asks for twice the letters the level
    does before a decode is judged at all. That lowers the risk without removing it:
    a code that happens to *be* base32 of English cannot be told from encoded English,
    and `data/eval` holds one such row on purpose. Telling codes apart properly needs
    a key-token recogniser, which is not built yet.
    """

    name = "base32"
    min_letters = 16

    def propose(self, text: str) -> Iterable[Candidate]:
        for match in BASE32_TOKEN.finditer(text):
            body = match.group().rstrip("=")
            # Base32 packs five bits per character, so only some lengths can be whole bytes.
            if len(body) % 8 in (1, 3, 6):
                continue
            try:
                decoded = base64.b32decode(body + "=" * (-len(body) % 8)).decode("utf-8")
            except (binascii.Error, UnicodeDecodeError, ValueError):
                continue
            if decoded and is_readable(decoded):
                yield Candidate(match.start(), match.end(), decoded)
