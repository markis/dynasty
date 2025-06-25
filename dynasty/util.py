"""Utility functions for Dynasty League Football data processing."""

import re
from collections.abc import Callable, Iterable, Iterator, Mapping
from datetime import UTC, date, datetime
from typing import Final, TypeVar, overload, override
from uuid import UUID, uuid5

T = TypeVar("T")

REMOVE: Final = re.compile(r"\bjr\.?|\bsr\.?|\biv|\biii|\bii")
REPLACE: Final = re.compile(r"\'|\"|\s+")
CLEAR: Final = re.compile(r"-+")
NAMESPACE: Final = UUID("1b9d6bcd-bbfd-4b2d-9b5d-ab8dfbbd4bed")

NAME_REPLACEMENTS: Final[Mapping[str, str]] = {
    "marquise-brown": "hollywood-brown",
    "frank-gore-jr": "frank-gore",
    "josh-palmer": "joshua-palmer",
    "gabriel-davis": "gabe-davis",
    "jeffery-wilson": "jeff-wilson",
}


def normalize_name(name: str) -> str:
    """
    Normalize a player name for consistent identification.

    Removes common suffixes (Jr, Sr, III, etc.), quotes, and excessive whitespace.
    Applies specific name replacements for known edge cases.

    Args:
        name: The player name to normalize

    Returns:
        The normalized player name with dashes instead of spaces

    """
    name = name.replace(".", "")
    name = REMOVE.sub("", name.lower())
    name = REPLACE.sub("-", name)
    name = NAME_REPLACEMENTS.get(name, name)
    return CLEAR.sub("-", name).strip("-")


def generate_id(name: str) -> UUID:
    """
    Generate a consistent UUID for a player based on their normalized name.

    Uses UUID5 with a fixed namespace to ensure the same player name
    always generates the same UUID across different runs.

    Args:
        name: The player name to generate an ID for

    Returns:
        A UUID5 generated from the normalized player name

    """
    return uuid5(NAMESPACE, normalize_name(name))


@overload
def get_date(date_string: str) -> date: ...


@overload
def get_date(date_string: None) -> None: ...


def get_date(date_string: str | None) -> date | None:
    """
    Parse a date string in YYYY-MM-DD format.

    Args:
        date_string: Date string in YYYY-MM-DD format, or None

    Returns:
        Parsed date object, or None if input was None

    """
    if date_string is None:
        return None
    return datetime.strptime(date_string, "%Y-%m-%d").replace(tzinfo=UTC).date()


def get_height(height: str) -> int | None:
    """
    Convert height string to total inches.

    Handles both feet'inches" format (e.g., "6'2"") and inches-only format.

    Args:
        height: Height string in various formats

    Returns:
        Height in total inches, or None if input is empty/invalid

    """
    if not height:
        return None

    if "'" in height:
        feet, inches = height.split("'", 2)
        inches = inches.replace('"', "")
        return int(feet) * 12 + int(inches)

    return int(height) if height else None


def get_placement(placement: int) -> str:
    """
    Convert a numeric placement to its ordinal string representation.

    Handles special cases for 11th, 12th, 13th and applies appropriate
    ordinal suffixes (st, nd, rd, th).

    Args:
        placement: The numeric placement/rank

    Returns:
        Ordinal string representation (e.g., "1st", "2nd", "3rd", "11th")

    """
    nd = 2
    rd = 3
    if placement in {11, 12, 13}:
        return f"{placement}th"
    if placement % 10 == 1:
        return f"{placement}st"
    if placement % 10 == nd:
        return f"{placement}nd"
    if placement % 10 == rd:
        return f"{placement}rd"
    return f"{placement}th"


def convert_date(value: str) -> date:
    """
    Convert a date string in YYYY-MM-DD format to a date object.

    Args:
        value: Date string in YYYY-MM-DD format

    Returns:
        Parsed date object with UTC timezone

    """
    return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=UTC).date()


class SideEffect(Iterable[T]):
    """
    Iterator wrapper that applies a side effect to each item.

    This class allows for tracking or logging items being processed
    in a generator without breaking the iteration flow. Useful for
    progress tracking and debugging.

    Args:
        iterable: The iterable to wrap
        side_effect: Function to call on each item

    """

    side_effect: Callable[[T], None]

    def __init__(self, iterable: Iterable[T], side_effect: Callable[[T], None]) -> None:
        """
        Initialize the SideEffect wrapper.

        Args:
            iterable: The iterable to wrap
            side_effect: Function to call on each item before yielding

        """
        self.iterable = iterable
        self.side_effect = side_effect

    @override
    def __iter__(self) -> Iterator[T]:
        """
        Iterate through items, applying side effect to each.

        Yields:
            Each item from the wrapped iterable after applying side effect

        """
        for item in self.iterable:
            self.side_effect(item)
            yield item
