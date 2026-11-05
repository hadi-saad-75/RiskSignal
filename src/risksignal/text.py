"""House style for human-readable prose, never executable code or stored records."""

import re

_DASH_AT_LINE_START = re.compile(r"(?m)^(\s*)[\u2013\u2014]\s+")
_DASH_IN_RANGE = re.compile(r"(?<=\d)\s*[\u2013\u2014]\s*(?=\d)")
_DASH_IN_COMPOUND = re.compile(r"(?<=\w)\u2013(?=\w)")
_ANY_LONG_DASH = re.compile(r"\s*[\u2013\u2014]+\s*")


def normalize_prose(text: str) -> str:
    """Replace long dashes and semicolons without changing numbers or identifiers."""
    text = _DASH_AT_LINE_START.sub(r"\1- ", text)
    text = _DASH_IN_RANGE.sub(" to ", text)
    text = _DASH_IN_COMPOUND.sub("-", text)
    return _ANY_LONG_DASH.sub(", ", text).replace(";", ",")
