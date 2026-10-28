"""The systems that can be evaluated: the deobfuscator and the baselines.

A system is a function from text to (output text, names of transforms applied).
"""

import unicodedata
from collections.abc import Callable

from text_deobfuscate import deobfuscate

System = Callable[[str], tuple[str, list[str]]]


def identity(text: str) -> tuple[str, list[str]]:
    return text, []


def nfkc(text: str) -> tuple[str, list[str]]:
    return unicodedata.normalize("NFKC", text), []


def ours(level: str) -> System:
    def run(text: str) -> tuple[str, list[str]]:
        result = deobfuscate(text, strictness=level, raise_errors=True)
        return result.text, [step.transform for step in result.steps]

    return run
