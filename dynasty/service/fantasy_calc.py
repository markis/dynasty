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
    maybeYoe: int | None
    espnId: str | None
    fleaflickerId: str | None


class FCRanking(TypedDict):
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
    maybeAdp: float | None
    maybeTradeFrequency: int | None


class FantasyCalcService:
    """Service for getting player rankings from FantasyCalc."""

    session: Final[RequestsSession]
    players: dict[str, Player]

    def __init__(self, session: RequestsSession | None = None) -> None:
        if session is None:
            session = RequestsSession()
        self.session = session

        # Prepare the sleeper map
        sleeper = SleeperService(session=session)
        players = sleeper.get_players()
        self.players = {player.sleeper_id: player for player in players if player.sleeper_id}

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
                err = "Backfilling is not supported for FantasyCalc"
                raise NotImplementedError(err)
            else:
                yield from self.get_todays_rankings(league_type)

    def get_todays_rankings(self, league_type: LeagueType) -> Iterable[PlayerRanking]:
        """
        Get player rankings from FantasyCalc.

        In the html, the player rankings are stored in a javascript array. This function
        parses the html and extracts the player rankings from the javascript array.
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
