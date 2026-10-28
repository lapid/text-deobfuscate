"""Samples for leetspeak function words ("1s", "4n", "h1", "4") and the digit look-alikes that must stay.

Two kinds, both added after the first build so every earlier row is unchanged:

- ``positives``: text in which function words are written with digits or symbols
  ("th1s 1s 4 t3st"), whole and inside clean text, plus conversational sentences and
  sentences that keep real numbers beside disguised words.
- ``CATEGORIES``: clean text whose digits only look like a function word ("It took 1s",
  "Page 4 is blank", "the h1 tag"). It must come back unchanged at every level.

The generator writes every function word that has a digit form, including the bare
"4" for "a" and "1" for "I", so the samples measure what the tool misses as well as
what it knows. The tool's own rules are separate and shorter.
"""

import re
from collections.abc import Callable, Iterator
from random import Random

from evaluation.obfuscator import LEET

FUNCTION_LEET = {
    "is": ("1s", "!s"), "as": ("4s", "@s"), "an": ("4n", "@n"), "at": ("@t", "4t"), "it": ("1t", "!t"),
    "in": ("1n", "!n"), "on": ("0n",), "or": ("0r",), "so": ("5o", "$o", "s0"), "we": ("w3",),
    "he": ("h3",), "me": ("m3",), "be": ("b3",), "hi": ("h1", "h!"), "am": ("4m", "@m"), "if": ("1f", "!f"),
    "oh": ("0h",), "no": ("n0",), "go": ("g0",), "do": ("d0",), "to": ("7o",),
}
ARTICLES = {"a": ("4", "@"), "i": ("1", "!")}
# A word on its own: not part of "1s", "h1", "W3C" or "can't".
WORD = re.compile(r"(?<![\w'’])[A-Za-z]+(?![\w'’])")
MIN_CONTENT = 2

CHAT = (
    "Hi there, this is a quick note about the meeting tomorrow.",
    "I think it is a good idea to send the report before Friday.",
    "We are at the office and the printer is broken again.",
    "He said it was a mistake, but nobody believed him.",
    "Oh no, the password is wrong and the account is locked.",
    "Please confirm your account, as it is about to expire.",
    "If you want to see the results, go to the shared folder.",
    "Do you know an easy way to reset the router?",
    "It is a lovely morning and we are going to the market.",
    "Thanks for the update, I am happy to join the call.",
    "This is an important message about your delivery.",
    "She is a doctor at the hospital on the corner.",
    "Hi, am I at the right place for the interview?",
    "So the package is on the way and it should arrive soon.",
    "Be careful with the link, it is not from the bank.",
    "We have a problem with the server and it is down.",
    "Your order is ready, go to the counter to collect it.",
    "He is a friend of mine and we work on the same team.",
    "Is it true that the shop is closed on Sunday?",
    "As soon as the payment is done, I will send the files.",
    "I am sorry, but the ticket is no longer valid.",
    "Look at this photo, it is a picture from our holiday.",
    "We need to be home before the storm hits the town.",
    "Oh, it is a secret, so do not tell anyone about the surprise.",
    "Hi John, I am writing to ask about the invoice.",
    "It is time to go, the taxi is waiting outside.",
    "Is this an offer or a trick to get my details?",
    "The meeting is at noon, and we will be late.",
    "If it is not too much trouble, send me a copy of the contract.",
    "He has a new job at a bank in the city centre.",
    "Do not click the button, it is a fake page.",
    "We are in the garden and it is a beautiful evening.",
    "This is a reminder that your subscription is about to end.",
    "I am at home, so I can take the call at any time.",
    "She went to the station, as the train was already late.",
    "It is an honour to be here, and I am glad to help.",
    "So we are agreed, the party is on Saturday at the club.",
    "Is he a member of the club, or is he a guest?",
    "Hi all, the new schedule is attached to this message.",
    "Go ahead and open the file, it is safe to read.",
)

# Real numbers beside words that will be disguised. The numbers must stay.
WITH_NUMBERS = (
    "The page took 1s to load, which is a problem for our visitors.",
    "Please wait 4 minutes, then confirm the payment on the screen.",
    "Meet me at 4 pm, the library is closed after that.",
    "Room 4 is open, so we can start the meeting there.",
    "He scored 4 goals in the first half, which is a record.",
    "Step 1 is to open the email and step 4 is to reply.",
    "The report is on page 4, and the table is on the next page.",
    "We have 1 hour before the train leaves for the airport.",
    "Chapter 4 is about the history of the company and its owners.",
    "The delay was 1s on average, which is acceptable for a service like this.",
    "She bought 4 tickets for the concert on the first of March.",
    "In the 1st round it was close, but the second round was easy.",
    "Our tests ran for 4h and the results are in the shared folder.",
    "Update the h1 heading and then publish the page tonight.",
    "The W3 standard describes this feature in the last section.",
    "He ordered 4 coffees, and the waiter brought them within a minute.",
    "Take 1 tablet a day with water until the medicine is finished.",
    "The 1s and 0s on the screen are the output of the program.",
    "Level 4 is the hardest one, so practice before you try it.",
    "There are 4 reasons to choose this plan over the other one.",
)


