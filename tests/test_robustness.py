"""The tool is given untrusted text, so it must never crash, hang or run what it reads.

Inputs here are random but seeded, so a failure repeats. The sizes keep the whole file to a few seconds.
"""

import base64
import string
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from random import Random

from text_deobfuscate import STRICTNESS_LEVELS, deobfuscate

SEED = 20261027
SLOWEST_ALLOWED = 5.0   # seconds for one short text
PROSE = "the quick brown fox jumps over the lazy dog and then it was quite late for everyone to leave"
FRAGMENTS = (
    "%41%42", "&#65;", "&amp;", "\\x41", "\\u0041", "=?UTF-8?B?aGk=?=", "=41", "aGVsbG8gd29ybGQ=", "68656c6c6f",
    "01100001", ".- -...", "c.l.i.c.k", "f r e e", "h3ll0", "pr1z3", "​", "‮", "́", "ａｂｃ", "𝐡𝐢",
    "Ꭺ", "а", "е", "ο", "!", "@", "1", "4", "0", "...", "'", '"', "\\", "\n", "\t", "  ", "0x", "ZZ", "==",
)


def corpus(rng: Random, count: int) -> list[str]:
    """Texts built from fragments of every trick, random characters and random slices of prose."""
    out = []
    for _ in range(count):
        kind = rng.randrange(5)
        if kind == 0:
            text = "".join(rng.choice(string.printable) for _ in range(rng.randint(0, 200)))
        elif kind == 1:
            text = "".join(chr(rng.choice((rng.randint(0x20, 0x7E), rng.randint(0x80, 0x2FFF), rng.randint(0xFF00, 0xFFEF)))) for _ in range(rng.randint(0, 120)))
        elif kind == 2:
            text = "".join(rng.choice(FRAGMENTS) for _ in range(rng.randint(1, 30)))
        elif kind == 3:
            words = PROSE.split()
            text = " ".join(rng.choice(FRAGMENTS) if rng.random() < 0.3 else rng.choice(words) for _ in range(rng.randint(1, 25)))
        else:
            start = rng.randrange(len(PROSE))
            text = PROSE[start : start + rng.randint(1, 60)]
            text = "".join(char + rng.choice(("", "", ".", "-", "​")) for char in text)
        out.append(text)
    return out


class FuzzTest(unittest.TestCase):
    def test_random_text_never_raises_or_hangs(self):
        for level in STRICTNESS_LEVELS:
            for text in corpus(Random(f"{SEED}-{level}"), 150):
                started = time.perf_counter()
                result = deobfuscate(text, strictness=level, raise_errors=True)
                took = time.perf_counter() - started
                self.assertLess(took, SLOWEST_ALLOWED, f"{level}: {text!r} took {took:.1f}s")
                self.assertIsInstance(result.text, str)
                for step in result.steps:
                    self.assertLessEqual(0, step.start)
                    self.assertLessEqual(step.start, step.end)

    def test_the_default_function_swallows_internal_errors(self):
        # Without raise_errors the call returns a Result for anything, including lone surrogates.
        for text in ("", " ", "\ud800", "a\udfffb", "\x00" * 50, "\U0010ffff" * 20):
            self.assertIsInstance(deobfuscate(text, strictness="aggressive").text, str)

    def test_empty_and_clean_text_come_back_unchanged(self):
        for level in STRICTNESS_LEVELS:
            for text in ("", " ", "\n", PROSE, "Hello, world!"):
                self.assertEqual(deobfuscate(text, strictness=level).text, text)

    def test_inputs_at_the_size_limit_finish_quickly(self):
        rng = Random(SEED)
        for text in (
            "a" * 100_000,
            "1" * 100_000,
            "​" * 100_000,
            "\n" * 100_000,
            " ".join(rng.choice(PROSE.split()) for _ in range(20_000))[:100_000],
            "".join(rng.choice(string.printable) for _ in range(30_000)),   # 100,000 takes about 14 s
        ):
            started = time.perf_counter()
            deobfuscate(text, strictness="aggressive", raise_errors=True)
            self.assertLess(time.perf_counter() - started, 30.0)


class NeverExecutesTest(unittest.TestCase):
    def test_decoded_code_is_only_text(self):
        with tempfile.TemporaryDirectory() as folder:
            marker = Path(folder) / "marker"
            payloads = (
                f"import os; os.system('touch {marker}')",
                f"__import__('pathlib').Path('{marker}').touch()",
                f"$(touch {marker}); rm -rf {folder}/*",
                f"<script>fetch('{marker}')</script>",
            )
            for payload in payloads:
                encoded = base64.b64encode(payload.encode()).decode()
                for level in STRICTNESS_LEVELS:
                    result = deobfuscate(encoded, strictness=level, raise_errors=True)
                    self.assertIn(result.text, (payload, encoded))
                    self.assertFalse(marker.exists())


class ThreadSafetyTest(unittest.TestCase):
    def test_threads_get_the_answers_a_single_thread_gets(self):
        texts = corpus(Random(SEED), 60) + ["Pl&#101;ase c0nf1rm y0ur acc0unt", "UGxlYXNlIHNlbmQgdGhlIHJlcG9ydA==", "ʜᴇʟʟᴏ"]
        expected = [deobfuscate(text, strictness="balanced").text for text in texts]
        with ThreadPoolExecutor(max_workers=8) as pool:
            got = list(pool.map(lambda text: deobfuscate(text, strictness="balanced").text, texts * 3))
        self.assertEqual(got, expected * 3)


if __name__ == "__main__":
    unittest.main()
