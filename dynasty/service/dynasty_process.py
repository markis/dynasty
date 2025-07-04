"""DynastyProcess Service for retrieving player rankings."""

import codecs
import csv
import io
import os
from collections.abc import Iterable
from types import TracebackType
from typing import Self, TypedDict, TypeGuard

import git
import requests

from dynasty.models import LeagueType, PlayerRanking, RankingSet
from dynasty.util import convert_date, generate_id

LATEST_RANKINGS = "https://raw.githubusercontent.com/dynastyprocess/data/master/files/values.csv"
RANKINGS_GIT = "https://github.com/dynastyprocess/data.git"
RANKINGS_PATH = "files/values.csv"

DYNASTY_PROCESS_GIT_PATH = os.getenv("DYNASTY_PROCESS_GIT_PATH", "")


class DynastyProcessRow(TypedDict):
    """
    Type definition for DynastyProcess CSV row data.

    Represents a single row from the DynastyProcess rankings CSV file,
    containing player name, date, values for different league types, and position.
    """

    player: str  # Player name
    scrape_date: str  # Date when data was scraped (YYYY-MM-DD format)
    value_1qb: str  # Value for standard (1QB) leagues
    value_2qb: str  # Value for SuperFlex (2QB) leagues
    pos: str  # Player position


def is_dynasty_process_row(row: dict[str, str]) -> TypeGuard[DynastyProcessRow]:
    """
    Type guard to validate if a dictionary represents a valid DynastyProcess row.

    Checks that all required fields are present in the row dictionary
    to ensure it matches the expected DynastyProcessRow structure.

    Args:
    ----
        row: Dictionary to validate

    Returns:
    -------
        True if the row contains all required fields, False otherwise

    """
    return all(key in row for key in ["player", "scrape_date", "value_1qb", "value_2qb", "pos"])


class DynastyProcess:
    """
    Service for retrieving player rankings from DynastyProcess.

    Provides methods to fetch current and historical player rankings
    from the DynastyProcess GitHub repository. Supports both live API
    access and historical data retrieval via Git.

    Attributes
    ----------
        session: HTTP session for making API requests

    """

    def __init__(self, session: requests.Session | None = None) -> None:
        """
        Initialize the DynastyProcess service with an optional HTTP session.

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

    def get_latest_rankings(self) -> Iterable[DynastyProcessRow] | None:
        """
        Get the latest player rankings from DynastyProcess GitHub repository.

        Fetches the most recent rankings CSV file directly from the
        DynastyProcess GitHub repository via HTTP.

        Returns
        -------
            Iterable of DynastyProcessRow dictionaries, or None if request fails

        Raises
        ------
            requests.HTTPError: If the HTTP request fails

        """
        response = self.session.get(LATEST_RANKINGS)
        response.raise_for_status()

        csv_reader = csv.DictReader(codecs.iterdecode(response.iter_lines(), "utf-8"))
        return (row for row in csv_reader if is_dynasty_process_row(row))

    def get_rankings_from_git(self) -> Iterable[DynastyProcessRow] | None:
        """
        Get historical player rankings from local DynastyProcess Git repository.

        Retrieves rankings data from all historical commits in a local clone
        of the DynastyProcess repository. Useful for building complete historical datasets.

        Returns
        -------
            Iterable of DynastyProcessRow dictionaries from all commits, or None if repo unavailable

        """
        repo = git.Repo(DYNASTY_PROCESS_GIT_PATH)
        commits = repo.iter_commits(paths=RANKINGS_PATH)

        for commit in commits:
            blob = commit.tree.join(RANKINGS_PATH)
            file_content = str(blob.data_stream.read().decode("utf-8"))
            io_contents = io.StringIO(file_content)
            csv_reader = csv.DictReader(io_contents)
            for row in csv_reader:
                if is_dynasty_process_row(row):
                    yield row
        return None

    def get_rankings(self, *, back_fill: bool = False) -> Iterable[PlayerRanking]:
        """
        Get player rankings from DynastyProcess.

        Retrieves player rankings for both Standard and SuperFlex league types,
        either from the latest data or complete historical dataset.

        Args:
        ----
            back_fill: If True, retrieves historical data from Git; if False, latest data only

        Returns:
        -------
            Iterable of PlayerRanking instances for all players and league types

        """
        rows = self.get_latest_rankings() if not back_fill else self.get_rankings_from_git()

        if rows is None:
            return []

        return (
            PlayerRanking(
                player_id=generate_id(row["player"]),
                league_type=league_type,
                date=convert_date(row["scrape_date"]),
                value=int(row["value_1qb"]) if league_type == LeagueType.Standard else int(row["value_2qb"]),
                ranking_set=RankingSet.DynastyProcess,
                is_pick=row["pos"] == "PICK",
            )
            for row in rows
            for league_type in (LeagueType.Standard, LeagueType.SuperFlex)
            if row
        )
