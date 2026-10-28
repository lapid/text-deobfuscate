"""Encodings that come from email: quoted-printable and MIME encoded words.

Both are everyday mail transport notations (RFC 2045, RFC 2047) rather than
disguises, but text copied out of a raw message arrives still encoded.
"""

import base64
import binascii
import quopri
import re
from collections.abc import Iterable

from text_deobfuscate.transforms.base import CHUNK, Candidate, Transform, is_readable

# An escape is "=" and two hex digits. Lower-case digits are not standard but occur.
ESCAPE = re.compile(r"=[0-9A-Fa-f]{2}")
# A soft line break: "=" at the end of a line, which stands for nothing at all.
SOFT_BREAK = re.compile(r"=\r?\n")
# A whole stretch of quoted-printable, which may run over several soft-broken lines.
# Spaces belong inside it: half-encoded text leaves them as they are, and a run cut
# at every space would offer the engine fragments too short to judge.
BODY = r"(?:[^=\r\n]|=[0-9A-Fa-f]{2}|=\r?\n)"
QP_RUN = re.compile(rf"{BODY}*=(?:[0-9A-Fa-f]{{2}}|\r?\n){BODY}*")

# =?charset?B?text?= with base64 inside, or ?Q? with quoted-printable inside.
MIME_WORD = re.compile(r"=\?([A-Za-z0-9][A-Za-z0-9._-]*)\?([BbQq])\?([^?\s]+)\?=")
# Neighbouring encoded words belong to one phrase; the space between them is not text.
MIME_PHRASE = re.compile(rf"{MIME_WORD.pattern}(?:[ \t]+{MIME_WORD.pattern})*")


def decode_quoted(run: str) -> str | None:
    """The text a quoted-printable run stands for, or None if it is not valid."""
    try:
        data = quopri.decodestring(run.encode())
    except (ValueError, binascii.Error):
        return None
    for encoding in ("utf-8", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return None


class QuotedPrintable(Transform):
    """Bytes written as "=" and two hex digits, with "=" at a line end meaning nothing.

    Certain rather than judged, like the other escape notations: a message is often
    only half encoded, so the undecoded form still reads as English and the score
    would hardly rise. The ambiguity is settled by rules instead.

    A word carrying two escapes is the notation; one escape on its own is more
    likely a mention or a formula ("x=41", "=A1+B2"), and is decoded only when
    another word in the text shows the notation outright. A soft line break cannot
    be anything else, so it counts as evidence by itself.
    """

    name = "quoted-printable"
    judged = False

    def propose(self, text: str) -> Iterable[Candidate]:
        # Evidence is counted word by word, but the rewrite is made on whole runs, so
        # that a soft break and the two halves of the word it splits are mended together.
        marked = [match for match in CHUNK.finditer(text) if ESCAPE.search(match.group())]
        if not (SOFT_BREAK.search(text) or any(len(ESCAPE.findall(m.group())) >= 2 for m in marked)):
            return
        for match in QP_RUN.finditer(text):
            decoded = decode_quoted(match.group())
            if decoded and decoded != match.group() and is_readable(decoded):
                yield Candidate(match.start(), match.end(), decoded)


def decode_word(charset: str, encoding: str, body: str) -> str | None:
    try:
        if encoding.upper() == "B":
            data = base64.b64decode(body + "=" * (-len(body) % 4), validate=True)
        else:
            # In an encoded word "_" stands for a space, which plain quoted-printable has no need of.
            data = quopri.decodestring(body.replace("_", " ").encode())
        return data.decode(charset)
    except (binascii.Error, LookupError, UnicodeDecodeError, ValueError):
        return None


class MimeWord(Transform):
    """Mail header text wrapped as =?charset?B?...?= or =?charset?Q?...?=.

    The wrapper is unambiguous, so the whole phrase is decoded at once: a space
    between two encoded words is part of the wrapping, not of the text.

    Certain rather than judged. ``=?utf-8?Q?...?=`` is not something English prose
    contains, and the encoded form still reads as words ("The_meeting_is_moved"),
    so the score barely rises and a judged proposal would be refused for that.
    Prose *about* the notation is safe: the encoding letter must be B or Q.
    """

    name = "mime-word"
    judged = False

    def propose(self, text: str) -> Iterable[Candidate]:
        for match in MIME_PHRASE.finditer(text):
            pieces = [decode_word(*word.groups()) for word in MIME_WORD.finditer(match.group())]
            if any(piece is None for piece in pieces):
                continue
            decoded = "".join(pieces)
            if decoded and decoded != match.group() and is_readable(decoded):
                yield Candidate(match.start(), match.end(), decoded)
