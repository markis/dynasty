from uuid import UUID

import pytest

from dynasty.models import PlayerPosition
from dynasty.util import generate_id, normalize_name


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("John Doe", UUID("5881c89f-0940-5181-ac25-ef063bd350b7")),
        ("John Doe Jr.", UUID("5881c89f-0940-5181-ac25-ef063bd350b7")),
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
