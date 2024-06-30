import logging
import os
from collections.abc import Container, Generator
from uuid import UUID

from tqdm import tqdm

from dynasty.db import Session, create_database, upsert_player_rankings, upsert_players
from dynasty.models import LeagueType, PlayerRanking, RankingSet
from dynasty.service.dynasty_process import DynastyProcess
from dynasty.service.keeptradecut import KTCService
from dynasty.service.sleeper import SleeperService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PlayerRankingGenerator:
    player_ids: set[UUID]

    def __init__(self) -> None:
        self.player_ids = set()

    def __call__(
        self, *, back_fill: bool, ranking_sets: Container[RankingSet] | None = None
    ) -> Generator[PlayerRanking, None, None]:
        ranking_count = 0
        player_ids: set[UUID] = set()

        if not ranking_sets or RankingSet.KeepTradeCut in ranking_sets:
            with KTCService() as ktc_service:
                for league_type in (LeagueType.Standard, LeagueType.SuperFlex):
                    rankings = (
                        ktc_service.get_player_full_history(league_type)
                        if back_fill
                        else ktc_service.get_rankings(league_type)
                    )
                    for ranking in tqdm(rankings, desc=f"Mapping KTC players ({league_type})"):
                        player_ids.add(ranking.player_id)
                        yield ranking
                        ranking_count += 1

        if not ranking_sets or RankingSet.DynastyProcess in ranking_sets:
            with DynastyProcess() as dp_service:
                rankings = dp_service.get_rankings(back_fill=back_fill)
                for ranking in tqdm(rankings, desc="Mapping Dynasty Process players"):
                    player_ids.add(ranking.player_id)
                    yield ranking
                    ranking_count += 1

        logger.info("Ranking Count: %d", ranking_count)


def import_players(*, back_fill: bool = False, ranking_sets: Container[RankingSet] | None = None) -> None:
    """
    Import player rankings from KeepTradeCut and Sleeper into the database.
    """
    engine = create_database()
    logger.info("Importing players")

    rankings = PlayerRankingGenerator()
    with Session(engine) as session:
        player_rankings = rankings(back_fill=back_fill, ranking_sets=ranking_sets)
        upsert_player_rankings(session, player_rankings)
        session.commit()

    with SleeperService() as sleeper_service:
        players = tqdm(
            (player for player in sleeper_service.get_players() if player.player_id in rankings.player_ids),
            desc="Inserting Players",
        )

        with Session(engine) as session:
            upsert_players(session, players)
            session.commit()


if __name__ == "__main__":
    back_fill = os.environ.get("BACK_FILL", "false").lower() in ("true", "yes", "on", "1")
    import_players(back_fill=back_fill)
