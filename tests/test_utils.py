from uuid import UUID

import pytest

from dynasty.models import PlayerPosition
from dynasty.util import generate_id, get_placement, normalize_name


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("John Doe", UUID("5881c89f-0940-5181-ac25-ef063bd350b7")),
        ("John Doe Jr.", UUID("5881c89f-0940-5181-ac25-ef063bd350b7")),
        ("Kenneth Walker", UUID("44ed3213-10f4-5986-b260-e0e9cec8b0e3")),
        ("Kenneth Walker III", UUID("44ed3213-10f4-5986-b260-e0e9cec8b0e3")),
    ],
)
def test_generate_id(value: str, expected: UUID) -> None:
    assert generate_id(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("John Doe", "john-doe"),
        ("John Doe Jr.", "john-doe"),
        ("John Doe Sr.", "john-doe"),
        ("John Doe III", "john-doe"),
        ("John-Doe", "john-doe"),
        ("A.J. Brown", "aj-brown"),
        ("AJ Brown", "aj-brown"),
        ("Marvin Harrison Jr.", "marvin-harrison"),
        ("Marquise Brown", "hollywood-brown"),
        ("Hollywood Brown", "hollywood-brown"),
        ("Kenneth Walker III", "kenneth-walker"),
    ],
)
def test_normalize_name(value: str, expected: UUID) -> None:
    assert normalize_name(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("RB", PlayerPosition.RB),
        ("QB1", PlayerPosition.QB),
        ("QB 1", PlayerPosition.QB),
        ("QB ", PlayerPosition.QB),
        ("QB 99", PlayerPosition.QB),
    ],
)
def test_positions(value: str, expected: PlayerPosition) -> None:
    assert PlayerPosition.from_str(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (1, "1st"),
        (2, "2nd"),
        (3, "3rd"),
        (4, "4th"),
        (5, "5th"),
        (6, "6th"),
        (7, "7th"),
        (8, "8th"),
        (9, "9th"),
        (10, "10th"),
        (11, "11th"),
        (12, "12th"),
        (13, "13th"),
    ],
)
def test_placement(value: int, expected: str) -> None:
    assert get_placement(value) == expected
