"""Strategy for writing tool results to storage during compaction."""

import json
import uuid
from typing import List, Dict, Any, Optional, Union, Callable, Tuple
from dataclasses import dataclass

from ..adapters.base import StorageAdapter, StorageWriteParams
from ..storage.known_keys import register_known_key


# Type alias for message dictionaries
Message = Dict[str, Any]

# Boundary type definition
Boundary = Union[
    str,  # "since-last-assistant-or-user-text" or "entire-conversation"
    Dict[str, Any],  # {"type": "first-n-messages", "count": int}
]


def format_storage_path_for_display(storage_uri: str, key: str) -> str:
    """Format a storage URI and key for display."""
    if not storage_uri:
        return key

    if storage_uri.startswith("blob:"):
        # blob root => blob:///<key>
        if storage_uri in ("blob:", "blob:/"):
            return f"blob:///{key}"
        # blob with prefix => blob://prefix/<key>
        if storage_uri.startswith("blob://"):
            base = storage_uri.rstrip("/")
            return f"{base}/{key}"
        # Fallback
        return f"{storage_uri}:{key}"

    # Default formatting uses colon separation
    return f"{storage_uri}:{key}"


def message_has_text_content(message: Optional[Message]) -> bool:
    """
    Determine whether a message has textual content (string or text parts).
    Used to detect conversational boundaries for compaction.
    """
    if not message:
        return False

    content = message.get("content")

    # String content
    if isinstance(content, str):
        return True

    # Array of content parts
    if isinstance(content, list):
        return any(
            part.get("type") == "text" and isinstance(part.get("text"), str)
            for part in content
            if isinstance(part, dict)
        )

    return False


def detect_window_start(messages: List[Message], boundary: Boundary) -> int:
    """
    Determine the starting index of the compaction window based on the chosen boundary.

    Args:
        messages: List of message dictionaries
        boundary: The boundary configuration

    Returns:
        The starting index for compaction
    """
    # Handle first-n-messages boundary
    if isinstance(boundary, dict) and boundary.get("type") == "first-n-messages":
        count = boundary.get("count", 0)
        if isinstance(count, (int, float)) and count >= 0:
            n = int(count)
            # Clamp to valid range [0, len - 1]
            upper_bound = max(0, len(messages) - 1)
            return min(n, upper_bound)

    # Handle entire-conversation boundary
    if boundary == "entire-conversation":
        return 0

    # Default: since-last-assistant-or-user-text
    window_start = 0
    for i in range(len(messages) - 2, -1, -1):
        msg = messages[i]
        is_boundary = (
            msg and msg.get("role") in ("assistant", "user") and message_has_text_content(msg)
        )
        if is_boundary:
            window_start = i + 1
            break

    return window_start


def detect_window_range(messages: List[Message], boundary: Boundary) -> Tuple[int, int]:
    """
    Determine the [start, end) window for compaction based on the chosen boundary.
    The end index is exclusive. The final assistant message (last item) is never compacted.

    Returns:
        Tuple of (start_index, end_index_exclusive)
    """
    if len(messages) <= 1:
        return (0, 0)

    start = detect_window_start(messages, boundary)
    # Never compact the last message
    end_exclusive = max(0, len(messages) - 1)

    return (start, end_exclusive)


def is_tool_message(msg: Message) -> bool:
    """Check if a message is a tool message with content array."""
    return msg and msg.get("role") == "tool" and isinstance(msg.get("content"), list)


@dataclass
class WriteToolResultsToStorageOptions:
    """Options for the write-tool-results-to-storage compaction strategy."""

    boundary: Boundary
    adapter: StorageAdapter
    serialize_result: Callable[[Any], str]
    storage_reader_tool_names: Optional[List[str]] = None


async def write_tool_results_to_storage_strategy(
    messages: List[Message], options: WriteToolResultsToStorageOptions
) -> List[Message]:
    """
    Compaction strategy that writes tool-result payloads to storage and replaces
    their in-line content with a concise reference to the persisted location.

    Args:
        messages: List of message dictionaries to compact
        options: Configuration options for the strategy

    Returns:
        Modified list of messages with tool results replaced by references
    """
    # Make a copy of messages to avoid mutation
    msgs = list(messages) if messages else []

    # Check if ends with assistant text message
    if not msgs:
        return msgs

    last_message = msgs[-1]
    ends_with_assistant_text = (
        last_message
        and last_message.get("role") == "assistant"
        and message_has_text_content(last_message)
    )

    if not ends_with_assistant_text:
        return msgs

    # Determine compaction window
    window_start, end_exclusive = detect_window_range(msgs, options.boundary)

    # Process messages in the window
    for i in range(window_start, min(end_exclusive, len(msgs))):
        msg = msgs[i]

        if not is_tool_message(msg):
            continue

        content = msg.get("content", [])
        if not isinstance(content, list):
            continue

        for part in content:
            if not isinstance(part, dict):
                continue

            if part.get("type") != "tool-result" or not part.get("output"):
                continue

            # Handle storage reader tools specially
            storage_reader_names = options.storage_reader_tool_names or [
                "readFile",
                "grepAndSearchFile",
            ]
            storage_reader_set = set(storage_reader_names)

            tool_name = part.get("toolName")
            if tool_name and tool_name in storage_reader_set:
                # Extract metadata from reader tool output
                output = part["output"]
                file_name = None
                key = None
                storage = None

                if isinstance(output, dict):
                    if output.get("type") == "json":
                        value = output.get("value", {})
                        if isinstance(value, dict):
                            file_name = value.get("fileName")
                            key = value.get("key")
                            storage = value.get("storage")
                    else:
                        file_name = output.get("fileName")
                        key = output.get("key")
                        storage = output.get("storage")

                # Create reference display
                if storage and key:
                    display = f"Read from storage: {format_storage_path_for_display(storage, key)}. Key: {key}"
                    register_known_key(storage, key)
                else:
                    display = f"Read from file: {file_name or '<unknown>'}"

                part["output"] = {"type": "text", "value": display}
                continue

            # Extract content to persist
            output = part["output"]
            content_to_persist = None

            if isinstance(output, dict):
                if output.get("type") == "json" and "value" in output:
                    value = output["value"]
                    content_to_persist = (
                        value if isinstance(value, str) else options.serialize_result(value)
                    )
                elif output.get("type") == "text" and "text" in output:
                    content_to_persist = output["text"]

            if not content_to_persist:
                continue

            # Write to storage
            file_name = f"{uuid.uuid4()}.txt"
            key = options.adapter.resolve_key(file_name)

            # Synchronous write (adapter should handle async internally if needed)
            result = options.adapter.write(
                StorageWriteParams(key=key, body=content_to_persist, content_type="text/plain")
            )

            # Replace with reference
            adapter_uri = str(options.adapter)
            is_file = adapter_uri.startswith("file:")
            written_prefix = "Written to file" if is_file else "Written to storage"

            part["output"] = {
                "type": "text",
                "value": (
                    f"{written_prefix}: {format_storage_path_for_display(adapter_uri, key)}. "
                    f"Key: {key}. Use the read/search tools to inspect its contents."
                ),
            }

            register_known_key(adapter_uri, key)

    return msgs
