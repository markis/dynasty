"""
Shared utilities for dynasty rankings analysis.

This module contains data fetching and processing functions used across multiple pages.
"""

import json
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime, timedelta
from os import environ
from pathlib import Path
from typing import Any, Final, NamedTuple

import numpy as np
import polars as pl
import streamlit as st
import streamlit.components.v1 as components
from scipy.stats import linregress
from sqlmodel import Session

from dynasty.db import create_database, get_player_rankings
from dynasty.models import League, LeagueType, RankingSet, Roster, StatusType
from dynasty.service.sleeper import SleeperService
from dynasty.util import generate_id

POSITIONS: Final[Iterable[str]] = ("QB", "RB", "WR", "TE")
POSITIONS_WITH_PICK: Final[Iterable[str]] = (*POSITIONS, "PICK")
IR_POSITIONS: Final[Iterable[str]] = ("IR", "NA", "O", "PUP", "NFI", "S")
DATA_DIR: Final[Path] = Path(__file__).resolve().parent.parent.joinpath("data")

HELP_TEXT_TREND: Final[str] = """
Trend is the slope of the linear regression based on the value history.
A positive trend indicates an increasing value, while a negative trend indicates a decreasing value.
"""


def get_cookie(name: str, default: str = "") -> str:
    """
    Get a cookie value by name.

    Args:
    ----
        name: The name of the cookie to retrieve
        default: Default value if cookie doesn't exist

    Returns:
    -------
        The cookie value or default if not found

    """
    return st.context.cookies.get(name, default)


def set_cookie(name: str, value: str) -> None:
    """
    Set a cookie value.

    Args:
    ----
        name: The name of the cookie
        value: The value to set

    """
    # Store in session state immediately
    st.session_state[f"cookie_{name}"] = value

    # Use a unique key for this cookie write
    cookie_key = f"cookie_{name}"
    if cookie_key not in st.session_state:
        st.session_state[cookie_key] = value


def dump_cookies() -> None:
    """
    Dump all cookies from session state to JavaScript.

    Reads all session state values with keys starting with 'cookie_' and
    generates JavaScript to set them as actual browser cookies.
    """
    cookie_script = "<script>"

    # Find all session state keys that start with 'cookie_'
    for key_, value in st.session_state.items():
        key = str(key_)
        if key.startswith("cookie_"):
            # Extract the actual cookie name (remove 'cookie_' prefix)
            cookie_name = key[7:]  # Remove 'cookie_' prefix
            # Escape quotes in the value to prevent JS errors
            escaped_value = str(value).replace('"', '\\"').replace("'", "\\'")
            cookie_script += f'document.cookie = "{cookie_name}={escaped_value}; path=/; max-age=2592000";'

    cookie_script += "</script>"

    # Only render if we have cookies to set
    if cookie_script != "<script></script>":
        components.html(cookie_script, height=0)


def render_home_nav() -> None:
    """
    Render a home navigation link at the top of pages.

    This provides a consistent way to navigate back to the main dashboard
    from any analysis page.
    """
    if st.button("🏠 Back to Home Dashboard", key="nav_home", use_container_width=False):
        st.switch_page("home.py")
    st.markdown("---")


class UserInput(NamedTuple):
    """User input for dynasty league analysis."""

    owner_id: str
    owner_name: str
    league: League
    rankings_set: RankingSet
    starters_only: bool = False
    include_picks: bool = False
    time_frame: timedelta = timedelta(days=30)


def get_league_name(league: League) -> str:
    """Get the name of the league for display purposes."""
    return league.name


@st.cache_data(ttl=300)
def get_leagues(sleeper_username: str) -> tuple[str, list[League]]:
    """
    Retrieve leagues for a given Sleeper username.

    Fetches all leagues associated with a Sleeper username and caches
    the results in Streamlit session state for performance.

    Args:
    ----
        sleeper_username: The Sleeper username to look up

    Returns:
    -------
        Tuple containing (sleeper_id, list_of_leagues). Returns ("", []) if user not found.

    """
    with SleeperService() as sleeper:
        sleeper_id = sleeper.get_sleeper_id(sleeper_username)
        if not sleeper_id:
            return "", []

        set_cookie("sleeper_id", sleeper_id)
        leagues = list(sleeper.get_leagues(sleeper_id))
        if not leagues:
            return "", []

        return sleeper_id, leagues


@st.cache_data(ttl=300)
def get_rosters(league_id: str, *, include_drafted: bool) -> Sequence[Roster]:
    """
    Retrieve rosters for a given league ID.

    Fetches roster information for all teams in a Sleeper league,
    optionally including drafted players.

    Args:
    ----
        league_id: The Sleeper league ID
        include_drafted: Whether to include recently drafted players

    Returns:
    -------
        Sequence of Roster objects for all teams in the league

    """
    with SleeperService() as sleeper:
        return sleeper.get_rosters(league_id, include_drafted=include_drafted)


