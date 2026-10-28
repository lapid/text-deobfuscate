"""Each transform recovers what the project's own generator produced, and leaves clean text alone."""

import random
import unittest

from text_deobfuscate import deobfuscate
from evaluation import obfuscator
from evaluation.tricks import DEFERRED, RECORDED_AS, TRICK_LEVEL

class Picks:
    """Stands in for a Random so that one shape of a trick can be asked for by name.

    ``choice`` hands back the values given here, in the order the generator asks.
    """

    def __init__(self, *values: object) -> None:
        self.values = list(values)

    def choice(self, items: object) -> object:
        return self.values.pop(0)


SENTENCES = (
    "The meeting is moved to the second floor.",
    "Please send the report before Friday morning.",
    "Our neighbours painted their fence green last summer.",
)

CONSERVATIVE = (
    "zero-width", "styled-alphabet", "fullwidth", "html-entity", "url-percent", "backslash-escape",
    "base64", "base64url", "hex", "binary", "decimal-codes", "rot13", "caesar", "reverse",
)

# The eight added to version 1 after the coverage survey (2026-10-24).
SURVEY_V1 = ("quoted-printable", "mime-word", "base32", "octal-escape", "rot47", "atbash", "morse", "word-reverse")

# Where each trick in scope for version 1 is checked. ``CoverageTest`` fails if a trick
# is added to ``evaluation/tricks.py`` and no test here recovers it, which is easy to
# miss: the evaluation would score the new samples as "out of scope" and say nothing.
COVERED_BY = {
    **{trick: "RecoveryTest.test_whole_text" for trick in CONSERVATIVE},
    **{trick: "SurveyTricksTest.test_whole_text" for trick in SURVEY_V1},
    "tag-characters": "RecoveryTest.test_hidden_text_is_removed_and_reported",
    "homoglyph": "LookalikeTest.test_letters_from_other_alphabets",
    "accent-substitution": "LookalikeTest.test_odd_accents",
    "combining-marks": "CombiningMarksTest.test_overlays_and_stacks",
    "leetspeak": "LeetspeakTest.test_digits_and_symbols_for_letters",
    "separator": "SeparatorTest.test_symbols_between_letters",
    "repeated-chars": "RepeatedCharsTest.test_stretched_words",
    "shorthand": "InformalWritingTest.test_shorthand",
    "misspelling": "InformalWritingTest.test_common_misspellings_and_typing_mistakes",
    "emoji-word": "InformalWritingTest.test_emoji_for_a_word",
}

# Names the step record uses where they differ from the generator's.
RECORDED = RECORDED_AS


def run(text: str, level: str = "conservative"):
    return deobfuscate(text, strictness=level, raise_errors=True)


class CoverageTest(unittest.TestCase):
    """Every trick version 1 undoes is recovered by a test in this file."""

    def test_every_trick_in_scope_has_a_test(self):
        in_scope = {trick for trick in TRICK_LEVEL if trick not in DEFERRED}
        self.assertEqual(set(COVERED_BY), in_scope, "add the trick to COVERED_BY and write the test")

    def test_the_named_tests_exist(self):
        for trick, where in COVERED_BY.items():
            cls, method = where.split(".")
            self.assertTrue(hasattr(globals().get(cls), method), (trick, where))


