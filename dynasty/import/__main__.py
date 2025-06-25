"""Module for importing player rankings and data from various fantasy football services."""

import logging
import os
from collections.abc import Container, Iterable
from typing import TypeVar
from uuid import UUID

from sqlmodel import Session
from tqdm import tqdm

from dynasty.db import create_database, upsert_player_rankings, upsert_players
from dynasty.models import Player, PlayerRanking, RankingSet
from dynasty.service.dynasty_process import DynastyProcess
from dynasty.service.fantasy_calc import FantasyCalcService
from dynasty.service.fantasy_navigator import FantasyNavigatorService
from dynasty.service.keeptradecut import KTCService
from dynasty.service.sleeper import SleeperService
from dynasty.util import SideEffect

T = TypeVar("T")
ALL_RANKING_SETS: Container[RankingSet] = (RankingSet.KeepTradeCut, RankingSet.DynastyProcess)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PlayerRankingRetriever:
    """
    Coordinator class for retrieving player rankings from multiple sources.

    Manages the process of fetching player rankings from various fantasy football
    ranking services and tracking which players are being processed for
    efficient player data retrieval.

    Attributes:
        player_ids: Set of player UUIDs that have been processed

    """

    player_ids: set[UUID]

    def __init__(self) -> None:
        """Initialize the PlayerRankingRetriever with an empty player ID set."""
        self.player_ids = set()

    def track(self, ranking: PlayerRanking) -> None:
        """
        Track a player ranking by adding its player ID to the set.

        Used as a side effect function to collect player IDs while
        processing rankings from various sources.

        Args:
            ranking: The PlayerRanking instance being processed

        """
        self.player_ids.add(ranking.player_id)

    def get_rankings(self, ranking_sets: Container[RankingSet], *, back_fill: bool) -> Iterable[PlayerRanking]:
        """
        Retrieve player rankings from multiple ranking services.

        Fetches rankings from the specified ranking services, with progress tracking
        and automatic player ID collection for later player data retrieval.

        Args:
            ranking_sets: Container of RankingSet enums specifying which services to use
            back_fill: Whether to retrieve historical data or current data only

        Yields:
            PlayerRanking instances from all specified ranking services

        """
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

        if RankingSet.FantasyCalc in ranking_sets:
            with FantasyCalcService() as fc_service:
                yield from tqdm(
                    SideEffect(fc_service.get_rankings(back_fill=back_fill), side_effect=self.track),
                    desc="Retrieving FantasyCalc rankings",
                )

        if RankingSet.FantasyNavigator in ranking_sets:
            with FantasyNavigatorService() as fn_service:
                yield from tqdm(
                    SideEffect(fn_service.get_rankings(back_fill=back_fill), side_effect=self.track),
                    desc="Retrieving FantasyNavigator rankings",
                )

    def get_players(self) -> Iterable[Player]:
        """
        Retrieve player data for all tracked player IDs from Sleeper.

        Fetches complete player information from Sleeper for all players
        that were encountered during ranking retrieval.

        Yields:
            Player instances for all tracked player IDs

        """
        with SleeperService() as sleeper_service:
            players = (player for player in sleeper_service.get_players() if player.player_id in self.player_ids)
            yield from tqdm(players, desc="Retrieving Sleeper players")


def import_players(ranking_sets: Container[RankingSet], *, back_fill: bool = False) -> None:
    """
    Import player rankings and player data into the database.

    Orchestrates the complete import process by retrieving rankings from
    specified services, collecting player data, and storing everything
    in the database with proper upsert handling.

    Args:
        ranking_sets: Container of RankingSet enums specifying which services to import from
        back_fill: Whether to retrieve historical data or current data only

    """
    engine = create_database()
    logger.info("Importing players")

    retriever = PlayerRankingRetriever()
    with Session(engine) as session:
        upsert_player_rankings(session, retriever.get_rankings(ranking_sets, back_fill=back_fill))
        upsert_players(session, retriever.get_players())


if __name__ == "__main__":
    RANKING_SETS = {
        RankingSet.FantasyNavigator,
        RankingSet.FantasyCalc,
        RankingSet.DynastyProcess,
        RankingSet.KeepTradeCut,
    }
    back_fill = os.environ.get("BACK_FILL", "false").lower() in ("true", "yes", "on", "1")
    import_players(RANKING_SETS, back_fill=back_fill)
