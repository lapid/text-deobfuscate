"""Undo text obfuscation and report which transforms were applied."""

from importlib import metadata as _metadata

from text_deobfuscate.core import STRICTNESS_LEVELS, deobfuscate
from text_deobfuscate.types import Result, Step

try:
    __version__ = _metadata.version("text-deobfuscate")
except _metadata.PackageNotFoundError:   # running from a source tree that was never installed
    __version__ = "unknown"

__all__ = ["STRICTNESS_LEVELS", "Result", "Step", "__version__", "deobfuscate"]
