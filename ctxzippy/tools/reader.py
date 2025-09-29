"""Read file tool for retrieving content from storage."""

from typing import Optional, Union, Dict, Any
from dataclasses import dataclass

from ..adapters.base import StorageAdapter, StorageReadParams
from ..adapters.filesystem import FileStorageAdapter
from ..storage.resolver import create_storage_adapter
from ..storage.known_keys import is_known_key


@dataclass
class ReadFileOptions:
    """Options for the read file tool."""

    description: Optional[str] = None
    """Custom description for the tool."""

    base_dir: Optional[str] = None
    """Base directory for file storage (if using filesystem adapter)."""

    storage: Optional[Union[str, StorageAdapter]] = None
    """Default storage used when not specified. Accepts URI or adapter."""


DEFAULT_DESCRIPTION = """
Read a file that was previously written to storage during this conversation.
Use the 'key' parameter with the value shown in 'Written to ... Key: <key>' messages.
This tool can only read files that were written during the current conversation.
"""


def read_file(key: str, options: Optional[ReadFileOptions] = None) -> Dict[str, Any]:
    """
    Read a file from storage that was previously written during this conversation.

    This is a reader tool that retrieves content using a storage key that was
    provided when the content was originally written.

    Args:
        key: The storage key to read (as provided in 'Key: <key>' messages)
        options: Optional configuration for the tool

    Returns:
        Dictionary containing:
        - key: The requested key
        - content: The file content (or error message)
        - storage: The storage URI

    Example:
        >>> result = read_file("abc123.txt")
        >>> print(result["content"])
    """
    if options is None:
        options = ReadFileOptions()

    try:
        # Create storage adapter
        if options.storage:
            adapter = create_storage_adapter(options.storage)
        elif options.base_dir:
            adapter = FileStorageAdapter(base_dir=options.base_dir)
        else:
            adapter = create_storage_adapter()

        storage_uri = str(adapter)

        # Check if key is known
        if not is_known_key(storage_uri, key):
            return {
                "key": key,
                "content": (
                    "Tool cannot be used: unknown key. Use a key previously surfaced via "
                    "'Written to ... Key: <key>' or 'Read from storage ... Key: <key>'. "
                    "If none exists, re-run the producing tool to persist and get a key."
                ),
                "storage": storage_uri,
            }

        # Read the content
        content = adapter.read_text(StorageReadParams(key=key))

        return {
            "key": key,
            "content": content,
            "storage": storage_uri,
        }

    except Exception as e:
        return {
            "key": key,
            "content": (
                f"Error reading file: {str(e)}. "
                "Are you sure the storage is correct? If yes, make the original "
                "tool call again with the same arguments instead of relying on "
                "readFile or grepAndSearchFile."
            ),
            "storage": str(adapter) if "adapter" in locals() else "unknown",
        }


def create_read_file_tool(options: Optional[ReadFileOptions] = None):
    """
    Create a read file tool function with the given options.

    This factory function is useful for frameworks that need a callable tool.

    Args:
        options: Configuration options for the tool

    Returns:
        A function that reads files from storage
    """

    def tool_fn(key: str) -> Dict[str, Any]:
        return read_file(key, options)

    tool_fn.__name__ = "readFile"
    tool_fn.__doc__ = (
        options.description if options and options.description else DEFAULT_DESCRIPTION
    )

    return tool_fn
