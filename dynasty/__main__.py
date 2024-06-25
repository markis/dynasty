import logging
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from uuid import UUID

from sqlmodel.orm.session import Session

from dynasty.db import create_database, upsert_player_rankings, upsert_players
from dynasty.models import LeagueType, Player, PlayerRanking
from dynasty.service.keeptradecut import KTCService
from dynasty.service.sleeper import SleeperService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class PlayerInfo:
    player: Player | None
    ktc_rankings: list[PlayerRanking]

    def __init__(self) -> None:
        self.player = None
        self.ktc_rankings = []


def get_player_map(league_type: LeagueType, *, back_fill: bool) -> Mapping[UUID, PlayerInfo]:
    player_map: defaultdict[UUID, PlayerInfo] = defaultdict(PlayerInfo)

    with KTCService() as ktc_service:
        rankings = (
            ktc_service.get_player_full_history(league_type) if back_fill else ktc_service.get_rankings(league_type)
        )
        for ranking in rankings:
            player_map[ranking.player_id].ktc_rankings.append(ranking)

    with SleeperService() as sleeper_service:
        for player in sleeper_service.get_players():
            if player.player_id in player_map:
                player_map[player.player_id].player = player

    ids_to_remove = [
        player_id
        for player_id, player_info in player_map.items()
        if not player_info.player or not player_info.ktc_rankings
    ]

    return {player_id: player_info for player_id, player_info in player_map.items() if player_id not in ids_to_remove}


def import_players(league_type: LeagueType, *, back_fill: bool = False) -> None:
    """
    Import player rankings from KeepTradeCut and Sleeper into the database.
    """
    engine = create_database()
    player_map = get_player_map(league_type, back_fill=back_fill)
    logger.info("Importing players", extra={"count": len(player_map), "league_type": league_type})
    with Session(engine) as session:
        upsert_players(
            session,
            [player_info.player for player_info in player_map.values() if player_info.player],
        )
        session.commit()

    with Session(engine) as session:
        upsert_player_rankings(
            session,
            [ranking for player_info in player_map.values() for ranking in player_info.ktc_rankings],
        )
        session.commit()

    logger.info("Import complete.")


if __name__ == "__main__":
    import_players(LeagueType.Standard, back_fill=False)
    import_players(LeagueType.SuperFlex, back_fill=False)
