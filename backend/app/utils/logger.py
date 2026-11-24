"""Central logger setup. Use get_logger(__name__) instead of print()."""

import logging

_LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
_configured = False


def get_logger(name: str) -> logging.Logger:
    """Return a named logger, configuring the root logger the first time."""
    global _configured
    if not _configured:
        logging.basicConfig(level=logging.INFO, format=_LOG_FORMAT)
        _configured = True
    return logging.getLogger(name)