def _content(word: str, rng: Random) -> str:
    spots = [i for i, char in enumerate(word) if char.lower() in LEET]
    if not spots:
        return word
    chosen = {i for i in spots if rng.random() < 0.7} or {rng.choice(spots)}
    return "".join(rng.choice(LEET[char.lower()]) if i in chosen else char for i, char in enumerate(word))


def disguise(text: str, rng: Random, *, articles: bool = False, functions: bool = True) -> str | None:
    """The text with function words and some longer words written in leetspeak.

    None unless at least two longer words and one function word (or article) changed.
    """
    made = {"content": 0, "function": 0}

    def change(match: re.Match) -> str:
        word = match.group()
        low = word.lower()
        if articles and low in ARTICLES and word.islower() and rng.random() < 0.8:
            made["function"] += 1
            return rng.choice(ARTICLES[low])
        if functions and low in FUNCTION_LEET and rng.random() < 0.7:
            made["function"] += 1
            form = rng.choice(FUNCTION_LEET[low])
            return word[0] + form[1:] if word[0].isupper() and form[0].isalpha() else form
        if len(word) >= 4 and rng.random() < 0.5:
            out = _content(word, rng)
            made["content"] += out != word
            return out
        return word

    out = WORD.sub(change, text)
    if made["content"] < MIN_CONTENT or not made["function"] or out == text:
        return None
    return out


def disguise_inside(text: str, rng: Random, **options: bool) -> str | None:
    """As ``disguise``, on one run of words inside the sentence."""
    words = text.split(" ")
    for _ in range(20):
        size = rng.randint(6, 10)
        if size >= len(words):
            return None
        start = rng.randint(0, len(words) - size)
        changed = disguise(" ".join(words[start : start + size]), rng, **options)
        if changed is not None:
            return " ".join([*words[:start], changed, *words[start + size :]])
    return None


WHOLE = 120
PARTIAL = 120
ARTICLE = 100
CHAT_PER_FRAME = 3
NUMBERS_PER_FRAME = 3


def positives(corpus: list[dict], rng: Random) -> Iterator[tuple[str, str, str, str, dict | None]]:
    """(category, mode, obfuscated, expected, corpus row or None for our own frames)."""
    pool = [row for row in corpus if 40 <= len(row["text"]) <= 170]

    def draw(category: str, mode: str, count: int, make: Callable[[str], str | None]) -> Iterator[tuple]:
        made = 0
        for row in rng.sample(pool, k=min(len(pool), count * 8)):
            text = make(row["text"])
            if text is not None:
                yield category, mode, text, row["text"], row
                made += 1
                if made == count:
                    return

    yield from draw("leet-function-words", "whole", WHOLE, lambda text: disguise(text, rng))
    yield from draw("leet-function-words", "partial", PARTIAL, lambda text: disguise_inside(text, rng))
    yield from draw("leet-article", "whole", ARTICLE, lambda text: disguise(text, rng, articles=True, functions=False))
    for frame in CHAT:
        for _ in range(CHAT_PER_FRAME):
            text = disguise(frame, rng, articles=rng.random() < 0.3)
            if text is not None:
                yield "leet-chat", "whole", text, frame, None
    for frame in WITH_NUMBERS:
        for _ in range(NUMBERS_PER_FRAME):
            text = disguise(frame, rng, articles=False)
            if text is not None:
                yield "leet-with-numbers", "partial", text, frame, None


# --- full leetspeak: every letter that has a digit form is written as the digit ----------

FULL = {"a": "4", "e": "3", "i": "1", "o": "0", "s": "5", "t": "7"}
FULL_WIDE = {**FULL, "l": "1", "b": "8", "g": "9", "z": "2"}
FULL_WHOLE = 200
FULL_PARTIAL = 100
FULL_WIDE_COUNT = 80


def full_leet(text: str, table: dict[str, str] = FULL, share: float = 1.0, rng: Random | None = None) -> str:
    """Every letter in the table becomes its digit (or, with a share below 1, most of them)."""
    return "".join(
        table[char.lower()] if char.lower() in table and (rng is None or rng.random() < share) else char
        for char in text
    )


