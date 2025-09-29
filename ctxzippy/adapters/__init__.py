"""Storage adapters for ctx-zip."""

from .base import StorageAdapter, StorageWriteParams, StorageReadParams, StorageWriteResult
from .filesystem import FileStorageAdapter

__all__ = [
    "StorageAdapter",
    "StorageWriteParams",
    "StorageReadParams",
    "StorageWriteResult",
    "FileStorageAdapter",
]
