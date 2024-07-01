import logging
import os
from collections.abc import Container, Iterable
from typing import TypeVar
from uuid import UUID

from tqdm import tqdm

from dynasty.db import Session, create_database, upsert_player_rankings, upsert_players
from dynasty.models import Player, PlayerRanking, RankingSet
from dynasty.service.dynasty_process import DynastyProcess
from dynasty.service.keeptradecut import KTCService
from dynasty.service.sleeper import SleeperService
from dynasty.util import SideEffect

T = TypeVar("T")
ALL_RANKING_SETS: Container[RankingSet] = (RankingSet.KeepTradeCut, RankingSet.DynastyProcess)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PlayerRankingRetriever:
    player_ids: set[UUID]

    def __init__(self) -> None:
        self.player_ids = set()

    def track(self, ranking: PlayerRanking) -> None:
        self.player_ids.add(ranking.player_id)

    def get_rankings(self, ranking_sets: Container[RankingSet], *, back_fill: bool) -> Iterable[PlayerRanking]:
        if RankingSet.KeepTradeCut in ranking_sets:
            with KTCService() as ktc_service:
                yield from tqdm(
                    SideEffect(ktc_service.get_rankings(back_fill=back_fill), side_effect=self.track),
                    desc="Retrieving KeepTradeCut rankings",
                )

        if RankingSet.DynastyProcess in ranking_sets:
            with DynastyProcess() as dp_service:
                yield from tqdm(
                    SideEffect(dp_service.get_rankings(back_fill=back_fill), side_effect=self.track),
                    desc="Retrieving DynastyProcess rankings",
                )

    def get_players(self) -> Iterable[Player]:
        with SleeperService() as sleeper_service:
            players = (player for player in sleeper_service.get_players() if player.player_id in self.player_ids)
            yield from tqdm(players, desc="Retrieving Sleeper players")


def import_players(ranking_sets: Container[RankingSet], *, back_fill: bool = False) -> None:
    engine = create_database()
    logger.info("Importing players")

    retriever = PlayerRankingRetriever()
    with Session(engine) as session:
        upsert_player_rankings(session, retriever.get_rankings(ranking_sets, back_fill=back_fill))
        upsert_players(session, retriever.get_players())


if __name__ == "__main__":
    back_fill = os.environ.get("BACK_FILL", "false").lower() in ("true", "yes", "on", "1")
    import_players({RankingSet.KeepTradeCut}, back_fill=back_fill)
