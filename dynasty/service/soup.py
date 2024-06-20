from types import TracebackType
from typing import Final, Self

import requests
from bs4 import BeautifulSoup
from bs4.element import NavigableString, Tag

DEFAULT_HEADERS: Final = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"
}


def get_text(tag: NavigableString | Tag | int | None) -> str:
    if tag is None:
        return ""
    if isinstance(tag, Tag | NavigableString | str):
        return tag.text.strip()
    return str(tag).strip()


class SoupService:
    """Service for getting BeautifulSoup objects from URLs."""

    session: Final[requests.Session]

    def __init__(self, session: requests.Session | None = None) -> None:
        if session is None:
            session = requests.Session()
        self.session = session

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        self.session.close()

    def get(self, url: str) -> BeautifulSoup:
        page = self.session.get(url, headers=DEFAULT_HEADERS)

        return BeautifulSoup(page.content, "html.parser")
