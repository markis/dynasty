# from collections.abc import Iterable, Sequence
# from datetime import date, datetime, timedelta
# from typing import TYPE_CHECKING
#
# import numpy as np
# import pandas as pd
# import plotly.express as px
# import streamlit as st
# from pandas.core.frame import DataFrame
# from sqlalchemy import join, select
# from sqlalchemy.orm import sessionmaker
# from sqlmodel import SQLModel, Table
#
# from dynasty.db import create_database
# from dynasty.models import League, Player, PlayerPosition, PlayerRanking
# from dynasty.service.sleeper import SleeperService
#
# if TYPE_CHECKING:
#     from sqlalchemy.sql.expression import Select
#
# st.set_page_config("Dynasty Rankings", ":football:", layout="wide")
# if "leagues" not in st.session_state:
#     st.session_state["leagues"] = None
#
#
# leagues: Sequence[League] = st.session_state.leagues
# if not leagues:
#     st.write("No leagues found. Please go back and try again.")
#     st.stop()
# league = st.selectbox(
#     "Select a league", (league for league in leagues), format_func=lambda x: x.name
# )
#
# league_id = ""
# owner_id = ""
#
# with SleeperService() as sleeper:
#     sleeper_ids = sleeper.get_rosters(league_id, owner_id)
#
#
# def get_table(sqlmodel_type: type[SQLModel]) -> Table:
#     return sqlmodel_type.__table__
#
#
# def get_player_rankings(sleeper_ids: Iterable[str]) -> DataFrame:
#     engine = create_database()
#     Session = sessionmaker(bind=engine)
#     session = Session()
#
#     player_table = get_table(Player)
#     playerranking_table = get_table(PlayerRanking)
#     one_year_ago = datetime.now() - timedelta(days=365)
#
#     query: Select[tuple[str, PlayerPosition, date, int]] = (
#         select(
#             player_table.c.full_name,
#             player_table.c.position,
#             playerranking_table.c.date,
#             playerranking_table.c.value,
#         )
#         .select_from(
#             join(
#                 player_table,
#                 playerranking_table,
#                 player_table.c.player_id == playerranking_table.c.player_id,
#             )
#         )
#         .where(player_table.c.sleeper_id.in_(sleeper_ids))
#         .where(playerranking_table.c.date > one_year_ago)
#         .order_by(playerranking_table.c.date)
#     )
#     # Execute the query
#     result = session.execute(query)
#     # Fetch the results into a DataFrame
#     data = result.fetchall()
#     # Close the session
#     session.close()
#     return pd.DataFrame(data, columns=np.array(["name", "position", "date", "value"]))
#
#
# df = get_player_rankings(sleeper_ids)
#
# if df.empty:
#     st.write("No data available")
#     st.stop()
#
# latest = df.groupby("name").last().reset_index()
# grouped_by_pos = latest.groupby("position")
# positions = ["QB", "RB", "WR", "TE"]
#
# columns = st.columns(4)
# positions = ["QB", "RB", "WR", "TE"]
# for pos, col in zip(positions, columns, strict=False):
#     with col:
#         st.write(f"#### {pos} rankings")
#         pos_df = (
#             grouped_by_pos.get_group(pos)
#             .sort_values(by="value", ascending=False)
#             .loc[:, ("name", "value")]
#         )
#         st.dataframe(
#             pos_df,
#             use_container_width=True,
#             column_config={"name": "Player", "value": "Value"},
#             hide_index=True,
#             key="value",
#         )
#
# fig = px.line(df, x="date", y="value", color="name", title="Player Rankings Over Time")
# _ = st.plotly_chart(fig, use_container_width=True)