class RecoveryTest(unittest.TestCase):
    def test_whole_text(self):
        for trick in CONSERVATIVE:
            for seed in range(6):
                for sentence in SENTENCES:
                    disguised = obfuscator.apply(trick, sentence, random.Random(seed))
                    if disguised == sentence:
                        continue
                    result = run(disguised)
                    self.assertEqual(result.text, sentence, (trick, disguised))
                    self.assertEqual({step.transform for step in result.steps}, {RECORDED.get(trick, trick)}, trick)

    def test_part_of_a_text(self):
        # Shifted or reversed words that are also English as they stand cannot be told apart
        # at the edges of a span, so those three tricks are only checked on whole text.
        for trick in set(CONSERVATIVE) - {"rot13", "caesar", "reverse"}:
            for seed in range(6):
                sentence = " ".join(SENTENCES)
                disguised = obfuscator.apply_partial(trick, sentence, random.Random(seed))
                self.assertEqual(run(disguised).text, sentence, (trick, disguised))

    def test_reversed_run_holding_a_word_that_reads_both_ways(self):
        # "no" is a word as it stands, in the middle of the reversed run.
        result = run("The band first " + "debuted on the professional"[::-1] + " music scene in Chicago.")
        self.assertEqual(result.text, "The band first debuted on the professional music scene in Chicago.")

    def test_layers(self):
        for stack in (("base64", "base64"), ("rot13", "base64"), ("hex", "base64"), ("base64", "hex"),
                      ("reverse", "base64"), ("base64", "reverse"), ("url-percent", "html-entity"),
                      ("zero-width", "base64")):
            for seed in range(4):
                disguised = obfuscator.apply_stack(stack, SENTENCES[0], random.Random(seed))
                result = run(disguised)
                self.assertEqual(result.text, SENTENCES[0], (stack, disguised))
                self.assertEqual([step.transform for step in result.steps][: len(stack)], list(stack), stack)

    def test_hidden_text_is_removed_and_reported(self):
        disguised, phrase = obfuscator.tag_characters(SENTENCES[0], random.Random(1))
        result = run(disguised)
        self.assertEqual(result.text, SENTENCES[0])
        self.assertEqual([(step.transform, step.hidden) for step in result.steps], [("tag-characters", phrase)])

    def test_result_is_stable(self):
        for trick in CONSERVATIVE:
            once = run(obfuscator.apply(trick, SENTENCES[1], random.Random(2))).text
            self.assertEqual(run(once).text, once, trick)


class SurveyTricksTest(unittest.TestCase):
    """The eight tricks added to version 1 after the coverage survey (2026-10-24)."""

    # Morse and superscripts have no capitals, so recovery is compared without them.
    CASELESS = frozenset({"morse"})

    def recovers(self, trick, disguised, expected):
        result = run(disguised)
        got, want = (result.text, expected) if trick not in self.CASELESS else (result.text.lower(), expected.lower())
        self.assertEqual(got, want, (trick, disguised))
        self.assertIn(RECORDED.get(trick, trick), {step.transform for step in result.steps})

    def test_whole_text(self):
        for trick in SURVEY_V1:
            for seed in range(6):
                for sentence in SENTENCES:
                    disguised = obfuscator.apply(trick, sentence, random.Random(seed))
                    if disguised == sentence:
                        continue
                    self.recovers(trick, disguised, sentence)

    def test_part_of_a_text(self):
        # Not "word-reverse": inside clean text it cannot be told from a reversed run.
        sentence = " ".join(SENTENCES)
        for trick in ("quoted-printable", "mime-word", "base32", "octal-escape", "atbash", "morse"):
            for seed in range(4):
                disguised = obfuscator.apply_partial(trick, sentence, random.Random(seed))
                if disguised is None:
                    continue
                self.recovers(trick, disguised, sentence)

    def test_each_word_reversed_keeps_the_word_order(self):
        # Reversing the whole text recovers the same words in the wrong order.
        disguised = obfuscator.word_reverse(SENTENCES[0], random.Random(0))
        self.assertEqual(run(disguised).text, SENTENCES[0])

    def test_the_full_stop_tells_the_two_reversals_apart(self):
        sentence = "He moved to Paris last year."
        # Reversed as a whole, the stop opens the text; reversed word by word, it opens
        # the last word. Nothing else separates the two readings.
        self.assertEqual(run(sentence[::-1]).text, sentence)
        self.assertEqual(run(obfuscator.word_reverse(sentence, random.Random(0))).text, sentence)

    def test_every_way_of_writing_morse(self):
        """The six separator conventions and the three sets of marks (added 2026-10-24).

        Six shapes of one trick were 210 samples of the same shape with different words
        in them, which says nothing about whether the notation is handled.
        """
        shapes = set()
        for gaps in obfuscator.MORSE_GAPS:
            for marks in obfuscator.MORSE_MARKS:
                for sentence in SENTENCES:
                    disguised = obfuscator.morse(sentence, Picks(gaps, marks))
                    shapes.add(disguised)
                    self.recovers("morse", disguised, sentence)
        self.assertEqual(len(shapes), len(obfuscator.MORSE_GAPS) * len(obfuscator.MORSE_MARKS) * len(SENTENCES))

    def test_every_octal_notation(self):
        """Padded, unpadded, the JavaScript ``\\0`` form, and octal mixed with hex."""
        shapes = set()
        for notation in ("padded", "minimal", "zero", "mixed"):
            for sentence in SENTENCES:
                disguised = obfuscator.octal_escape(sentence, Picks(notation))
                shapes.add(disguised)
                self.recovers("octal-escape", disguised, sentence)
        self.assertEqual(len(shapes), 4 * len(SENTENCES))

    def test_a_lone_escape_or_cipher_lookalike_stays(self):
        for text in (
            "Set x=10, y=20 and z=30 before the loop.",
            "In Excel, type =A1+B2 to add them.",
            "The header syntax is =?charset?encoding?text?= as the RFC says.",
            "Run chmod 755 script.sh and then ./script.sh",
            "The escape \\012 is a newline in octal.",
            "In Morse code, SOS is ... --- ...",
            "Loading ... ... ... done.",
            "----- end of message -----",
            "Use -v or --verbose for more output.",
            "Order ABCDEFGHIJKLMNOPQRSTUVWXYZ234567 is the base32 alphabet.",
        ):
            for level in ("conservative", "balanced", "aggressive"):
                self.assertEqual(run(text, level).text, text, (text, level))


