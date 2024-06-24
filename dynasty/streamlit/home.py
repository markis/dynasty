from collections.abc import Iterable, Sequence
from textwrap import dedent
from typing import Final, NamedTuple

import pandas as pd
import plotly.express as px
import streamlit as st
from pandas.core.frame import DataFrame

from dynasty.models import League, LeagueType, RankingSet, Roster
from dynasty.service.sleeper import SleeperService

POSITIONS: Final[Iterable[str]] = ("QB", "RB", "WR", "TE")


class UserInput(NamedTuple):
    owner_id: str
    league: League
    rankings_set: RankingSet
    starters_only: bool = False


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

        return sleeper_id, leagues


@st.cache_data(ttl=300)
def get_rosters(league_id: str) -> Sequence[Roster]:
    with SleeperService() as sleeper:
        return sleeper.get_rosters(league_id)


@st.cache_data(ttl=300)
def get_rosters_df(league_id: str) -> DataFrame:
    def is_starter(roster: Roster, sleeper_id: int) -> bool:
        return sleeper_id in roster.starters

    rosters = get_rosters(league_id)
    arr = (
        (roster.name, sleeper_id, is_starter(roster, sleeper_id)) for roster in rosters for sleeper_id in roster.players
    )
    return pd.DataFrame(arr, columns=["owner_name", "sleeper_id", "is_starter"])


@st.cache_data(ttl=300)
def get_rankings(league_type: LeagueType, ranking_set: RankingSet = RankingSet.KeepTradeCut) -> DataFrame:
    return pd.read_csv(f"./dynasty/streamlit/{ranking_set.name.lower()}-{league_type.value.lower()}.csv")


@st.cache_data(ttl=300)
def get_players() -> DataFrame:
    return pd.read_csv("./dynasty/streamlit/players.csv")


def get_league_values(roster_df: DataFrame, *, only_starters: bool = False) -> DataFrame:
    if only_starters:
        roster_df = roster_df[roster_df["is_starter"]]

    league_values = roster_df.groupby("owner_name")["value"].sum().reset_index()

    owner_pos_values = roster_df.groupby(["owner_name", "position"])["value"].sum().reset_index()
    owner_pos_values = owner_pos_values.pivot(index="owner_name", columns="position", values="value").reset_index()

    league_values = pd.merge(league_values, owner_pos_values, on="owner_name", how="left")
    league_values = league_values[["owner_name", "value", *POSITIONS]]

    return league_values.sort_values(by="value", ascending=False)


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

    rankings_set = st.sidebar.selectbox("Rankings Set", [RankingSet.KeepTradeCut])
    if not rankings_set:
        rankings_set = RankingSet.KeepTradeCut

    starters_only = st.sidebar.checkbox("Starters Only", key="starters_only")

    return UserInput(owner_id, league, rankings_set, starters_only)


def render(user_input: UserInput) -> None:
    owner_id, league, _, starters_only = user_input
    _ = st.header(league.name)
    details = st.expander("League Info", expanded=False)
    _ = details.markdown(
        dedent(f"""
        * {owner_id}
        * {league.id}
        * {league.league_type}
        * {league.team_count} teams
        """)
    )

    rankings_df = get_rankings(league.league_type)
    rankings_df = pd.merge(get_players(), rankings_df, on="sleeper_id", how="inner")
    latest = rankings_df.groupby("full_name").last().reset_index()

    roster_df = pd.merge(latest, get_rosters_df(league.id), on="sleeper_id", how="inner")
    league_values = get_league_values(roster_df, only_starters=starters_only)

    league_values_long_df = league_values.loc[:, ("owner_name", *POSITIONS)].melt(
        id_vars="owner_name", value_vars=POSITIONS, var_name="position", value_name="value"
    )
    _ = st.plotly_chart(
        px.bar(league_values_long_df, x="owner_name", y="value", color="position"), use_container_width=True
    )

    _ = st.dataframe(league_values, hide_index=True, use_container_width=True)

    # for roster in get_rosters(user_input.league.id):
    #     _ = st.dataframe(latest[latest["sleeper_id"].isin(roster.starters)])

    # df = pd.merge(df, get_players(), on="sleeper_id", how="inner")
    # df.sort_values(by="date", inplace=True)
    #
    # latest = df.groupby("full_name").last().reset_index()
    #
    # st.dataframe(latest)

    # grouped_by_pos = latest.groupby("position")
    #
    # columns = st.columns(4)
    # for pos, col in zip(POSITIONS, columns, strict=False):
    #     with col:
    #         st.write(f"#### {pos} rankings")
    #         pos_df: DataFrame = (
    #             grouped_by_pos.get_group(pos)
    #             .sort_values(by="value", ascending=False)
    #             .loc[:, ("full_name", "value")]  # type: ignore[index]
    #         )
    #         _ = st.dataframe(
    #             pos_df,
    #             use_container_width=True,
    #             column_config={"full_name": "Player", "value": "Value"},
    #             hide_index=True,
    #             key="value",
    #         )
    #
    # fig = px.line(df, x="date", y="value", color="full_name", title="Player Rankings Over Time")
    # _ = st.plotly_chart(fig, use_container_width=True)


if __name__ == "__main__":
    init()
    user_input = get_user_input()
    if user_input:
        render(user_input)
