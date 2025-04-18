from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any, Final, NamedTuple

import numpy as np
import plotly.express as px
import polars as pl
import streamlit as st
from scipy.stats import linregress
from sqlmodel import Session

from dynasty.db import create_database, get_player_rankings
from dynasty.models import League, LeagueType, RankingSet, Roster
from dynasty.service.sleeper import SleeperService
from dynasty.util import generate_id

POSITIONS: Final[Iterable[str]] = ("QB", "RB", "WR", "TE")
POSITIONS_WITH_PICK: Final[Iterable[str]] = (*POSITIONS, "PICK")
DATA_DIR: Final[Path] = Path(__file__).resolve().parent.joinpath("data")

HELP_TEXT_TREND: Final[str] = """
Trend is the slope of the linear regression based on the value history.
A positive trend indicates an increasing value, while a negative trend indicates a decreasing value.
"""


class UserInput(NamedTuple):
    owner_id: str
    league: League
    rankings_set: RankingSet
    starters_only: bool = False
    include_picks: bool = False


def get_league_name(league: League) -> str:
    return league.name


@st.cache_data(ttl=300)
def get_leagues(sleeper_username: str) -> tuple[str, list[League]]:
    with SleeperService() as sleeper:
        sleeper_id = sleeper.get_sleeper_id(sleeper_username)
        st.session_state["sleeper_id"] = sleeper_id
        if not sleeper_id:
            return "", []

        leagues = sleeper.get_leagues(sleeper_id)
        st.session_state["leagues"] = leagues
        if not leagues:
            return "", []

        return sleeper_id, list(leagues)


@st.cache_data(ttl=300)
def get_rosters(league_id: str) -> Sequence[Roster]:
    with SleeperService() as sleeper:
        return sleeper.get_rosters(league_id)


def get_rosters_df(
    league_id: str, ranking_set: RankingSet, _players_df: pl.DataFrame, *, include_picks: bool
) -> pl.DataFrame:
    def is_starter(roster: Roster, sleeper_id: int) -> bool:
        return sleeper_id in roster.starters

    rosters = get_rosters(league_id)
    arr: list[tuple[str, str, bool]] = [
        (roster.name, str(sleeper_id), is_starter(roster, sleeper_id))
        for roster in rosters
        for sleeper_id in roster.players
    ]
    rosters_df = pl.DataFrame(arr, orient="row", schema={"owner_name": pl.String, "sleeper_id": pl.String, "is_starter": pl.Boolean})
    rosters_df = rosters_df.join(_players_df, on="sleeper_id", how="full", coalesce=True)

    if not include_picks:
        return rosters_df

    # get value by player_id from players_df
    _player_vals_by_id = {
        player_id: value for player_id, value in _players_df.select(["player_id", "value"]).rows() if value is not None
    }

    def get_pick_row(roster_name: str, pick: str) -> tuple[str, str, str, str, int]:
        player_id = str(generate_id(pick))
        return (roster_name, player_id, pick, "PICK", _player_vals_by_id.get(player_id, 0))

    picks_arr = [get_pick_row(roster.name, pick) for roster in rosters for pick in roster.picks]
    picks_df = pl.DataFrame(
        picks_arr,
        orient="row",
        schema={
            "owner_name": pl.String,
            "player_id": pl.String,
            "full_name": pl.String,
            "position": pl.String,
            "value": pl.Int64,
        },
    )
    return pl.concat((rosters_df, picks_df), how="diagonal")


@st.cache_data(ttl=300)
def get_rankings(league_type: LeagueType, ranking_set: RankingSet) -> pl.DataFrame:
    import os

    if psql_url := os.getenv("PSQL_URL"):
        engine = create_database(psql_url)

        with Session(engine) as session:
            rankings = (
                (str(ranking.player_id), ranking.date, ranking.value)
                for ranking in get_player_rankings(session, league_type, ranking_set)
            )
            return pl.DataFrame(
                rankings,
                schema={"player_id": pl.String, "date": pl.Date, "value": pl.Int64},
            )
    else:
        return pl.read_csv(
            DATA_DIR / f"{ranking_set.name.lower()}-{league_type.value.lower()}.csv",
            schema={"player_id": pl.String, "date": pl.Date, "value": pl.Int64},
        )


