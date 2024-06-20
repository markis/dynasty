from collections.abc import Iterable
from typing import Final

import pandas as pd
import plotly.express as px
import streamlit as st
from pandas.core.frame import DataFrame

from dynasty.models import League
from dynasty.service.sleeper import SleeperService

POSITIONS: Final[Iterable[str]] = ("QB", "RB", "WR", "TE")


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
def get_roster(league_id: str, owner_id: str) -> DataFrame:
    df = pd.read_csv("./dynasty/streamlit/ktc-standard.csv")

    with SleeperService() as sleeper:
        sleeper_ids_str = sleeper.get_rosters(league_id, owner_id)
        sleeper_ids = [int(sleeper_id) for sleeper_id in sleeper_ids_str if sleeper_id and sleeper_id.isnumeric()]

        return df[df["sleeper_id"].isin(sleeper_ids)]


@st.cache_data(ttl=300)
def get_players() -> DataFrame:
    return pd.read_csv("./dynasty/streamlit/players.csv")


def init() -> None:
    if "sleeper_id" not in st.session_state or "sleeper_username" not in st.session_state:
        st.session_state["sleeper_id"] = None
        st.session_state["sleeper_username"] = None
        st.session_state["leagues"] = None
        st.session_state["selected_league"] = None


def render() -> None:
    st.set_page_config("Dynasty Rankings", ":football:", layout="wide")

    user_col, league_col = st.columns(2)

    form = user_col.form("sleeper_form", border=False)
    sleeper_username = form.text_input("Sleeper Username", key="sleeper_username")
    _ = form.form_submit_button("Get Leagues")

    if not sleeper_username:
        return
    sleeper_id, leagues = get_leagues(sleeper_username)
    if not leagues:
        league_col.write("No leagues found. Please try again.")
        return

    selected_league = league_col.selectbox(
        "Select a league",
        leagues,
        key="selected_league",
        format_func=get_league_name,
    )

    if not selected_league:
        return

    df = get_roster(selected_league.id, sleeper_id)
    if df.empty:
        st.write("No players found. Please try again.")
        return

    df = pd.merge(df, get_players(), on="sleeper_id", how="inner")
    df.sort_values(by="date", inplace=True)

    latest = df.groupby("full_name").last().reset_index()
    grouped_by_pos = latest.groupby("position")

    columns = st.columns(4)
    for pos, col in zip(POSITIONS, columns, strict=False):
        with col:
            st.write(f"#### {pos} rankings")
            pos_df: DataFrame = (
                grouped_by_pos.get_group(pos).sort_values(by="value", ascending=False).loc[:, ("full_name", "value")]  # type: ignore[index]
            )
            _ = st.dataframe(
                pos_df,
                use_container_width=True,
                column_config={"full_name": "Player", "value": "Value"},
                hide_index=True,
                key="value",
            )

    fig = px.line(df, x="date", y="value", color="full_name", title="Player Rankings Over Time")
    _ = st.plotly_chart(fig, use_container_width=True)


if __name__ == "__main__":
    init()
    render()
