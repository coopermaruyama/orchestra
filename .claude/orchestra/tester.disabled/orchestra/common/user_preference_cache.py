from collections import OrderedDict
from typing import Any, Optional


class UserPreferenceCache:
    def __init__(self, max_size: int = 100):
        """
        Initialize an in-memory cache for user preferences.

        :param max_size: Maximum number of preferences to store (default 100)
        """
        self._cache: OrderedDict[str, Any] = OrderedDict()
        self._max_size = max_size

    def get(self, key: str, default: Optional[Any] = None) -> Optional[Any]:
        """
        Retrieve a user preference, updating its recency.

        :param key: Preference key
        :param default: Value to return if key not found
        :return: Preference value or default
        """
        if key not in self._cache:
            return default

        # Move to end to mark as recently used
        value = self._cache[key]
        self._cache.move_to_end(key)
        return value

    def set(self, key: str, value: Any) -> None:
        """
        Set a user preference, potentially evicting the least recently used item.

        :param key: Preference key
        :param value: Preference value
        """
        # Remove if key exists to update its position
        if key in self._cache:
            del self._cache[key]

        # Add new item
        self._cache[key] = value

        # Evict oldest item if over limit
        if len(self._cache) > self._max_size:
            self._cache.popitem(last=False)

    def clear(self) -> None:
        """Clear all user preferences."""
        self._cache.clear()

    def __len__(self) -> int:
        """Return the number of preferences in the cache."""
        return len(self._cache)

    def __contains__(self, key: str) -> bool:
        """Check if a preference exists in the cache."""
        return key in self._cache
