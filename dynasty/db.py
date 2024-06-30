from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from os import getenv

from sqlalchemy import Engine, create_engine
from sqlalchemy.dialects.postgresql import insert
from sqlmodel import Session, SQLModel, select

from dynasty.models import LeagueType, Player, PlayerRanking, RankingSet

PSQL_URL = getenv("PSQL_URL", "")


def create_database(url: str = PSQL_URL) -> Engine:
    if not url:
        err = "PSQL_URL environment variable must be set"
        raise ValueError(err)
    engine = create_engine(url)
    SQLModel.metadata.create_all(engine)
    return engine


def upsert_players(session: Session, players: Iterable[Player]) -> None:
    for count, player in enumerate(players):
        stmt = (
            insert(Player)
            .values(
                player_id=player.player_id,
                first_name=player.first_name,
                last_name=player.last_name,
                full_name=player.full_name,
                birth_date=player.birth_date,
                team=player.team,
                number=player.number,
                college=player.college,
                high_school=player.high_school,
                position=player.position,
                age=player.age,
                height=player.height,
                weight=player.weight,
                years_exp=player.years_exp,
                status=player.status,
                active=player.active,
                sleeper_id=player.sleeper_id,
                espn_id=player.espn_id,
                fantasy_data_id=player.fantasy_data_id,
                gsis_id=player.gsis_id,
                oddsjam_id=player.oddsjam_id,
                rotowire_id=player.rotowire_id,
                rotoworld_id=player.rotoworld_id,
                sportradar_id=player.sportradar_id,
                stats_id=player.stats_id,
                swish_id=player.swish_id,
                yahoo_id=player.yahoo_id,
            )
            .on_conflict_do_update(
                index_elements=["player_id"],
                set_={
                    "first_name": player.first_name,
                    "last_name": player.last_name,
                    "full_name": player.full_name,
                    "birth_date": player.birth_date,
                    "team": player.team,
                    "number": player.number,
                    "college": player.college,
                    "high_school": player.high_school,
                    "position": player.position,
                    "age": player.age,
                    "height": player.height,
                    "weight": player.weight,
                    "years_exp": player.years_exp,
                    "status": player.status,
                    "active": player.active,
                    "espn_id": player.espn_id,
                    "fantasy_data_id": player.fantasy_data_id,
                    "gsis_id": player.gsis_id,
                    "oddsjam_id": player.oddsjam_id,
                    "rotowire_id": player.rotowire_id,
                    "rotoworld_id": player.rotoworld_id,
                    "sleeper_id": player.sleeper_id,
                    "sportradar_id": player.sportradar_id,
                    "stats_id": player.stats_id,
                    "swish_id": player.swish_id,
                    "yahoo_id": player.yahoo_id,
                },
            )
        )
        session.exec(stmt)  # type: ignore[call-overload]

        if count % 100 == 0:
            session.commit()


def upsert_player_rankings(session: Session, player_rankings: Iterable[PlayerRanking]) -> None:
    for count, ranking in enumerate(player_rankings):
        stmt = (
            insert(PlayerRanking)
            .values(
                player_id=ranking.player_id,
                league_type=ranking.league_type,
                date=ranking.date,
                value=ranking.value,
                ranking_set=ranking.ranking_set,
                is_pick=ranking.is_pick,
            )
            .on_conflict_do_update(
                index_elements=["player_id", "league_type", "date", "ranking_set"],
                set_={"value": ranking.value},
            )
        )
        session.exec(stmt)  # type: ignore[call-overload]

        if count % 100 == 0:
            session.commit()


def get_player_rankings(session: Session, league_type: LeagueType, ranking_set: RankingSet) -> Iterable[PlayerRanking]:
    query = (
        select(PlayerRanking)
        .where(
            (PlayerRanking.league_type == league_type)
            & (PlayerRanking.date > datetime.now(tz=UTC).date() - timedelta(days=365))
            & (PlayerRanking.ranking_set == ranking_set.value)
        )
        .order_by(PlayerRanking.date)
    )
    return session.exec(query)
