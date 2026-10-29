# Code of conduct

We want a place where people can work on this project without being harassed or belittled.

**Scope.** These rules apply to everything in and around the project: issues, pull requests,
discussions, commit messages, code, and the data in the evaluation sets.

## How we treat each other

- Be respectful. Disagree with the code, the data or the idea, not with the person.
- No harassment, insults, discrimination, or unwanted sexual attention.
- Do not publish other people's private information.
- Assume good faith, and say plainly when you are unsure.

## Offensive material in the data

Phishing, spam and prompt-injection text often contains profanity, insults, crude talk and
sometimes hateful language, and a tool that must read such text has to be tested on it. So the
evaluation sets keep real examples of it. There is a difference between that and abuse:

- **Allowed as data:** real texts, with their source and licence, that contain profanity, crude
  language or hateful language, including slurs, because that is how the real text is written. A
  sample may be added for the trick it shows, such as a disguised swear word, a masked insult in
  a phishing mail, or a rude injected instruction. Keep to what the sample needs: no more of
  such text than the trick requires, and only in the data files, not repeated in code, comments
  or documentation.
- **Not allowed, anywhere:** text we write ourselves to insult, threaten or demean a person or
  a group, including new slurs or hateful sentences made up for tests; material that sexualises
  children; threats or harassment aimed at a named private person; and other people's private
  information (home addresses, phone numbers, personal email addresses). Where a real text holds
  such details, mask them and say so in the commit.
- **Never as a joke or a test of limits.** Offensive samples are added because the tool needs
  them, not because they are offensive. Say in the pull request what the sample tests.
- **In discussion,** quote offensive text only as far as needed to explain a problem, and say
  that you are quoting data.

We do not use the project to build anything meant to deceive or harm people.

## Enforcement

The maintainer may remove comments, issues or pull requests that break these rules. For a first
or minor breach the maintainer will say what went wrong and ask for a change. If it continues, or
the breach is serious, the person may be blocked from the project. The maintainer's decision is
final.

## Reporting

Use the repository's private reporting form: the Security tab, "Report a vulnerability"
(https://github.com/lapid/text-deobfuscate/security/advisories/new). Start the title with
"Conduct:" so it is not mistaken for a security issue. Only the maintainer sees it. Do not report
conduct problems in a public issue.
