"""Tests for reader tools."""

import tempfile
import json

import pytest

from ctxzip.tools import read_file, grep_and_search_file, ReadFileOptions, GrepAndSearchFileOptions
from ctxzip.adapters import FileStorageAdapter, StorageWriteParams
from ctxzip.storage import register_known_key, clear_known_keys


class TestReadFileTool:
    """Test suite for the read file tool."""

    def setup_method(self):
        """Set up test fixtures."""
        clear_known_keys()
        self.temp_dir = tempfile.mkdtemp(prefix="ctxzip_tools_test_")
        self.adapter = FileStorageAdapter(base_dir=self.temp_dir)

        # Write a test file
        self.adapter.write(
            StorageWriteParams(
                key="test_data.json",
                body=json.dumps({"test": "data", "value": 123}),
                content_type="application/json",
            )
        )

        # Register the key as known
        register_known_key(str(self.adapter), "test_data.json")

    def teardown_method(self):
        """Clean up after tests."""
        clear_known_keys()
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_read_known_file(self):
        """Test reading a file that was previously written."""
        options = ReadFileOptions(storage=self.adapter)
        result = read_file("test_data.json", options)

        assert result["key"] == "test_data.json"
        assert "test" in result["content"]
        assert "123" in result["content"]
        assert result["storage"] == str(self.adapter)

    def test_read_unknown_file(self):
        """Test reading a file that wasn't registered as known."""
        options = ReadFileOptions(storage=self.adapter)
        result = read_file("unknown.txt", options)

        assert result["key"] == "unknown.txt"
        assert "unknown key" in result["content"].lower()
        assert "Tool cannot be used" in result["content"]

    def test_read_with_base_dir(self):
        """Test reading with base_dir option."""
        # Register key for this test
        adapter = FileStorageAdapter(base_dir=self.temp_dir)
        register_known_key(str(adapter), "test_data.json")

        options = ReadFileOptions(base_dir=self.temp_dir)
        result = read_file("test_data.json", options)

        assert result["key"] == "test_data.json"
        assert "test" in result["content"]

    def test_read_error_handling(self):
        """Test error handling when reading fails."""
        # Create adapter but don't write file
        clear_known_keys()
        register_known_key(str(self.adapter), "missing.txt")

        options = ReadFileOptions(storage=self.adapter)
        result = read_file("missing.txt", options)

        assert "Error reading file" in result["content"]
        assert result["key"] == "missing.txt"


class TestGrepAndSearchFileTool:
    """Test suite for the grep and search file tool."""

    def setup_method(self):
        """Set up test fixtures."""
        clear_known_keys()
        self.temp_dir = tempfile.mkdtemp(prefix="ctxzip_grep_test_")
        self.adapter = FileStorageAdapter(base_dir=self.temp_dir)

        # Write test files
        test_data = {
            "users": [
                {"name": "Alice", "age": 30, "email": "alice@example.com"},
                {"name": "Bob", "age": 25, "email": "bob@example.com"},
                {"name": "Charlie", "age": 35, "email": "charlie@test.com"},
            ],
            "config": {"debug": True, "timeout": 30, "server": "https://api.example.com"},
        }

        self.adapter.write(
            StorageWriteParams(key="data.json", body=json.dumps(test_data, indent=2))
        )

        # Write text file
        self.adapter.write(
            StorageWriteParams(
                key="log.txt",
                body="""2024-01-01 INFO Starting application
2024-01-01 ERROR Failed to connect to database
2024-01-01 WARN Retrying connection
2024-01-01 INFO Connection established
2024-01-01 ERROR Invalid user credentials
2024-01-01 INFO User logged in successfully""",
            )
        )

        # Register keys
        register_known_key(str(self.adapter), "data.json")
        register_known_key(str(self.adapter), "log.txt")

    def teardown_method(self):
        """Clean up after tests."""
        clear_known_keys()
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_search_json_file(self):
        """Test searching in a JSON file."""
        options = GrepAndSearchFileOptions(storage=self.adapter)

        # Search for email addresses
        result = grep_and_search_file("data.json", r'"email".*example\.com', options=options)

        assert result["key"] == "data.json"
        assert result["pattern"] == r'"email".*example\.com'
        assert "matches" in result
        assert len(result["matches"]) == 2  # Alice and Bob

        for match in result["matches"]:
            assert "example.com" in match["content"]

    def test_search_text_file(self):
        """Test searching in a text file."""
        options = GrepAndSearchFileOptions(storage=self.adapter)

        # Search for ERROR lines
        result = grep_and_search_file("log.txt", "ERROR", options=options)

        assert result["key"] == "log.txt"
        assert "matches" in result
        assert len(result["matches"]) == 2

        for match in result["matches"]:
            assert "ERROR" in match["content"]

    def test_search_with_flags(self):
        """Test searching with regex flags."""
        options = GrepAndSearchFileOptions(storage=self.adapter)

        # Case-insensitive search
        result = grep_and_search_file("data.json", "alice", flags="i", options=options)

        assert "matches" in result
        assert len(result["matches"]) >= 1
        assert any("alice" in match["content"].lower() for match in result["matches"])

    def test_search_unknown_file(self):
        """Test searching a file that wasn't registered."""
        options = GrepAndSearchFileOptions(storage=self.adapter)
        result = grep_and_search_file("unknown.txt", "pattern", options=options)

        assert "unknown key" in result["content"].lower()
        assert "Tool cannot be used" in result["content"]

    def test_invalid_regex(self):
        """Test handling of invalid regex patterns."""
        options = GrepAndSearchFileOptions(storage=self.adapter)

        # Invalid regex with unmatched parenthesis
        result = grep_and_search_file("data.json", "(invalid", options=options)

        assert "Invalid regex" in result["content"]
        assert result["pattern"] == "(invalid"

    def test_search_no_matches(self):
        """Test searching with no matches."""
        options = GrepAndSearchFileOptions(storage=self.adapter)

        result = grep_and_search_file("data.json", "nonexistent_pattern_xyz", options=options)

        assert result["key"] == "data.json"
        assert "matches" in result
        assert len(result["matches"]) == 0


class TestKnownKeys:
    """Test the known keys tracking system."""

    def test_register_and_check_keys(self):
        """Test registering and checking known keys."""
        from ctxzip.storage import register_known_key, is_known_key, clear_known_keys

        clear_known_keys()

        # Register some keys
        register_known_key("file:///tmp", "file1.txt")
        register_known_key("file:///tmp", "file2.txt")
        register_known_key("s3://bucket", "object.json")

        # Check registered keys
        assert is_known_key("file:///tmp", "file1.txt")
        assert is_known_key("file:///tmp", "file2.txt")
        assert is_known_key("s3://bucket", "object.json")

        # Check unregistered keys
        assert not is_known_key("file:///tmp", "file3.txt")
        assert not is_known_key("s3://bucket", "other.json")
        assert not is_known_key("file:///other", "file1.txt")

        # Clear and verify
        clear_known_keys()
        assert not is_known_key("file:///tmp", "file1.txt")
