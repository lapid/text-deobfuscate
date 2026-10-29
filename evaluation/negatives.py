"""Generates clean text that looks like obfuscation but must come back unchanged."""

import base64
import uuid
from collections.abc import Callable
from random import Random

CARRIERS = (
    "{}",
    "Please check {} before you reply.",
    "The value is {} as far as I can tell.",
    "See {} for details.",
    "I was given {} yesterday.",
    "Note: {}",
)

NUMBERS = (
    "Take route 66 west for 3 miles, then exit 4B.",
    "We shipped v2.0.1 on 2026-10-08 at 14:30.",
    "The model is a B4 and the part number is X1-900E.",
    "Flight BA2490 departs gate A1 at 06:05.",
    "Call 0800 169 6031 between 10am and 9pm.",
    "It costs $4.50, or 3 for $12, until 31/12.",
    "Fe2O3 and C6H12O6 react at pH 7.4.",
    "Set the timer to 00:45 and the oven to 180C.",
    "Room 101 is on floor 1, next to lift 3A.",
    "The 1st, 2nd and 3rd prizes go to teams 7, 11 and 40.",
    "My postcode is LS1 3AJ and my bus is the 5A.",
    "Order #A1B2-0034 ships in 3-5 days.",
    "Windows 11, iOS 17 and Python 3.14 are supported.",
    "The ratio was 4:3 in 1080p and 16:9 in 4K.",
    "Mix 100ml of H2O with 5g of NaCl.",
)

URLS = (
    "https://example.com/a%20b?q=1&r=2",
    "https://example.org/search?q=free%20prize&lang=en#top",
    "http://example.net/files/My%20Report%20%28final%29.pdf",
    "https://example.com/path/to/page.html?ref=abc123&utm_source=mail",
    "www.example.co.uk/~user/index.php?id=42",
    "https://example.com/caf%C3%A9/menu",
    "ftp://files.example.com/pub/v1.2.3/",
    "https://example.com/redirect?to=https%3A%2F%2Fexample.org%2Fhome",
)

EMAILS = (
    "first.last+tag@example.co.uk",
    "j0hn_d03@example.com",
    "support-team@mail.example.org",
    "a.b.c.d@example.net",
    "info@4u-example.com",
)

PATHS = (
    r"C:\Users\name\new\table.txt",
    r"C:\temp\x64\update\notes.txt",
    r"\\server\share\reports\2026\q3.xlsx",
    "/usr/local/lib/python3.14/site-packages",
    "~/projects/app/src/utils/base64.js",
    r"D:\backup\u0041rchive\file.bin",
    "./build/x86_64/release/app.exe",
)

CODE = (
    "print(base64.b64encode(b'hi'))  # aGk=",
    'pattern = re.compile(r"\\x00|\\u200b|\\s+")',
    "<p>Fish &amp; chips &lt; 5 &gt; 3</p>",
    'echo "Hello\\tWorld\\n" | tr a-z A-Z',
    "const s = '\\u00e9t\\u00e9';",
    "SELECT name FROM users WHERE id = 0x1F;",
    "color: #ff00aa; margin: 0 auto;",
    "curl 'https://example.com/?q=a%20b' -H 'Accept: */*'",
    "if (x & 0xFF) == 0b1010: return x << 2",
    "git checkout -b fix/issue-42 && git push -u origin HEAD",
    "for i in range(10): total += i ** 2",
    'String s = new String(bytes, "UTF-8");',
)

ABOUT = (
    "In HTML, write &amp; to show an ampersand and &lt; for a less-than sign.",
    "Use \\n for a newline and \\t for a tab.",
    "A space becomes %20 in a URL.",
    "The string \\u00e9 is the escape for an accented e.",
    "Type &nbsp; when you need a non-breaking space.",
    "Base64 text often ends with = or ==.",
)

