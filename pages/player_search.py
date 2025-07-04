"""
Player Search & Compare Page.

This page provides advanced player search functionality with filters and side-by-side
player comparisons with historical trends and similar player suggestions.
"""

import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import plotly.express as px
import plotly.graph_objects as go
import polars as pl
import streamlit as st
from plotly.subplots import make_subplots

from pages.shared_utils import (
    HELP_TEXT_TREND,
    POSITIONS,
    UserInput,
    get_processed_data,
    get_user_input,
    render_home_nav,
)

st.set_page_config("Player Search & Compare", ":mag:", layout="wide")


def init_search_session_state() -> None:
    """Initialize search-specific session state."""
    if "selected_players" not in st.session_state:
        st.session_state.selected_players = []


def advanced_player_search(
    players_df: pl.DataFrame, rankings_df: pl.DataFrame, roster_df: pl.DataFrame, search_filters: dict
) -> pl.DataFrame:
    """
    Perform advanced player search with multiple filters.

    Args:
    ----
        players_df: DataFrame of all players
        rankings_df: DataFrame of player rankings
        roster_df: DataFrame of roster information
        search_filters: Dictionary of search criteria

    Returns:
    -------
        Filtered DataFrame of players

    """
    # Join all data
    player_data = rankings_df.join(players_df, on="player_id", how="inner")
    player_data = player_data.join(roster_df.select(["player_id", "owner_name"]), on="player_id", how="left")

    # Apply filters
    filtered_df = player_data

    # Name search
    if search_filters.get("name_search"):
        name_pattern = f".*{re.escape(search_filters['name_search'])}.*"
        filtered_df = filtered_df.filter(pl.col("full_name").str.contains(name_pattern, strict=False))

    # Position filter
    if search_filters.get("positions") and search_filters["positions"] != ["All"]:
        filtered_df = filtered_df.filter(pl.col("position").is_in(search_filters["positions"]))

    # Value range
    if search_filters.get("value_min") is not None:
        filtered_df = filtered_df.filter(pl.col("value") >= search_filters["value_min"])
    if search_filters.get("value_max") is not None:
        filtered_df = filtered_df.filter(pl.col("value") <= search_filters["value_max"])

    # Trend filter
    if search_filters.get("trend_direction") == "Trending Up":
        filtered_df = filtered_df.filter(pl.col("trend") > 0.05)
    elif search_filters.get("trend_direction") == "Trending Down":
        filtered_df = filtered_df.filter(pl.col("trend") < -0.05)
    elif search_filters.get("trend_direction") == "Stable":
        filtered_df = filtered_df.filter((pl.col("trend") >= -0.05) & (pl.col("trend") <= 0.05))

    # Availability filter
    if search_filters.get("availability") == "Available":
        filtered_df = filtered_df.filter(pl.col("owner_name").is_null())
    elif search_filters.get("availability") == "Rostered":
        filtered_df = filtered_df.filter(pl.col("owner_name").is_not_null())

    return filtered_df.sort("value", descending=True)


def create_comparison_chart(players_data: list[pl.DataFrame]) -> go.Figure:
    """
    Create a comparison chart for selected players.

    Args:
    ----
        players_data: List of DataFrames for each player

    Returns:
    -------
        Plotly figure with comparison visualization

    """
    if not players_data:
        return go.Figure()

    # Extract data for comparison
    comparison_data = []
    for player_df in players_data:
        if len(player_df) > 0:
            row = player_df.row(0, named=True)
            comparison_data.append(
                {
                    "Player": row.get("full_name", "Unknown"),
                    "Value": row.get("value", 0),
                    "Trend": row.get("trend", 0),
                    "Position": row.get("position", "Unknown"),
                }
            )

    if not comparison_data:
        return go.Figure()

    # Create comparison charts
    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=("Player Values", "Value Trends"),
        specs=[[{"secondary_y": False}, {"secondary_y": False}]],
    )

    # Value comparison
    players = [d["Player"] for d in comparison_data]
    values = [d["Value"] for d in comparison_data]
    trends = [d["Trend"] for d in comparison_data]

    fig.add_trace(go.Bar(x=players, y=values, name="Value", marker_color="skyblue"), row=1, col=1)

    # Trend comparison
    colors = ["green" if t > 0 else "red" if t < 0 else "gray" for t in trends]
    fig.add_trace(go.Bar(x=players, y=trends, name="Trend", marker_color=colors), row=1, col=2)

    fig.update_layout(height=400, showlegend=False)
    fig.update_xaxes(title_text="Players", row=1, col=1)
    fig.update_xaxes(title_text="Players", row=1, col=2)
    fig.update_yaxes(title_text="Fantasy Value", row=1, col=1)
    fig.update_yaxes(title_text="Trend Score", row=1, col=2)

    return fig