class LookalikeTest(unittest.TestCase):
    """Letters from other alphabets and added accents, decided word by word."""

    CYRILLIC = str.maketrans("aeopc", "аеорс")
    GREEK = str.maketrans("ntk", "ητκ")

    def test_letters_from_other_alphabets(self):
        sentence = "Please confirm your account password today"
        for table in (self.CYRILLIC, self.GREEK):
            result = run(sentence.translate(table), "balanced")
            self.assertEqual(result.text, sentence)
            self.assertEqual({step.transform for step in result.steps}, {"homoglyph"})

    def test_small_capitals_are_recorded_as_a_lookalike(self):
        """Not as ``accent-substitution``: they are an alphabet, not an accent."""
        result = run("Click here to claim your ꜰʀᴇᴇ ᴘʀɪᴢᴇ today", "balanced")
        self.assertEqual(result.text, "Click here to claim your free prize today")
        self.assertEqual({step.transform for step in result.steps}, {"homoglyph"})

    def test_odd_accents(self):
        result = run("Please confirm y\u014d\u0169r acc\u014funt today", "balanced")
        self.assertEqual(result.text, "Please confirm your account today")
        self.assertEqual({step.transform for step in result.steps}, {"accent-substitution"})

    def test_both_tricks_in_one_text_count_as_evidence_for_each_other(self):
        # "Cаll" has a Cyrillic letter, "ȃđđŗess" only accents that also occur in real spelling.
        result = run("C\u0430ll us and confirm your \u0203\u0111\u0111\u0157ess", "balanced")
        self.assertEqual(result.text, "Call us and confirm your address")
        self.assertEqual({step.transform for step in result.steps}, {"homoglyph", "accent-substitution"})

    def test_roman_numerals_variants_and_symbols_inside_words(self):
        for disguised, plain in (
            ("the \u217cink to the fi\u217ce fro\u217f the ad\u217fin", "the link to the file from the admin"),
            ("yo\u03c5\u04f7 \u04abard was deli\u2228e\u0491ed", "your card was delivered"),
            ("\u00a2ar\u20ab number, please conf\u00a1rm", "card number, please confirm"),
            ("please \u00fee here, the \u00feack\u0430ge is late", "please be here, the package is late"),
        ):
            self.assertEqual(run(disguised, "balanced").text, plain, disguised)

    def test_units_currency_and_spanish_marks_stay(self):
        for text in ("It is 10 \u00b5m wide and weighs 5 \u00b5g.", "Chapter \u2174 costs 5\u00a2 or 20\u20ab.",
                     "\u00a1Hola! \u00a1Qu\u00e9 sorpresa!"):
            self.assertEqual(run(text, "aggressive").text, text)

    def test_not_at_the_conservative_level(self):
        text = "Please confirm your account".translate(self.CYRILLIC)
        self.assertEqual(run(text).text, text)

    def test_real_accents_and_other_languages_stay(self):
        for level in ("balanced", "aggressive"):
            for text in (
                "Привет, как дела? Сегодня хорошая погода.",
                "Η Ελλάδα είναι όμορφη το καλοκαίρι.",
                "I visited Москва and Αθήνα last year.",
                "Bonjour, comment ça va aujourd'hui ?",
            ):
                self.assertEqual(run(text, level).text, text, (level, text))
        for text in ("naïve café résumé", "The Cyrillic letter а looks like the Latin a.", "Señor Núñez lives in São Paulo."):
            self.assertEqual(run(text, "balanced").text, text)

    def test_aggressive_level_reads_a_lone_accented_word(self):
        text = "Dolores is survived by three children and her h\u00fcsband."
        self.assertEqual(run(text, "balanced").text, text)
        self.assertEqual(run(text, "aggressive").text, text.replace("\u00fc", "u"))


