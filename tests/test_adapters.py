"""Tests for storage adapters."""

import tempfile
import os
from pathlib import Path

import pytest

from ctxzippy.adapters import (
    FileStorageAdapter,
    StorageWriteParams,
    StorageReadParams,
)
from ctxzippy.adapters.filesystem import file_uri_to_options


class TestFileStorageAdapter:
    """Test suite for filesystem storage adapter."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp(prefix="ctxzippy_adapter_test_")
        self.adapter = FileStorageAdapter(base_dir=self.temp_dir)

    def teardown_method(self):
        """Clean up after tests."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_resolve_key(self):
        """Test key resolution with path safety."""
        # Basic resolution
        assert self.adapter.resolve_key("file.txt") == "file.txt"

        # With prefix
        adapter_with_prefix = FileStorageAdapter(self.temp_dir, prefix="data")
        assert adapter_with_prefix.resolve_key("file.txt") == "data/file.txt"

        # Path traversal attempts should be sanitized
        assert self.adapter.resolve_key("../file.txt") == "file.txt"
        assert self.adapter.resolve_key("..\\..\\file.txt") == "file.txt"
        assert self.adapter.resolve_key("/absolute/path") == "absolute/path"

    def test_write_and_read_text(self):
        """Test writing and reading text content."""
        params = StorageWriteParams(key="test.txt", body="Hello, World!", content_type="text/plain")

        # Write
        result = self.adapter.write(params)
        assert result.key == "test.txt"
        assert result.url.startswith("file://")

        # Verify file exists
        file_path = Path(self.temp_dir) / "test.txt"
        assert file_path.exists()
        assert file_path.read_text() == "Hello, World!"

        # Read back
        content = self.adapter.read_text(StorageReadParams(key="test.txt"))
        assert content == "Hello, World!"

    def test_write_and_read_bytes(self):
        """Test writing and reading binary content."""
        binary_data = b"\x00\x01\x02\x03"
        params = StorageWriteParams(key="binary.dat", body=binary_data)

        # Write
        result = self.adapter.write(params)
        assert result.key == "binary.dat"

        # Verify file
        file_path = Path(self.temp_dir) / "binary.dat"
        assert file_path.read_bytes() == binary_data

        # Read as stream
        with self.adapter.open_read_stream(StorageReadParams(key="binary.dat")) as stream:
            content = stream.read()
            assert content == binary_data

    def test_write_creates_directories(self):
        """Test that write creates necessary parent directories."""
        params = StorageWriteParams(key="nested/deep/file.txt", body="Content")

        result = self.adapter.write(params)
        assert result.key == "nested/deep/file.txt"

        # Check directory structure
        file_path = Path(self.temp_dir) / "nested" / "deep" / "file.txt"
        assert file_path.exists()
        assert file_path.read_text() == "Content"

    def test_read_nonexistent_file(self):
        """Test reading a file that doesn't exist."""
        with pytest.raises(FileNotFoundError):
            self.adapter.read_text(StorageReadParams(key="nonexistent.txt"))

        with pytest.raises(FileNotFoundError):
            self.adapter.open_read_stream(StorageReadParams(key="nonexistent.txt"))

    def test_adapter_string_representation(self):
        """Test the string representation of the adapter."""
        # Without prefix
        str_repr = str(self.adapter)
        assert str_repr.startswith("file://")
        assert self.temp_dir in str_repr

        # With prefix
        adapter_with_prefix = FileStorageAdapter(self.temp_dir, prefix="data")
        str_repr = str(adapter_with_prefix)
        assert str_repr.endswith("/data")

    def test_file_uri_to_options(self):
        """Test parsing file:// URIs into options."""
        # Unix-style path
        options = file_uri_to_options("file:///tmp/storage")
        assert options == {"base_dir": "/tmp/storage"}

        # Windows-style path (if on Windows)
        if os.name == "nt":
            options = file_uri_to_options("file:///C:/temp/storage")
            assert options["base_dir"].replace("\\", "/") == "C:/temp/storage"

        # Invalid URI
        with pytest.raises(ValueError):
            file_uri_to_options("http://example.com")


class TestStorageAdapterProtocol:
    """Test the storage adapter protocol compliance."""

    def test_filesystem_adapter_implements_protocol(self):
        """Test that FileStorageAdapter implements the StorageAdapter protocol."""
        from ctxzippy.adapters.base import StorageAdapter

        adapter = FileStorageAdapter(base_dir="/tmp")

        # Check all required methods exist
        assert hasattr(adapter, "write")
        assert hasattr(adapter, "read_text")
        assert hasattr(adapter, "open_read_stream")
        assert hasattr(adapter, "resolve_key")
        assert hasattr(adapter, "__str__")

        # Check method signatures (basic check)
        assert callable(adapter.write)
        assert callable(adapter.read_text)
        assert callable(adapter.open_read_stream)
        assert callable(adapter.resolve_key)

        # The adapter should be assignable to the protocol type
        _: StorageAdapter = adapter  # Type check only