NON_ENGLISH = (
    "Привет, как дела? Сегодня хорошая погода.",
    "Я не знаю, что сказать по этому поводу.",
    "Москва — столица России.",
    "Спасибо большое за вашу помощь.",
    "Η Ελλάδα είναι όμορφη το καλοκαίρι.",
    "Καλημέρα, τι κάνεις σήμερα;",
    "Ευχαριστώ πολύ για τη βοήθεια.",
    "שלום עולם, מה שלומך היום?",
    "אני לא יודע מה להגיד על זה.",
    "תודה רבה על העזרה שלך.",
    "Bonjour, comment ça va aujourd'hui ?",
    "Je ne sais pas ce qu'il faut dire à ce sujet.",
    "Guten Morgen, wie geht es Ihnen heute?",
    "Die Straße ist wegen Bauarbeiten gesperrt.",
    "¿Dónde está la estación de tren más cercana?",
    "Mañana vamos a la playa con los niños.",
    "Grazie mille per il vostro aiuto.",
    "こんにちは、今日はいい天気ですね。",
    "你好，今天天气很好。",
    "مرحبا، كيف حالك اليوم؟",
    "Dziękuję bardzo za pomoc.",
    "Jag vet inte vad jag ska säga om det.",
)

MIXED_SCRIPT = (
    "I visited Москва and Αθήνα last year.",
    "The Russian word мир means both peace and world.",
    "In Greek, λόγος can mean word or reason.",
    "She signed the card with שלום at the bottom.",
    "The symbol π is about 3.14159 and Δ means change.",
    "Our Tokyo office (東京) opens at 9am.",
    "The Cyrillic letter а looks like the Latin a.",
    "Add α-tocopherol and β-carotene to the mix.",
)

ACCENTS = (
    "naïve café résumé",
    "Zoë Brontë and Søren Kierkegaard met Antonín Dvořák.",
    "The façade of the château was déjà vu.",
    "Beyoncé, Björk and Sinéad O'Connor",
    "A piñata, a jalapeño and crème brûlée.",
    "Señor Núñez lives in São Paulo.",
    "Händel and Brontë, Gödel and Erdős.",
)

EMOJI = (
    "Great job 👍🏽 see you 👨‍👩‍👧 soon",
    "Happy birthday!! 🎉🎂🥳",
    "On my way 🚗💨 be there in 5",
    "I ❤️ this so much 😂😂",
    "Flags: 🇬🇧 🇺🇸 🏳️‍🌈",
    "Thanks 🙏🏻 you're the best ✨",
)

SYMBOLS = (
    "E = mc², H₂O, 10 µm, ½ cup, 25 °C",
    "The area is 50 m² and the volume 12 m³.",
    "x ≤ 5 and y ≠ 0, so x·y → ∞ is false.",
    "Price: €20 or £17.50 — whichever is lower…",
    "© 2026 Example Ltd. All rights reserved ®",
    "Turn 90° left, then go ¼ mile.",
    "Use the № 5 key and the § 12 clause.",
)

SHORTHAND = (
    "c u l8r 2nite",
    "sum1 left this 4 u",
    "gr8 news, thx m8",
    "b4 u go, txt me",
    "im goin2bed now, nite",
    "wait 4 me, b there in 2 mins",
    "any1 want 2 come 2moro?",
    "dont4get 2 call ur mum",
    "that was 2 ez lol",
    "w8 4 it, almost done",
    "happy 18th! have a gr8 1",
    "U R 2 good 2 b 4gotten",
)

HEADINGS = (
    "W E L C O M E",
    "C H A P T E R   O N E",
    "S A L E   N O W   O N",
    "A. B. Smith, Ph.D., e.g. i.e. U.S.A.",
    "J. R. R. Tolkien and C. S. Lewis",
    "Meet at 5 p.m. in the U.K. office, i.e. room B.",
    "T-shirt, X-ray, U-turn and e-mail",
    "one_two_three and snake_case_name",
    "Rock * Paper * Scissors",
    "N.B. the R.S.V.P. date is a.s.a.p.",
)

EMPHASIS = (
    "Sooo good!!! Nooooo way.",
    "Yessss, finally!",
    "Aaaargh, I missed the bus again.",
    "That is sooooo cool.",
    "Hmmmm, let me think.",
    "Whaaat? Reeeally?",
    "Zzzzz... still asleep.",
    "Brrrr, it's freezing.",
)

WORD_PLAY = (
    "deadbeef cafe babe face",
    "a bad cafe added a faded facade",
    "The words ant and nag are a rot13 pair, like bar and one.",
    "level, radar, and stressed/desserts",
    "Was it a car or a cat I saw?",
    "xkcd, qwerty, asdf, lorem ipsum dolor sit amet",
    "Zyzzyva, syzygy and rhythm have odd spellings.",
    "live and evil, stop and pots, drawer and reward",
)

SHORT = ("ok", "No.", "Yes?", "Thanks!", "See you.", "lol", "Why not?", "On it.", "Hi", "Not now", "Good one", "OK then")