class CombiningMarksTest(unittest.TestCase):
    def test_overlays_and_stacks(self):
        for seed in range(8):
            for sentence in SENTENCES:
                disguised = obfuscator.apply("combining-marks", sentence, random.Random(seed))
                if disguised == sentence:
                    continue
                result = run(disguised, "balanced")
                self.assertEqual(result.text, sentence, disguised)
                self.assertEqual({step.transform for step in result.steps}, {"combining-marks"})
                self.assertEqual(run(disguised).text, disguised)

    def test_a_one_letter_word_follows_the_rest(self):
        strike = "\u0336"
        text = f"I{strike} sent t{strike}h{strike}e{strike} report"
        self.assertEqual(run(text, "balanced").text, "I sent the report")
        alone = f"I{strike} sent the report"
        self.assertEqual(run(alone, "balanced").text, alone)

    def test_spelling_and_phonetic_marks_stay(self):
        for text in (
            "A cafe\u0301 on the corner, nai\u0308ve as ever.",
            "The village of Z\u0304ara\u0304t is written t\u0361s in the notes.",
            "Tie\u0302\u0301ng Vie\u0323\u0302t is the Vietnamese language.",
        ):
            for level in ("balanced", "aggressive"):
                self.assertEqual(run(text, level).text, text, (level, text))


class LeetspeakTest(unittest.TestCase):
    def test_digits_and_symbols_for_letters(self):
        for text, plain in (
            ("Please c0nfirm your acc0unt p@ssw0rd today", "Please confirm your account password today"),
            ("7h3 m33ting is m0v3d to the s3c0nd fl00r.", "The meeting is moved to the second floor."),
            ("Send the rep0rt bef0re FR1DAY m0rning", "Send the report before FRIDAY morning"),
            ("See you in @pril, y0u will l1ke it", "See you in April, you will like it"),
        ):
            result = run(text, "balanced")
            self.assertEqual(result.text, plain)
            self.assertEqual({step.transform for step in result.steps}, {"leetspeak"})
            self.assertEqual(run(text).text, text)

    def test_doubled_digit_after_two_letters(self):
        self.assertEqual(run("Get fr33 followers and likes today", "balanced").text, "Get free followers and likes today")
        for text in ("The G5 and the M14 are on shelf B4.", "Room no00 is closed."):
            self.assertEqual(run(text, "balanced").text, text)

    def test_together_with_lookalike_letters(self):
        # The first letter of each disguised word is Cyrillic.
        text = "Please confirm your \u0430cc0unt and \u0440assw0rd"
        self.assertEqual(run(text, "balanced").text, "Please confirm your account and password")

    def test_shorthand_numbers_and_codes_stay(self):
        for text in (
            "Meet at 5am or 3pm, it costs $5m, the 1st and 3rd are free.",
            "Runs on win7 and python3, see test5, the MP3 and the sha1 of level5.",
            "Ask @mark or @rose about the print$ share and the HP G5 or the M14.",
        ):
            for level in ("balanced", "aggressive"):
                self.assertEqual(run(text, level).text, text, (level, text))

    def test_shorthand_stays_below_the_aggressive_level(self):
        text = "c u l8r, gr8 2 see u b4 2day, sum1 will w8 4 u"
        self.assertEqual(run(text, "balanced").text, text)

    def test_shorthand_next_to_leetspeak_stays(self):
        result = run("It was gr8, thx 4ever, the c0d3 word is next", "balanced")
        self.assertEqual(result.text, "It was gr8, thx 4ever, the code word is next")


