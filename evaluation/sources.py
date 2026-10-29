"""Downloads raw text from each source into ``data/cache/``.

Each ``fetch_*`` function returns documents as dicts with ``text`` or
``paragraphs``, a ``source`` credit line, a ``url`` and a ``licence``. Results
are cached, so a second run does no network requests. Random sampling by the
remote sites means a fresh download gives different documents: the committed
corpus files, not this module, are the record of what the evaluation uses.
"""

import gzip
import html
import json
import re
import time
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "cache"
USER_AGENT = "text-deobfuscate-eval/0.1 (https://github.com/lapid/text-deobfuscate)"

# Project Gutenberg book numbers, all published before 1929 (public domain in the United States).
BOOKS = {
    "dev": {1342: "Pride and Prejudice", 1661: "The Adventures of Sherlock Holmes", 64317: "The Great Gatsby",
            55: "The Wonderful Wizard of Oz", 20203: "Autobiography of Benjamin Franklin"},
    "test": {11: "Alice's Adventures in Wonderland", 84: "Frankenstein", 35: "The Time Machine", 2814: "Dubliners",
             541: "The Age of Innocence"},
}

STACK_EXCHANGE_SITES = ("english", "cooking", "travel", "superuser", "askubuntu", "workplace", "diy", "movies")
SMS_URL = "https://archive.ics.uci.edu/static/public/228/sms+spam+collection.zip"


def _get(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(request, timeout=60) as response:  # nosec B310
        data = response.read()
        return gzip.decompress(data) if response.headers.get("Content-Encoding") == "gzip" else data


def _cached_json(name: str, make) -> list[dict]:
    path = CACHE / name
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(make(), ensure_ascii=False), encoding="utf-8")
    return json.loads(path.read_text(encoding="utf-8"))


def fetch_books(split: str) -> list[dict]:
    docs = []
    for number, title in BOOKS[split].items():
        path = CACHE / "gutenberg" / f"pg{number}.txt"
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(_get(f"https://www.gutenberg.org/cache/epub/{number}/pg{number}.txt"))
        raw = path.read_text(encoding="utf-8-sig")
        start = re.search(r"\*\*\* ?START OF.*?\*\*\*", raw)
        end = re.search(r"\*\*\* ?END OF", raw)
        body = raw[start.end() if start else 0 : end.start() if end else len(raw)]
        paragraphs = []
        for block in re.split(r"\n\s*\n", body.replace("\r\n", "\n")):
            # Underscores mark italics in these files; they are markup, not the author's text.
            para = " ".join(block.replace("_", "").split())
            if para and "[" not in para and "Gutenberg" not in para and any(char.islower() for char in para):
                paragraphs.append(para)
        docs.append({"paragraphs": paragraphs, "source": f"{title} (public-domain book)",
                     "url": f"https://www.gutenberg.org/ebooks/{number}", "licence": "Public domain"})
    return docs


def _wiki_random(host: str, batches: int) -> list[dict]:
    query = urllib.parse.urlencode({
        "action": "query", "format": "json", "generator": "random", "grnnamespace": 0,
        "grnfilterredir": "nonredirects", "grnlimit": 20, "prop": "extracts|info", "inprop": "url",
        "explaintext": 1, "exintro": 1, "exlimit": 20,
    })
    pages: dict[str, dict] = {}
    for _ in range(batches):
        data = json.loads(_get(f"https://{host}/w/api.php?{query}"))
        for page in data.get("query", {}).get("pages", {}).values():
            if page.get("extract"):
                pages[page["title"]] = {"title": page["title"], "url": page["fullurl"],
                                        "revision": page.get("lastrevid"), "extract": page["extract"]}
        time.sleep(0.5)
    return sorted(pages.values(), key=lambda page: page["title"])


def fetch_wikipedia() -> list[dict]:
    pages = _cached_json("wikipedia.json", lambda: _wiki_random("en.wikipedia.org", 110))
    return [
        {"paragraphs": [" ".join(p.split()) for p in page["extract"].split("\n") if p.strip()],
         "source": f"Wikipedia: {page['title']}", "url": page["url"], "licence": "CC BY-SA 4.0"}
        for page in pages
        # Formula markup left in the plain-text extract is not prose.
        if "displaystyle" not in page["extract"]
    ]