ACRONYMS = (
    "NASA, FBI and the EU met at the UN.",
    "The CEO of IBM spoke to the BBC about AI.",
    "FYI the ETA is ASAP, per the FAQ.",
    "URGENT: REPLY BY FRIDAY OR LOSE YOUR PLACE",
    "PDF, HTML, CSS, JSON and XML files",
)

# Accented text that was decoded with the wrong character encoding. Repairing
# it is out of scope, so it must come back unchanged.
MOJIBAKE_SOURCES = ("The café is closed on Monday.", "Send £20 to Zoë today.", "It’s a “quoted” word — see?", "Señor Núñez will be late.")


def _hex(rng: Random, length: int) -> str:
    return "".join(rng.choice("0123456789abcdef") for _ in range(length))


def _hash(rng: Random) -> str:
    kind = rng.choice(("commit", "sha256", "md5", "bare", "colour"))
    if kind == "commit":
        return f"commit {_hex(rng, rng.choice((7, 40)))}"
    if kind == "sha256":
        return f"sha256: {_hex(rng, 64)}"
    if kind == "md5":
        return f"md5 {_hex(rng, 32)}"
    if kind == "colour":
        return f"#{_hex(rng, 6)} and #{_hex(rng, 6).upper()}"
    return _hex(rng, rng.choice((16, 32, 40, 64)))


def _uuid(rng: Random) -> str:
    return str(uuid.UUID(int=rng.getrandbits(128), version=4))


def _token(rng: Random) -> str:
    raw = rng.randbytes(rng.choice((12, 16, 24, 32)))
    kind = rng.choice(("base64", "base64url", "hexkey"))
    if kind == "base64":
        return f"token={base64.b64encode(raw).decode()}"
    if kind == "base64url":
        return f"session id {base64.urlsafe_b64encode(raw).decode().rstrip('=')}"
    return f"key {raw.hex().upper()}"


def _mojibake(rng: Random) -> str:
    return rng.choice(MOJIBAKE_SOURCES).encode("utf-8").decode("cp1252", errors="replace")


def _from(options: tuple[str, ...], *, carried: bool = False) -> Callable[[Random], str]:
    def make(rng: Random) -> str:
        text = rng.choice(options)
        return rng.choice(CARRIERS).format(text) if carried else text

    return make


def _carried(make: Callable[[Random], str]) -> Callable[[Random], str]:
    return lambda rng: rng.choice(CARRIERS).format(make(rng))


# category -> (generator, how many per split)
CATEGORIES: dict[str, tuple[Callable[[Random], str], int]] = {
    "numbers": (_from(NUMBERS), 40),
    "hash": (_carried(_hash), 80),
    "uuid": (_carried(_uuid), 40),
    "token": (_carried(_token), 80),
    "url": (_from(URLS, carried=True), 40),
    "email": (_from(EMAILS, carried=True), 25),
    "path": (_from(PATHS, carried=True), 35),
    "code": (_from(CODE), 40),
    "about-obfuscation": (_from(ABOUT), 20),
    "non-english": (_from(NON_ENGLISH), 60),
    "mixed-script": (_from(MIXED_SCRIPT), 30),
    "accents": (_from(ACCENTS), 25),
    "emoji": (_from(EMOJI), 25),
    "symbols": (_from(SYMBOLS), 25),
    "shorthand": (_from(SHORTHAND), 40),
    "headings": (_from(HEADINGS), 30),
    "emphasis": (_from(EMPHASIS), 25),
    "word-play": (_from(WORD_PLAY), 25),
    "short": (_from(SHORT), 30),
    "acronyms": (_from(ACRONYMS), 20),
    "wrong-encoding": (_mojibake, 15),
}


# Added with the coverage survey: clean text
# that the survey's new transforms could mistake for their trick.

# Right-to-left text, where bidi marks and controls are correct.
BIDI = (
    "The sign said שלום\u200f and nothing else.",
    "שלום עולם\u200e (hello world) is the usual first program.",
    "مرحبا\u061c 2026 بالعربية",
    "Her name is written \u2067מרים\u2069 in Hebrew.",
    "\u202bזה טקסט בעברית\u202c",
    "Price: \u2066€25\u2069 per person.",
    "הספר \u202dABC-123\u202c נמצא במדף",
)