def get_players_and_rankings(
    league_type: LeagueType, ranking_set: RankingSet, _players_df: pl.DataFrame
) -> pl.DataFrame:
    rankings_df = get_rankings(league_type, ranking_set)
    rankings_df = (
        rankings_df.group_by("player_id")
        .agg(pl.col("value").last().alias("value"), pl.col("value").explode().alias("value_history"))
        .sort("value", descending=True, nulls_last=True)
    )
    rankings_df = rankings_df.with_columns(
        pl.Series(
            "trend",
            values=determine_trend(rankings_df["value_history"]),
        ),
    )
    return rankings_df.join(_players_df, on="player_id", how="full", coalesce=True)


def get_players() -> pl.DataFrame:
    with SleeperService() as sleeper:
        players = sleeper.get_players()

    player_arr = [(player.full_name, str(player.player_id), player.sleeper_id, player.position) for player in players]

    return pl.DataFrame(
        player_arr,
        orient="row",
        schema={"full_name": pl.String, "player_id": pl.String, "sleeper_id": pl.String, "position": pl.String},
    )

def determine_trend(value_history: Iterable[Sequence[float]]) -> list[float]:
    """
    Determine the linear regression slope for each sequence in value_history.
    Returns a list of slopes indicating the trend direction for each sequence.
    """

    slopes = []
    for nums in value_history:
        nums = [float(num) for num in nums if not np.isnan(num)]
        if len(nums) < 2 or np.var(nums) == 0:
            slopes.append(0.0)  # No trend if no variance
            continue
        x = np.arange(len(nums))
        result: Any = linregress(x, nums)
        slopes.append(result.slope if result.slope is not None else 0.0)
    return slopes



def init() -> None:
    st.set_page_config("Dynasty Rankings", ":football:", layout="wide")
    fields: Iterable[str] = ("sleeper_id", "sleeper", "leagues", "league")
    if not all(field in st.session_state for field in fields):
        st.session_state.update({field: None for field in fields})


def get_user_input() -> UserInput | None:
    sleeper_username = st.sidebar.text_input("Sleeper Username", key="sleeper")
    if not sleeper_username:
        return

    owner_id, leagues = get_leagues(sleeper_username)
    if not leagues:
        return

    league = st.sidebar.selectbox(
        "Select a league",
        leagues,
        key="league",
        format_func=get_league_name,
    )
    if not league:
        return

    rankings_set = (
        st.sidebar.selectbox("Rankings Set", [RankingSet.KeepTradeCut, RankingSet.DynastyProcess], key="rankings_set")
        or RankingSet.KeepTradeCut
    )

    starters_only = st.sidebar.checkbox("Starters Only", key="starters_only")
    include_picks = st.sidebar.checkbox(
        "Include Picks", key="include_picks", value=not starters_only, disabled=starters_only
    )

    return UserInput(owner_id, league, rankings_set, starters_only, include_picks)


# def forecast_values(value_history: Sequence[Sequence[int]], days: int = 30) -> Sequence[Sequence[float]]:
#     """Forecast future values using Prophet model"""
#
#     forecasts: list[Sequence[float]] = []
#
#     for history in value_history:
#         if len(history) <= 1:
#             forecasts.append([])
#             continue
#
#         try:
#             model = ARIMA(history, order=(days, 1, 0))  # You can tune the order parameters
#             model_fit = model.fit()
#             forecast = model_fit.forecast(steps=days)
#             forecasts.append(forecast)
#         except Exception as e:
#             forecasts.append([])
#             print(history)
#
#     return forecasts


