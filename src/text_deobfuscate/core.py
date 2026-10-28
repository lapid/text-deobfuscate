from text_deobfuscate.engine import LEVELS, Engine
from text_deobfuscate.types import Result

STRICTNESS_LEVELS = LEVELS


def deobfuscate(text: str, *, strictness: str = "conservative", raise_errors: bool = False) -> Result:
    """Return ``text`` with obfuscation undone, plus the steps applied.

    If anything goes wrong internally the text is returned unchanged, unless
    ``raise_errors`` is set.
    """
    if strictness not in STRICTNESS_LEVELS:
        raise ValueError(f"strictness must be one of {STRICTNESS_LEVELS}, got {strictness!r}")
    try:
        output, steps = Engine(strictness).run(text)
    except Exception:
        if raise_errors:
            raise
        return Result(text=text)
    return Result(text=output, steps=steps)
