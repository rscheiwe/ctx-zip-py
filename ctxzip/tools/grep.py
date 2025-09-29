"""Grep and search tool for finding patterns in stored content."""

import re
from typing import Optional, Union, Dict, Any, List
from dataclasses import dataclass

from ..adapters.base import StorageAdapter
from ..adapters.filesystem import FileStorageAdapter
from ..storage.resolver import create_storage_adapter
from ..storage.known_keys import is_known_key
from ..storage.grep import grep_object


@dataclass
class GrepAndSearchFileOptions:
    """Options for the grep and search file tool."""

    description: Optional[str] = None
    """Custom description for the tool."""

    base_dir: Optional[str] = None
    """Base directory for file storage (if using filesystem adapter)."""

    storage: Optional[Union[str, StorageAdapter]] = None
    """Default storage used when not specified. Accepts URI or adapter."""


DEFAULT_DESCRIPTION = """
Search for a pattern in a file that was previously written to storage.
Use the 'key' parameter with the value shown in 'Written to ... Key: <key>' messages.
Provide a regex pattern to search for, and optional flags (i for case-insensitive, m for multiline, etc).
Returns matching lines with line numbers.
"""


def grep_and_search_file(
    key: str,
    pattern: str,
    flags: Optional[str] = None,
    options: Optional[GrepAndSearchFileOptions] = None,
) -> Dict[str, Any]:
    """
    Search for a pattern in a file that was previously written to storage.

    This tool uses regular expressions to find matching lines in stored content
    and returns them with line numbers.

    Args:
        key: The storage key to search (as provided in 'Key: <key>' messages)
        pattern: Regular expression pattern to search for
        flags: Optional regex flags (e.g., 'i' for case-insensitive, 'm' for multiline)
        options: Optional configuration for the tool

    Returns:
        Dictionary containing:
        - key: The requested key
        - pattern: The search pattern
        - flags: The regex flags used
        - matches: List of matching lines (or error in 'content' field)
        - storage: The storage URI

    Example:
        >>> result = grep_and_search_file("data.json", r'"status":\s*"error"', flags="i")
        >>> for match in result.get("matches", []):
        ...     print(f"{match.line_number}: {match.content}")
    """
    if options is None:
        options = GrepAndSearchFileOptions()

    # Compile the regex pattern
    try:
        regex_flags = 0
        if flags:
            if "i" in flags:
                regex_flags |= re.IGNORECASE
            if "m" in flags:
                regex_flags |= re.MULTILINE
            if "s" in flags:
                regex_flags |= re.DOTALL
        regex = re.compile(pattern, regex_flags)
    except re.error as e:
        return {
            "key": key,
            "pattern": pattern,
            "flags": flags or "",
            "content": f"Invalid regex: {str(e)}",
        }

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
                "pattern": pattern,
                "flags": flags or "",
                "content": (
                    "Tool cannot be used: unknown key. Use a key previously surfaced via "
                    "'Written to ... Key: <key>' or 'Read from storage ... Key: <key>'. "
                    "If none exists, re-run the producing tool to persist and get a key."
                ),
                "storage": storage_uri,
            }

        # Search the content
        matches = grep_object(adapter, key, regex)

        # Convert matches to serializable format
        match_list = [{"line_number": m.line_number, "content": m.content} for m in matches]

        return {
            "key": key,
            "pattern": pattern,
            "flags": flags or "",
            "matches": match_list,
            "storage": storage_uri,
        }

    except Exception as e:
        return {
            "key": key,
            "pattern": pattern,
            "flags": flags or "",
            "content": (
                f"Error searching file: {str(e)}. "
                "Are you sure the storage is correct? If yes, make the original "
                "tool call again with the same arguments instead of relying on "
                "readFile or grepAndSearchFile."
            ),
            "storage": str(adapter) if "adapter" in locals() else "unknown",
        }


def create_grep_and_search_file_tool(options: Optional[GrepAndSearchFileOptions] = None):
    """
    Create a grep and search file tool function with the given options.

    This factory function is useful for frameworks that need a callable tool.

    Args:
        options: Configuration options for the tool

    Returns:
        A function that searches files in storage
    """

    def tool_fn(key: str, pattern: str, flags: Optional[str] = None) -> Dict[str, Any]:
        return grep_and_search_file(key, pattern, flags, options)

    tool_fn.__name__ = "grepAndSearchFile"
    tool_fn.__doc__ = (
        options.description if options and options.description else DEFAULT_DESCRIPTION
    )

    return tool_fn
