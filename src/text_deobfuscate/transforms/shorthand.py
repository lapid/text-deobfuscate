"""Texting shorthand written out: "c u l8r" becomes "see you later".

This is informal writing, not disguise, so it runs only at the ``aggressive``
level. The list is short and holds only forms with one usual meaning. One- and
two-character forms that are also ordinary text ("2", "4", "r", "c", "U") are
written out only where the words next to them make the meaning plain.
"""

import re
from collections.abc import Iterable

from text_deobfuscate.transforms.base import Candidate, Transform

TOKEN = re.compile(r"(?<![\w'’@#/.\-])[A-Za-z0-9]+(?![\w'’@/\-])")

ALWAYS = {
    "ur": "your", "l8r": "later", "gr8": "great", "b4": "before", "pls": "please", "plz": "please",
    "thx": "thanks", "thnx": "thanks", "tnx": "thanks", "tmrw": "tomorrow", "2moro": "tomorrow",
    "2morrow": "tomorrow", "2mrw": "tomorrow", "2nite": "tonight", "2day": "today", "ppl": "people",
    "cuz": "because", "coz": "because", "msg": "message", "txt": "text", "abt": "about", "tho": "though",
    "thru": "through", "luv": "love", "nite": "night", "sum1": "someone", "some1": "someone",
    "any1": "anyone", "every1": "everyone", "evry1": "everyone", "4ever": "forever", "w8": "wait",
    "m8": "mate", "wknd": "weekend", "bday": "birthday", "u": "you", "wat": "what",
    "wot": "what", "frm": "from", "jst": "just", "gd": "good", "rly": "really", "2gether": "together",
    "4get": "forget", "4got": "forgot", "h8": "hate", "sry": "sorry", "bcoz": "because", "wud": "would",
    "cud": "could", "shud": "should", "enuf": "enough",
}
# Also a name ("Ty"), so read only in capitals.
CAPITALS_ONLY = {"ty": "thank you"}
# Read only next to these words: "r u", "we r", "c u", "i c".
BESIDE = {
    "r": ("are", frozenset(("u you y we they there how where what who why ur").split())),
    "c": ("see", frozenset(("u you ya i").split())),
}
# "2" and "4" are numbers unless a word like these follows: "4 u", "2 the", "2 come".
AFTER_NUMBER = {
    "4": ("for", frozenset(("u you me my ur your the a him her us them this that it ever").split())),
    "2": ("to", frozenset(("u you me my ur your the him her us them this it b be c see go come do get say tell call "
                          "ask have make know meet").split())),
}


# Words a number counts, so that "2 min" and "4 more" stay numbers.
COUNTED = frozenset(
    ("min hr hour day week month year more less other others each per of or and to in pm am am. x times people "
     "men women children percent million billion thousand hundred dozen").split()
)


def like(token: str, plain: str, shouting: bool = False) -> str:
    """``plain`` in the capitals of ``token``; all capitals only if the whole text is."""
    if token.isupper() and len(token) > 1 and shouting:
        return plain.upper()
    return plain.capitalize() if token[0].isupper() else plain


class Shorthand(Transform):
    name = "shorthand"
    level = "aggressive"
    # The decision is made here, word by word; the scorer has nothing to add for one word.
    judged = False
    late = True

    def propose(self, text: str) -> Iterable[Candidate]:
        tokens = list(TOKEN.finditer(text))
        sure: list[Candidate] = []
        unsure: list[Candidate] = []
        loose: list[Candidate] = []
        capitals = numbers = 0
        for index, match in enumerate(tokens):
            token = match.group()
            lower = token.lower()
            before = tokens[index - 1].group() if index else ""
            after = tokens[index + 1].group() if index + 1 < len(tokens) else ""
            if lower in ALWAYS or (lower in CAPITALS_ONLY and token.isupper()):
                candidate = Candidate(match.start(), match.end(), like(token, (ALWAYS | CAPITALS_ONLY)[lower], text.isupper()))
                # In capitals these are also names and labels: "U Thant", "MSG", "a TXT record".
                (unsure if token.isupper() else sure).append(candidate)
                capitals += token.isupper() and len(token) > 1
            elif lower in BESIDE:
                plain, words = BESIDE[lower]
                if before.lower() in words or after.lower() in words:
                    sure.append(Candidate(match.start(), match.end(), like(token, plain, text.isupper())))
            elif lower in AFTER_NUMBER:
                plain, words = AFTER_NUMBER[lower]
                if before.isdigit() or not (after.islower() or text.isupper()):
                    continue
                if after.lower() in words:
                    unsure.append(Candidate(match.start(), match.end(), plain))
                    numbers += 1
                elif after.isalpha() and not after.lower().endswith("s") and after.lower() not in COUNTED:
                    # "2 walk", "4 help": only in a text that is plainly written in shorthand.
                    loose.append(Candidate(match.start(), match.end(), plain))
        yield from sure
        # Without a plain case, a form in capitals and a number read as a word must back each other up.
        if sure or (capitals and numbers):
            yield from unsure
        if len(sure) >= 2:
            yield from loose
