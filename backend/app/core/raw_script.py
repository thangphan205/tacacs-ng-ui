"""
Checks for a Profile's raw tac_plus-ng script text (#359).

The generator wraps the text as `profile <name> { script { <text> } }`, so the
text must be a script body: no wrappers of its own, and braces that close only
what it opened. An extra `}` would end the profile early and let the rest of
the text add top-level config. tac_plus-ng's own `-P` check still validates
the result; these checks only guard the wrapper.

Pure functions with no app imports, so `models.py` can use them in validators.
"""

import re

MAX_RAW_SCRIPT_BYTES = 64 * 1024

_WORD = re.compile(r"[A-Za-z0-9_.\-]+")
_PROFILE_BLOCK = re.compile(r"^\s*profile\s+([^\s{]+)\s*\{", re.MULTILINE)


def check_raw_script(text: str) -> list[str]:
    """
    Problems that would break the surrounding config, as readable messages
    with line numbers; empty when the text is a usable script body.

    Strings ("..." with backslash escapes), `#` comments and `/regex/` after
    `=~` or `!~` are skipped, so braces and slashes inside them are fine.
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
            while i < n and text[i] != "\n":
                i += 1
            continue

        if ch == '"' or (ch == "/" and last_two in ("=~", "!~")):
            kind = "string" if ch == '"' else "regex"
            start_line = line
            i += 1
            while i < n and text[i] != ch:
                if text[i] == "\\":
                    i += 1
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


def profile_names_in(text: str) -> set[str]:
    """Names of `profile <name> {` blocks defined in raw config text."""
    return set(_PROFILE_BLOCK.findall(text))
