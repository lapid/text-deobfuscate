# Security

## What the tool does with input

It reads text and decodes it. It never executes the input, never fetches anything named in it, and
limits its work: inputs over 100,000 characters are returned unchanged, and layers are followed
four deep, with a cap on the number of candidates tried for one text.

## What counts as a security problem

- The tool runs, imports or fetches something because of what the input says.
- A short input that makes the tool use unreasonable time or memory (a denial of service).
- Output that hides or changes the meaning of text in a way that could mislead a person who
  relies on it (for example, a decoded step that is not recorded in the step list).

A wrong or missed deobfuscation is not a security problem. Please open an ordinary issue for it.

## Reporting

Please report privately through GitHub: **Security** tab, then **Report a vulnerability**
(private vulnerability reporting). Do not open a public issue for a vulnerability. Say which
version you tested and give an input that shows the problem.

You can expect an acknowledgement within a week. This is a small project with one maintainer, so
fixes follow as time allows; we will tell you what we decide.

## Supported versions

Only the latest release.