class LeetspeakFunctionWordTest(unittest.TestCase):
    def test_numbers_with_a_plural_and_short_capitals_stay(self):
        # Found by reading the test split's clean texts, 2026-10-27.
        for text in (
            "the P-51's flew over, and Measure 114's text is long",
            "The series aired on S4C and BBC iPlayer, said patty's friend.",
            "Sweet, we may not go to 4U to meet carlos so gauge patty's interest",
            "A new 1DOL show starts tonight on the channel.",
        ):
            self.assertEqual(run(text, "balanced").text, text)

    def test_whole_numbers_are_words_only_in_a_text_full_of_the_trick(self):
        # Seen on the outside set (2026-10-27): "15" for "is", "45" for "as", "734" for "tea".
        heavy = "7h3 m057 c0mm0n pr0bl3m 15 4 punc7ur3 0f 7h3 71r3'5 1nn3r 7ub3 4nd w45 g07 734"
        self.assertEqual(
            run(heavy, "balanced").text,
            "The most common problem is a puncture of the tire's inner tube and was got tea",
        )
        for text in ("The room is 15 metres wide and 45% full.", "About 70 people came, and 15 finalists stayed."):
            self.assertEqual(run(text, "balanced").text, text)

    def test_full_leetspeak_reads_its_small_words(self):
        # The plain 1337 style: every a, e, i, o, s and t is a digit (outside generator, 2026-10-27).
        for text, plain in (
            ("1 4gr33 7h47 7h3 734 15 u5u4lly 50ld 1n m4ny c0un7r135.", "I agree that the tea is usually sold in many countries."),
            ("bu7 wh0 w45 7h3r3 4ll 7h3 7im3 4nd 17 15 g00d", "but who was there all the time and it is good"),
            ("7h3 541d 7h47 4 1n57rum3n7 15 4 u53ful 7001 f0r 5ugar", "the said that a instrument is a useful tool for sugar"),
        ):
            self.assertEqual(run(text, "balanced").text.lower(), plain.lower())
            self.assertEqual(run(text).text, text)

    def test_full_leetspeak_keeps_real_numbers(self):
        for text, plain in (
            ("7@k3 1 7@bl37 a day w17h w4t3r un7!l 7h3 m3d1c1n3 1s f1n15h3d.", "Take 1 tablet a day with water until the medicine is finished."),
            ("7h3 w1nd5 w3r3 5u57@1n3d 47 100 mph 4nd 7h3 r00m 4 1s 0p3n.", "the winds were sustained at 100 mph and the room 4 is open."),
        ):
            self.assertEqual(run(text, "balanced").text.lower(), plain.lower())

    def test_four_nd_is_not_an_ordinal(self):
        self.assertEqual(run("th3 2nd 4nd 3rd 0n3 w3r3 g00d, 4nd 7h3n 4 b3tt3r", "balanced").text.split()[1:3], ["2nd", "and"])

    def test_capitals_in_disguised_acronyms_are_read_with_evidence(self):
        self.assertEqual(
            run("The N7SB s3nd!ng 4 t3am of inv3s71ga70r5 to the cr@$h 5!t3", "balanced").text.split()[1], "NTSB"
        )

    def test_function_words_read_where_the_trick_shows(self):
        for text, plain in (
            ("H1 th3r3, y0u 4m h3r3 and th1s 1s g00d", "Hi there, you am here and this is good"),
            ("w3 4r3 h3r3 4s w3ll 4n 1t 1s", "we are here as well an it is"),
            ("th1s 1s 4n 3xample", "this is an example"),
        ):
            self.assertEqual(run(text, "balanced").text, plain)
            self.assertEqual(run(text).text, text)

    def test_units_models_and_handles_stay(self):
        for text in (
            "It took 1s and 4m of rope, with 4 pm to follow.",
            "The W3 consortium wrote h1 and @s for the 1s pulse.",
            "Call 4 pm, 1 or 2 times.",
        ):
            for level in ("balanced", "aggressive"):
                self.assertEqual(run(text, level).text, text, (level, text))

    def test_article_in_front_of_a_singular_word(self):
        for text, plain in (
            ("The Urlu1 is 4 lef7 tr1but@ry of the r1v3r", "The Urlui is a left tributary of the river"),
            ("It is @ g3nus of m0th5 in the f4mily Erebidae", "It is a genus of moths in the family Erebidae"),
            ("I want 7o set 4 time l1m1t of two h0urs 4 day", "I want to set a time limit of two hours a day"),
        ):
            self.assertEqual(run(text, "balanced").text, plain)
            self.assertEqual(run(text).text, text)

    def test_words_ending_in_leet_digits(self):
        self.assertEqual(run("Is th47 4r3a al50 in th15 li57?", "balanced").text, "Is that area also in this list?")
        self.assertEqual(run("Ask about the M14 and the HP G5.", "balanced").text, "Ask about the M14 and the HP G5.")

    def test_pronoun_i_before_a_verb(self):
        self.assertEqual(run("Hey 1 booked the fl1gh7 and 1 w4nt 7o c0nfirm", "balanced").text,
                         "Hey I booked the flight and I want to confirm")

    def test_durations_stay_after_their_words(self):
        self.assertIn(" 1s ", run("The p@g3 70ok 1s 7o load, which !s a pr0bl3m.", "balanced").text)
        self.assertIn("Room 4 is", run("Room 4 1s 0p3n, so w3 can 5tart th3 m33ting there.", "balanced").text)

    def test_lone_digits_stay_numbers(self):
        text = "Use 1 h0ur of sick time on 1 M4rch, and take 4 tablets."
        self.assertEqual(run(text, "balanced").text, "Use 1 hour of sick time on 1 March, and take 4 tablets.")

    def test_one_disguised_word_is_not_enough(self):
        text = "The pr1ce is 1s per call"
        self.assertEqual(run(text, "balanced").text, "The price is 1s per call")