def get_rosters_df(
    league_id: str,
    _ranking_set: RankingSet,
    _players_df: pl.DataFrame,
    *,
    include_picks: bool,
    include_drafted: bool,
) -> pl.DataFrame:
    """
    Retrieve and process roster data into a Polars DataFrame.

    Converts roster data from the Sleeper API into a structured DataFrame
    with player information, ownership, and starter status. Optionally
    includes draft picks with their estimated values.

    Args:
    ----
        league_id: The Sleeper league ID
        _ranking_set: The ranking set being used (for pick valuations)
        _players_df: DataFrame containing player information and values
        include_picks: Whether to include draft picks in the output
        include_drafted: Whether to include recently drafted players

    Returns:
    -------
        DataFrame with columns for owner_name, player info, starter status, and values

    """

    def is_starter(roster: Roster, sleeper_id: int) -> bool:
        return sleeper_id in roster.starters

    rosters = get_rosters(league_id, include_drafted=include_drafted)
    arr: list[tuple[str, str, bool]] = [
        (roster.name, str(sleeper_id), is_starter(roster, sleeper_id))
        for roster in rosters
        for sleeper_id in roster.players
    ]
    rosters_df = pl.DataFrame(
        arr,
        orient="row",
        schema={"owner_name": pl.String, "sleeper_id": pl.String, "is_starter": pl.Boolean},
    )
    # Remove any duplicate entries from roster data
    rosters_df = rosters_df.unique(subset=["owner_name", "sleeper_id"], keep="first")
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
    """
    Retrieve player rankings from the database within a specified time frame.

    Fetches historical ranking data from the database for a specific league type
    and ranking source, limited to the specified time window.

    Args:
    ----
        league_type: The league format (Standard or SuperFlex)
        ranking_set: The source of rankings (KeepTradeCut, DynastyProcess, etc.)
        time_frame: How far back to retrieve rankings data

    Returns:
    -------
        DataFrame with player_id, date, and value columns

    Raises:
    ------
        ValueError: If PSQL_URL environment variable is not set

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
    league_type: LeagueType,
    ranking_set: RankingSet,
    _players_df: pl.DataFrame,
    time_frame: timedelta,
) -> pl.DataFrame:
    """
    Retrieve and process player rankings with trend analysis.

    Combines ranking data with player information and calculates value trends
    using linear regression on historical data points.

    Args:
    ----
        league_type: The league format (Standard or SuperFlex)
        ranking_set: The source of rankings
        _players_df: DataFrame containing player information
        time_frame: Time window for historical data analysis

    Returns:
    -------
        DataFrame with player info, current values, value history, and trends

    """
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
    """
    Retrieve all NFL players from Sleeper and convert to DataFrame.

    Fetches the complete player database from Sleeper and converts it
    into a structured DataFrame for analysis and display.

    Returns
    -------
        DataFrame with player names, IDs, positions, and injury status

    """
    with SleeperService() as sleeper:
        players = sleeper.get_players()

    player_arr = [
        (player.full_name, str(player.player_id), player.sleeper_id, player.position, player.injury_status)
        for player in players
    ]

    return pl.DataFrame(
        player_arr,
        orient="row",
        schema={
            "full_name": pl.String,
            "player_id": pl.String,
            "sleeper_id": pl.String,
            "position": pl.String,
            "injury_status": pl.String,
        },
    )


def determine_trend(value_history: Iterable[Sequence[float]]) -> list[float]:
    """
    Calculate linear regression trends for player value histories.

    Computes the slope of linear regression for each player's value history
    to determine if their value is trending up, down, or staying flat.

    Args:
    ----
        value_history: Iterable of sequences containing historical values for each player

    Returns:
    -------
        List of trend slopes, where positive values indicate increasing value

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


