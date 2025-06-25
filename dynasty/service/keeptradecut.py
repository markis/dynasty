"""Service for retrieving player rankings from KeepTradeCut."""

import json
import logging
from collections.abc import Iterable
from datetime import UTC, date, datetime
from types import TracebackType
from typing import Final, Self, TypedDict

from bs4.element import Tag

from dynasty.models import LeagueType, PlayerPosition, PlayerRanking, RankingSet
from dynasty.service.soup import SoupService
from dynasty.util import generate_id

logger = logging.getLogger(__name__)

URL: Final = "https://keeptradecut.com/dynasty-rankings?format=1"
SUPER_FLEX_URL: Final = "https://keeptradecut.com/dynasty-rankings?format=2"
PLAYER_URL: Final = "https://keeptradecut.com/dynasty-rankings/players/"


class KTCValue(TypedDict):
    """
    Type definition for KeepTradeCut historical value data point.

    Represents a single data point in a player's value history,
    containing the value and date information.
    """

    v: int  # Value
    d: str  # Date string


class KTCValuesBasic(TypedDict):
    """
    Type definition for basic KeepTradeCut player values.

    Contains fundamental ranking and tier information for a player
    in standard scoring formats.
    """

    value: int
    rank: int
    positionalRank: int
    overallTier: int
    positionalTier: int


class KTCValues(KTCValuesBasic):
    """
    Type definition for comprehensive KeepTradeCut player values.

    Extends the basic values with additional metrics including trends,
    start/sit values, and various scoring format variations.
    """

    startSitValue: int
    overallTrend: int
    positionalTrend: int
    overall7DayTrend: int
    positional7DayTrend: int
    kept: int
    traded: int
    cut: int
    diff: int
    isOutThisWeek: bool
    tep: KTCValuesBasic  # Tight End Premium values
    ttep: KTCValuesBasic  # Two Tight End Premium values
    tetep: KTCValuesBasic  # Three Tight End Premium values


class KTCPlayerData(TypedDict):
    """
    Type definition for KeepTradeCut player data response.

    Represents the complete player data structure returned from the
    KeepTradeCut API, including biographical information, physical
    attributes, and values for different league formats.
    """

    playerName: str
    playerID: int
    slug: str
    position: str
    positionID: int
    team: str
    rookie: bool
    age: float
    heightFeet: int
    heightInches: int
    weight: int
    seasonsExperience: int
    pickRound: int
    pickNum: int
    isFeatured: bool
    isStartSitFeatured: bool
    isTrending: bool
    isDevyReturningToSchool: bool
    isDevyYearDecrement: bool
    oneQBValues: KTCValues  # Standard league values
    superflexValues: KTCValues  # SuperFlex league values
    number: int
    teamLongName: str
    birthday: str
    draftYear: int
    college: str
    byeWeek: int