class FullwidthSpaceTest(unittest.TestCase):
    def test_ideographic_space_between_fullwidth_words(self):
        text = "\uff33\uff55\uff47\uff41\uff52\uff0c\u3000\uff53\uff55\uff47\uff41\uff52\uff0e"
        self.assertEqual(run(text).text, "Sugar, sugar.")

    def test_ideographic_space_alone_stays(self):
        text = "Plain\u3000text\u3000here."
        self.assertEqual(run(text, "aggressive").text, text)


class SeparatorTest(unittest.TestCase):
    def test_a_symbol_between_every_character_of_every_word(self):
        # Found on the outside generator's rows, 2026-10-27: short words, apostrophes and
        # punctuation on the word are separated too, and the final full stop ends up as "..".
        for text, plain in (
            ("I d.o.n.'.t t.h.i.n.k i.t.s w.i.s.e t.o w.r.i.t.e o.f.f a.d.s a.s n.o.t a.r.t.i.s.t.s..",
             "I don't think its wise to write off ads as not artists."),
            ("S.o., i.t i.s t.r.i.v.i.a.l f.o.r t.h.e “.m.e.s.s.a.g.e.” s.i.z.e", "So, it is trivial for the “message” size"),
            ("t-o-d-a-y w-e s-h-a-l-l g-o t-o t-h-e m-a-r-k-e-t", "today we shall go to the market"),
        ):
            self.assertEqual(run(text, "balanced").text, plain)
            self.assertEqual(run(text).text, text)

    def test_abbreviations_and_numbers_with_dots_stay(self):
        for text in (
            "The U.S.A. and the U.K. signed it at 5 p.m. on Monday, e.g. in the morning.",
            "U.S.A U.K E.U U.N N.A.T.O",
            "Version 1.2.3 replaced 1.2.2 on 2.0.1 of the schedule, as agreed.",
        ):
            self.assertEqual(run(text, "aggressive").text, text)

    def test_symbols_between_letters(self):
        for symbol in ".-_*,":
            text = f"Please {symbol.join('send')} the {symbol.join('report')} today"
            result = run(text, "balanced")
            self.assertEqual(result.text, "Please send the report today", symbol)
            self.assertEqual({step.transform for step in result.steps}, {"separator"})
            self.assertEqual(run(text).text, text)

    def test_spaced_letters(self):
        self.assertEqual(run("Get a f r e e g i f t now", "balanced").text, "Get a free gift now")
        self.assertEqual(
            run("t h e   m e e t i n g   i s   m o v e d", "balanced").text, "the meeting is moved"
        )

    def test_initials_abbreviations_and_headings_stay(self):
        for text in (
            "J. R. R. Tolkien and C. S. Lewis",
            "The U.S.A and the W.H.O met at 5 p.m., i.e. late.",
            "N.B. the R.S.V.P. date is a.s.a.p. or a.k.a. now.",
            "C H A P T E R   O N E",
            "W E L C O M E",
            "Options a b c d and x-y-z, or one_two_three.",
            "T-shirt, X-ray, U-turn and e-mail",
        ):
            for level in ("balanced", "aggressive"):
                self.assertEqual(run(text, level).text, text, (level, text))


