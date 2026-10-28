"""Which writing system a character belongs to. ``unicodedata`` does not say."""

from bisect import bisect_right

from text_deobfuscate import resources

# Punctuation, digits and marks are shared by all scripts and say nothing about a word.
SHARED = frozenset({"Common", "Inherited", "Unknown"})


def script_of(char: str) -> str:
    starts, ends, names = resources.scripts()
    index = bisect_right(starts, ord(char)) - 1
    return names[index] if index >= 0 and ord(char) <= ends[index] else "Unknown"


def scripts_in(text: str) -> set[str]:
    return {script_of(char) for char in text} - SHARED


def is_mixed_script(word: str) -> bool:
    """Whether a word combines letters from more than one writing system."""
    return len(scripts_in(word)) > 1
