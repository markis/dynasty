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
    player_full_name: str
    pos_rank: str
    team: str | None
    age: str | None
    player_value: int
    player_rank: int
    _rownum: int
    _position: str
    roster_type: str
    rank_type: str
    _insert_date: str


class FantasyNavigatorService:
    """Service for getting player rankings from FantasyNavigator."""

    session: Final[RequestsSession]

    def __init__(self, session: RequestsSession | None = None) -> None:
        if session is None:
            session = RequestsSession()
        self.session = session

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.session.close()

    def get_rankings(self, *, back_fill: bool) -> Iterable[PlayerRanking]:
        for league_type in (LeagueType.SuperFlex, LeagueType.Standard):
            if back_fill:
                err = "Backfilling is not supported for FantasyNavigator"
                raise NotImplementedError(err)
            else:
                yield from self.get_todays_rankings(league_type)

    def get_todays_rankings(self, _league_type: LeagueType) -> Iterable[PlayerRanking]:
        """
        Get player rankings from FantasyNavigator.

        In the html, the player rankings are stored in a javascript array. This function
        parses the html and extracts the player rankings from the javascript array.
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
