"""Database operations for the Dynasty Fantasy Football application."""

from collections.abc import Iterable
from datetime import datetime, timedelta
from os import getenv

from sqlalchemy import Engine, create_engine
from sqlalchemy.dialects.postgresql import insert
from sqlmodel import Session, SQLModel, select

from dynasty.models import LeagueType, Pick, Player, PlayerRanking, RankingSet

PSQL_URL = getenv("PSQL_URL", "")


def create_database(url: str = PSQL_URL) -> Engine:
    """Create a database engine and initialize the schema."""
    if not url:
        err = "PSQL_URL environment variable must be set"
        raise ValueError(err)
    engine = create_engine(url)
    SQLModel.metadata.create_all(engine)
    return engine


def upsert_players(session: Session, players: Iterable[Player], *, batch_size: int = 500) -> None:
    """
    Upsert players into the database, updating existing records if necessary.

    Args:
    ----
        session: Database session
        players: Iterable of Player objects to upsert
        batch_size: Number of records to process before committing (default: 500)

    """
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

        if count % batch_size == 0 and count > 0:
            session.commit()
    session.commit()


def upsert_player_rankings(
    session: Session, player_rankings: Iterable[PlayerRanking], *, batch_size: int = 1000
) -> None:
    """
    Upsert player rankings into the database, updating existing records if necessary.

    Args:
    ----
        session: Database session
        player_rankings: Iterable of PlayerRanking objects to upsert
        batch_size: Number of records to process before committing (default: 1000)

    """
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

        if count % batch_size == 0 and count > 0:
            session.commit()
    session.commit()


def record_picks(session: Session, picks: list[Pick]) -> int:
    """Record a list of picks in the database, avoiding duplicates."""
    if not picks:
        return 0

    pick_values = [
        {
            "league_id": pick.league_id,
            "draft_id": pick.draft_id,
            "sleeper_id": pick.sleeper_id,
            "picked_by": pick.picked_by,
            "pick_no": pick.pick_no,
            "round": pick.round,
        }
        for pick in picks
    ]

    stmt = insert(Pick).values(pick_values).on_conflict_do_nothing()
    result = session.exec(stmt)  # type: ignore[call-overload]
    session.commit()
    return int(result.rowcount)


def get_player_rankings(
    session: Session,
    league_type: LeagueType,
    ranking_set: RankingSet,
    end_date: datetime,
    time_frame: timedelta,
) -> Iterable[PlayerRanking]:
    """Retrieve player rankings for a specific league type and ranking set within a given time frame."""
    query = (
        select(PlayerRanking)
        .where(
            PlayerRanking.league_type == league_type,
            PlayerRanking.date > end_date - time_frame,
            PlayerRanking.date <= end_date,
            PlayerRanking.ranking_set == ranking_set.value,
        )
        .order_by(PlayerRanking.player_id, PlayerRanking.date)  # type: ignore[arg-type]
    )
    return session.exec(query)
