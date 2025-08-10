"""
Player Rankings Page.

This page provides comprehensive player rankings analysis with filtering
and comparison capabilities.
"""

import plotly.express as px
import polars as pl
import streamlit as st

from pages.shared_utils import (
    HELP_TEXT_TREND,
    POSITIONS,
    UserInput,
    dump_cookies,
    get_processed_data,
    get_user_input,
    render_home_nav,
)

st.set_page_config("Player Rankings", ":bar_chart:", layout="wide")

# Constants
STABLE_TREND_THRESHOLD = 0.1


def _load_rankings_data(user_input: UserInput) -> pl.DataFrame:
    """Load and process player rankings data."""
    # Progress bar for data loading
    prog = st.progress(0)

    # Get processed data
    players_df, rankings_df, roster_df = get_processed_data(user_input)
    _ = prog.progress(100)
    _ = prog.empty()

    # Get all rankings (not just league rosters)
    return rankings_df.filter(pl.col("value").is_not_null()).sort("value", descending=True, nulls_last=True)


def _render_position_filter(all_rankings_df: pl.DataFrame) -> list[str]:
    """Render position filter in sidebar."""
    available_positions = sorted(
        [pos for pos in all_rankings_df.get_column("position").unique().to_list() if pos is not None]
    )
    return st.sidebar.multiselect(
        "Select positions", options=available_positions, default=available_positions, help="Filter by position"
    )


def _apply_position_filter(all_rankings_df: pl.DataFrame, selected_positions: list[str]) -> pl.DataFrame:
    """Apply position filter to rankings data."""
    if selected_positions:
        return all_rankings_df.filter(pl.col("position").is_in(selected_positions))
    return all_rankings_df


def _render_value_range_filter(filtered_rankings: pl.DataFrame) -> pl.DataFrame:
    """Render value range filter and apply it."""
    if len(filtered_rankings) > 0:
        value_col = filtered_rankings.get_column("value")
        min_val = value_col.min()
        max_val = value_col.max()

        if min_val is not None and max_val is not None:
            min_value = int(min_val) if isinstance(min_val, (int, float)) else 0
            max_value = int(max_val) if isinstance(max_val, (int, float)) else 100

            value_range = st.sidebar.slider(
                "Value Range",
                min_value=min_value,
                max_value=max_value,
                value=(min_value, max_value),
                help="Filter by value range",
            )

            return filtered_rankings.filter((pl.col("value") >= value_range[0]) & (pl.col("value") <= value_range[1]))

    return filtered_rankings


def _render_trend_filter(filtered_rankings: pl.DataFrame) -> pl.DataFrame:
    """Render trend filter and apply it."""
    if len(filtered_rankings) > 0:
        trend_col = filtered_rankings.get_column("trend")
        trend_min = trend_col.min()
        trend_max = trend_col.max()

        if trend_min is not None and trend_max is not None:
            trend_filter = st.sidebar.selectbox(
                "Trend Filter",
                options=["All", "Rising (>0)", "Falling (<0)", "Stable (≈0)"],
                help="Filter by trend direction",
            )

            if trend_filter == "Rising (>0)":
                return filtered_rankings.filter(pl.col("trend") > 0)
            if trend_filter == "Falling (<0)":
                return filtered_rankings.filter(pl.col("trend") < 0)
            if trend_filter == "Stable (≈0)":
                return filtered_rankings.filter(pl.col("trend").abs() < STABLE_TREND_THRESHOLD)

    return filtered_rankings


def _render_top_n_filter(filtered_rankings: pl.DataFrame) -> pl.DataFrame:
    """Render top N filter and apply it."""
    top_n = st.sidebar.number_input(
        "Show Top N Players", min_value=10, max_value=500, value=100, step=10, help="Limit results to top N players"
    )
    return filtered_rankings.head(top_n)


