"""Service for retrieving player rankings from FantasyCalc."""

import logging
from collections.abc import Iterable
from datetime import UTC, date, datetime
from types import TracebackType
from typing import Final, Self, TypedDict

from requests import Session as RequestsSession

from dynasty.models import LeagueType, Player, PlayerPosition, PlayerRanking, RankingSet
from dynasty.service.sleeper import SleeperService
from dynasty.util import generate_id

logger = logging.getLogger(__name__)

STANDARD_URL = "https://api.fantasycalc.com/values/current?isDynasty=true&numQbs=1&numTeams=12&ppr=1&includeAdp=false"
SUPER_FLEX_URL = "https://api.fantasycalc.com/values/current?isDynasty=true&numQbs=2&numTeams=12&ppr=1&includeAdp=false"


class FCPlayer(TypedDict):
    """
    Type definition for FantasyCalc player data.

    Represents player information returned from the FantasyCalc API,
    containing biographical data and external service identifiers.
    """

    id: int
    name: str
    mflId: str
    sleeperId: str
    position: str
    maybeBirthday: str | None
    maybeHeight: str | None
    maybeWeight: int | None
    maybeCollege: str | None
    maybeTeam: str | None
    maybeAge: float | None
    maybeYoe: int | None  # Years of experience
    espnId: str | None
    fleaflickerId: str | None


class FCRanking(TypedDict):
    """
    Type definition for FantasyCalc ranking data response.

    Represents a complete ranking entry from the FantasyCalc API,
    including player information, values, trends, and metadata.
    """

    player: FCPlayer
    value: int
    overallRank: int
    positionRank: int
    trend30Day: int
    redraftDynastyValueDifference: int
    redraftDynastyValuePercDifference: int
    redraftValue: int
    combinedValue: int
    maybeMovingStandardDeviation: int | None
    maybeMovingStandardDeviationPerc: int | None
    maybeMovingStandardDeviationAdjusted: int | None
    displayTrend: bool
    maybeOwner: str | None
    starter: bool
    maybeTier: int | None
    maybeAdp: float | None  # Average Draft Position
    maybeTradeFrequency: int | None


class FantasyCalcService:
    """
    Service for retrieving player rankings from FantasyCalc.

    Provides methods to fetch current player rankings from the FantasyCalc
    dynasty fantasy football ranking service. Supports both Standard and
    SuperFlex league formats.

    Attributes:
        session: HTTP session for making API requests
        players: Dictionary mapping Sleeper IDs to Player objects for cross-referencing

    """

    session: Final[RequestsSession]
    players: dict[str, Player]

    def __init__(self, session: RequestsSession | None = None) -> None:
        """
        Initialize the FantasyCalcService with an optional HTTP session.

        Sets up the service and builds a mapping of Sleeper player IDs to Player objects
        for cross-referencing player data between services.

        Args:
            session: Optional HTTP session for making requests. If None, a new session is created.

        """
        if session is None:
            session = RequestsSession()
        self.session = session

        # Prepare the sleeper map
        sleeper = SleeperService(session=session)
        players = sleeper.get_players()
        self.players = {player.sleeper_id: player for player in players if player.sleeper_id}

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
        Get player rankings from FantasyCalc for both league types.

        Retrieves current rankings for both Standard and SuperFlex league formats.
        Historical data backfilling is not supported by FantasyCalc.

        Args:
            back_fill: If True, raises NotImplementedError as backfilling is not supported

        Returns:
            Iterable of PlayerRanking instances for all players and league types

        Raises:
            NotImplementedError: If back_fill is True, as historical data is not available

        """
        for league_type in (LeagueType.SuperFlex, LeagueType.Standard):
            if back_fill:
                err = "Backfilling is not supported for FantasyCalc"
                raise NotImplementedError(err)
            else:
                yield from self.get_todays_rankings(league_type)

    def get_todays_rankings(self, league_type: LeagueType) -> Iterable[PlayerRanking]:
        """
        Get current player rankings from FantasyCalc API.

        Retrieves today's player rankings for the specified league type
        from the FantasyCalc API endpoint.

        Args:
            league_type: The league format to get rankings for (Standard or SuperFlex)

        Yields:
            PlayerRanking instances for all players in the specified league type

        Raises:
            ValueError: If the API request fails or returns an error status

        """
        url: str = SUPER_FLEX_URL if league_type == LeagueType.SuperFlex else STANDARD_URL
        response = self.session.get(url)
        if not response.ok:
            err = f"Error getting player rankings from FantasyCalc: {response.status_code}"
            raise ValueError(err)

        today = datetime.now(UTC).date()
        json_data: list[FCRanking] = response.json()
        for player_data in json_data:
            try:
                yield self.convert_player_data(player_data, league_type=league_type, now=today)
            except (ValueError, TypeError, IndexError) as e:
                logger.debug("Error processing player data: %s, player_data: %s", e, player_data)

    def convert_player_data(self, data: FCRanking, league_type: LeagueType, *, now: date) -> PlayerRanking:
        """
        Convert FantasyCalc ranking data to internal PlayerRanking model.

        Transforms ranking data from FantasyCalc's format into the application's
        PlayerRanking model, using Sleeper ID cross-referencing when available.

        Args:
            data: Ranking data from FantasyCalc API
            league_type: League format (Standard or SuperFlex)
            now: Date for this ranking snapshot

        Returns:
            PlayerRanking model instance with converted data

        """
        sleeper_id = data["player"]["sleeperId"]
        player = self.players.get(sleeper_id)
        player_id = player.player_id if player else generate_id(data["player"]["name"])
        position = PlayerPosition.from_str(data["player"]["position"])
        return PlayerRanking(
            player_id=player_id,
            ranking_set=RankingSet.FantasyCalc,
            value=data["value"],
            league_type=league_type,
            date=now,
            is_pick=position == PlayerPosition.PICK,
        )
