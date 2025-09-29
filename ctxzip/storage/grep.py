"""Grep/search functionality for stored content."""

import re
from dataclasses import dataclass
from typing import List, Pattern, Union
import json

from ..adapters.base import StorageAdapter, StorageReadParams


@dataclass
class GrepResultLine:
    """A single line matching a grep pattern."""

    line_number: int
    content: str

    def __str__(self) -> str:
        return f"{self.line_number}: {self.content}"


def grep_object(
    adapter: StorageAdapter, key: str, pattern: Pattern[str], max_results: int = 100
) -> List[GrepResultLine]:
    """
    Search for a pattern in stored content.

    Args:
        adapter: The storage adapter to read from
        key: The storage key to search
        pattern: Compiled regex pattern to search for
        max_results: Maximum number of matches to return

    Returns:
        List of matching lines with line numbers
    """
    results = []

    try:
        # Read the content
        content = adapter.read_text(StorageReadParams(key=key))

        # Try to parse as JSON first for better structured search
        try:
            obj = json.loads(content)
            # Convert back to pretty-printed JSON for line-based search
            content = json.dumps(obj, indent=2)
        except (json.JSONDecodeError, TypeError):
            # Not JSON, use as-is
            pass

        # Split into lines and search
        lines = content.splitlines()
        for i, line in enumerate(lines, start=1):
            if pattern.search(line):
                results.append(GrepResultLine(line_number=i, content=line))
                if len(results) >= max_results:
                    break

    except Exception as e:
        # Return empty results on error
        pass

    return results


def grep_text(
    text: str, pattern: Union[str, Pattern[str]], flags: str = "", max_results: int = 100
) -> List[GrepResultLine]:
    """
    Search for a pattern in text content.

    Args:
        text: The text to search
        pattern: Regex pattern (string or compiled)
        flags: Regex flags as a string (e.g., "i" for case-insensitive)
        max_results: Maximum number of matches to return

    Returns:
        List of matching lines with line numbers
    """
    # Compile pattern if needed
    if isinstance(pattern, str):
        regex_flags = 0
        if "i" in flags:
            regex_flags |= re.IGNORECASE
        if "m" in flags:
            regex_flags |= re.MULTILINE
        if "s" in flags:
            regex_flags |= re.DOTALL
        pattern = re.compile(pattern, regex_flags)

    results = []
    lines = text.splitlines()

    for i, line in enumerate(lines, start=1):
        if pattern.search(line):
            results.append(GrepResultLine(line_number=i, content=line))
            if len(results) >= max_results:
                break

    return results
