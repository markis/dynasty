from collections.abc import Iterable, Sequence
from typing import Final, NamedTuple

import pandas as pd
import streamlit as st
from pandas.core.frame import DataFrame

from dynasty.models import League, LeagueType, RankingSet, Roster
from dynasty.service.sleeper import SleeperService

POSITIONS: Final[Iterable[str]] = ("QB", "RB", "WR", "TE")


class UserInput(NamedTuple):
    owner_id: str
    league: League


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
def get_rankings(league_type: LeagueType, ranking_set: RankingSet = RankingSet.KeeperTradeCut) -> DataFrame:
    return pd.read_csv(f"./dynasty/streamlit/{ranking_set.value}-{league_type.value}.csv")


@st.cache_data(ttl=300)
def get_players() -> DataFrame:
    return pd.read_csv("./dynasty/streamlit/players.csv")


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

    return UserInput(owner_id, league)


def render(user_input: UserInput) -> None:
    owner_id, league = user_input
    _ = st.header(league.name)
    _ = st.markdown(owner_id)

    rankings_df = get_rankings(league.league_type)
    rankings_df = pd.merge(rankings_df, get_players(), on="sleeper_id", how="inner")
    latest = rankings_df.groupby("full_name").last().reset_index()

    roster_df = pd.merge(get_rosters_df(league.id), latest, on="sleeper_id", how="inner")

    owner_values = roster_df.groupby("owner_name")["value"].sum().reset_index()
    owner_values.rename(columns={"value": "roster_value"}, inplace=True)
    owner_starter_values = roster_df[roster_df["is_starter"]].groupby("owner_name")["value"].sum().reset_index()
    owner_starter_values.rename(columns={"value": "starters_value"}, inplace=True)
    owner_bench_values = roster_df[~roster_df["is_starter"]].groupby("owner_name")["value"].sum().reset_index()
    owner_bench_values.rename(columns={"value": "bench_value"}, inplace=True)

    owner_pos_values = roster_df.groupby(["owner_name", "position"])["value"].sum().reset_index()
    owner_pos_values = owner_pos_values.pivot(index="owner_name", columns="position", values="value").reset_index()
    owner_pos_values.rename(
        columns={"QB": "QB_value", "RB": "RB_value", "WR": "WR_value", "TE": "TE_value"}, inplace=True
    )

    owner_pos_starter_values = (
        roster_df[roster_df["is_starter"]].groupby(["owner_name", "position"])["value"].sum().reset_index()
    )
    owner_pos_starter_values = owner_pos_starter_values.pivot(
        index="owner_name", columns="position", values="value"
    ).reset_index()
    owner_pos_starter_values.rename(
        columns={
            "QB": "QB_starter_value",
            "RB": "RB_starter_value",
            "WR": "WR_starter_value",
            "TE": "TE_starter_value",
        },
        inplace=True,
    )

    owner_values = pd.merge(owner_values, owner_starter_values, on="owner_name", how="left")
    owner_values = pd.merge(owner_values, owner_bench_values, on="owner_name", how="left")
    owner_values = pd.merge(owner_values, owner_pos_values, on="owner_name", how="left")
    owner_values = pd.merge(owner_values, owner_pos_starter_values, on="owner_name", how="left")
    _ = st.dataframe(owner_values)

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