def _render_rankings_statistics(all_rankings_df: pl.DataFrame, filtered_rankings: pl.DataFrame) -> None:
    """Render rankings statistics."""
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Players", len(all_rankings_df))
    with col2:
        st.metric("Filtered Results", len(filtered_rankings))
    with col3:
        if len(filtered_rankings) > 0:
            avg_value = filtered_rankings.get_column("value").mean()
            if avg_value is not None:
                st.metric("Average Value", f"{avg_value:.0f}")
    with col4:
        if len(filtered_rankings) > 0:
            # Count players with positive trends
            positive_trends = filtered_rankings.filter(pl.col("trend") > 0)
            st.metric("Rising Players", len(positive_trends))


def _render_value_distribution_chart(filtered_rankings: pl.DataFrame) -> None:
    """Render value distribution chart."""
    if len(filtered_rankings) > 0:
        st.subheader("Value Distribution by Position")

        # Create position distribution chart
        fig = px.box(
            filtered_rankings.to_pandas(),
            x="position",
            y="value",
            title="Player Value Distribution by Position",
            points="outliers",
        )
        fig.update_layout(xaxis_title="Position", yaxis_title="Value")
        st.plotly_chart(fig, use_container_width=True)


def _render_rankings_table(filtered_rankings: pl.DataFrame) -> None:
    """Render the main player rankings table."""
    st.subheader("Player Rankings")

    if len(filtered_rankings) > 0:
        # Add rank column
        ranked_df = filtered_rankings.with_row_index("rank").with_columns((pl.col("rank") + 1).alias("rank"))

        st.dataframe(
            ranked_df,
            column_config={
                "rank": st.column_config.NumberColumn("Rank", width="small"),
                "full_name": st.column_config.Column("Player", width="medium"),
                "position": st.column_config.Column("Position", width="small"),
                "value": st.column_config.NumberColumn("Value", width="small"),
                "trend": st.column_config.NumberColumn("Trend", format="%.2f", width="small", help=HELP_TEXT_TREND),
                "value_history": st.column_config.AreaChartColumn("Value History", width="large"),
                "player_id": None,
                "sleeper_id": None,
                "injury_status": None,
            },
            column_order=("rank", "full_name", "position", "value", "trend", "value_history"),
            hide_index=True,
            use_container_width=True,
        )
    else:
        st.info("No players match your current filters.")


def _render_position_breakdown(filtered_rankings: pl.DataFrame) -> None:
    """Render position rankings breakdown with tabs."""
    if len(filtered_rankings) > 0:
        st.subheader("Position Rankings")

        # Get position data
        position_data = (
            filtered_rankings.group_by("position")
            .agg(
                [
                    pl.col("full_name").head(10).alias("top_players"),
                    pl.col("value").head(10).alias("top_values"),
                    pl.col("full_name").count().alias("total_count"),
                    pl.col("value").mean().alias("avg_value"),
                    pl.col("value").max().alias("max_value"),
                ]
            )
            .sort("max_value", descending=True)
        )

        positions_list = position_data.get_column("position").to_list()

        if positions_list:
            # Create tabs for each position
            tabs = st.tabs(positions_list)

            for i, pos in enumerate(positions_list):
                with tabs[i]:
                    pos_data = position_data.filter(pl.col("position") == pos)

                    # Position statistics
                    total_count = pos_data.get_column("total_count").to_list()[0]
                    avg_value = pos_data.get_column("avg_value").to_list()[0]
                    max_value = pos_data.get_column("max_value").to_list()[0]

                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Total Players", total_count)
                    with col2:
                        st.metric("Average Value", f"{avg_value:.0f}" if avg_value else "N/A")
                    with col3:
                        st.metric("Top Value", f"{max_value:.0f}" if max_value else "N/A")

                    # Top players table
                    st.markdown("#### Top Players")

                    players = pos_data.get_column("top_players").to_list()[0]
                    values = pos_data.get_column("top_values").to_list()[0]

                    if players and values:
                        top_players_df = pl.DataFrame(
                            {"Rank": range(1, len(players) + 1), "Player": players, "Value": values}
                        )

                        st.dataframe(
                            top_players_df,
                            column_config={
                                "Rank": st.column_config.NumberColumn("Rank", width="small"),
                                "Player": st.column_config.Column("Player", width="medium"),
                                "Value": st.column_config.NumberColumn("Value", width="small"),
                            },
                            hide_index=True,
                            use_container_width=True,
                        )