class KTCService:
    """
    Service for retrieving player rankings from KeepTradeCut.

    Provides methods to fetch current and historical player rankings
    from the KeepTradeCut dynasty fantasy football ranking service.
    Supports both standard and SuperFlex league formats.

    Attributes:
        soup_service: Service for making HTTP requests and parsing HTML

    """

    soup_service: Final[SoupService]

    def __init__(self, soup_service: SoupService | None = None) -> None:
        """
        Initialize the KTCService with an optional SoupService.

        Args:
            soup_service: Optional SoupService for making requests. If None, a new instance is created.

        """
        if soup_service is None:
            soup_service = SoupService()
        self.soup_service = soup_service

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
        Exit the context manager and close the service.

        Args:
            exc_type: Exception type if an exception occurred
            exc_val: Exception value if an exception occurred
            exc_tb: Exception traceback if an exception occurred

        """
        self.soup_service.close()

    @staticmethod
    def convert_player_data(data: KTCPlayerData, league_type: LeagueType, *, now: date) -> PlayerRanking:
        """
        Convert KeepTradeCut player data to internal PlayerRanking model.

        Transforms player data from KeepTradeCut's format into the application's
        PlayerRanking model, selecting appropriate values based on league type.

        Args:
            data: Player data from KeepTradeCut API
            league_type: League format (Standard or SuperFlex)
            now: Date for this ranking snapshot

        Returns:
            PlayerRanking model instance with converted data

        """
        position = PlayerPosition.from_str(data["position"])
        if league_type == LeagueType.SuperFlex:
            return PlayerRanking(
                player_id=generate_id(data["playerName"]),
                ranking_set=RankingSet.KeepTradeCut,
                value=data["superflexValues"]["value"],
                league_type=LeagueType.SuperFlex,
                date=now,
                is_pick=position == PlayerPosition.PICK,
            )
        return PlayerRanking(
            player_id=generate_id(data["playerName"]),
            ranking_set=RankingSet.KeepTradeCut,
            value=data["oneQBValues"]["value"],
            league_type=LeagueType.Standard,
            date=now,
            is_pick=position == PlayerPosition.PICK,
        )

    def _get_data_from_page(self, url: str, variable: str) -> str | None:
        """
        Extract JavaScript variable data from a KeepTradeCut page.

        Parses the HTML page to find and extract JSON data embedded in JavaScript variables.
        This is used to retrieve player ranking data from KeepTradeCut's web pages.

        Args:
            url: The URL to fetch and parse
            variable: The JavaScript variable name to extract

        Returns:
            JSON string data from the variable, or None if not found

        Raises:
            ValueError: If the page body cannot be found
            TypeError: If script elements cannot be found

        """
        doc = self.soup_service.get(url)
        body = doc.find("body")
        if body is None:
            err = "Could not find body element on page"
            raise ValueError(err)
        if not isinstance(body, Tag):
            err = "Body element is not a valid tag"
            raise TypeError(err)
        script_element = body.find("script")
        if not isinstance(script_element, Tag):
            err = "Could not find script elements on page"
            raise TypeError(err)

        token = f"var {variable} = "
        for line in script_element.text.splitlines():
            clean_line = line.strip()
            if clean_line.startswith(token):
                # remove the leading "var playersArray = "
                data = clean_line[len(token) :]
                # remove the trailing semicolon
                return data.rstrip(";")
        return None

    def get_rankings(self, *, back_fill: bool) -> Iterable[PlayerRanking]:
        """
        Get player rankings from KeepTradeCut for both league types.

        Retrieves rankings for both Standard and SuperFlex league formats,
        either for the current date only or full historical data.

        Args:
            back_fill: If True, retrieves full historical data; if False, current data only

        Yields:
            PlayerRanking instances for all players and league types

        """
        for league_type in (LeagueType.SuperFlex, LeagueType.Standard):
            if back_fill:
                yield from self.get_player_full_history(league_type)
            else:
                yield from self.get_todays_rankings(league_type)

    def get_todays_rankings(self, league_type: LeagueType) -> Iterable[PlayerRanking]:
        """
        Get current player rankings from KeepTradeCut.

        Retrieves today's player rankings for the specified league type.
        The rankings are embedded in JavaScript on the KeepTradeCut web page.

        Args:
            league_type: The league format to get rankings for (Standard or SuperFlex)

        Yields:
            PlayerRanking instances for all players in the specified league type

        Raises:
            ValueError: If player data cannot be found on the page

        """
        url: str = SUPER_FLEX_URL if league_type == LeagueType.SuperFlex else URL
        data = self._get_data_from_page(url, "playersArray")
        if data is None:
            err = "Could not find player data on page"
            raise ValueError(err)

        today = datetime.now(UTC).date()
        json_data: list[KTCPlayerData] = json.loads(data)
        for player_data in json_data:
            try:
                yield self.convert_player_data(player_data, league_type=league_type, now=today)
            except (ValueError, TypeError, IndexError) as e:
                logger.debug("Error processing player data: %s, player_data: %s", e, player_data)

    def get_player_full_history(self, league_type: LeagueType) -> Iterable[PlayerRanking]:
        """
        Get complete historical rankings for all players from KeepTradeCut.

        Retrieves the full value history for each player by scraping individual
        player pages. This provides historical trend data for analysis.

        Args:
            league_type: The league format to get rankings for (Standard or SuperFlex)

        Yields:
            PlayerRanking instances for all historical data points

        Raises:
            ValueError: If player data cannot be found on pages

        """
        url: str = SUPER_FLEX_URL if league_type == LeagueType.SuperFlex else URL
        data = self._get_data_from_page(url, "playersArray")
        if data is None:
            err = "Could not find player data on page"
            raise ValueError(err)

        json_data: list[KTCPlayerData] = json.loads(data)

        for player in json_data:
            player_slug: str = player["slug"]
            player_id = generate_id(player["playerName"])

            player_url: str = f"{PLAYER_URL}{player_slug}"
            variable = "playerOneQB" if league_type == LeagueType.Standard else "playerSuperflex"

            data = self._get_data_from_page(player_url, variable)
            if data is None:
                err = "Could not find player data on page"
                raise ValueError(err)

            is_pick = PlayerPosition.from_str(player["position"]) == PlayerPosition.PICK
            player_data: dict[str, list[KTCValue]] = json.loads(data)
            for value in player_data["overallValue"]:
                date_str = value["d"]
                try:
                    date_dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=UTC).date()
                except ValueError:
                    date_dt = datetime.strptime(date_str, "%y%m%d").replace(tzinfo=UTC).date()

                yield PlayerRanking(
                    player_id=player_id,
                    value=value["v"],
                    ranking_set=RankingSet.KeepTradeCut,
                    league_type=league_type,
                    date=date_dt,
                    is_pick=is_pick,
                )
