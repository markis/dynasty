import re
from datetime import UTC, date, datetime
from typing import Final, overload
from uuid import UUID, uuid5

REMOVE: Final = re.compile(r"\bjr\.?|\bsr\.?|\biv|\biii|\bii")
REPLACE: Final = re.compile(r"\'|\"|\s+")
CLEAR: Final = re.compile(r"-+")
NAMESPACE: Final = UUID("1b9d6bcd-bbfd-4b2d-9b5d-ab8dfbbd4bed")


def normalize_name(name: str) -> str:
    name = name.replace(".", "")
    name = REMOVE.sub("", name.lower())
    name = REPLACE.sub("-", name)
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
