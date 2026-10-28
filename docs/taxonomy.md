# Obfuscation taxonomy

What the tool undoes, at which strictness level, and what it leaves alone. Names in the first
column are the `tricks` labels used in `data/samples/`.

## In v1

| Trick | Example | Level | Risk and main guard |
|---|---|---|---|
| `zero-width` | `p​a​s​s` with invisible characters between letters | conservative | Low. Keep joiners inside emoji sequences and in non-Latin text |
| `styled-alphabet`, `fullwidth` | `𝐇𝐞𝐥𝐥𝐨`, `Ｈｅｌｌｏ` | conservative | Low. Leave lone symbols such as `²`, `½`, `µ` |
| `html-entity` | `Tom &amp; Jerry` | conservative | Low. Not inside text that is about HTML |
| `url-percent` | `free%20prize` | conservative | Low to medium. Not inside a URL |
| `backslash-escape` | `\x48\x65`, `\u0048` | conservative | Medium. Not file paths; not `\n` in prose |
| `base64`, `base64url` | `SGVsbG8gd29ybGQ=` | conservative | Medium. Result must be valid, printable, and score as English; tokens and keys do not |
| `hex`, `binary`, `decimal-codes` | `48 65 6c 6c 6f` | conservative | Medium. Hashes, UUIDs and colour codes decode to noise and are rejected |
| `rot13`, `caesar` | `Uryyb jbeyq` | conservative | Medium. Needs enough words; short real words can be rot13 pairs |
| `reverse` | `dlrow olleH` | conservative | Medium. Needs enough words; palindromes. A run may continue across a word that reads both ways (`eht no detubed`) if it has 12 letters or more |
| `tag-characters` | Invisible Unicode tag characters carrying hidden text | conservative | Low. Removed from the text; the hidden content is shown in the step record |
| `combining-marks` | `H̶e̶l̶l̶o̶` | balanced | Medium. Accents on real letters stay |
| `homoglyph` | `аccount` with a Cyrillic `а` | balanced | High. Only in mixed-script words, or when the result is a known word. Roman-numeral characters and a few symbols (`¢`, `₫`, `∨`, `¡`) are read as letters only inside a word that becomes a known word; `µm` and `5¢` stay. Small capitals (`ꜰʀᴇᴇ ᴘʀɪᴢᴇ`) count here, not as `accent-substitution`: Unicode files them as Latin letters but they are an alphabet, not an accent |
| `accent-substitution` | `yōũr pass words`, `taĺk` | balanced | High. Seen in real phishing mail. Remove an accent only when the word is not a known word with it and is one without it; `café` and names stay |
| `leetspeak` | `h3ll0`, `p@$$w0rd`, `h1`, `1s` | balanced | High. Result must be a known word; shorthand such as `l8r`, `sum1` is left alone; two-character function words (`1s`, `4n`) and a lone `4` or `@` for "a" only beside two longer disguised words, never after a number, preposition or list word |
| `separator` | `f r e e`, `c.l.i.c.k` | balanced | High. Initials, abbreviations, spaced headings |
| `repeated-chars` | `heeellooo` | aggressive | High. Emphasis is often intended; several valid collapses |

### Added after the coverage survey (2026-10-24)

From the maintainer's coverage survey of published obfuscation techniques. All at `conservative`: each has input that
ordinary English does not contain.

