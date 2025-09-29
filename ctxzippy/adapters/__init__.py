"""Storage adapters for ctx-zip."""

from .base import StorageAdapter, StorageWriteParams, StorageReadParams, StorageWriteResult
from .filesystem import FileStorageAdapter

# Optional S3 adapter - only import if boto3 is available
try:
    from .s3 import S3StorageAdapter, S3StorageOptions, s3_uri_to_options
    __all__ = [
        "StorageAdapter",
        "StorageWriteParams",
        "StorageReadParams",
        "StorageWriteResult",
        "FileStorageAdapter",
        "S3StorageAdapter",
        "S3StorageOptions",
        "s3_uri_to_options",
    ]
except ImportError:
    # S3 dependencies not installed
    __all__ = [
        "StorageAdapter",
        "StorageWriteParams",
        "StorageReadParams",
        "StorageWriteResult",
        "FileStorageAdapter",
    ]
