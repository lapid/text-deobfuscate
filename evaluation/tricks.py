"""Names of the obfuscation tricks and the strictness level that undoes each.

These names are the contract between the samples (``tricks``), the obfuscator,
and the deobfuscator's step record (``Step.transform``). See docs/taxonomy.md.
"""

LEVELS = ("conservative", "balanced", "aggressive")

TRICK_LEVEL = {
    "zero-width": "conservative",
    "tag-characters": "conservative",
    "styled-alphabet": "conservative",
    "fullwidth": "conservative",
    "html-entity": "conservative",
    "url-percent": "conservative",
    "backslash-escape": "conservative",
    "base64": "conservative",
    "base64url": "conservative",
    "hex": "conservative",
    "binary": "conservative",
    "decimal-codes": "conservative",
    "rot13": "conservative",
    "caesar": "conservative",
    "reverse": "conservative",
    "combining-marks": "balanced",
    "homoglyph": "balanced",
    "accent-substitution": "balanced",
    "leetspeak": "balanced",
    "separator": "balanced",
    "repeated-chars": "aggressive",
    "shorthand": "aggressive",
    "misspelling": "aggressive",
    "emoji-word": "aggressive",
    # Added from the coverage survey.
    "bidi-control": "conservative",
    "control-chars": "conservative",
    "other-invisible": "conservative",
    "variation-selector": "conservative",
    "quoted-printable": "conservative",
    "mime-word": "conservative",
    "base32": "conservative",
    "octal-escape": "conservative",
    "rot47": "conservative",
    "atbash": "conservative",
    "morse": "conservative",
    "word-reverse": "conservative",
    "squared-letters": "conservative",
    "regional-indicator": "conservative",
    "superscript": "conservative",
}

# Tricks from the coverage survey. The sets were built before them, so their samples
# are added at the end from a random stream of their own.
SURVEY = (
    "bidi-control", "control-chars", "other-invisible", "variation-selector", "quoted-printable", "mime-word",
    "base32", "octal-escape", "rot47", "atbash", "morse", "word-reverse", "squared-letters",
    "regional-indicator", "superscript",
)

# Samples exist for these, but version 1 does not undo them (owner, 2026-10-24: the
# Unicode carriers and the extra styled ranges wait for version 2 and the owner's unseen
# set). They are scored as above every level, so they count as neither recovered nor
# missed. Remove a name from here when its transform is written.
DEFERRED = frozenset(
    {"bidi-control", "control-chars", "other-invisible", "variation-selector", "squared-letters",
     "regional-indicator", "superscript"}
)

# Informal writing rather than disguise. Rewriting it is asked for only at the
# ``aggressive`` level, and it is how people normally write text messages.
NORMALISING = frozenset({"shorthand", "misspelling", "emoji-word"})

# Tricks that replace a span with an opaque token. In a partial sample they
# need a span long enough to be recognisable.
ENCODINGS = frozenset(
    {"html-entity", "url-percent", "backslash-escape", "base64", "base64url", "hex", "binary",
     "decimal-codes", "rot13", "caesar", "reverse", "quoted-printable", "mime-word", "base32", "octal-escape",
     "rot47", "atbash", "morse", "word-reverse"}
)


def in_scope(tricks: list[str], level: str) -> bool:
    """Whether a deobfuscator at ``level`` is expected to undo all of ``tricks``."""
    limit = LEVELS.index(level)
    if any(trick in DEFERRED for trick in tricks):
        return False
    return all(LEVELS.index(TRICK_LEVEL[trick]) <= limit for trick in tricks)


# Tricks the step record cannot tell apart, mapped to the name it reports.
RECORDED_AS = {
    "base64url": "base64",
    "other-invisible": "zero-width",
    "octal-escape": "backslash-escape",
    "word-reverse": "reverse",
    "squared-letters": "styled-alphabet",
    "regional-indicator": "styled-alphabet",
    "superscript": "styled-alphabet",
}
