"""Salesforce release and API version helpers.

Salesforce ships three releases a year. Each bumps the API version by one and
the internal doc release number (seen in atlas URLs, e.g. ``264.0``) by two:

    doc_release = 2 * api_version + 128

API 60.0 = Spring '24 (doc 248), 61.0 = Summer '24, 62.0 = Winter '25, ...
"""

from __future__ import annotations

import re

_SEASONS = ("Spring", "Summer", "Winter")
_BASE_API = 60  # Spring '24


def doc_release_to_api(doc_release: float | int | str) -> float:
    return (float(doc_release) - 128) / 2


def api_to_doc_release(api_version: float | int | str) -> float:
    return float(api_version) * 2 + 128


def api_to_release_name(api_version: float | int | str) -> str:
    """Return a release label like "Winter '27" for an API version."""
    api = int(float(api_version))
    idx = api - _BASE_API
    season = _SEASONS[idx % 3]
    if season == "Winter":
        year = 25 + (api - 62) // 3
    else:
        year = 24 + idx // 3
    return f"{season} '{year % 100:02d}"


_RELEASE_RE = re.compile(r"(Spring|Summer|Winter)\s*'?(\d{2})", re.I)


def release_name_to_api(name: str) -> float | None:
    m = _RELEASE_RE.search(name or "")
    if not m:
        return None
    season, yy = m.group(1).title(), int(m.group(2))
    if season == "Winter":
        api = 62 + (yy - 25) * 3
    elif season == "Spring":
        api = 60 + (yy - 24) * 3
    else:
        api = 61 + (yy - 24) * 3
    return float(api)


def version_info(*, doc_release: str | None = None, api_version: str | None = None) -> dict:
    """Build a consistent version dict from whichever value is known."""
    api: float | None = None
    if api_version:
        api = float(api_version)
    elif doc_release:
        api = doc_release_to_api(doc_release)
    if api is None:
        return {"api_version": None, "doc_release": None, "release": None}
    return {
        "api_version": f"{api:.1f}",
        "doc_release": f"{api_to_doc_release(api):.1f}",
        "release": api_to_release_name(api),
    }


def parse_release_spec(spec: str | float | int | None) -> str | None:
    """Turn a user release setting into an atlas doc release like "264.0".

    Accepts "latest" (or empty) -> None, a release name ("Winter '27"),
    an API version ("68.0" or 68) or a doc release ("264.0").
    """
    if spec is None:
        return None
    text = str(spec).strip()
    if not text or text.lower() == "latest":
        return None
    if re.fullmatch(r"\d+(\.\d+)?", text):
        num = float(text)
        return f"{num:.1f}" if num >= 200 else f"{api_to_doc_release(num):.1f}"
    api = release_name_to_api(text)
    if api is None:
        raise ValueError(f"Unrecognised release {spec!r}. Use 'latest', \"Winter '27\", '68.0' or '264.0'.")
    return f"{api_to_doc_release(api):.1f}"