def render(user_input: UserInput) -> None:
    owner_id, league, ranking_set, starters_only, include_picks = user_input
    prog = st.progress(0)
    positions = POSITIONS_WITH_PICK if include_picks and not starters_only else POSITIONS

    st.header(league.name)
    with st.expander("League Info", expanded=False):
        st.markdown(f"""
        * Owner: {owner_id}
        * League ID: {league.id}
        * Type: {league.league_type}
        * Teams: {league.team_count}
        """)

    _ = prog.progress(10)
    players_df = get_players()
    _ = prog.progress(50)
    rankings_df = get_players_and_rankings(league.league_type, ranking_set, players_df)
    _ = prog.progress(80)

    roster_df = (
        get_rosters_df(league.id, ranking_set, rankings_df, include_picks=include_picks)
        .join(players_df, on="player_id", how="full", coalesce=True, suffix="_new")
        .with_columns(
            pl.when(pl.col("position").is_null())
            .then(pl.col("position_new"))
            .otherwise(pl.col("position"))
            .alias("position"),
            pl.when(pl.col("full_name").is_null())
            .then(pl.col("full_name_new"))
            .otherwise(pl.col("full_name"))
            .alias("full_name"),
        )
        .select(
            "owner_name",
            "player_id",
            "sleeper_id",
            "full_name",
            "position",
            "is_starter",
            "value",
            "trend",
            "value_history",
        )
        .filter(pl.col("full_name").is_not_null())
        .sort("value", descending=True, nulls_last=True)
    )

    if starters_only:
        roster_df = roster_df.filter(pl.col("is_starter"))

    league_values = (
        roster_df.filter(pl.col("owner_name").is_not_null())
        .group_by("owner_name")
        .agg(pl.col("value").sum().alias("value"), pl.col("trend").mean().alias("trend"))
        .join(
            other=(
                roster_df.group_by("owner_name", "position")
                .agg(pl.col("value").sum())
                .pivot(index="owner_name", on="position", values="value")
            ),
            on="owner_name",
            how="left",
            coalesce=True,
        )
        .select(pl.col(["owner_name", "value", "trend", *positions]))
        .sort("value", descending=True, nulls_last=True)
    )

    league_values_long_df = league_values.select(pl.col(["owner_name", *positions])).unpivot(
        index="owner_name", on=positions, variable_name="position", value_name="value"
    )

    _ = prog.progress(100)
    _ = prog.empty()

    _ = st.plotly_chart(
        px.bar(league_values_long_df, x="owner_name", y="value", color="position"), use_container_width=True
    )

    _ = st.dataframe(
        league_values,
        column_config={
            "full_name": st.column_config.Column("Player", width="small"),
            "value": st.column_config.NumberColumn("Value", width="small"),
            "trend": st.column_config.NumberColumn("Trend", format="%.2f", width="small", help=HELP_TEXT_TREND),
            **{pos: st.column_config.NumberColumn(pos, width="small") for pos in positions},
        },
        hide_index=True,
        use_container_width=True,
    )

    owners = sorted((str(name) for name in league_values["owner_name"].unique()), key=lambda x: x.lower())
    for owner in owners:
        expander = st.expander(f"{owner} Roster", expanded=False)
        owner_roster_df = roster_df.filter(pl.col("owner_name") == owner)

        for pos, col in zip(positions, expander.columns(len(positions)), strict=False):
            _ = col.markdown(f"#### {pos}")
            group_by_pos = owner_roster_df.filter(pl.col("position") == pos).select(("full_name", "value"))
            _ = col.dataframe(group_by_pos, use_container_width=True, hide_index=True)

        _ = expander.dataframe(
            owner_roster_df.select("full_name", "position", "value", "trend", "value_history"),
            column_config={
                "full_name": st.column_config.Column("Player", width="small"),
                "position": st.column_config.Column("Position", width="small"),
                "value": st.column_config.NumberColumn("Value", width="small"),
                "trend": st.column_config.NumberColumn("Trend", format="%.2f", width="small", help=HELP_TEXT_TREND),
                "value_history": st.column_config.AreaChartColumn("Value History", width="large"),
            },
            use_container_width=True,
            hide_index=True,
        )

    fa_rankings_df = (
        get_rosters_df(league.id, ranking_set, rankings_df, include_picks=include_picks)
        .filter(pl.col("owner_name").is_null(), pl.col("value").is_not_null(), pl.col("position").is_in(POSITIONS))
        .sort("value", descending=True, nulls_last=True)
    )
    _ = st.markdown("## Free Agents")
    _ = st.dataframe(
        fa_rankings_df,
        column_config={
            "full_name": st.column_config.Column("Player", width="small"),
            "position": st.column_config.Column("Position", width="small"),
            "value": st.column_config.NumberColumn("Value", width="small"),
            "trend": st.column_config.NumberColumn("Trend", format="%.2f", width="small", help=HELP_TEXT_TREND),
            "value_history": st.column_config.AreaChartColumn("Value History", width="large"),
            "owner_name": None,
            "sleeper_id": None,
            "is_starter": None,
            "player_id": None,
        },
        column_order=("full_name", "position", "value", "trend", "value_history"),
        hide_index=True,
        use_container_width=True,
    )


if __name__ == "__main__":
    init()
    if user_input := get_user_input():
        render(user_input)
