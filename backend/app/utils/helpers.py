"""Misc helpers shared across services."""

import re

# Anything that is not a letter, digit, dot, dash or underscore
_UNSAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]")


def safe_folder_name(*parts: str | int) -> str:
    """Join parts into a folder name that is safe on Windows, e.g. '3_octocat_Hello-World'."""
    joined = "_".join(str(part) for part in parts)
    return _UNSAFE_CHARS.sub("-", joined)
