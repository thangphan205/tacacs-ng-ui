"""Rendering shared by the profile and ruleset script generators."""


def script_header(condition: str, key: str, value: str) -> str:
    """The opening of one script block, without the brace.

    `else` takes no test expression: `else (k==v)` is a syntax error that
    `tac_plus-ng -P` rejects, so the key/value stored on an `else` row is ignored.
    """
    condition = condition.strip()
    if condition == "else":
        return "else"
    return f"{condition} ({key}=={value})"