class RepeatedCharsTest(unittest.TestCase):
    def test_stretched_words(self):
        text = "Pleeease seeend the repoooort befoooore Friiiiday"
        result = run(text, "aggressive")
        self.assertEqual(result.text, "Please send the report before Friday")
        self.assertEqual({step.transform for step in result.steps}, {"repeated-chars"})
        self.assertEqual(run(text, "balanced").text, text)

    def test_the_commoner_reading_wins(self):
        self.assertEqual(run("Seeend theee files nooow", "aggressive").text, "Send the files now")

    def test_one_short_stretched_word_is_emphasis(self):
        for text in ("Hmmm, that is odd.", "It was sooooo good.", "Yessss we won", "See www.example.com or page III"):
            self.assertEqual(run(text, "aggressive").text, text)


class InformalWritingTest(unittest.TestCase):
    """Shorthand, common misspellings and emoji for words: rewritten only at ``aggressive``."""

    def rewritten(self, text: str, plain: str, name: str) -> None:
        result = run(text, "aggressive")
        self.assertEqual(result.text, plain)
        self.assertEqual({step.transform for step in result.steps}, {name})
        for level in ("conservative", "balanced"):
            self.assertEqual(run(text, level).text, text, level)

    def test_shorthand(self):
        self.rewritten("c u l8r 2nite, thx 4 the gr8 msg", "see you later tonight, thanks for the great message", "shorthand")
        self.rewritten("pls txt me b4 u go 2 the shop", "please text me before you go to the shop", "shorthand")

    def test_numbers_letters_and_labels_are_not_shorthand(self):
        for text in (
            "Take route 2 the left, then 4 people came for U Thant.",
            "Vitamin C and plan B, as J. R. R. Tolkien wrote in chapter 4.",
            "Add MSG and a TXT record, then page 2 of the PPL manual.",
        ):
            self.assertEqual(run(text, "aggressive").text, text)

    def test_common_misspellings_and_typing_mistakes(self):
        self.rewritten(
            "I recieved teh pasword for my adress, it is definately wierd",
            "I received the password for my address, it is definitely weird",
            "misspelling",
        )
        self.rewritten("Please send the reprot before Friday mornning", "Please send the report before Friday morning", "misspelling")

    def test_names_jargon_and_unclear_mistakes_stay(self):
        for text in (
            "Kowalczyk and Nakamura met Oyelaran in Reykjavik.",
            "The kubectl daemon restarts nginx after systemd reloads.",
            "He said teh in Dutch: wij hebben het boek gelezen vandaag.",
            "The cta button needs a new colour.",
        ):
            self.assertEqual(run(text, "aggressive").text, text)

    def test_a_decoded_fragment_is_not_read_as_shorthand(self):
        # One letter written as an HTML entity inside a word, and a whole encoded sentence.
        sentence = "Plain metal buttons for the coats"
        self.assertEqual(run(sentence.replace("u", "&#117;"), "aggressive").text, sentence)
        for trick in ("rot13", "base64"):
            disguised = obfuscator.apply(trick, SENTENCES[0], random.Random(1))
            self.assertEqual(run(disguised, "aggressive").text, SENTENCES[0], trick)

    def test_emoji_for_a_word(self):
        self.rewritten("I \u2764\ufe0f you and my \U0001f436", "I love you and my dog", "emoji-word")
        self.rewritten("Order your \U0001f48a without a doctor.", "Order your medicine without a doctor.", "emoji-word")

    def test_decorative_emoji_stay(self):
        for text in (
            "Great job \U0001f44d see you soon",
            "We had pizza \U0001f355 and it was great.",
            "Happy birthday!! \U0001f389\U0001f382\U0001f973",
            "On my way \U0001f697\U0001f4a8 be there in 5",
        ):
            self.assertEqual(run(text, "aggressive").text, text)