def get_user_input() -> UserInput | None:
    """
    Collect and validate user input from Streamlit sidebar.

    Creates an interactive sidebar interface for users to select their
    Sleeper username, league, ranking preferences, and analysis options.
    Manages URL query parameters for shareable links.

    Returns
    -------
        UserInput object with all user selections, or None if required inputs are missing

    """
    # Get default values from query parameters or cookies
    query_params = st.query_params
    default_sleeper = query_params.get("sleeper") or get_cookie("sleeper", "")
    default_rankings_set = query_params.get("rankings_set") or get_cookie("rankings_set", RankingSet.KeepTradeCut.value)
    default_starters_only = (
        query_params.get("starters_only", "false") or get_cookie("starters_only", "false")
    ).lower() == "true"
    default_include_picks = (
        query_params.get("include_picks", "true").lower() == "true"
        or get_cookie("include_picks", "true").lower() == "true"
    )
    default_trending_days = int(query_params.get("trending_days") or get_cookie("trending_days", "30"))

    # Get username and validate leagues
    sleeper_username = st.sidebar.text_input("Sleeper Username", key="sleeper", value=default_sleeper)
    if not (sleeper_username and (result := get_leagues(sleeper_username))):
        return None
    st.query_params.update({"sleeper": sleeper_username})
    set_cookie("sleeper", sleeper_username)
    owner_id, leagues = result

    # Prepare league_id list and a lookup dict
    league_id_to_league = {league.id: league for league in leagues}
    league_ids = list(league_id_to_league.keys())

    # Get league_id from query params or cookies
    league_id_default = query_params.get("league_id", get_cookie("league_id", ""))
    # If not in query or invalid, fall back to first league
    default_league_id = league_id_default if league_id_default in league_id_to_league else ""

    # League selection by league_id
    league_id = st.sidebar.selectbox(
        "Select a league",
        options=league_ids,
        index=league_ids.index(default_league_id) if default_league_id in league_ids else 0,
        key="league_id",
        format_func=lambda lid: get_league_name(league_id_to_league[lid]),
    )
    if not league_id:
        return None
    st.query_params.update({"league_id": league_id})
    set_cookie("league_id", league_id)
    league = league_id_to_league[league_id]

    # Analysis configuration - use defaults from query params
    ranking_options = [
        RankingSet.KeepTradeCut,
        RankingSet.DynastyProcess,
        RankingSet.FantasyCalc,
        RankingSet.FantasyNavigator,
    ]

    # Find the default ranking set index
    try:
        default_ranking_index = next(i for i, rs in enumerate(ranking_options) if rs.value == default_rankings_set)
    except StopIteration:
        default_ranking_index = 0

    rankings_set = (
        st.sidebar.selectbox(
            "Rankings Set",
            options=ranking_options,
            index=default_ranking_index,
            key="rankings_set",
            help="Select the source of player rankings",
        )
        or RankingSet.KeepTradeCut
    )
    st.query_params.update({"rankings_set": rankings_set.value})
    set_cookie("rankings_set", rankings_set.value)

    starters_only = st.sidebar.checkbox(
        "Starters Only", key="starters_only", value=default_starters_only, help="Show only starting players"
    )
    st.query_params.update({"starters_only": str(starters_only).lower()})
    set_cookie("starters_only", str(starters_only).lower())

    include_picks = st.sidebar.checkbox(
        "Include Picks",
        key="include_picks",
        value=default_include_picks and not starters_only,
        disabled=starters_only,
        help="Include draft picks in analysis",
    )
    st.query_params.update({"include_picks": str(include_picks).lower()})
    set_cookie("include_picks", str(include_picks).lower())

    trending_days = st.sidebar.slider(
        "Trending Days",
        key="trending_days",
        min_value=1,
        max_value=365,
        value=default_trending_days,
        help="Number of days to analyze trends",
    )
    st.query_params.update({"trending_days": str(trending_days)})
    set_cookie("trending_days", str(trending_days))

    # Save cookies after collecting all user input
    dump_cookies()

    return UserInput(
        owner_id=owner_id,
        owner_name=sleeper_username,
        league=league,
        rankings_set=rankings_set,
        starters_only=starters_only,
        include_picks=include_picks,
        time_frame=timedelta(days=trending_days),
    )


def get_processed_data(user_input: UserInput) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    """
    Get all processed data needed for analysis.

    Args:
    ----
        user_input: UserInput object containing all user preferences

    Returns:
    -------
        Tuple of (players_df, rankings_df, roster_df)

    """
    owner_id, current_username, league, ranking_set, starters_only, include_picks, time_frame = user_input

    players_df = get_players()
    rankings_df = get_players_and_rankings(league.league_type, ranking_set, players_df, time_frame)

    include_drafted = league.status == StatusType.Drafting
    roster_df = (
        get_rosters_df(
            league.id,
            ranking_set,
            rankings_df,
            include_picks=include_picks,
            include_drafted=include_drafted,
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
            "injury_status",
        )
        .filter(pl.col("full_name").is_not_null())
        .unique(subset=["player_id", "owner_name"], keep="first")  # Remove duplicates
        .sort("value", descending=True, nulls_last=True)
    )

    if starters_only and "is_starter" in roster_df.columns:
        roster_df = roster_df.filter(pl.col("is_starter"))

    return players_df, rankings_df, roster_df
