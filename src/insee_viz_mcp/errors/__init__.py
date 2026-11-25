"""The error contract: the single type tools and services raise.

Re-exported here so callers name the concern rather than the file: `from ...errors import
AppToolError`. A failure the caller must read raises one of these; everything else is a bug.
"""

from .error import AppToolError, ErrorCode

__all__ = [
    "AppToolError",
    "ErrorCode",
]
