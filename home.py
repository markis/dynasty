from collections.abc import Iterable, Sequence
from datetime import UTC, datetime, timedelta
from os import environ
from pathlib import Path
from typing import Any, Final, NamedTuple

import numpy as np
import plotly.express as px
import polars as pl
import streamlit as st
from scipy.stats import linregress
from sqlmodel import Session

from dynasty.db import create_database, get_player_rankings
from dynasty.models import League, LeagueType, RankingSet, Roster, StatusType
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
    time_frame: timedelta = timedelta(days=30)


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
def get_rosters(league_id: str, *, include_drafted: bool) -> Sequence[Roster]:
    with SleeperService() as sleeper:
        return sleeper.get_rosters(league_id, include_drafted=include_drafted)


def get_rosters_df(
    league_id: str, _ranking_set: RankingSet, _players_df: pl.DataFrame, *, include_picks: bool, include_drafted: bool
) -> pl.DataFrame:
    def is_starter(roster: Roster, sleeper_id: int) -> bool:
        return sleeper_id in roster.starters

    rosters = get_rosters(league_id, include_drafted=include_drafted)
    arr: list[tuple[str, str, bool]] = [
        (roster.name, str(sleeper_id), is_starter(roster, sleeper_id))
        for roster in rosters
        for sleeper_id in roster.players
    ]
    rosters_df = pl.DataFrame(
        arr, orient="row", schema={"owner_name": pl.String, "sleeper_id": pl.String, "is_starter": pl.Boolean}
    )
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
def get_rankings(league_type: LeagueType, ranking_set: RankingSet, time_frame: timedelta) -> pl.DataFrame:
    """Retrieve player rankings from database or CSV file.

    Args:
        league_type: Type of league (e.g., dynasty, redraft)
        ranking_set: Set of rankings to retrieve

    Returns:
        DataFrame containing player rankings with player_id, date, and value columns
    """
    psql_url = environ.get("PSQL_URL")
    if psql_url is None:
        error_msg = "PSQL_URL environment variable is not set."
        raise ValueError(error_msg)
    engine = create_database(psql_url)
    today = datetime.now(UTC)

    with Session(engine) as session:
        rankings = get_player_rankings(
            session=session,
            league_type=league_type,
            ranking_set=ranking_set,
            end_date=today,
            time_frame=time_frame,
        )

        return pl.DataFrame(
            ((str(r.player_id), r.date, r.value) for r in rankings),
            schema={"player_id": pl.String, "date": pl.Date, "value": pl.Int64},
        )


def get_players_and_rankings(
    league_type: LeagueType, ranking_set: RankingSet, _players_df: pl.DataFrame, time_frame: timedelta
) -> pl.DataFrame:
    rankings_df = get_rankings(league_type, ranking_set, time_frame=time_frame)
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
    min_no_for_trend = 2

    slopes = []
    for history_nums in value_history:
        nums = [float(num) for num in history_nums if not np.isnan(num)]
        if len(nums) < min_no_for_trend or np.var(nums) == 0:
            slopes.append(0.0)  # No trend if no variance
            continue
        x = np.arange(len(nums))
        result: Any = linregress(x, nums)
        slopes.append(result.slope if result.slope is not None else 0.0)
    return slopes


def init() -> None:
    st.set_page_config("Dynasty Rankings", ":football:", layout="wide")
    fields = frozenset({"sleeper_id", "sleeper", "leagues", "league", "league_id"})

    # Get query parameters and flatten any list values
    query_defaults = {k: v[0] if isinstance(v, list) else v for k, v in st.query_params.items()}

    # Update session state only for missing fields
    st.session_state.update({field: query_defaults.get(field) for field in fields if field not in st.session_state})


def get_user_input() -> UserInput | None:
    """Get user input from Streamlit sidebar for dynasty league analysis.

    Returns:
        UserInput object with user selections or None if required fields are missing
    """
    # Get username and validate leagues
    sleeper_username = st.sidebar.text_input("Sleeper Username", key="sleeper")
    if not (sleeper_username and (result := get_leagues(sleeper_username))):
        return None
    st.query_params.update({"sleeper": sleeper_username})
    owner_id, leagues = result

    # Prepare league_id list and a lookup dict
    league_id_to_league = {league.id: league for league in leagues}
    league_ids = list(league_id_to_league.keys())

    # Get league_id from query params if present
    league_id_default = st.query_params.get("league_id", [None])[0]
    # If not in query, fall back to session state or first league
    default_league_id = league_id_default if league_id_default in league_id_to_league else league_ids[0]

    # League selection by league_id
    league_id = st.sidebar.selectbox(
        "Select a league",
        options=league_ids,
        index=league_ids.index(default_league_id),
        key="league_id",
        format_func=lambda lid: get_league_name(league_id_to_league[lid]),
    )
    if not league_id:
        return None
    st.query_params.update({"league_id": league_id})
    league = league_id_to_league[league_id]

    # Analysis configuration
    rankings_set = (
        st.sidebar.selectbox(
            "Rankings Set",
            options=[
                RankingSet.KeepTradeCut,
                RankingSet.DynastyProcess,
                RankingSet.FantasyCalc,
                RankingSet.FantasyNavigator,
            ],
            key="rankings_set",
            help="Select the source of player rankings",
        )
        or RankingSet.KeepTradeCut
    )
    st.query_params.update({"rankings_set": rankings_set})

    starters_only = st.sidebar.checkbox("Starters Only", key="starters_only", help="Show only starting players")
    st.query_params.update({"starters_only": starters_only})

    include_picks = st.sidebar.checkbox(
        "Include Picks",
        key="include_picks",
        value=not starters_only,
        disabled=starters_only,
        help="Include draft picks in analysis",
    )
    st.query_params.update({"include_picks": include_picks})

    trending_days = st.sidebar.slider(
        "Trending Days",
        key="trending_days",
        min_value=1,
        max_value=365,
        value=30,
        help="Number of days to analyze trends",
    )
    st.query_params.update({"trending_days": trending_days})

    return UserInput(
        owner_id=owner_id,
        league=league,
        rankings_set=rankings_set,
        starters_only=starters_only,
        include_picks=include_picks,
        time_frame=timedelta(days=trending_days),
    )


def render(user_input: UserInput) -> None:
    owner_id, league, ranking_set, starters_only, include_picks, time_frame = user_input
    prog = st.progress(0)
    positions = POSITIONS_WITH_PICK if include_picks and not starters_only else POSITIONS

    st.header(league.name)
    with st.expander("League Info", expanded=False):
        st.markdown(f"""
        * Owner: {owner_id}
        * League ID: {league.id}
        * Type: {league.league_type}
        * Teams: {league.team_count}
        * Status: {league.status}
        """)

    _ = prog.progress(10)
    players_df = get_players()
    _ = prog.progress(50)
    rankings_df = get_players_and_rankings(league.league_type, ranking_set, players_df, time_frame)
    _ = prog.progress(80)

    include_drafted = league.status == StatusType.Drafting
    roster_df = (
        get_rosters_df(
            league.id, ranking_set, rankings_df, include_picks=include_picks, include_drafted=include_drafted
        )
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

    existing_positions = [pos for pos in positions if pos in roster_df.get_column("position").unique().to_list()]
    positions = [pos for pos in positions if pos in existing_positions]
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
        get_rosters_df(
            league.id, ranking_set, rankings_df, include_picks=include_picks, include_drafted=include_drafted
        )
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
