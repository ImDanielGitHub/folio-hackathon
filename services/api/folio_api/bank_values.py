"""Strict, dependency-free parsing shared by banking adapters and staging."""

import re
from datetime import datetime

_RFC3339 = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:\.(?P<fraction>[0-9]{1,18}))?(?:Z|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])"
)


def parse_timestamp(value):
    match = _RFC3339.fullmatch(value) if isinstance(value, str) else None
    if not match:
        raise ValueError("Explicit RFC3339 date-time with valid timezone required.")
    fraction = match.group("fraction")
    if fraction and len(fraction) > 6 and any(d != "0" for d in fraction[6:]):
        raise ValueError("Sub-microsecond timestamp precision is not supported.")
    # fromisoformat alone normalizes malformed offsets such as +00:60.
    # The grammar check above rejects those before parsing calendar components.
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
