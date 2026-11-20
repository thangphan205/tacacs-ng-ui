"""
RADIUS dictionaries for the generated tac_plus-ng config.

tac_plus-ng resolves every RADIUS attribute name (`radius[Service-Type]`,
`set radius[MikroTik:MikroTik-Group] = full`) through `radius.dictionary`
blocks, and ships none of its own. The built-in set lives next to this module
in `radius_dictionary.cfg`. Admins may append more vendors as text
(`TacacsNgSetting.radius_dictionary_extra`).

That text is written verbatim inside `id = tac_plus-ng { }`, so it must not be
able to close the block or add other config. Rather than mirror tac_plus-ng's
tokenizer, it is checked against the dictionary grammar itself, which is
small and has no strings (`parse_radius_dictionary` in config_radius.c):

    radius.dictionary [NAME ID [format = T, L]] {
        attribute NAME ID TYPE [{ NAME NUMBER ... }]
    }

Every token must be a keyword, a name made of `[A-Za-z0-9_.-]`, a number, or
one of `{ } = ,` where the grammar expects it; anything else is refused. The
syntax check (`tac_plus-ng -P`) at Generate then catches what the grammar
cannot, such as an attribute defined twice.

Pure functions with no app imports, so `models.py` can use them in validators.
"""

import re
from functools import cache
from pathlib import Path

MAX_RADIUS_DICTIONARY_BYTES = 64 * 1024

_BUILTIN_PATH = Path(__file__).with_name("radius_dictionary.cfg")

# Attribute types tac_plus-ng accepts (config_radius.c, parse_radius_dictionary).
ATTRIBUTE_TYPES = frozenset(
    {
        "string",
        "octets",
        "address",
        "ipaddr",
        "ipv4addr",
        "ipv6addr",
        "enum",
        "integer",
        "time",
        "vsa",
    }
)
# Types whose attribute may carry a `{ Name Number ... }` list of named values.
_VALUE_TYPES = frozenset({"integer", "time", "enum"})

_TOKEN = re.compile(r"[{}=,]|[^\s{}=,]+")
_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_.\-]*\Z")
# A value name may start with a digit ("802.11", "3GPP").
_VALUE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.\-]*\Z")
_NUMBER = re.compile(r"[0-9]+\Z")
# Words tac_plus-ng treats specially wherever they appear.
_RESERVED = frozenset({"include", "radius.dictionary", "attribute", "format"})


class _Tokens:
    def __init__(self, tokens: list[tuple[str, int]]) -> None:
        self._tokens = tokens
        self._i = 0

    def peek(self) -> str | None:
        return self._tokens[self._i][0] if self._i < len(self._tokens) else None

    @property
    def line(self) -> int:
        if self._i < len(self._tokens):
            return self._tokens[self._i][1]
        return self._tokens[-1][1] if self._tokens else 1

    def take(self) -> str:
        token = self._tokens[self._i][0]
        self._i += 1
        return token


def _tokenize(text: str) -> tuple[list[tuple[str, int]], list[str]]:
    tokens: list[tuple[str, int]] = []
    for line_no, raw in enumerate(text.split("\n"), start=1):
        line = raw
        hash_at = line.find("#")
        if hash_at != -1:
            if hash_at > 0 and line[hash_at - 1] not in " \t":
                return [], [
                    f"Line {line_no}: put a space before `#` to start a comment."
                ]
            line = line[:hash_at]
        for match in _TOKEN.finditer(line):
            tokens.append((match.group(), line_no))
    return tokens, []


def _number(tokens: _Tokens, what: str) -> int:
    line = tokens.line
    token = tokens.peek()
    if token is None or not _NUMBER.match(token):
        raise ValueError(f"Line {line}: expected {what}, got {token or 'end of text'}.")
    tokens.take()
    return int(token)


def _expect(tokens: _Tokens, expected: str) -> None:
    line = tokens.line
    token = tokens.peek()
    if token != expected:
        raise ValueError(
            f"Line {line}: expected `{expected}`, got {token or 'end of text'}."
        )
    tokens.take()


def _name(tokens: _Tokens, what: str, pattern: re.Pattern[str] = _NAME) -> str:
    line = tokens.line
    token = tokens.peek()
    if token is None or token in _RESERVED or not pattern.match(token):
        raise ValueError(f"Line {line}: expected {what}, got {token or 'end of text'}.")
    tokens.take()
    return token


def _dictionary(tokens: _Tokens) -> None:
    _expect(tokens, "radius.dictionary")
    if tokens.peek() != "{":
        _name(tokens, "a vendor name")
        if _number(tokens, "a vendor id") < 1:
            raise ValueError(f"Line {tokens.line}: vendor id must be at least 1.")
        if tokens.peek() == "format":
            tokens.take()
            _expect(tokens, "=")
            if _number(tokens, "the attribute type length") not in (1, 2, 4):
                raise ValueError(
                    f"Line {tokens.line}: format type length must be 1, 2 or 4."
                )
            _expect(tokens, ",")
            if _number(tokens, "the attribute length length") > 2:
                raise ValueError(
                    f"Line {tokens.line}: format length length must be 0, 1 or 2."
                )
    _expect(tokens, "{")
    while tokens.peek() == "attribute":
        tokens.take()
        _name(tokens, "an attribute name")
        if _number(tokens, "an attribute number") < 1:
            raise ValueError(
                f"Line {tokens.line}: attribute number must be at least 1."
            )
        line = tokens.line
        kind = tokens.peek()
        if kind not in ATTRIBUTE_TYPES:
            raise ValueError(
                f"Line {line}: expected an attribute type "
                f"({', '.join(sorted(ATTRIBUTE_TYPES))}), got {kind or 'end of text'}."
            )
        tokens.take()
        if kind in _VALUE_TYPES and tokens.peek() == "{":
            tokens.take()
            while tokens.peek() != "}":
                _name(tokens, "a value name or `}`", _VALUE_NAME)
                _number(tokens, "a value number")
            tokens.take()
    _expect(tokens, "}")


def check_radius_dictionary(text: str) -> list[str]:
    """
    Problems with `radius.dictionary` text, as readable messages with line
    numbers; empty when the text is nothing but dictionary blocks.
    """
    try:
        size = len(text.encode())
    except UnicodeEncodeError:
        return ["RADIUS dictionary contains characters that cannot be encoded."]
    if size > MAX_RADIUS_DICTIONARY_BYTES:
        return [
            f"RADIUS dictionary is larger than {MAX_RADIUS_DICTIONARY_BYTES // 1024} KiB."
        ]
    token_list, errors = _tokenize(text)
    if errors:
        return errors
    tokens = _Tokens(token_list)
    try:
        while tokens.peek() is not None:
            _dictionary(tokens)
    except ValueError as e:
        return [str(e)]
    return []


def normalize_radius_dictionary(text: str | None) -> str | None:
    """
    Cleaned dictionary text, or None for blank text. Raises `ValueError`
    with the problem found.
    """
    if text is None:
        return None
    cleaned = "\n".join(line.rstrip() for line in text.strip("\n").split("\n"))
    if not cleaned.strip():
        return None
    errors = check_radius_dictionary(cleaned)
    if errors:
        raise ValueError(" ".join(errors))
    return cleaned


@cache
def builtin_radius_dictionary() -> str:
    """The dictionary shipped with the app, as config text."""
    return _BUILTIN_PATH.read_text()
