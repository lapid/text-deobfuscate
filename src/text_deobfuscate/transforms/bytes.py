"""Text written out as the numbers of its bytes: hex, binary or decimal."""

import re
from collections.abc import Iterable

from text_deobfuscate.transforms.base import Candidate, Transform, is_readable

EDGE = r"(?<![0-9A-Za-z])", r"(?![0-9A-Za-z])"
HEX_PLAIN = re.compile(EDGE[0] + r"(?:[0-9a-fA-F]{2}){6,}" + EDGE[1])
HEX_SPACED = re.compile(EDGE[0] + r"(?:0x)?[0-9a-fA-F]{2}(?:[ ,]+(?:0x)?[0-9a-fA-F]{2}){3,}" + EDGE[1])
BINARY = re.compile(EDGE[0] + r"[01]{8}(?: ?[01]{8}){3,}" + EDGE[1])
DECIMAL = re.compile(EDGE[0] + r"[0-9]{1,3}(?:(?: |, ?)[0-9]{1,3}){3,}" + EDGE[1])


def as_text(data: bytes) -> str | None:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return None
    return text if text and is_readable(text) else None


class Hex(Transform):
    name = "hex"
    # Hashes are hex too; they are told apart by not decoding to readable text.
    ignores_protection = True

    def propose(self, text: str) -> Iterable[Candidate]:
        for pattern in (HEX_SPACED, HEX_PLAIN):
            for match in pattern.finditer(text):
                digits = re.sub(r"0x|[ ,]", "", match.group())
                decoded = as_text(bytes.fromhex(digits)) if len(digits) % 2 == 0 else None
                if decoded:
                    yield Candidate(match.start(), match.end(), decoded)


class Binary(Transform):
    name = "binary"

    def propose(self, text: str) -> Iterable[Candidate]:
        for match in BINARY.finditer(text):
            bits = match.group().replace(" ", "")
            decoded = as_text(bytes(int(bits[i : i + 8], 2) for i in range(0, len(bits), 8)))
            if decoded:
                yield Candidate(match.start(), match.end(), decoded)


class DecimalCodes(Transform):
    name = "decimal-codes"

    def propose(self, text: str) -> Iterable[Candidate]:
        for match in DECIMAL.finditer(text):
            numbers = [int(number) for number in re.findall(r"[0-9]+", match.group())]
            if max(numbers) > 255:
                continue
            decoded = as_text(bytes(numbers))
            if decoded:
                yield Candidate(match.start(), match.end(), decoded)
