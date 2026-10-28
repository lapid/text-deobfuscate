"""An emoji standing in for a word: "I ❤️ you", "Happy 🎂".

Informal writing, not disguise, so this runs only at the ``aggressive`` level.
Most emoji decorate a sentence rather than replace a word, and those are left
alone: one at the end of a sentence, one in a row of several, and one that
repeats the word next to it ("pizza 🍕").
"""

import re
from collections.abc import Iterable

from text_deobfuscate.transforms.base import Candidate, Transform

WORDS = {
    "❤": "love", "♥": "love", "🔥": "fire", "💰": "money", "💵": "money", "📱": "phone", "📞": "phone",
    "☎": "phone", "📧": "email", "✉": "letter", "🏠": "house", "🏡": "house", "🚗": "car", "🎁": "gift",
    "🔑": "key", "🌍": "world", "🌎": "world", "☀": "sun", "🌙": "moon", "⭐": "star", "🐶": "dog",
    "🐕": "dog", "🐱": "cat", "🐈": "cat", "📖": "book", "📚": "books", "💻": "computer", "🎂": "birthday",
    "🍰": "cake", "💊": "medicine", "☕": "coffee", "🍕": "pizza", "🍺": "beer", "🍷": "wine", "🏦": "bank",
    "👀": "eyes", "🎵": "music", "🎶": "music", "🌧": "rain", "❄": "snow", "🌳": "tree", "🌸": "flower",
    "🌹": "rose", "🐟": "fish", "🐦": "bird", "🐴": "horse", "👑": "crown", "🏫": "school", "🏥": "hospital",
    "✈": "plane", "🚆": "train", "🚢": "ship", "🚌": "bus", "💧": "water", "👶": "baby", "📷": "camera",
    "⚽": "football", "🎮": "game", "💡": "idea", "⏰": "time", "🍎": "apple", "💍": "ring", "🔒": "lock",
}
# A variation selector or a skin tone may follow the emoji itself.
EMOJI = re.compile("(" + "|".join(map(re.escape, WORDS)) + ")[️\U0001f3fb-\U0001f3ff]?")
WORD_BEFORE = re.compile(r"([A-Za-z]+) $")
WORD_AFTER = re.compile(r" ([A-Za-z]+)")
# After one of these an emoji is the noun, even at the end of a sentence: "happy 🎂", "my 🐶".
LEADS = frozenset(
    "a an the my your our his her their this that some no any of for with to in on at by and or happy "
    "good new big little old free more".split()
)


def is_symbol(char: str) -> bool:
    return char in WORDS or ord(char) >= 0x1F000 or char in "‍️"


class EmojiWord(Transform):
    name = "emoji-word"
    level = "aggressive"
    # The decision is made here, one emoji at a time; the scorer has nothing to add for one word.
    judged = False
    late = True

    def propose(self, text: str) -> Iterable[Candidate]:
        for match in EMOJI.finditer(text):
            word = WORDS[match.group(1)]
            before = WORD_BEFORE.search(text[: match.start()])
            after = WORD_AFTER.match(text, match.end())
            rest = text[match.end() :].lstrip(" ")
            if before is None or (rest and is_symbol(rest[0])):
                continue
            beside = {before.group(1).lower()} | ({after.group(1).lower()} if after else set())
            if beside & {word, word + "s", word.rstrip("s")}:
                continue
            if after is not None or before.group(1).lower() in LEADS:
                yield Candidate(match.start(), match.end(), word)
