"""SoupService: A service for fetching and parsing HTML content using BeautifulSoup."""

from types import TracebackType
from typing import Final, Self

import requests
from bs4 import BeautifulSoup
from bs4.element import NavigableString, Tag

DEFAULT_HEADERS: Final = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36",
}


def get_text(tag: NavigableString | Tag | int | None) -> str:
    """
    Extract text content from a BeautifulSoup element.

    Safely extracts text from various BeautifulSoup element types,
    handling None values and different element types gracefully.

    Args:
    ----
        tag: The BeautifulSoup element to extract text from

    Returns:
    -------
        Stripped text content, or empty string if tag is None

    """
    if tag is None:
        return ""
    if isinstance(tag, Tag | NavigableString | str):
        return tag.text.strip()
    return str(tag).strip()


class SoupService:
    """
    Service for fetching and parsing HTML content using BeautifulSoup.

    Provides a convenient interface for making HTTP requests and parsing
    the response content into BeautifulSoup objects for web scraping.

    Attributes
    ----------
        session: HTTP session for making requests with consistent headers

    """

    session: Final[requests.Session]

    def __init__(self, session: requests.Session | None = None) -> None:
        """
        Initialize the SoupService with an optional HTTP session.

        Args:
        ----
            session: Optional HTTP session for making requests. If None, a new session is created.

        """
        if session is None:
            session = requests.Session()
        self.session = session

    def __enter__(self) -> Self:
        """
        Enter the context manager and return the service instance.

        Returns
        -------
            Self instance for use in context manager

        """
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """
        Exit the context manager and close the session.

        Args:
        ----
            exc_type: Exception type if an exception occurred
            exc_val: Exception value if an exception occurred
            exc_tb: Exception traceback if an exception occurred

        """
        self.close()

    def close(self) -> None:
        """Close the HTTP session to free resources."""
        self.session.close()

    def get(self, url: str) -> BeautifulSoup:
        """
        Fetch and parse HTML content from a URL.

        Makes an HTTP GET request to the specified URL and parses the
        response content into a BeautifulSoup object for further processing.

        Args:
        ----
            url: The URL to fetch content from

        Returns:
        -------
            BeautifulSoup object containing the parsed HTML content

        """
        page = self.session.get(url, headers=DEFAULT_HEADERS)

        return BeautifulSoup(page.content, "html.parser")
