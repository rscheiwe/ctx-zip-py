"""Track known storage keys for validation in reader tools."""

from typing import Set, Tuple

# Global registry of (storage_uri, key) pairs that have been written
_known_keys: Set[Tuple[str, str]] = set()


def register_known_key(storage_uri: str, key: str) -> None:
    """
    Register a key as known/valid for a given storage.

    This is used to track which keys have been written during the conversation
    to prevent arbitrary file access through reader tools.

    Args:
        storage_uri: The storage adapter's URI representation
        key: The storage key that was written
    """
    _known_keys.add((storage_uri, key))


def is_known_key(storage_uri: str, key: str) -> bool:
    """
    Check if a key is known/valid for a given storage.

    Args:
        storage_uri: The storage adapter's URI representation
        key: The storage key to check

    Returns:
        True if the key has been registered, False otherwise
    """
    return (storage_uri, key) in _known_keys


def clear_known_keys() -> None:
    """Clear all known keys. Useful for testing."""
    _known_keys.clear()