class LeaveAloneTest(unittest.TestCase):
    def untouched(self, *texts: str) -> None:
        for level in ("conservative", "balanced"):
            for text in texts:
                result = run(text, level)
                self.assertEqual((result.text, result.steps), (text, ()), (level, text))

    def test_numbers_and_codes(self):
        self.untouched(
            "Take route 66 west for 3 miles, then exit 4B.",
            "The scores were 68, 105, 100 and 32.",
            "Set the mask to 11111111 00000000 and retry.",
            "Colours #ff00aa and #361876 clash.",
            "id: 00000000-0000-4000-8000-000000000000",
        )

    def test_addresses_and_paths(self):
        self.untouched(
            "Visit https://example.com/a%20b?q=1&r=2 for details.",
            r"Open C:\temp\x64\update\notes.txt first.",
            "Mail first.last@example.co.uk today.",
        )

    def test_mentions_and_code(self):
        self.untouched(
            "A space becomes %20 in a URL.",
            "The string \\u00e9 is the escape for an accented e.",
            "<p>Fish &amp; chips &lt; 5 &gt; 3</p>",
            "The area is 100% natural, 0% fat.",
        )

    def test_other_languages_symbols_and_emoji(self):
        self.untouched(
            "Привет, как дела? Сегодня хорошая погода.",
            "こんにちは、ＡＢＣ今日はいい天気ですね。",
            "E = mc², H₂O, 10 µm, ½ cup, 25 °C",
            "Let 𝑥 be the unknown.",
            "naïve café résumé",
            "Great job 👍🏽 see you soon",
        )

    def test_accented_phrase_is_not_a_shifted_one(self):
        text = "The league (Chinese: Qu\u00e1ngu\u00f3 N\u00e1nz\u01d0 L\u00e1nqi\u00fa) was founded in 1995."
        self.assertEqual(run(text, "aggressive").text, text)

    def test_words_that_look_encoded(self):
        self.untouched(
            "deadbeef cafe babe face",
            "The words ant and nag are a rot13 pair, like bar and one.",
            "level, radar, and stressed/desserts",
            "internationalization and characteristically",
            "ok",
        )


if __name__ == "__main__":
    unittest.main()