def render_player_search(user_input: UserInput) -> None:
    """
    Render the player search and compare interface.

    Args:
    ----
        user_input: UserInput object containing all user preferences

    """
    owner_id, current_username, league, ranking_set, starters_only, include_picks, time_frame = user_input

    # Initialize search-specific session state
    init_search_session_state()

    st.header("🔍 Player Search & Compare")
    st.markdown("Advanced player search with filtering and side-by-side comparisons")

    # Get processed data
    with st.spinner("Loading player data..."):
        players_df, rankings_df, roster_df = get_processed_data(user_input)

    if len(rankings_df) == 0:
        st.warning("No player data available.")
        return

    # Sidebar filters
    with st.sidebar:
        st.subheader("🔍 Search Filters")

        # Name search
        name_search = st.text_input("Player Name", placeholder="Search by name...")

        # Position filter
        position_values = rankings_df.filter(pl.col("position").is_not_null()).get_column("position").unique().to_list()
        all_positions = ["All", *sorted(position_values)]
        selected_positions = st.multiselect("Positions", all_positions, default=["All"])

        # Value range
        value_range = st.slider("Value Range", 0, 10000, (0, 10000))

        # Trend direction
        trend_options = ["All", "Trending Up", "Stable", "Trending Down"]
        trend_filter = st.selectbox("Trend Direction", trend_options)

        # Availability
        availability_options = ["All", "Available", "Rostered"]
        availability_filter = st.selectbox("Availability", availability_options)

        # Apply filters button
        apply_filters = st.button("🔍 Apply Filters", use_container_width=True)

    # Main content area
    tab1, tab2 = st.tabs(["Search Results", "Player Comparison"])

    with tab1:
        st.subheader("Search Results")

        # Build search filters
        search_filters = {
            "name_search": name_search if name_search else None,
            "positions": selected_positions,
            "value_min": value_range[0],
            "value_max": value_range[1],
            "trend_direction": trend_filter if trend_filter != "All" else None,
            "availability": availability_filter if availability_filter != "All" else None,
        }

        # Perform search
        if apply_filters or name_search:
            search_results = advanced_player_search(players_df, rankings_df, roster_df, search_filters)

            if len(search_results) > 0:
                st.success(f"Found {len(search_results)} players matching your criteria")

                # Add to comparison section
                col1, col2 = st.columns([3, 1])

                with col2:
                    if st.button("Clear Comparison"):
                        st.session_state.selected_players = []
                        st.rerun()

                # Display results
                display_results = search_results.select(["full_name", "position", "value", "trend", "owner_name"]).head(
                    50
                )

                # Create interactive table
                for i, row in enumerate(display_results.iter_rows(named=True)):
                    player_name = row["full_name"]
                    position = row["position"]
                    value = row["value"]
                    trend = row["trend"]
                    owner = row["owner_name"] if row["owner_name"] else "Available"

                    # Player row with add button
                    col1, col2, col3, col4, col5, col6 = st.columns([3, 1, 1, 1, 2, 1])

                    with col1:
                        st.write(f"**{player_name}**")
                    with col2:
                        st.write(position)
                    with col3:
                        st.write(f"{value:,}")
                    with col4:
                        trend_emoji = "📈" if trend > 0.05 else "📉" if trend < -0.05 else "➡️"
                        st.write(f"{trend_emoji} {trend:.3f}")
                    with col5:
                        st.write(owner)
                    with col6:
                        if st.button("+ Compare", key=f"add_{i}_{player_name}"):
                            if player_name not in st.session_state.selected_players:
                                st.session_state.selected_players.append(player_name)
                                st.rerun()

                    if i < len(display_results) - 1:
                        st.divider()

            else:
                st.info("No players found matching your criteria. Try adjusting your filters.")
        else:
            st.info("Use the filters in the sidebar and click 'Apply Filters' to search for players.")

    with tab2:
        st.subheader("Player Comparison")

        if len(st.session_state.selected_players) > 0:
            st.markdown(f"**Comparing {len(st.session_state.selected_players)} players:**")

            # Get data for selected players
            selected_player_data = []
            for player_name in st.session_state.selected_players:
                player_data = (
                    rankings_df.join(players_df, on="player_id", how="inner")
                    .join(roster_df.select(["player_id", "owner_name"]), on="player_id", how="left")
                    .filter(pl.col("full_name") == player_name)
                )

                if len(player_data) > 0:
                    selected_player_data.append(player_data)

            if selected_player_data:
                # Comparison chart
                comparison_fig = create_comparison_chart(selected_player_data)
                st.plotly_chart(comparison_fig, use_container_width=True)

                # Detailed comparison table
                st.markdown("#### Detailed Comparison")

                comparison_table = []
                for player_data in selected_player_data:
                    if len(player_data) > 0:
                        row = player_data.row(0, named=True)

                        comparison_table.append(
                            {
                                "Player": row["full_name"],
                                "Position": row["position"],
                                "Value": row["value"],
                                "Trend": f"{row['trend']:.3f}",
                                "Owner": row["owner_name"] if row["owner_name"] else "Available",
                            }
                        )

                if comparison_table:
                    comparison_df = pl.DataFrame(comparison_table)
                    st.dataframe(comparison_df, hide_index=True, use_container_width=True)

                # Remove players from comparison
                st.markdown("#### Manage Comparison")
                cols = st.columns(len(st.session_state.selected_players))
                for i, player_name in enumerate(st.session_state.selected_players):
                    with cols[i % len(cols)]:
                        if st.button(f"Remove {player_name}", key=f"remove_{i}"):
                            st.session_state.selected_players.remove(player_name)
                            st.rerun()
        else:
            st.info("No players selected for comparison. Add players from the Search Results tab.")


def main() -> None:
    """Main function for the player search page."""
    render_home_nav()

    user_input = get_user_input()
    if user_input:
        render_player_search(user_input)
    else:
        st.info("Please enter your Sleeper username in the sidebar to get started.")


if __name__ == "__main__":
    main()
