from os import getenv

from sqlalchemy import Engine, create_engine
from sqlalchemy.dialects.postgresql import insert
from sqlmodel import Session, SQLModel

from dynasty.models import Player, PlayerRanking

PSQL_URL = getenv("PSQL_URL", "")


def create_database(url: str = PSQL_URL) -> Engine:
    if not url:
        err = "PSQL_URL environment variable must be set"
        raise ValueError(err)
    engine = create_engine(url)
    SQLModel.metadata.create_all(engine)
    return engine


def upsert_players(session: Session, players: list[Player]) -> None:
    for player in players:
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


def upsert_player_rankings(session: Session, player_rankings: list[PlayerRanking]) -> None:
    for ranking in player_rankings:
        stmt = (
            insert(PlayerRanking)
            .values(
                player_id=ranking.player_id,
                league_type=ranking.league_type,
                date=ranking.date,
                value=ranking.value,
                is_pick=ranking.is_pick,
            )
            .on_conflict_do_update(
                index_elements=["player_id", "league_type", "date"],
                set_={"value": ranking.value},
            )
        )
        session.exec(stmt)  # type: ignore[call-overload]
