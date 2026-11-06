"""
Checks for a Profile's raw tac_plus-ng script text (#359).

The generator wraps the text as `profile <name> { script { <text> } }`, so the
text must be a script body: no wrappers of its own, and braces that close only
what it opened. An extra `}` would end the profile early and let the rest of
the text add top-level config that `tac_plus-ng -P` happily accepts.

The guard only works if it sees exactly the braces tac_plus-ng sees, so it
mirrors tac_plus-ng's tokenizer where that was verified against the binary,
and refuses the text where it was not:

- `"..."` and `'...'` are strings, with backslash escapes, and may span lines.
- `/.../` is a regex only right after `=~` or `!~`, with backslash escapes,
  on one line. Anywhere else `/` is an ordinary character.
- `#` starts a comment after whitespace or at the start of a line. Right after
  a word character it is part of the word (`1#x` is one token, and in `1#}`
  the `}` still closes a block), while after `)` it starts a comment. Those
  rules differ by neighbour, so any `#` not preceded by whitespace is refused
  rather than guessed at: a brace the guard counts but tac_plus-ng hides is as
  dangerous as the reverse.
- A backslash outside strings and regexes does not escape a brace.

Pure functions with no app imports, so `models.py` can use them in validators.
"""

import re

MAX_RAW_SCRIPT_BYTES = 64 * 1024

_WORD = re.compile(r"[A-Za-z0-9_.\-]+")
# `profile name {` or `profile "name" {`, at the start of a line.
_PROFILE_BLOCK = re.compile(
    r"""^\s*profile\s+(?:"([^"]+)"|'([^']+)'|([^\s{"']+))\s*\{""", re.MULTILINE
)


def check_raw_script(text: str) -> list[str]:
    """
    Problems that would break the surrounding config, as readable messages
    with line numbers; empty when the text is a usable script body.
    """
    errors: list[str] = []
    if len(text.encode()) > MAX_RAW_SCRIPT_BYTES:
        return [f"Raw script is larger than {MAX_RAW_SCRIPT_BYTES // 1024} KiB."]

    depth = 0
    line = 1
    i = 0
    n = len(text)
    first_word: str | None = None
    last_two = ""  # last two non-space characters outside strings and comments

    while i < n:
        ch = text[i]

        if ch == "\n":
            line += 1
            i += 1
            continue
        if ch in " \t\r":
            i += 1
            continue

        if ch == "#":
            if i > 0 and text[i - 1] not in " \t\r\n":
                errors.append(
                    f"Line {line}: put a space before `#` to start a comment, "
                    "or quote a value that contains `#`."
                )
                return errors
            while i < n and text[i] != "\n":
                i += 1
            continue

        if ch in "\"'" or (ch == "/" and last_two in ("=~", "!~")):
            kind = "regex" if ch == "/" else "string"
            start_line = line
            i += 1
            while i < n and text[i] != ch:
                if text[i] == "\\":
                    i += 1
                    if i < n and text[i] == "\n":
                        line += 1
                elif text[i] == "\n":
                    if kind == "regex":
                        break
                    line += 1
                i += 1
            if i >= n or text[i] != ch:
                errors.append(f"Line {start_line}: unterminated {kind}.")
                return errors
            i += 1
            last_two = ch * 2
            continue

        word = _WORD.match(text, i)
        if word:
            token = word.group()
            if first_word is None:
                first_word = token
                rest = text[word.end() :].lstrip()
                if token == "profile":
                    errors.append(
                        "Paste only the script body: the generator writes the "
                        "`profile <name> { script { ... } }` wrapper."
                    )
                elif token == "script" and rest.startswith("{"):
                    errors.append(
                        "Paste only what goes inside `script { }`: the generator "
                        "writes that block."
                    )
            if token == "include":
                errors.append(f"Line {line}: `include` is not allowed in a raw script.")
            last_two = token[-2:]
            i = word.end()
            continue

        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth < 0:
                errors.append(
                    f"Line {line}: `}}` closes more blocks than the script opened."
                )
                return errors
        last_two = (last_two + ch)[-2:]
        i += 1

    if depth > 0:
        errors.append(f"{depth} `{{` left unclosed at the end of the script.")
    return errors


def normalize_raw_script(text: str | None) -> str | None:
    """
    The one place raw-script text is cleaned and checked: surrounding blank
    lines and trailing spaces dropped, blank text read as no raw script.
    Raises `ValueError` with every problem found.
    """
    if text is None:
        return None
    cleaned = text.strip("\n").rstrip()
    if not cleaned.strip():
        return None
    errors = check_raw_script(cleaned)
    if errors:
        raise ValueError(" ".join(errors))
    return cleaned


def profile_names_in(text: str) -> set[str]:
    """Names of `profile <name> {` blocks defined in raw config text."""
    return {next(g for g in m if g) for m in _PROFILE_BLOCK.findall(text)}
