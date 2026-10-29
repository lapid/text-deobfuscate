import base64
import codecs
import unittest
from unittest import mock

from text_deobfuscate import deobfuscate, scorer, scripts
from text_deobfuscate.engine import MAX_INPUT_CHARS, Engine
from text_deobfuscate.protect import protected_spans
from text_deobfuscate.transforms import Candidate, Transform


def b64(text: str) -> str:
    return base64.b64encode(text.encode()).decode()


def run(text: str, level: str = "conservative"):
    return deobfuscate(text, strictness=level, raise_errors=True)


class ScorerTest(unittest.TestCase):
    def test_known_words(self):
        for word in ("hello", "Hello", "HELLO", "Elizabeth", "don't", "don’t", "dog's", "a", "I"):
            self.assertTrue(scorer.is_word(word), word)
        for word in ("uryyb", "xqzt", "b", "h3llo"):
            self.assertFalse(scorer.is_word(word), word)

    def test_english_scores_above_gibberish(self):
        self.assertGreater(scorer.english_score("Please send the report before Friday."), 0.9)
        for gibberish in ("Cyrnfr fraq gur ercbeg orsber Sevqnl.", ".yadirF erofeb troper", "1234 5678"):
            self.assertLess(scorer.english_score(gibberish), 0.4, gibberish)


class ScriptsTest(unittest.TestCase):
    def test_script_lookup(self):
        self.assertEqual([scripts.script_of(c) for c in "aаα1 "], ["Latin", "Cyrillic", "Greek", "Common", "Common"])

    def test_mixed_script(self):
        self.assertTrue(scripts.is_mixed_script("аccount"))  # the first letter is Cyrillic
        self.assertFalse(scripts.is_mixed_script("account"))
        self.assertFalse(scripts.is_mixed_script("Привет"))
        self.assertFalse(scripts.is_mixed_script("route-66"))


class ProtectTest(unittest.TestCase):
    def test_finds_addresses_and_identifiers(self):
        for text in (
            "https://example.com/a%20b?q=1",
            "first.last@example.co.uk",
            r"C:\Users\name\new\table.txt",
            "/usr/local/lib/python3.14",
            "00000000-0000-4000-8000-000000000000",
            "#ff00aa",
        ):
            spans = protected_spans(f"see {text} now")
            self.assertTrue(any(end - start >= len(text) - 1 for start, end in spans), text)

    def test_prose_is_not_protected(self):
        self.assertEqual(protected_spans("Nothing to see here, and/or there."), [])


class EngineTest(unittest.TestCase):
    def test_base64(self):
        result = run(b64("Please send the report before Friday."))
        self.assertEqual(result.text, "Please send the report before Friday.")
        self.assertEqual([step.transform for step in result.steps], ["base64"])

    def test_nested_layers_are_recorded_in_order(self):
        text = b64(b64("The meeting is moved to the second floor."))
        result = run(text)
        self.assertEqual(result.text, "The meeting is moved to the second floor.")
        self.assertEqual([step.transform for step in result.steps], ["base64", "base64"])
        self.assertEqual(result.steps[0].before, text)
        self.assertEqual(result.steps[1].before, result.steps[0].after)

    def test_partial_span_and_offsets(self):
        token = b64("Your account password has expired.")
        result = run(f"Decode this: {token} and reply.")
        self.assertEqual(result.text, "Decode this: Your account password has expired. and reply.")
        step = result.steps[0]
        self.assertEqual((step.start, step.end, step.before), (13, 13 + len(token), token))

    def test_rot13_whole_and_partial(self):
        whole = "Sherlock Holmes said nothing at all."
        self.assertEqual(run(codecs.encode(whole, "rot13")).text, whole)
        self.assertEqual(
            run("Ubj pbhyq ur fcner unys gra thousand pounds?").text, "How could he spare half ten thousand pounds?"
        )

    def test_different_layers(self):
        result = run(codecs.encode(b64("Please send the report before Friday."), "rot13"))
        self.assertEqual(result.text, "Please send the report before Friday.")
        self.assertEqual([step.transform for step in result.steps], ["rot13", "base64"])

    def test_clean_text_is_untouched(self):
        for text in (
            "Take route 66 west for 3 miles.",
            "The words ant and nag are a rot13 pair, like bar and one.",
            "internationalization",
            "ok",
            "",
            "Привет, как дела?",
            "deadbeef cafe babe face",
            b64("\x00\x01 not text \x02"),
        ):
            result = run(text, "aggressive")
            self.assertEqual((result.text, result.steps), (text, ()), text)

    def test_running_twice_changes_nothing_more(self):
        once = run(f"Note: {b64('The meeting is moved to the second floor.')}").text
        self.assertEqual(run(once).text, once)

    def test_oversized_input_is_returned_unchanged(self):
        text = b64("Please send the report before Friday.") + " " + "x" * MAX_INPUT_CHARS
        self.assertEqual(run(text).text, text)

    def test_short_reversed_english_is_recovered_and_short_foreign_phrases_are_not_reversed(self):
        for level in ("conservative", "balanced", "aggressive"):
            self.assertEqual(deobfuscate("dlrow olleh", strictness=level).text, "world hello")
            self.assertEqual(deobfuscate("Hello dlrow olleh", strictness=level).text, "Hello world hello")
            self.assertEqual(deobfuscate("No pasa nada", strictness=level).text, "No pasa nada")

    def test_result_says_when_the_text_was_not_fully_read(self):
        self.assertFalse(deobfuscate("hello").truncated)
        self.assertTrue(deobfuscate("x" * (MAX_INPUT_CHARS + 1)).truncated)
        with mock.patch("text_deobfuscate.engine.MAX_WORK_CHARS", 10):
            self.assertTrue(deobfuscate(b64("Please send the report before Friday.")).truncated)

    def test_errors_are_contained_unless_asked_for(self):
        class Broken(Transform):
            name = "base64"

            def propose(self, text):
                raise RuntimeError("boom")

        with self.assertRaises(RuntimeError):
            Engine("conservative", (Broken(),)).run("anything")

    def test_level_gates_transforms_and_unjudged_proposals_apply(self):
        class Shout(Transform):
            name = "reverse"
            level = "balanced"
            judged = False

            def propose(self, text):
                if "!" not in text:
                    yield Candidate(0, len(text), text + "!")

        self.assertEqual(Engine("conservative", (Shout(),)).run("hi")[0], "hi")
        self.assertEqual(Engine("balanced", (Shout(),)).run("hi")[0], "hi!")

    def test_a_certain_transform_applies_all_its_proposals_together(self):
        class Pairs(Transform):
            name = "reverse"
            judged = False

            def propose(self, text):
                # Proposes only while the text still holds two marks, as a transform that needs evidence does.
                spots = [index for index, char in enumerate(text) if char == "*"]
                if len(spots) >= 2:
                    for index in spots:
                        yield Candidate(index, index + 1, "--")

        text, steps = Engine("conservative", (Pairs(),)).run("a*b*c")
        self.assertEqual(text, "a--b--c")
        # Each step's span is in the text as it stood before that step.
        self.assertEqual([(step.start, step.end) for step in steps], [(1, 2), (4, 5)])

    def test_protected_spans_are_skipped(self):
        class Upper(Transform):
            name = "reverse"
            judged = False

            def propose(self, text):
                for start in range(len(text)):
                    if text[start].islower():
                        yield Candidate(start, start + 1, text[start].upper())
                        return

        text, _ = Engine("conservative", (Upper(),)).run("https://example.com")
        self.assertEqual(text, "https://example.com")


if __name__ == "__main__":
    unittest.main()
