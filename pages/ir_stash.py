"""
IR Stash Page.

This page provides analysis of injured players that might be valuable
stash candidates for future seasons.
"""

import polars as pl
import streamlit as st

from pages.shared_utils import (
    HELP_TEXT_TREND,
    IR_POSITIONS,
    POSITIONS,
    get_processed_data,
    get_rosters_df,
    get_user_input,
    render_home_nav,
)

st.set_page_config("IR Stash", ":hospital:", layout="wide")


def render_ir_stash(user_input) -> None:
    """
    Render IR stash analysis.

    Args:
    ----
        user_input: UserInput object containing all user preferences

    """
    owner_id, current_username, league, ranking_set, starters_only, include_picks, time_frame = user_input

    st.header(f"IR Stash Candidates - {league.name}")

    st.info("""
    **IR Stash Strategy**: These are injured players who are currently unowned but may provide
    significant value when they return from injury. Perfect for stashing on IR spots or picking
    up before others notice their potential.
    """)

    # Progress bar for data loading
    prog = st.progress(0)

    # Get processed data
    players_df, rankings_df, roster_df = get_processed_data(user_input)
    _ = prog.progress(80)

    # Get IR stash candidates
    from dynasty.models import StatusType

    include_drafted = league.status == StatusType.Drafting

    ir_fa_rankings_df = (
        get_rosters_df(
            league.id,
            ranking_set,
            rankings_df,
            include_picks=include_picks,
            include_drafted=include_drafted,
        )
        .filter(
            pl.col("owner_name").is_null(),
            pl.col("value").is_not_null(),
            pl.col("position").is_in(list(POSITIONS)),
            pl.col("injury_status").is_in(list(IR_POSITIONS)),
        )
        .unique(subset=["player_id"], keep="first")  # Remove duplicates
        .sort("value", descending=True, nulls_last=True)
    )

    _ = prog.progress(100)
    _ = prog.empty()

    # Show injury status legend
    st.subheader("Injury Status Legend")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("**IR** - Injured Reserve")
        st.markdown("**O** - Out")
    with col2:
        st.markdown("**PUP** - Physically Unable to Perform")
        st.markdown("**NFI** - Non-Football Injury")
    with col3:
        st.markdown("**NA** - Not Available")
        st.markdown("**S** - Suspended")

    # Position and injury status filters
    st.subheader("Filters")
    col1, col2 = st.columns(2)

    with col1:
        available_positions = sorted(ir_fa_rankings_df.get_column("position").unique().to_list())
        selected_positions = st.multiselect(
            "Select positions to show",
            options=available_positions,
            default=available_positions,
            help="Filter by position",
        )

    with col2:
        available_injury_statuses = sorted(ir_fa_rankings_df.get_column("injury_status").unique().to_list())
        selected_injury_statuses = st.multiselect(
            "Select injury statuses",
            options=available_injury_statuses,
            default=available_injury_statuses,
            help="Filter by injury status",
        )

    # Apply filters
    filtered_ir_df = ir_fa_rankings_df
    if selected_positions:
        filtered_ir_df = filtered_ir_df.filter(pl.col("position").is_in(selected_positions))
    if selected_injury_statuses:
        filtered_ir_df = filtered_ir_df.filter(pl.col("injury_status").is_in(selected_injury_statuses))

    # Show statistics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total IR Candidates", len(ir_fa_rankings_df))
    with col2:
        st.metric("Filtered Results", len(filtered_ir_df))
    with col3:
        if len(filtered_ir_df) > 0:
            avg_value = filtered_ir_df.get_column("value").mean()
            if avg_value is not None:
                st.metric("Average Value", f"{avg_value:.0f}")
    with col4:
        if len(filtered_ir_df) > 0:
            max_value = filtered_ir_df.get_column("value").max()
            if max_value is not None:
                st.metric("Highest Value", f"{max_value}")

    # IR stash candidates table
    st.subheader("IR Stash Candidates")

    if len(filtered_ir_df) > 0:
        st.dataframe(
            filtered_ir_df,
            column_config={
                "full_name": st.column_config.Column("Player", width="medium"),
                "position": st.column_config.Column("Position", width="small"),
                "value": st.column_config.NumberColumn("Value", width="small"),
                "injury_status": st.column_config.Column("Injury Status", width="small"),
                "trend": st.column_config.NumberColumn("Trend", format="%.2f", width="small", help=HELP_TEXT_TREND),
                "value_history": st.column_config.AreaChartColumn("Value History", width="large"),
                "owner_name": None,
                "sleeper_id": None,
                "is_starter": None,
                "player_id": None,
            },
            column_order=("full_name", "position", "value", "injury_status", "trend", "value_history"),
            hide_index=True,
            use_container_width=True,
        )
    else:
        st.info("No IR stash candidates match your current filters.")

    # High-value stashes by position
    if len(filtered_ir_df) > 0:
        st.subheader("Top IR Stashes by Position")

        # Get top 3 players per position
        top_by_position = (
            filtered_ir_df.group_by("position")
            .agg(pl.col("full_name", "value", "injury_status").head(3))
            .sort("position")
        )

        # Create columns for each position
        positions_with_data = top_by_position.get_column("position").to_list()
        if positions_with_data:
            cols = st.columns(len(positions_with_data))

            for i, pos in enumerate(positions_with_data):
                with cols[i]:
                    st.markdown(f"### {pos}")
                    pos_data = top_by_position.filter(pl.col("position") == pos)

                    # Extract the lists for this position
                    names = pos_data.get_column("full_name").to_list()[0]
                    values = pos_data.get_column("value").to_list()[0]
                    injuries = pos_data.get_column("injury_status").to_list()[0]

                    # Create a small dataframe for this position
                    pos_df = pl.DataFrame({"Player": names, "Value": values, "Status": injuries})

                    st.dataframe(
                        pos_df,
                        column_config={
                            "Player": st.column_config.Column("Player", width="medium"),
                            "Value": st.column_config.NumberColumn("Value", width="small"),
                            "Status": st.column_config.Column("Status", width="small"),
                        },
                        hide_index=True,
                        use_container_width=True,
                    )

    # Strategy tips
    with st.expander("IR Stash Strategy Tips", expanded=False):
        st.markdown("""
        ### Successful IR Stashing Strategy:

        1. **Target High-Value Players**: Focus on players with significant fantasy value (>50 points)
        2. **Monitor Injury Timelines**: Research expected return dates and recovery progress
        3. **Position Scarcity**: Prioritize positions that are harder to find on waivers (RB, high-end WR)
        4. **Age Considerations**: Younger players may have better long-term recovery potential
        5. **Team Situation**: Consider if the player will return to a favorable role
        6. **League Format**: More valuable in deeper leagues and dynasty formats

        ### Red Flags:
        - Players with recurring injuries
        - Older players with major injuries
        - Players whose teams have moved on with replacements
        - Career-threatening injuries
        """)


def main() -> None:
    """Main function for the IR stash page."""
    render_home_nav()

    user_input = get_user_input()
    if user_input:
        render_ir_stash(user_input)
    else:
        st.info("Please enter your Sleeper username in the sidebar to get started.")


if __name__ == "__main__":
    main()
