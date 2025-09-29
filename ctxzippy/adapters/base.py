"""Base storage adapter protocol and types."""

from abc import ABC, abstractmethod
from typing import Protocol, Optional, Union, IO
from dataclasses import dataclass


@dataclass
class StorageWriteParams:
    """Parameters for writing to storage."""

    key: str
    body: Union[str, bytes]
    content_type: Optional[str] = None


@dataclass
class StorageReadParams:
    """Parameters for reading from storage."""

    key: str


@dataclass
class StorageWriteResult:
    """Result of a storage write operation."""

    key: str
    url: Optional[str] = None


class StorageAdapter(Protocol):
    """
    Protocol for storage adapters that persist and retrieve content.

    Implementations should provide pluggable backends (filesystem, S3, etc.)
    while maintaining a consistent interface.
    """

    def write(self, params: StorageWriteParams) -> StorageWriteResult:
        """
        Write content to storage.

        Args:
            params: Write parameters including key, body, and optional content type

        Returns:
            StorageWriteResult with the key and optional URL
        """
        ...

    def read_text(self, params: StorageReadParams) -> str:
        """
        Read text content from storage.

        Args:
            params: Read parameters including the key

        Returns:
            The text content as a string
        """
        ...

    def open_read_stream(self, params: StorageReadParams) -> IO[bytes]:
        """
        Open a readable stream for the content.

        Args:
            params: Read parameters including the key

        Returns:
            A file-like object for reading bytes
        """
        ...

    def resolve_key(self, name: str) -> str:
        """
        Resolve a logical name to a fully-qualified storage key.

        This method applies any necessary prefixing or namespacing.

        Args:
            name: The logical name to resolve

        Returns:
            The fully-qualified storage key
        """
        ...

    def __str__(self) -> str:
        """
        Return a human-readable identifier for this storage adapter.

        Examples:
            - "file:///base/path"
            - "s3://bucket/prefix"
            - "blob://container/prefix"
        """
        ...


class BaseStorageAdapter(ABC):
    """Abstract base class for storage adapters with common functionality."""

    @abstractmethod
    def write(self, params: StorageWriteParams) -> StorageWriteResult:
        """Write content to storage."""
        pass

    @abstractmethod
    def read_text(self, params: StorageReadParams) -> str:
        """Read text content from storage."""
        pass

    def open_read_stream(self, params: StorageReadParams) -> IO[bytes]:
        """
        Default implementation that reads all text and returns a BytesIO stream.
        Subclasses should override for more efficient streaming.
        """
        import io

        text = self.read_text(params)
        return io.BytesIO(text.encode("utf-8"))

    @abstractmethod
    def resolve_key(self, name: str) -> str:
        """Resolve a logical name to a storage key."""
        pass

    @abstractmethod
    def __str__(self) -> str:
        """Return a human-readable identifier."""
        pass