# Single variation selectors are how emoji and some characters are meant to be written.
# The emoji here are deliberately ones the tool does not read as words: an emoji that
# stands for a word is an intended rewrite at `aggressive`, tested by the `emoji`
# category, and would hide what this category is for.
SELECTORS = (
    "I packed my ☂️ before leaving.",
    "Press 1️⃣ for sales.",
    "The forecast shows ⛅️ today and ☔️ tomorrow.",
    "The family name 葛\U000e0100 is written with a variant form.",
    "Copyright ©️ 2026, all rights reserved.",
    "Please sort the waste ♻️ before Friday.",
)

# Flags are pairs of regional indicators.
FLAGS = (
    "We ship to \U0001f1fa\U0001f1f8 \U0001f1ec\U0001f1e7 \U0001f1eb\U0001f1f7 and \U0001f1e9\U0001f1ea.",
    "Go \U0001f1ee\U0001f1f9!",
    "Happy Canada Day \U0001f1e8\U0001f1e6",
    "\U0001f1ef\U0001f1f5\U0001f1f0\U0001f1f7\U0001f1e8\U0001f1f3 are the three teams left.",
    "Trip plan: \U0001f1ea\U0001f1f8 then \U0001f1f5\U0001f1f9",
    "\U0001f1fa\U0001f1f8\U0001f1fa\U0001f1f8\U0001f1fa\U0001f1f8",
)

# Superscripts and modifier letters in ordinary use: maths, ordinals, phonetics.
SUPERSCRIPTS = (
    "E = mc² and xⁿ + yⁿ = zⁿ.",
    "The meeting is on the 1ˢᵗ of May.",
    "She came 2ⁿᵈ and he came 3ʳᵈ.",
    "In English, the p in pin is aspirated: [pʰɪn].",
    "The plural is written kʷ in some transcriptions.",
    "Mᵐᵉ Dupont will see you now.",
    "The unit is m² or km², not m2.",
)

# Equals signs and dashes in ordinary text.
EQUALS_AND_DASHES = (
    "Set x=10, y=20 and z=30 before the loop.",
    "In Excel, type =A1+B2 to add them.",
    "2+2=4 and 3+3=6, as every child knows.",
    "Use LIMIT=20 and RETRY=3 in the config file.",
    "The header syntax is =?charset?encoding?text?= as the RFC says.",
    "Wait for it... -- and then -- nothing.",
    "Loading ... ... ... done.",
    "Use -v or --verbose for more output.",
    "In Morse code, SOS is ... --- ...",
    "----- end of message -----",
    "Score: 3 - 1. Next game: Saturday.",
    "A long line =========== under a heading.",
)

# Octal-looking escapes in code, and capitals that look like base32.
CODE_LIKE = (
    "printf '\\033[1;31mError\\033[0m\\n'",
    "Run chmod 755 script.sh and then ./script.sh",
    "The escape \\012 is a newline in octal.",
    "Your code is JBSWY3DPEHPK3PXP; keep it secret.",
    "Licence key: MFRGGZDFMZTWQ2LK",
    "Order ABCDEFGHIJKLMNOPQRSTUVWXYZ234567 is the base32 alphabet.",
    "Ticket NBSWY3DPEB3W64TMMQ======",
)

# Korean text, where Hangul fillers are part of the writing system.
HANGUL = (
    "ㅤㅤ is a blank name some players use.",
    "가ᅟᅠ are jamo letters.",
    "안녕하세요ㅤ반갑습니다",
)

LATER_CATEGORIES: dict[str, tuple[Callable[[Random], str], int]] = {
    "bidi": (_from(BIDI), 7),
    "variation-selectors": (_from(SELECTORS), 6),
    "flags": (_from(FLAGS), 6),
    "superscripts": (_from(SUPERSCRIPTS), 7),
    "equals-and-dashes": (_from(EQUALS_AND_DASHES), 12),
    "code-like": (_from(CODE_LIKE), 7),
    "hangul": (_from(HANGUL), 3),
}


def generate(rng: Random, categories: dict[str, tuple[Callable[[Random], str], int]] | None = None) -> list[tuple[str, str]]:
    """Distinct (category, text) pairs."""
    out: list[tuple[str, str]] = []
    for category, (make, count) in (CATEGORIES if categories is None else categories).items():
        seen: set[str] = set()
        for _ in range(count * 5):
            if len(seen) >= count:
                break
            seen.add(make(rng))
        out.extend((category, text) for text in sorted(seen))
    return out
