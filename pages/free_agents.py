"""
Free Agents Page.

This page provides analysis of available players in the league,
including their rankings, values, and trends.
"""

import polars as pl
import streamlit as st

from pages.shared_utils import (
    HELP_TEXT_TREND,
    POSITIONS,
    get_processed_data,
    get_user_input,
    render_home_nav,
)

st.set_page_config("Free Agents", ":runner:", layout="wide")


def render_free_agents(user_input) -> None:
    """
    Render free agents analysis.

    Args:
    ----
        user_input: UserInput object containing all user preferences

    """
    owner_id, current_username, league, ranking_set, starters_only, include_picks, time_frame = user_input

    st.header(f"Free Agents - {league.name}")

    # Progress bar for data loading
    prog = st.progress(0)

    # Get processed data
    players_df, rankings_df, roster_df = get_processed_data(user_input)
    _ = prog.progress(60)

    # Get only rostered players (players who actually have an owner)
    rostered_players = roster_df.filter(pl.col("owner_name").is_not_null())
    rostered_player_ids = set(rostered_players.get_column("player_id").to_list())
    _ = prog.progress(80)

    # Get free agents - all ranked players who are NOT on any roster
    fa_rankings_df = (
        rankings_df.filter(
            pl.col("value").is_not_null(),
            pl.col("position").is_in(list(POSITIONS)),
            ~pl.col("player_id").is_in(list(rostered_player_ids)),  # Exclude rostered players
        )
        .unique(subset=["player_id"], keep="first")  # Remove duplicates
        .sort("value", descending=True, nulls_last=True)
    )

    _ = prog.progress(100)
    _ = prog.empty()

    # Position filter
    st.subheader("Filter by Position")
    available_positions = sorted(fa_rankings_df.get_column("position").unique().to_list())
    selected_positions = st.multiselect(
        "Select positions to show",
        options=available_positions,
        default=available_positions,
        help="Filter free agents by position",
    )

    if selected_positions:
        filtered_fa_df = fa_rankings_df.filter(pl.col("position").is_in(selected_positions))
    else:
        filtered_fa_df = fa_rankings_df

    # Value filter
    if len(filtered_fa_df) > 0:
        value_col = filtered_fa_df.get_column("value")
        min_val = value_col.min()
        max_val = value_col.max()

        # Ensure we have valid numeric values before converting
        if (
            min_val is not None
            and max_val is not None
            and isinstance(min_val, (int, float))
            and isinstance(max_val, (int, float))
        ):
            min_value = int(min_val)
            max_value = int(max_val)

            value_range = st.slider(
                "Minimum Value",
                min_value=min_value,
                max_value=max_value,
                value=min_value,
                help="Filter players by minimum value",
            )

            filtered_fa_df = filtered_fa_df.filter(pl.col("value") >= value_range)

    # Show statistics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Free Agents", len(fa_rankings_df))
    with col2:
        st.metric("Filtered Results", len(filtered_fa_df))
    with col3:
        if len(filtered_fa_df) > 0:
            avg_value_raw = filtered_fa_df.get_column("value").mean()
            if avg_value_raw is not None and isinstance(avg_value_raw, (int, float)):
                avg_value = int(avg_value_raw)
                st.metric("Average Value", avg_value)

    # Free agents table
    st.subheader("Available Players")

    if len(filtered_fa_df) > 0:
        st.dataframe(
            filtered_fa_df,
            column_config={
                "full_name": st.column_config.Column("Player", width="medium"),
                "position": st.column_config.Column("Position", width="small"),
                "value": st.column_config.NumberColumn("Value", width="small"),
                "trend": st.column_config.NumberColumn("Trend", format="%.2f", width="small", help=HELP_TEXT_TREND),
                "value_history": st.column_config.AreaChartColumn("Value History", width="large"),
                "owner_name": None,
                "sleeper_id": None,
                "is_starter": None,
                "player_id": None,
                "injury_status": None,
            },
            column_order=("full_name", "position", "value", "trend", "value_history"),
            hide_index=True,
            use_container_width=True,
        )
    else:
        st.info("No free agents match your current filters.")

    # Top players by position
    if len(filtered_fa_df) > 0:
        st.subheader("Top Free Agents by Position")

        # Get top 5 players per position
        top_by_position = (
            filtered_fa_df.group_by("position").agg(pl.col("full_name", "value", "trend").head(5)).sort("position")
        )

        # Create columns for each position
        positions_with_data = top_by_position.get_column("position").to_list()
        cols = st.columns(len(positions_with_data))

        for i, pos in enumerate(positions_with_data):
            with cols[i]:
                st.markdown(f"### {pos}")
                pos_data = top_by_position.filter(pl.col("position") == pos)

                # Extract the lists for this position
                names = pos_data.get_column("full_name").to_list()[0]
                values = pos_data.get_column("value").to_list()[0]
                trends = pos_data.get_column("trend").to_list()[0]

                # Create a small dataframe for this position
                pos_df = pl.DataFrame({"Player": names, "Value": values, "Trend": trends})

                st.dataframe(
                    pos_df,
                    column_config={
                        "Player": st.column_config.Column("Player", width="medium"),
                        "Value": st.column_config.NumberColumn("Value", width="small"),
                        "Trend": st.column_config.NumberColumn("Trend", format="%.2f", width="small"),
                    },
                    hide_index=True,
                    use_container_width=True,
                )


def main() -> None:
    """Main function for the free agents page."""
    render_home_nav()

    user_input = get_user_input()
    if user_input:
        render_free_agents(user_input)
    else:
        st.info("Please enter your Sleeper username in the sidebar to get started.")


if __name__ == "__main__":
    main()