def full_positives(corpus: list[dict], rng: Random) -> Iterator[tuple[str, str, str, str, dict | None]]:
    """The plain 1337 style: whole texts, a run inside a text, short lines, a wider table, real numbers kept."""
    pool = [row for row in corpus if 40 <= len(row["text"]) <= 170]
    sample = rng.sample(pool, k=min(len(pool), FULL_WHOLE + FULL_PARTIAL + FULL_WIDE_COUNT + 40))
    for row in sample[:FULL_WHOLE]:
        yield "leet-full", "whole", full_leet(row["text"]), row["text"], row
    for row in sample[FULL_WHOLE : FULL_WHOLE + FULL_PARTIAL]:
        words = row["text"].split(" ")
        size = min(len(words) - 1, rng.randint(6, 12))
        start = rng.randint(0, len(words) - size)
        changed = full_leet(" ".join(words[start : start + size]))
        yield "leet-full", "partial", " ".join([*words[:start], changed, *words[start + size :]]), row["text"], row
    for row in sample[FULL_WHOLE + FULL_PARTIAL :][:FULL_WIDE_COUNT]:
        yield "leet-full-wide", "whole", full_leet(row["text"], FULL_WIDE, 0.85, rng), row["text"], row
    for frame in CHAT:
        yield "leet-full-short", "whole", full_leet(frame), frame, None
    for frame in WITH_NUMBERS:
        yield "leet-full-with-numbers", "whole", full_leet(frame), frame, None


# --- clean text with digits that only look like a function word ---------------------

def _fill(templates: tuple[str, ...], **slots: tuple[str, ...]) -> Callable[[Random], str]:
    def make(rng: Random) -> str:
        return rng.choice(templates).format(**{name: rng.choice(options) for name, options in slots.items()})

    return make


N = tuple("1 2 3 4 5 6 7 8 9".split())
NOUNS = ("apples", "tickets", "goals", "questions", "owls", "boxes", "chairs", "pages", "cups", "answers", "points")
MONTHS = ("March", "May", "June", "October", "April", "January")

CATEGORIES: dict[str, tuple[Callable[[Random], str], int]] = {
    "digit-units": (_fill(
        ("It took {n}s to load the page.", "Latency is under {n}s per call.", "Wait {n}s, then retry.",
         "The timeout is set to {n}s.", "The race lasted {n}h {n2}m in the rain.", "We need {n}m of rope for the knot.",
         "The pulse repeats every {n}s and the signal is clean.", "He ran the lap in {n}m {n2}s."),
        n=N, n2=N), 40),
    "digit-times": (_fill(
        ("Meet at {n} pm in the lobby.", "The shop closes at {n} am on Sunday.", "Call me after {n} p.m. tonight.",
         "The train leaves at {n}:30 and arrives at {n2}:15.", "Lunch is at {n} and the talk is at {n2}."),
        n=N, n2=N), 30),
    "digit-list-numbers": (_fill(
        ("Page {n} is blank.", "Step {n} is done; step {n2} is next.", "Chapter {n} is short.", "Room {n} is closed today.",
         "Item {n} is missing from the box.", "Section {n} as amended applies here.", "Level {n} is the hardest one.",
         "Row {n} is empty and row {n2} is full.", "Figure {n} is on the next page."),
        n=N, n2=N), 40),
    "digit-counts": (_fill(
        ("Buy {n} {noun} at the market.", "We saw {n} {noun} in the garden.", "There are {n} {noun} on the table.",
         "He scored {n} goals in the 1st half.", "Take {n} a day with water.", "Order {n} or {n2} {noun} today.",
         "Use {n} hour of sick time on {month} {n2}.", "She had {n} {noun} and {n2} questions."),
        n=N, n2=N, noun=NOUNS, month=MONTHS), 40),
    "digit-tech-terms": (_fill(
        ("The {term} is described in the last section.", "Update the {term} and publish the page.",
         "Check the {term} before you ship it.", "A new {term} arrived this week."),
        term=("h1 tag", "h1 heading", "W3 consortium", "W3C standard", "A4 paper", "B4 shelf", "m1 chip", "h1b visa",
              "4k screen", "1st place", "3d model", "x1 model", "P4 server")), 30),
    "digit-binary": (_fill(
        ("The 1s and 0s on the screen are the output.", "A file is just 1s and 0s underneath.",
         "Count the 1s in the {n}-bit number.", "Only 0s and 1s are allowed in the field."),
        n=N), 15),
}
