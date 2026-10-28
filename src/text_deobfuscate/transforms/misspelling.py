"""Common spelling mistakes and common typing mistakes: "recieve", "teh", "adress".

Informal writing, not disguise, so this runs only at the ``aggressive`` level,
and it is narrow on purpose. A word is corrected when it is not a known word and
either it is on a short list of well-known misspellings, or exactly one known
word is reached by swapping two neighbouring letters or removing a doubled one.
Names, jargon and anything with several possible corrections are left alone.
"""

import re
from collections.abc import Iterable

from text_deobfuscate import resources, scorer
from text_deobfuscate.transforms.base import Candidate, Transform

WORD = re.compile(r"(?<![\w'’@#/.\-])[A-Za-z]+(?![\w'’@/\-])")
MIN_TYPO_LENGTH = 6
# Share of the other words that must be known; below it the text is not plain English.
MIN_KNOWN = 0.7

COMMON = {
    "teh": "the", "adn": "and", "taht": "that", "wiht": "with", "thier": "their", "recieve": "receive",
    "recieved": "received", "definately": "definitely", "definitly": "definitely", "seperate": "separate",
    "seperately": "separately", "untill": "until", "wich": "which", "becuase": "because",
    "beacuse": "because", "beleive": "believe", "belive": "believe", "goverment": "government",
    "tommorow": "tomorrow", "tommorrow": "tomorrow", "tomorow": "tomorrow", "begining": "beginning",
    "diffrent": "different", "freind": "friend", "realy": "really", "adress": "address",
    "buisness": "business", "bussiness": "business", "calender": "calendar", "neccessary": "necessary",
    "necesary": "necessary", "occured": "occurred", "occurence": "occurrence", "wierd": "weird",
    "accomodate": "accommodate", "acheive": "achieve", "accross": "across", "agressive": "aggressive",
    "apparantly": "apparently", "arguement": "argument", "basicly": "basically", "collegue": "colleague",
    "comming": "coming", "commited": "committed", "concious": "conscious", "embarass": "embarrass",
    "enviroment": "environment", "existance": "existence", "familar": "familiar", "finaly": "finally",
    "foriegn": "foreign", "fourty": "forty", "gaurd": "guard", "grammer": "grammar", "happend": "happened",
    "harrass": "harass", "immediatly": "immediately", "independant": "independent", "knowlege": "knowledge",
    "liason": "liaison", "libary": "library", "lisence": "license", "maintainance": "maintenance",
    "noticable": "noticeable", "occassion": "occasion", "paralell": "parallel", "persistant": "persistent",
    "posession": "possession", "prefered": "preferred", "privelege": "privilege", "probaly": "probably",
    "publically": "publicly", "reccomend": "recommend", "recomend": "recommend", "refered": "referred",
    "relevent": "relevant", "rember": "remember", "remeber": "remember", "resistence": "resistance",
    "succesful": "successful", "successfull": "successful", "suprise": "surprise", "tendancy": "tendency",
    "therefor": "therefore", "threshhold": "threshold", "truely": "truly", "unfortunatly": "unfortunately",
    "usefull": "useful", "writting": "writing", "alot": "a lot", "aswell": "as well", "pasword": "password",
    "acount": "account", "adresses": "addresses", "congradulations": "congratulations", "garantee": "guarantee",
    "guarentee": "guarantee", "payed": "paid", "recieving": "receiving", "sucess": "success",
    "wether": "whether", "whith": "with", "woudl": "would", "shoudl": "should", "coudl": "could",
    "dont": "don't", "didnt": "didn't", "doesnt": "doesn't", "cant": "can't", "wont": "won't", "isnt": "isn't",
    "wasnt": "wasn't", "couldnt": "couldn't", "wouldnt": "wouldn't", "shouldnt": "shouldn't", "im": "I'm",
    "ive": "I've", "thats": "that's", "youre": "you're", "theres": "there's", "whats": "what's",
    "hes": "he's", "shes": "she's", "arent": "aren't", "werent": "weren't", "havent": "haven't",
    "hasnt": "hasn't",
}
# Listed forms that are also words; they are corrected only when spelled without capitals in mid-sentence.
ALSO_WORDS = frozenset({"cant", "wont", "im", "dont"})


def is_plain_word(word: str) -> bool:
    return word.lower() in resources.words()


ENDINGS = (("ies", "y"), ("es", ""), ("s", ""), ("ed", ""), ("ed", "e"), ("ing", ""), ("ing", "e"), ("ly", ""),
           ("er", ""), ("er", "e"), ("est", ""), ("ness", ""), ("ise", "ize"), ("ised", "ized"), ("isation", "ization"))


def is_inflected_word(word: str) -> bool:
    """A regular form of a known word that the word list does not spell out ("militaries")."""
    return any(word.endswith(ending) and is_plain_word(word[: -len(ending)] + instead) for ending, instead in ENDINGS)


def typing_fix(word: str) -> str | None:
    """The one known word reached by undoing a swap of neighbours or a doubled letter."""
    found: set[str] = set()
    for index in range(len(word) - 1):
        if word[index] == word[index + 1]:
            found.add(word[:index] + word[index + 1 :])
        else:
            found.add(word[:index] + word[index + 1] + word[index] + word[index + 2 :])
    known = {plain for plain in found if is_plain_word(plain)}
    return known.pop() if len(known) == 1 else None


def like(token: str, plain: str) -> str:
    if token.isupper() and len(token) > 1:
        return plain.upper()
    return plain[0].upper() + plain[1:] if token[0].isupper() else plain


class Misspelling(Transform):
    name = "misspelling"
    level = "aggressive"
    # The decision is made here, word by word; the scorer has nothing to add for one word.
    judged = False
    late = True

    def propose(self, text: str) -> Iterable[Candidate]:
        found: list[Candidate] = []
        known = total = 0
        for match in WORD.finditer(text):
            word = match.group()
            lower = word.lower()
            if lower in COMMON and (lower not in ALSO_WORDS or word.islower()) and not (word.isupper() and len(word) < 4):
                if lower in ALSO_WORDS or not is_plain_word(word):
                    found.append(Candidate(match.start(), match.end(), like(word, COMMON[lower])))
                    continue
            if len(word) > 1:
                total += 1
                known += scorer.is_word(word)
            if len(word) >= MIN_TYPO_LENGTH and word.islower() and not scorer.is_word(word) and not is_inflected_word(word):
                plain = typing_fix(word)
                if plain is not None:
                    found.append(Candidate(match.start(), match.end(), plain))
        if found and (not total or known >= total * MIN_KNOWN):
            yield from found
