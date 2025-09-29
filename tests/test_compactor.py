"""Tests for the message compaction functionality."""

import json
import tempfile
import asyncio
from pathlib import Path
from typing import List, Dict, Any

import pytest

from ctxzip import compact_messages, CompactOptions
from ctxzip.adapters import FileStorageAdapter
from ctxzip.storage import clear_known_keys


# Helper to run async functions in tests
def async_run(coro):
    """Run an async coroutine."""
    return asyncio.run(coro)


class TestCompactor:
    """Test suite for message compaction."""

    def setup_method(self):
        """Set up test fixtures."""
        # Clear known keys before each test
        clear_known_keys()
        # Create a temporary directory for storage
        self.temp_dir = tempfile.mkdtemp(prefix="ctxzip_test_")
        self.storage_adapter = FileStorageAdapter(base_dir=self.temp_dir)

    def teardown_method(self):
        """Clean up after tests."""
        clear_known_keys()
        # Clean up temp directory
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_basic_compaction(self):
        """Test basic message compaction with tool results."""
        messages = [
            {"role": "user", "content": "Analyze this data"},
            {
                "role": "tool",
                "content": [
                    {
                        "type": "tool-result",
                        "toolName": "analyze",
                        "output": {
                            "type": "json",
                            "value": {"data": "large" * 1000, "status": "complete"},
                        },
                    }
                ],
            },
            {"role": "assistant", "content": "Analysis complete"},
        ]

        options = CompactOptions(storage=self.storage_adapter, boundary="entire-conversation")

        result = async_run(compact_messages(messages, options))

        # Check that the tool result was replaced
        assert len(result) == 3
        assert result[0] == messages[0]  # User message unchanged
        assert result[2] == messages[2]  # Assistant message unchanged

        # Check tool message was compacted
        tool_msg = result[1]
        assert tool_msg["role"] == "tool"
        tool_output = tool_msg["content"][0]["output"]
        assert tool_output["type"] == "text"
        assert "Written to" in tool_output["value"]
        assert "Key:" in tool_output["value"]

    def test_boundary_since_last_text(self):
        """Test compaction with since-last-assistant-or-user-text boundary."""
        messages = [
            {"role": "user", "content": "First request"},
            {
                "role": "tool",
                "content": [
                    {"type": "tool-result", "output": {"type": "json", "value": {"old": "data"}}}
                ],
            },
            {"role": "assistant", "content": "First response"},
            {"role": "user", "content": "Second request"},
            {
                "role": "tool",
                "content": [
                    {"type": "tool-result", "output": {"type": "json", "value": {"new": "data"}}}
                ],
            },
            {"role": "assistant", "content": "Second response"},
        ]

        options = CompactOptions(
            storage=self.storage_adapter, boundary="since-last-assistant-or-user-text"
        )

        result = async_run(compact_messages(messages, options))

        # Only the last tool message should be compacted
        assert result[1]["content"][0]["output"]["type"] == "json"  # Old data unchanged
        assert "Written to" in result[4]["content"][0]["output"]["value"]  # New data compacted

    def test_boundary_first_n_messages(self):
        """Test compaction with first-n-messages boundary."""
        messages = [
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": "Request"},
            {
                "role": "tool",
                "content": [
                    {"type": "tool-result", "output": {"type": "json", "value": {"data": "value"}}}
                ],
            },
            {"role": "assistant", "content": "Response"},
        ]

        options = CompactOptions(
            storage=self.storage_adapter, boundary={"type": "first-n-messages", "count": 2}
        )

        result = async_run(compact_messages(messages, options))

        # First 2 messages should be kept intact
        assert result[0] == messages[0]
        assert result[1] == messages[1]
        # Tool message should be compacted
        assert "Written to" in result[2]["content"][0]["output"]["value"]

    def test_storage_reader_tools_not_rewritten(self):
        """Test that reader tool results are not re-written to storage."""
        messages = [
            {"role": "user", "content": "Read the file"},
            {
                "role": "tool",
                "content": [
                    {
                        "type": "tool-result",
                        "toolName": "readFile",
                        "output": {
                            "type": "json",
                            "value": {
                                "key": "data.txt",
                                "content": "File contents",
                                "storage": "file:///tmp",
                            },
                        },
                    }
                ],
            },
            {"role": "assistant", "content": "File read successfully"},
        ]

        options = CompactOptions(storage=self.storage_adapter, boundary="entire-conversation")

        result = async_run(compact_messages(messages, options))

        # Reader tool output should be replaced with reference, not re-written
        tool_output = result[1]["content"][0]["output"]
        assert tool_output["type"] == "text"
        assert "Read from" in tool_output["value"]
        assert "data.txt" in tool_output["value"]

    def test_empty_messages(self):
        """Test compaction with empty message list."""
        result = async_run(compact_messages([], CompactOptions()))
        assert result == []

    def test_no_tool_messages(self):
        """Test compaction with no tool messages."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]

        result = async_run(compact_messages(messages, CompactOptions()))
        assert result == messages

    def test_custom_serializer(self):
        """Test compaction with custom serializer function."""

        def custom_serializer(value):
            return f"CUSTOM: {json.dumps(value)}"

        messages = [
            {"role": "user", "content": "Process"},
            {
                "role": "tool",
                "content": [
                    {"type": "tool-result", "output": {"type": "json", "value": {"test": "data"}}}
                ],
            },
            {"role": "assistant", "content": "Done"},
        ]

        options = CompactOptions(
            storage=self.storage_adapter,
            serialize_result=custom_serializer,
            boundary="entire-conversation",
        )

        result = async_run(compact_messages(messages, options))

        # Check file was written with custom serialization
        key = None
        output_text = result[1]["content"][0]["output"]["value"]
        prev_part = None
        for part in output_text.split():
            if prev_part == "Key:":
                key = part.rstrip(".")
                break
            prev_part = part

        if key:
            file_path = Path(self.temp_dir) / key
            content = file_path.read_text()
            assert content.startswith("CUSTOM:")

    def test_text_output_compaction(self):
        """Test compaction of text-type tool outputs."""
        messages = [
            {"role": "user", "content": "Generate report"},
            {
                "role": "tool",
                "content": [
                    {
                        "type": "tool-result",
                        "output": {"type": "text", "text": "A very long report " * 500},
                    }
                ],
            },
            {"role": "assistant", "content": "Report generated"},
        ]

        options = CompactOptions(storage=self.storage_adapter, boundary="entire-conversation")

        result = async_run(compact_messages(messages, options))

        # Text output should be compacted
        tool_output = result[1]["content"][0]["output"]
        assert tool_output["type"] == "text"
        assert "Written to" in tool_output["value"]


class TestBoundaryDetection:
    """Test suite for boundary detection logic."""

    def test_detect_window_entire_conversation(self):
        """Test window detection for entire conversation."""
        from ctxzip.strategies.write_tool_results import detect_window_range

        messages = [
            {"role": "user", "content": "1"},
            {"role": "tool", "content": []},
            {"role": "assistant", "content": "2"},
            {"role": "tool", "content": []},
            {"role": "assistant", "content": "3"},
        ]

        start, end = detect_window_range(messages, "entire-conversation")
        assert start == 0
        assert end == 4  # Excludes last message

    def test_detect_window_since_last_text(self):
        """Test window detection for since-last-assistant-or-user-text."""
        from ctxzip.strategies.write_tool_results import detect_window_range

        messages = [
            {"role": "tool", "content": []},
            {"role": "assistant", "content": "Response"},
            {"role": "tool", "content": []},
            {"role": "tool", "content": []},
            {"role": "assistant", "content": "Final"},
        ]

        start, end = detect_window_range(messages, "since-last-assistant-or-user-text")
        assert start == 2  # After the first assistant message
        assert end == 4  # Excludes last message

    def test_detect_window_first_n(self):
        """Test window detection for first-n-messages."""
        from ctxzip.strategies.write_tool_results import detect_window_range

        messages = [
            {"role": "system", "content": "System"},
            {"role": "user", "content": "User"},
            {"role": "tool", "content": []},
            {"role": "tool", "content": []},
            {"role": "assistant", "content": "Assistant"},
        ]

        start, end = detect_window_range(messages, {"type": "first-n-messages", "count": 2})
        assert start == 2  # After first 2 messages
        assert end == 4  # Excludes last message

    def test_message_has_text_content(self):
        """Test detection of messages with text content."""
        from ctxzip.strategies.write_tool_results import message_has_text_content

        # String content
        assert message_has_text_content({"content": "Hello"})

        # Array with text part
        assert message_has_text_content({"content": [{"type": "text", "text": "Hello"}]})

        # Array without text part
        assert not message_has_text_content({"content": [{"type": "image", "url": "..."}]})

        # No content
        assert not message_has_text_content({"role": "tool"})

        # None
        assert not message_has_text_content(None)
