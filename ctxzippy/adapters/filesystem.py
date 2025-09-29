"""Filesystem storage adapter implementation."""

import os
from pathlib import Path
from typing import Optional, Union, IO
from urllib.parse import urlparse
from urllib.request import url2pathname

from .base import BaseStorageAdapter, StorageWriteParams, StorageReadParams, StorageWriteResult


class FileStorageAdapter(BaseStorageAdapter):
    """
    Storage adapter that persists content to the local filesystem.

    This adapter writes files to a base directory and supports optional
    prefixing for organization.
    """

    def __init__(self, base_dir: Union[str, Path], prefix: Optional[str] = None):
        """
        Initialize a filesystem storage adapter.

        Args:
            base_dir: The absolute base directory for storage
            prefix: Optional subdirectory/prefix inside base_dir
        """
        self.base_dir = Path(base_dir).resolve()
        self.prefix = prefix or ""

        # Ensure base directory exists
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def resolve_key(self, name: str) -> str:
        """
        Resolve a logical name to a storage key.

        Sanitizes the name to prevent path traversal attacks.
        """
        # Remove any path traversal attempts
        safe_name = name.replace("\\", "/").replace("../", "").lstrip("/")

        if self.prefix:
            # Remove trailing slash from prefix and combine
            prefix_clean = self.prefix.rstrip("/")
            return f"{prefix_clean}/{safe_name}"
        return safe_name

    def write(self, params: StorageWriteParams) -> StorageWriteResult:
        """Write content to a file."""
        full_path = self.base_dir / params.key

        # Create parent directories if needed
        full_path.parent.mkdir(parents=True, exist_ok=True)

        # Write content
        if isinstance(params.body, str):
            full_path.write_text(params.body, encoding="utf-8")
        else:
            full_path.write_bytes(params.body)

        # Return result with file:// URL
        url = full_path.as_uri()
        return StorageWriteResult(key=params.key, url=url)

    def read_text(self, params: StorageReadParams) -> str:
        """Read text content from a file."""
        full_path = self.base_dir / params.key

        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {params.key}")

        return full_path.read_text(encoding="utf-8")

    def open_read_stream(self, params: StorageReadParams) -> IO[bytes]:
        """Open a file stream for reading."""
        full_path = self.base_dir / params.key

        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {params.key}")

        return open(full_path, "rb")

    def __str__(self) -> str:
        """Return a file:// URI representation."""
        base_uri = self.base_dir.as_uri()
        if self.prefix:
            # Ensure single slash between base and prefix
            return f"{base_uri.rstrip('/')}/{self.prefix}"
        return base_uri


def file_uri_to_options(uri: str) -> dict:
    """
    Parse a file:// URI into FileStorageAdapter options.

    Args:
        uri: A file:// URI

    Returns:
        Dictionary with 'base_dir' and optionally 'prefix'

    Raises:
        ValueError: If the URI is not a valid file:// URI
    """
    parsed = urlparse(uri)
    if parsed.scheme != "file":
        raise ValueError(f"Invalid file URI: {uri}")

    # Convert URL path to local filesystem path
    path = url2pathname(parsed.path)

    # On Windows, url2pathname might return paths like '\C:\path'
    # We need to handle this case
    if os.name == "nt" and path.startswith("\\"):
        path = path[1:]

    return {"base_dir": path}