| Trick | Example | Level | Risk and main guard |
|---|---|---|---|
| `quoted-printable` | `account=20is=20suspended` | conservative | Medium. A word with two escapes is the notation; one alone is a mention or a formula (`x=10`, `=A1+B2`) unless another word shows it. A soft line break (`=` at a line end) is evidence by itself |
| `mime-word` | `=?UTF-8?B?...?=`, `=?utf-8?Q?...?=` | conservative | Low. The wrapper cannot be anything else, and the encoding letter must be `B` or `Q`, so prose about the notation is left alone |
| `base32` | `MNWGSY3LEBUGK4TFEB2G6IDW` | conservative | Medium. Licence keys share the alphabet; told apart by not decoding to readable English |
| `octal-escape` | `\143\154\151\143\153` | conservative | Medium. Three escapes in a row at least: `\033` alone is a real escape in a shell command. Four notations: padded, unpadded (`\40`), the JavaScript `\0143` form, and octal mixed with `\x` hex in one run. Reported as `backslash-escape` |
| `rot47` | `!=62D6 G6C:7J` | conservative | Medium. Same guards as `caesar`, 10 letters. A run may grow over fragments with no letters (`@?` is "on") |
| `atbash` | `xorxp sviv` | conservative | Medium. Same guards as `caesar`, 10 letters |
| `morse` | `-.-. .-.. .. -.-. -.-` | conservative | Medium. Capitals cannot come back. An ellipsis, a rule of dashes, a row of underscores or a markdown table's pipes decodes to a letter or two, which the minimum on letters refuses. Words may be parted by a slash, a double slash, a pipe, a wider gap or a line break; the marks may be `.`/`-`, `·`/`−` or the underscore for a dash |
| `word-reverse` | `esaelP dnes eht troper` | conservative | Medium. Each word backwards with the word order kept. Reported as `reverse`. Only told from a wholly reversed text by where the capital and the full stop sit, so inside clean text it is usually missed |

### Informal writing (`aggressive` only)

These three are not disguise: people write this way on purpose. They were added to version 1 on
2026-10-12 at the owner's request, in a narrow form, and run only at `aggressive` and only after
every other transform has finished.

| Trick | Example | Level | Main guard |
|---|---|---|---|
| `shorthand` | `c u l8r`, `thx 4 the msg` | aggressive | A short list of forms with one usual meaning. `2`, `4`, `r`, `c` and forms in capitals only where the neighbouring words make the meaning plain |
| `misspelling` | `recieve`, `teh`, `adress` | aggressive | A list of common misspellings, plus two typing slips (neighbouring letters swapped, a letter doubled) when exactly one known word results. Names and jargon stay |
| `emoji-word` | `I ❤️ you`, `Happy 🎂` | aggressive | A short list. Only between words or after a word like "my" or "the". Decorative emoji stay |

Stacked and partial cases are in scope for all of the above: several layers on one span, and an
obfuscated span inside clean text.

## Out of scope

| Thing | Example | Why |
|---|---|---|
| Wrong-encoding damage | `ú1.20` for `£1.20`, `Ã©` for `é` | Not in v1; a separate problem with dedicated tools. Must come back unchanged |
| Uncommon spelling mistakes, dropped letters, slang | `pirze`, `gol`, `gonna` | Would need general spelling correction; rewrites the author's words |
| Shorthand and emoji outside the short lists | `prolly`, ✨ for "wonderful" | No single usual meaning |
| Keyed ciphers | Vigenere, XOR | Needs key search; later |
| Bidi controls, deletion controls, the rest of Unicode's invisible characters, variation-selector payloads, letter-shaped emoji, regional indicators, superscripts | | Surveyed and deferred to version 2 (owner, 2026-10-24), to be judged on a set the agent has not seen. Samples exist in the evaluation sets and are scored as out of scope |
| Upside-down text, a word split once by a hyphen, empty HTML tags inside a word | `ʎouǝɯ`, `fr-ee`, `fr<b></b>ee` | Surveyed and deferred to version 2: each needs judgment about words |
| Dropped vowels, truncation, scrambled letters, phonetic spelling, pig latin, reversed word order | `clck hr`, `Cilck hree` | Surveyed and ruled out: no single answer, or needs the meaning of the sentence |
| Code obfuscation | Minified or packed scripts | Different problem |
| Languages other than English | | Returned unchanged |
| Compression, encryption, file formats | gzip, PGP | Not text obfuscation |
