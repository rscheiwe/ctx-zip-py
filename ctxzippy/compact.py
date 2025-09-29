"""Main compaction API for ctx-zip."""

import json
from typing import List, Dict, Any, Optional, Union, Callable
from dataclasses import dataclass, field

from .adapters.base import StorageAdapter
from .storage.resolver import create_storage_adapter
from .strategies.write_tool_results import (
    write_tool_results_to_storage_strategy,
    WriteToolResultsToStorageOptions,
    Boundary,
)


# Type alias for message dictionaries
Message = Dict[str, Any]


@dataclass
class CompactOptions:
    """
    Options for compacting a conversation by persisting large tool outputs to storage
    and replacing them with lightweight references.
    """

    strategy: str = "write-tool-results-to-storage"
    """Compaction strategy to use. Currently only 'write-tool-results-to-storage' is supported."""

    storage: Optional[Union[str, StorageAdapter]] = None
    """
    Storage destination for persisting tool outputs. Accepts either:
    - A URI string (e.g., 'file:///path', 's3://bucket/prefix')
    - A StorageAdapter instance
    - None (uses a temporary directory)
    """

    boundary: Boundary = "since-last-assistant-or-user-text"
    """
    Controls where the compaction window starts:
    - 'since-last-assistant-or-user-text': Start after the most recent assistant/user text message
    - 'entire-conversation': Start at the beginning
    - {'type': 'first-n-messages', 'count': N}: Keep the first N messages intact
    """

    serialize_result: Optional[Callable[[Any], str]] = None
    """
    Function to convert tool outputs (objects) to strings before writing to storage.
    Defaults to JSON.stringify with 2-space indentation.
    """

    storage_reader_tool_names: List[str] = field(default_factory=list)
    """
    Tool names that are recognized as reading from storage (e.g., read/search tools).
    Their results will not be re-written; instead, a friendly reference to the source is shown.
    Defaults include 'readFile' and 'grepAndSearchFile'.
    """

    def __post_init__(self):
        """Set defaults after initialization."""
        if self.serialize_result is None:
            self.serialize_result = lambda v: json.dumps(v, indent=2)

        # Add default reader tool names if not provided
        if not self.storage_reader_tool_names:
            self.storage_reader_tool_names = ["readFile", "grepAndSearchFile"]


async def compact_messages(
    messages: List[Message], options: Optional[CompactOptions] = None
) -> List[Message]:
    """
    Compact a sequence of messages by writing large tool outputs to configured storage
    and replacing them with succinct references, keeping your model context lean.

    This is the main entry point for the ctx-zip library.

    Args:
        messages: List of message dictionaries with 'role', 'content', etc.
        options: Configuration options for compaction (uses defaults if not provided)

    Returns:
        Modified list of messages with tool results replaced by storage references

    Raises:
        ValueError: If an unknown strategy is specified

    Example:
        >>> messages = [
        ...     {"role": "user", "content": "Run the analysis"},
        ...     {"role": "tool", "content": [
        ...         {"type": "tool-result", "output": {"type": "json", "value": large_data}}
        ...     ]},
        ...     {"role": "assistant", "content": "Analysis complete"}
        ... ]
        >>> compacted = await compact_messages(messages)
        >>> # Tool results are now replaced with storage references
    """
    # Use default options if not provided
    if options is None:
        options = CompactOptions()

    # Create storage adapter
    adapter = create_storage_adapter(options.storage)

    # Build strategy options
    strategy_options = WriteToolResultsToStorageOptions(
        boundary=options.boundary,
        adapter=adapter,
        serialize_result=options.serialize_result or (lambda v: json.dumps(v, indent=2)),
        storage_reader_tool_names=options.storage_reader_tool_names
        or ["readFile", "grepAndSearchFile"],
    )

    # Apply the chosen strategy
    if options.strategy == "write-tool-results-to-storage":
        return await write_tool_results_to_storage_strategy(messages, strategy_options)
    else:
        raise ValueError(f"Unknown compaction strategy: {options.strategy}")


def compact_messages_sync(
    messages: List[Message], options: Optional[CompactOptions] = None
) -> List[Message]:
    """
    Synchronous version of compact_messages for non-async contexts.

    Note: The underlying storage adapters should handle their I/O synchronously.

    Args:
        messages: List of message dictionaries with 'role', 'content', etc.
        options: Configuration options for compaction (uses defaults if not provided)

    Returns:
        Modified list of messages with tool results replaced by storage references
    """
    import asyncio

    # Check if there's already an event loop running
    try:
        loop = asyncio.get_running_loop()
        # If we're already in an async context, we can't use asyncio.run
        # Create a task and run it
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, compact_messages(messages, options))
            return future.result()
    except RuntimeError:
        # No event loop, we can use asyncio.run directly
        return asyncio.run(compact_messages(messages, options))
