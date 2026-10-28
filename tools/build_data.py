"""Builds the data files shipped inside the package.

    uv run python tools/build_data.py

Writes into ``src/text_deobfuscate/data/``:

- ``words.txt``: English word list from SCOWL.
- ``ngrams.txt``: character four-gram counts from public-domain books.
- ``scripts.txt``: which script each Unicode character belongs to.
- ``lookalikes.txt``: non-ASCII letters that look like ASCII letters, from Unicode's confusables table.

Sources are downloaded into ``data/cache/`` on first use. The books used here
must never overlap with the evaluation corpus (``evaluation/sources.py``), or
the scorer would have seen the text it is evaluated on.
"""

import io
import re
import tarfile
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "cache"
OUT = ROOT / "src" / "text_deobfuscate" / "data"

SCOWL_URL = "https://downloads.sourceforge.net/project/wordlist/SCOWL/2020.12.07/scowl-2020.12.07.tar.gz"
SCOWL_MAX_SIZE = 60
SCOWL_ACCENTED_MAX_SIZE = 80
SCOWL_FILE = re.compile(r"final/(english|american|british|british_z)-(words|upper|proper-names|contractions|abbreviations)\.(\d+)$")

SCRIPTS_URL = "https://www.unicode.org/Public/UCD/latest/ucd/Scripts.txt"

# Project Gutenberg book numbers: fiction and non-fiction, all public domain in
# the United States, none used by the evaluation corpus.
NGRAM_BOOKS = (2701, 98, 1400, 345, 174, 76, 1260, 120, 219, 43, 2009, 3300, 147, 7370, 815, 1232, 2554, 1184, 2852, 1727)
NGRAM_SIZE = 4
NGRAM_MIN_COUNT = 3


def download(url: str, name: str) -> Path:
    path = CACHE / name
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        request = urllib.request.Request(url, headers={"User-Agent": "text-deobfuscate-build/0.1"})
        with urllib.request.urlopen(request, timeout=120) as response:
            path.write_bytes(response.read())
    return path


def build_words() -> int:
    words: set[str] = set()
    with tarfile.open(download(SCOWL_URL, "scowl/scowl.tar.gz")) as archive:
        for member in archive.getmembers():
            match = SCOWL_FILE.search(member.name)
            if not match or int(match.group(3)) > SCOWL_ACCENTED_MAX_SIZE:
                continue
            rare = int(match.group(3)) > SCOWL_MAX_SIZE
            for line in io.TextIOWrapper(archive.extractfile(member), encoding="iso-8859-1"):
                word = line.strip()
                # Rarer lists contribute only accented spellings ("résumé"), so that a
                # correctly accented word is known and is not mistaken for a disguise.
                if rare and word.isascii():
                    continue
                # Possessives are handled when text is split into words.
                if word and not word.endswith("'s"):
                    words.add(word)
    (OUT / "words.txt").write_text("\n".join(sorted(words)) + "\n", encoding="utf-8")
    return len(words)


def letters_only(text: str) -> str:
    """Lowercase letters with single spaces; everything else is a word break."""
    return " ".join(re.sub(r"[^a-z]+", " ", text.lower()).split())


def build_ngrams() -> tuple[int, int]:
    counts: Counter[str] = Counter()
    for book in NGRAM_BOOKS:
        raw = download(f"https://www.gutenberg.org/cache/epub/{book}/pg{book}.txt", f"gutenberg/pg{book}.txt").read_text(encoding="utf-8-sig")
        start = re.search(r"\*\*\* ?START OF.*?\*\*\*", raw)
        end = re.search(r"\*\*\* ?END OF", raw)
        text = " " + letters_only(raw[start.end() if start else 0 : end.start() if end else len(raw)]) + " "
        counts.update(text[i : i + NGRAM_SIZE] for i in range(len(text) - NGRAM_SIZE + 1))
    kept = {gram: count for gram, count in counts.items() if count >= NGRAM_MIN_COUNT}
    total = sum(counts.values())
    lines = [f"# {NGRAM_SIZE}-grams over a-z and space; total count {total}"]
    lines += [f"{gram}\t{count}" for gram, count in sorted(kept.items())]
    (OUT / "ngrams.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(kept), total


def build_scripts() -> int:
    ranges: list[tuple[int, int, str]] = []
    for line in download(SCRIPTS_URL, "unicode/Scripts.txt").read_text(encoding="utf-8").splitlines():
        match = re.match(r"([0-9A-F]+)(?:\.\.([0-9A-F]+))?\s*;\s*(\w+)", line)
        if match:
            ranges.append((int(match.group(1), 16), int(match.group(2) or match.group(1), 16), match.group(3)))
    ranges.sort()
    merged: list[list] = []
    for start, end, script in ranges:
        if merged and merged[-1][2] == script and merged[-1][1] + 1 == start:
            merged[-1][1] = end
        else:
            merged.append([start, end, script])
    (OUT / "scripts.txt").write_text("".join(f"{start:X} {end:X} {script}\n" for start, end, script in merged), encoding="utf-8")
    return len(merged)


def build_lookalikes() -> int:
    """Non-ASCII letters that Unicode lists as looking like ASCII letters.

    Only this direction is safe to apply: the full table also maps ASCII to
    ASCII ("m" to "rn", "1" to "l"). 
    """
    import unicodedata

    lines = []
    for line in (ROOT / "data" / "reference" / "confusables.txt").read_text(encoding="utf-8-sig").splitlines():
        fields = [field.strip() for field in line.split("#")[0].split(";")]
        if len(fields) < 2 or not fields[0]:
            continue
        source = "".join(chr(int(code, 16)) for code in fields[0].split())
        target = "".join(chr(int(code, 16)) for code in fields[1].split())
        if len(source) != 1 or source.isascii() or not unicodedata.category(source).startswith("L"):
            continue
        # Styled and fullwidth letters fold to ASCII by themselves and have their own transform.
        if unicodedata.normalize("NFKC", source).isascii():
            continue
        if target.isascii() and target.isalpha() and len(target) <= 2:
            lines.append(f"{source}\t{target}")
    (OUT / "lookalikes.txt").write_text("\n".join(sorted(lines)) + "\n", encoding="utf-8")
    return len(lines)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"words: {build_words()}")
    kept, total = build_ngrams()
    print(f"ngrams: {kept} kept, {total} counted")
    print(f"scripts: {build_scripts()} ranges")
    print(f"lookalikes: {build_lookalikes()}")


if __name__ == "__main__":
    main()
