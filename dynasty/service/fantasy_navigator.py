"""Service for retrieving player rankings from FantasyCalc."""

import logging
from collections.abc import Iterable
from datetime import UTC, date, datetime
from types import TracebackType
from typing import Final, Self, TypedDict

from requests import Session as RequestsSession

from dynasty.models import LeagueType, PlayerPosition, PlayerRanking, RankingSet
from dynasty.util import generate_id

logger = logging.getLogger(__name__)

URL = "https://fantasy-navigator-latest.onrender.com/ranks?platform=sf"


class FNRanking(TypedDict):
    """
    Type definition for FantasyNavigator ranking data response.

    Represents a single ranking entry from the FantasyNavigator API,
    containing player information, value, and metadata for dynasty rankings.
    """

    player_full_name: str
    pos_rank: str  # Positional rank as string
    team: str | None
    age: str | None
    player_value: int
    player_rank: int  # Overall rank
    _rownum: int  # Internal row number
    _position: str  # Player position
    roster_type: str  # League format (sf_value for SuperFlex)
    rank_type: str  # Type of ranking (dynasty, redraft, etc.)
    _insert_date: str  # Date when ranking was inserted


class FantasyNavigatorService:
    """
    Service for retrieving player rankings from FantasyNavigator.

    Provides methods to fetch current player rankings from the FantasyNavigator
    dynasty fantasy football ranking service. Supports both Standard and
    SuperFlex league formats.

    Attributes:
        session: HTTP session for making API requests

    """

    session: Final[RequestsSession]

    def __init__(self, session: RequestsSession | None = None) -> None:
        """
        Initialize the FantasyNavigatorService with an optional HTTP session.

        Args:
            session: Optional HTTP session for making requests. If None, a new session is created.

        """
        if session is None:
            session = RequestsSession()
        self.session = session

    def __enter__(self) -> Self:
        """
        Enter the context manager and return the service instance.

        Returns:
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
            exc_type: Exception type if an exception occurred
            exc_val: Exception value if an exception occurred
            exc_tb: Exception traceback if an exception occurred

        """
        self.session.close()

    def get_rankings(self, *, back_fill: bool) -> Iterable[PlayerRanking]:
        """
        Get player rankings from FantasyNavigator for both league types.

        Retrieves current rankings for both Standard and SuperFlex league formats.
        Historical data backfilling is not supported by FantasyNavigator.

        Args:
            back_fill: If True, raises NotImplementedError as backfilling is not supported

        Returns:
            Iterable of PlayerRanking instances for all players and league types

        Raises:
            NotImplementedError: If back_fill is True, as historical data is not available

        """
        for league_type in (LeagueType.SuperFlex, LeagueType.Standard):
            if back_fill:
                err = "Backfilling is not supported for FantasyNavigator"
                raise NotImplementedError(err)
            else:
                yield from self.get_todays_rankings(league_type)

    def get_todays_rankings(self, _league_type: LeagueType) -> Iterable[PlayerRanking]:
        """
        Get current player rankings from FantasyNavigator API.

        Retrieves today's player rankings from the FantasyNavigator API.
        The API returns data for both league types in a single response,
        so the league_type parameter is not used for API selection.

        Args:
            _league_type: League format parameter (not used in API call)

        Yields:
            PlayerRanking instances for all players in both league types

        Raises:
            ValueError: If the API request fails or returns an error status

        """
        url: str = URL
        response = self.session.get(url)
        if not response.ok:
            err = f"Error getting player rankings from FantasyNavigator: {response.status_code}"
            raise ValueError(err)

        today = datetime.now(UTC).date()
        json_data: list[FNRanking] = response.json()
        for player_data in json_data:
            try:
                ranking = self.convert_player_data(player_data, now=today)
                if ranking is not None:
                    yield ranking
            except (ValueError, TypeError, IndexError) as e:
                logger.debug("Error processing player data: %s, player_data: %s", e, player_data)

    @staticmethod
    def convert_player_data(data: FNRanking, *, now: date) -> PlayerRanking | None:
        """
        Convert FantasyNavigator ranking data to internal PlayerRanking model.

        Transforms ranking data from FantasyNavigator's format into the application's
        PlayerRanking model. Filters for dynasty rankings only and determines league
        type based on roster_type field.

        Args:
            data: Ranking data from FantasyNavigator API
            now: Date for this ranking snapshot

        Returns:
            PlayerRanking model instance, or None if not a dynasty ranking

        """
        if data["rank_type"] != "dynasty":
            return None

        league_type = LeagueType.SuperFlex if data["roster_type"] == "sf_value" else LeagueType.Standard
        position = PlayerPosition.from_str(data["_position"])
        return PlayerRanking(
            player_id=generate_id(data["player_full_name"]),
            ranking_set=RankingSet.FantasyNavigator,
            value=data["player_value"],
            league_type=league_type,
            date=now,
            is_pick=position == PlayerPosition.PICK,
        )
