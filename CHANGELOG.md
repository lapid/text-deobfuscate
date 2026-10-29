# Changelog

All notable changes to this project are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/), with the usual caveat that anything before 1.0 may
change in a minor release.

## [Unreleased]

### Added

- `Result.truncated` (and `"truncated"` in `--json` output) is true when the input was over the
  size limit or the scanning budget ran out, so the text may be only partly decoded.
- Ruff, mypy (strict) and bandit run in CI, and the build checks that the wheel carries
  `py.typed` and the data files.

### Fixed

- Short reversed English ("dlrow olleh") is recovered again as a run of reversed words; only
  reversing a short text as a whole stays off, which keeps "No pasa nada" untouched.
- Accented English with a plural or regular ending ("façades", "touchés", "crêpes"), a few more
  words ("rosé", "ménage", "cañon") and accents typed as combining marks are no longer rewritten.
- Raw bidirectional control characters in the evaluation sources are written as escapes.

## [0.1.0a1] - 2026-10-29

First public release, `0.1.0a1`: an alpha pre-release (`pip install` skips it unless asked with `--pre`). `0.1.0` follows
once an independent set has been run and early feedback is in.

### Added

- `deobfuscate(text, strictness=...)` returns a `Result` with the text and an ordered record of
  the steps applied (transform, span, before, after, confidence). Command line:
  `text-deobfuscate [--strictness LEVEL] [--json] [--version] [TEXT]`.
- Thirty-two transforms: invisible characters and hidden text, styled and fullwidth letters,
  HTML, URL, backslash and octal escapes, base64, base32, hex, binary, decimal codes,
  quoted-printable, MIME encoded words, ROT13, ROT47, Caesar shifts, Atbash, Morse, reversal and
  per-word reversal; at `balanced` homoglyphs, accent substitution, combining marks, leetspeak
  and separators between letters; at `aggressive` a looser lookalike pass, repeated characters,
  texting shorthand, common misspellings and emoji standing for a word.
- Three strictness levels (`conservative`, `balanced`, `aggressive`). A transform is applied
  only when the result reads more like English; clean text is left alone.
- Layers are followed four deep. Inputs over 100,000 characters are returned unchanged, and one
  call scans at most 1,000,000 characters in total.

### Known limits

- English only. Other languages and scripts pass through unchanged.
- Capitals hidden behind a leetspeak digit, and alternating case, are not restored.
- Shifted or reversed words inside otherwise plain text recover poorly.
- The worst case in time is 100,000 random printable characters, about ten seconds at `aggressive` and six at `balanced`.
- Most evaluation samples come from our own generators; see the README for what was measured on
  text we did not write.
