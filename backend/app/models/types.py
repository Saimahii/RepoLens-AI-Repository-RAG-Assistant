"""Shared column types for the models."""

from sqlalchemy import Text
from sqlalchemy.dialects.mysql import MEDIUMTEXT

# MySQL TEXT holds only 64 KB. Code chunks and AI answers can be larger,
# so on MySQL we use MEDIUMTEXT (16 MB). Other databases get plain Text.
LongText = Text().with_variant(MEDIUMTEXT(), "mysql")

# Allowed values, kept here so services and schemas can reuse them.
REPO_STATUSES: tuple[str, ...] = ("pending", "cloning", "parsing", "embedding", "done", "failed")
SYMBOL_TYPES: tuple[str, ...] = ("function", "class", "method", "module")
MESSAGE_ROLES: tuple[str, ...] = ("user", "assistant")
