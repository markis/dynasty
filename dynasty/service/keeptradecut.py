import json
import logging
from collections.abc import Iterable
from datetime import UTC, date, datetime
from types import TracebackType
from typing import Final, Self, TypedDict
from uuid import UUID

from bs4.element import Tag

from dynasty.models import LeagueType, PlayerPosition, PlayerRanking
from dynasty.service.soup import SoupService
from dynasty.util import generate_id

logger = logging.getLogger(__name__)

URL: Final = "https://keeptradecut.com/dynasty-rankings?format=1"
SUPER_FLEX_URL: Final = "https://keeptradecut.com/dynasty-rankings?format=2"
PLAYER_URL: Final = "https://keeptradecut.com/dynasty-rankings/players/"


class KTCValue(TypedDict):
    v: int
    d: str


class KTCValuesBasic(TypedDict):
    value: int
    rank: int
    positionalRank: int
    overallTier: int
    positionalTier: int


class KTCValues(KTCValuesBasic):
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
    tep: KTCValuesBasic
    ttep: KTCValuesBasic
    tetep: KTCValuesBasic


class KTCPlayerData(TypedDict):
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
    oneQBValues: KTCValues
    superflexValues: KTCValues
    number: int
    teamLongName: str
    birthday: str
    draftYear: int
    college: str
    byeWeek: int


class KTCService:
    """Service for getting player rankings from KeepTradeCut."""

    soup_service: Final[SoupService]

    def __init__(self, soup_service: SoupService | None = None) -> None:
        if soup_service is None:
            soup_service = SoupService()
        self.soup_service = soup_service

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.soup_service.close()

    @staticmethod
    def convert_player_data(data: KTCPlayerData, league_type: LeagueType, *, now: date) -> PlayerRanking:
        position = PlayerPosition.from_str(data["position"])
        if league_type == LeagueType.SuperFlex:
            return PlayerRanking(
                player_id=generate_id(data["playerName"]),
                value=data["superflexValues"]["value"],
                league_type=LeagueType.SuperFlex,
                date=now,
                is_pick=position == PlayerPosition.PICK,
            )
        return PlayerRanking(
            player_id=generate_id(data["playerName"]),
            value=data["oneQBValues"]["value"],
            league_type=LeagueType.Standard,
            date=now,
            is_pick=position == PlayerPosition.PICK,
        )

    def _get_data_from_page(self, url: str, variable: str) -> str | None:
        doc = self.soup_service.get(url)
        body = doc.find("body")
        if body is None:
            err = "Could not find body element on page"
            raise ValueError(err)
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

    def get_rankings(self, league_type: LeagueType) -> Iterable[PlayerRanking]:
        """
        Get player rankings from KeepTradeCut.

        In the html, the player rankings are stored in a javascript array. This function
        parses the html and extracts the player rankings from the javascript array.
        """
        url: str = SUPER_FLEX_URL if league_type == LeagueType.SuperFlex else URL
        data = self._get_data_from_page(url, "playersArray")
        if data is None:
            err = "Could not find player data on page"
            raise ValueError(err)

        id_list: list[UUID] = []
        today = datetime.now(UTC).date()
        json_data: list[KTCPlayerData] = json.loads(data)
        for player_data in json_data:
            try:
                ranking = self.convert_player_data(player_data, league_type=league_type, now=today)
                self.check_duplicate_player(ranking, id_list)

                id_list.append(ranking.player_id)
                yield ranking
            except (ValueError, TypeError, IndexError) as e:
                logger.debug("Error processing player data: %s, player_data: %s", e, player_data)

    @staticmethod
    def check_duplicate_player(ranking: PlayerRanking, id_list: list[UUID]) -> None:
        """Check if a player is already in the list of player ids."""
        if ranking.player_id in id_list:
            err = f"Duplicate player ID found: {ranking.player_id}"
            raise ValueError(err)

    def get_player_full_history(self, league_type: LeagueType) -> Iterable[PlayerRanking]:
        """
        Get the full history

        In the html, the player rankings are stored in a javascript array
        """
        url: str = SUPER_FLEX_URL if league_type == LeagueType.SuperFlex else URL
        data = self._get_data_from_page(url, "playersArray")
        if data is None:
            err = "Could not find player data on page"
            raise ValueError(err)

        json_data: list[KTCPlayerData] = json.loads(data)

        for player in json_data:
            player_slug: str = player["slug"]
            player_id: UUID = generate_id(player["playerName"])

            player_url: str = f"{PLAYER_URL}{player_slug}"
            data = self._get_data_from_page(player_url, "playerOneQB")
            if data is None:
                err = "Could not find player data on page"
                raise ValueError(err)

            player_data: dict[str, list[KTCValue]] = json.loads(data)
            for value in player_data["overallValue"]:
                yield PlayerRanking(
                    player_id=player_id,
                    value=value["v"],
                    league_type=league_type,
                    date=datetime.strptime(value["d"], "%Y-%m-%d").replace(tzinfo=UTC).date(),
                )
