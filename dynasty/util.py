import re
from collections.abc import Mapping
from datetime import UTC, date, datetime
from typing import Final, overload
from uuid import UUID, uuid5

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
    name = name.replace(".", "")
    name = REMOVE.sub("", name.lower())
    name = REPLACE.sub("-", name)
    name = NAME_REPLACEMENTS.get(name, name)
    return CLEAR.sub("-", name).strip("-")


def generate_id(name: str) -> UUID:
    return uuid5(NAMESPACE, normalize_name(name))


@overload
def get_date(date_string: str) -> date: ...


@overload
def get_date(date_string: None) -> None: ...


def get_date(date_string: str | None) -> date | None:
    if date_string is None:
        return None
    return datetime.strptime(date_string, "%Y-%m-%d").replace(tzinfo=UTC).date()


def get_height(height: str) -> int | None:
    if not height:
        return None

    if "'" in height:
        feet, inches = height.split("'", 2)
        inches = inches.replace('"', "")
        return int(feet) * 12 + int(inches)

    return int(height) if height else None


def get_placement(placement: int) -> str:
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
    return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=UTC).date()