def _render_trend_analysis(filtered_rankings: pl.DataFrame) -> None:
    """Render trend analysis section."""
    with st.expander("Trend Analysis", expanded=False):
        if len(filtered_rankings) > 0:
            st.subheader("Biggest Movers")

            # Rising players
            rising_players = filtered_rankings.filter(pl.col("trend") > 0).sort("trend", descending=True).head(10)

            # Falling players
            falling_players = filtered_rankings.filter(pl.col("trend") < 0).sort("trend").head(10)

            col1, col2 = st.columns(2)

            with col1:
                st.markdown("#### 🚀 Biggest Risers")
                if len(rising_players) > 0:
                    st.dataframe(
                        rising_players.select(["full_name", "position", "value", "trend"]),
                        column_config={
                            "full_name": st.column_config.Column("Player", width="medium"),
                            "position": st.column_config.Column("Pos", width="small"),
                            "value": st.column_config.NumberColumn("Value", width="small"),
                            "trend": st.column_config.NumberColumn("Trend", format="%.2f", width="small"),
                        },
                        hide_index=True,
                        use_container_width=True,
                    )
                else:
                    st.info("No rising players in current filter.")

            with col2:
                st.markdown("#### 📉 Biggest Fallers")
                if len(falling_players) > 0:
                    st.dataframe(
                        falling_players.select(["full_name", "position", "value", "trend"]),
                        column_config={
                            "full_name": st.column_config.Column("Player", width="medium"),
                            "position": st.column_config.Column("Pos", width="small"),
                            "value": st.column_config.NumberColumn("Value", width="small"),
                            "trend": st.column_config.NumberColumn("Trend", format="%.2f", width="small"),
                        },
                        hide_index=True,
                        use_container_width=True,
                    )
                else:
                    st.info("No falling players in current filter.")


def render_player_rankings(user_input: UserInput) -> None:
    """
    Render player rankings analysis.

    Args:
    ----
        user_input: UserInput object containing all user preferences

    """
    owner_id, current_username, league, ranking_set, starters_only, include_picks, time_frame = user_input

    st.header(f"Player Rankings - {ranking_set.value}")

    # Load data
    all_rankings_df = _load_rankings_data(user_input)

    # Sidebar filters
    st.sidebar.subheader("Ranking Filters")

    # Position filter
    selected_positions = _render_position_filter(all_rankings_df)
    filtered_rankings = _apply_position_filter(all_rankings_df, selected_positions)

    # Value range filter
    filtered_rankings = _render_value_range_filter(filtered_rankings)

    # Trend filter
    filtered_rankings = _render_trend_filter(filtered_rankings)

    # Top N filter
    filtered_rankings = _render_top_n_filter(filtered_rankings)

    # Show statistics
    _render_rankings_statistics(all_rankings_df, filtered_rankings)

    # Value distribution chart
    _render_value_distribution_chart(filtered_rankings)

    # Rankings table
    _render_rankings_table(filtered_rankings)

    # Position rankings breakdown
    _render_position_breakdown(filtered_rankings)

    # Trend analysis
    _render_trend_analysis(filtered_rankings)


def main() -> None:
    """Player rankings page."""
    render_home_nav()

    user_input = get_user_input()
    if user_input:
        render_player_rankings(user_input)
    else:
        st.info("Please enter your Sleeper username in the sidebar to get started.")

    dump_cookies()


if __name__ == "__main__":
    main()
