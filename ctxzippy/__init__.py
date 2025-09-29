"""
ctx-zip: A Python library for compacting large tool-call results in conversation histories.

This package helps reduce context size by persisting large tool outputs to storage
and replacing them with lightweight references.
"""

from .compact import compact_messages, CompactOptions
from .adapters.base import StorageAdapter
from .adapters.filesystem import FileStorageAdapter
from .tools.reader import read_file
from .tools.grep import grep_and_search_file

__version__ = "0.1.0"

__all__ = [
    "compact_messages",
    "CompactOptions",
    "StorageAdapter",
    "FileStorageAdapter",
    "read_file",
    "grep_and_search_file",
]