def fetch_wikinews() -> list[dict]:
    pages = _cached_json("wikinews.json", lambda: _wiki_random("en.wikinews.org", 60))
    docs = []
    for page in pages:
        lines = [" ".join(line.split()) for line in page["extract"].split("\n") if line.strip()]
        year = re.search(r"\b(19|20)\d\d\b", lines[0]) if lines else None
        if not year or len(lines) < 2:
            continue
        # The first line is the dateline. The licence depends on the publication date;
        # articles from the changeover years are skipped rather than guessed.
        when = int(year.group())
        if when in (2005, 2024):
            continue
        licence = "Public domain" if when < 2005 else "CC BY 2.5" if when < 2024 else "CC BY 4.0"
        docs.append({"paragraphs": lines[1:], "source": f"Wikinews: {page['title']}", "url": page["url"], "licence": licence})
    return docs


def _stack_exchange() -> list[dict]:
    questions = []
    for site in STACK_EXCHANGE_SITES:
        for page in (2, 3, 4, 5):
            query = urllib.parse.urlencode({"site": site, "pagesize": 100, "page": page, "order": "desc",
                                            "sort": "activity", "filter": "withbody"})
            data = json.loads(_get(f"https://api.stackexchange.com/2.3/questions?{query}"))
            for item in data.get("items", []):
                questions.append({"site": site, "link": item["link"], "licence": item.get("content_license"),
                                  "author": html.unescape(item.get("owner", {}).get("display_name", "unknown")),
                                  "body": item["body"]})
            time.sleep(max(data.get("backoff", 0), 0.5))
    return questions


def fetch_stack_exchange() -> list[dict]:
    from evaluation.text import html_paragraphs

    return [
        {"paragraphs": html_paragraphs(question["body"]),
         "source": f"Stack Exchange ({question['site']}), question by {question['author']}",
         "url": question["link"], "licence": question["licence"]}
        for question in _cached_json("stack_exchange.json", _stack_exchange)
        if question["licence"] and question["licence"].startswith("CC BY-SA")
    ]


# Private details in personal messages are masked (owner, 2026-10-27). Only addresses that end in
# a real top-level domain count: "d@y5.w1ll" is a disguised word, not an address.
EMAIL = re.compile(
    r"[A-Za-z0-9._%+-]+@[A-Za-z-]+(?:\.[A-Za-z-]+)*\.(?:com|net|org|edu|gov|info|biz|co|uk|in|us|ca|au|de|sg|my)\b"
)
PHONE = re.compile(r"(?<![\w.])\d{9,}(?![\w])")


def mask_private(text: str) -> str:
    """Replace an email address or a long digit string (a phone number) with a placeholder."""
    return PHONE.sub(lambda match: "0" * len(match.group()), EMAIL.sub("user@example.com", text))


def fetch_sms() -> list[dict]:
    """Personal messages ("ham") from the SMS Spam Collection. Spam is left out."""
    path = CACHE / "sms" / "sms.zip"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(_get(SMS_URL))
    lines = zipfile.ZipFile(path).read("SMSSpamCollection").decode("utf-8").splitlines()
    docs = []
    for line in lines:
        label, _, text = line.partition("\t")
        if label == "ham" and text.strip():
            docs.append({"text": text.strip(), "source": "SMS Spam Collection v.1 (Almeida and Hidalgo, 2011)",
                         "url": "https://doi.org/10.24432/C5CC84", "licence": "CC BY 4.0"})
    return docs


BITCORE = "https://datasets-server.huggingface.co/rows?dataset=AutoML/bitcore&config=default&split=train"


def _bitcore() -> list[dict]:
    rows: list[dict] = []
    total = None
    while total is None or len(rows) < total:
        for attempt in range(6):
            try:
                data = json.loads(_get(f"{BITCORE}&offset={len(rows)}&length=100"))
                break
            except OSError:
                time.sleep(5 * (attempt + 1))
        else:
            raise RuntimeError(f"BitCore download failed at row {len(rows)}")
        total = data["num_rows_total"]
        rows.extend(item["row"] for item in data["rows"])
        time.sleep(0.3)
    return rows


def fetch_bitcore() -> list[dict]:
    """Real phishing sentences with visual perturbations and their restored text.

    The dataset states no licence, so it is used locally and never committed.
    Rows are {"id", "text", "label"}; labels are lowercased by the dataset's authors.
    """
    return _cached_json("bitcore.json", _bitcore)
