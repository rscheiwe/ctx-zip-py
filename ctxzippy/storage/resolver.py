"""Storage adapter resolution and creation utilities."""

import os
from pathlib import Path
from typing import Optional, Union
from urllib.parse import urlparse

from ..adapters.base import StorageAdapter
from ..adapters.filesystem import FileStorageAdapter, file_uri_to_options


def create_storage_adapter(
    uri_or_adapter: Optional[Union[str, StorageAdapter]] = None
) -> StorageAdapter:
    """
    Create or return a storage adapter from a URI string or adapter instance.

    Args:
        uri_or_adapter: Either:
            - A URI string (e.g., "file:///path", "s3://bucket/prefix")
            - An existing StorageAdapter instance
            - None (defaults to a temp directory adapter)

    Returns:
        A StorageAdapter instance

    Raises:
        ValueError: If the URI scheme is not supported
    """
    # If already an adapter, return it
    if uri_or_adapter is not None and hasattr(uri_or_adapter, "write"):
        return uri_or_adapter

    # If no URI provided, create default temp directory adapter
    if uri_or_adapter is None:
        import tempfile

        temp_dir = tempfile.mkdtemp(prefix="ctxzippy_")
        return FileStorageAdapter(base_dir=temp_dir)

    # Parse URI and create appropriate adapter
    uri = str(uri_or_adapter)
    parsed = urlparse(uri)

    if parsed.scheme == "file":
        options = file_uri_to_options(uri)
        return FileStorageAdapter(**options)
    elif parsed.scheme == "s3":
        try:
            from ..adapters.s3 import S3StorageAdapter, s3_uri_to_options
            options = s3_uri_to_options(uri)
            return S3StorageAdapter(options)
        except ImportError:
            raise ImportError(
                "S3 storage requires boto3. Install with: pip install ctxzippy[s3]"
            )
    elif parsed.scheme == "blob":
        # Placeholder for future blob adapters
        raise NotImplementedError(
            f"Storage adapter for '{parsed.scheme}' not yet implemented. "
            f"Currently only 'file://' URIs are supported."
        )
    else:
        raise ValueError(f"Unsupported storage URI scheme: {parsed.scheme}")


def resolve_file_uri_from_base_dir(base_dir: Union[str, Path]) -> str:
    """
    Create a file:// URI from a base directory path.

    Args:
        base_dir: The base directory path

    Returns:
        A file:// URI string
    """
    path = Path(base_dir).resolve()
    return path.as_uri()
