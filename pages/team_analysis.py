"""
Team Analysis Page.

This page provides comprehensive team analysis including valuations, roster comparisons,
and individual team breakdowns with position-specific details.
"""

from json import dumps

import plotly.express as px
import polars as pl
import streamlit as st

from pages.shared_utils import (
    HELP_TEXT_TREND,
    POSITIONS,
    POSITIONS_WITH_PICK,
    UserInput,
    dump_cookies,
    get_processed_data,
    get_user_input,
    render_home_nav,
)

st.set_page_config("Team Analysis", ":bar_chart:", layout="wide")


def render_team_analysis(user_input: UserInput) -> None:
    """
    Render team analysis dashboard.

    Args:
    ----
        user_input: UserInput object containing all user preferences

    """
    owner_id, current_username, league, ranking_set, starters_only, include_picks, time_frame = user_input

    st.header(f"Team Analysis - {league.name}")

    # Show league info
    with st.expander("League Info", expanded=False):
        st.markdown(f"""
        * Owner: {owner_id}
        * League ID: {league.id}
        * Type: {league.league_type}
        * Scoring: {league.scoring_type}
        * Bonus TEP: {league.bonus_tep or "None"}
        * Teams: {league.team_count}
        * Status: {league.status}
        * Roster Positions: {", ".join(league.roster_positions)}
        """)

    # Progress bar for data loading
    prog = st.progress(0)

    # Get processed data
    players_df, rankings_df, roster_df = get_processed_data(user_input)
    _ = prog.progress(50)

    # Determine positions to show
    positions = POSITIONS_WITH_PICK if include_picks and not starters_only else POSITIONS
    existing_positions = roster_df.get_column("position").unique().to_list()
    positions = [pos for pos in positions if pos in existing_positions]

    # Calculate league valuations
    league_values = (
        roster_df.filter(pl.col("owner_name").is_not_null())
        .group_by("owner_name")
        .agg(pl.col("value").sum().alias("value"), pl.col("trend").mean().alias("trend"))
        .join(
            other=roster_df.filter(pl.col("owner_name").is_not_null())
            .group_by("owner_name", "position")
            .agg(pl.col("value").sum())
            .pivot(index="owner_name", on="position", values="value"),
            on="owner_name",
            how="left",
        )
        .with_columns([pl.col(pos).fill_null(0) for pos in positions])
        .select(["owner_name", "value", "trend", *positions])
        .sort("value", descending=True, nulls_last=True)
    )

    # Create long format for plotting
    league_values_long_df = league_values.select(pl.col(["owner_name", *positions])).unpivot(
        index="owner_name",
        on=positions,
        variable_name="position",
        value_name="value",
    )

    _ = prog.progress(100)
    _ = prog.empty()

    # Team valuations chart
    st.subheader("Team Valuations by Position")
    fig = px.bar(
        league_values_long_df, x="owner_name", y="value", color="position", title="Total Team Value by Position"
    )
    fig.update_layout(xaxis_title="Team Owner", yaxis_title="Total Value")
    st.plotly_chart(fig, use_container_width=True)

    # Team valuations table
    st.subheader("Team Valuations Summary")
    st.dataframe(
        league_values,
        column_config={
            "owner_name": st.column_config.Column("Owner", width="medium"),
            "value": st.column_config.NumberColumn("Total Value", width="small"),
            "trend": st.column_config.NumberColumn("Trend", format="%.2f", width="small", help=HELP_TEXT_TREND),
            **{pos: st.column_config.NumberColumn(pos, width="small") for pos in positions},
        },
        hide_index=True,
        use_container_width=True,
    )

    # Individual team analysis
    st.subheader("Individual Team Analysis")
    owners = sorted((str(name) for name in league_values["owner_name"].unique()), key=lambda x: x.lower())

    for owner in owners:
        with st.expander(f"{owner} Roster", expanded=False):
            owner_roster_df = roster_df.filter(pl.col("owner_name") == owner)

            # Position breakdown in columns
            cols = st.columns(len(positions))
            for pos, col in zip(positions, cols, strict=False):
                with col:
                    st.markdown(f"#### {pos}")
                    pos_players = owner_roster_df.filter(pl.col("position") == pos).select(("full_name", "value"))
                    st.dataframe(pos_players, use_container_width=True, hide_index=True)

            # Detailed roster table
            st.markdown("#### Complete Roster")
            st.dataframe(
                owner_roster_df.select("full_name", "position", "value", "trend", "value_history"),
                column_config={
                    "full_name": st.column_config.Column("Player", width="medium"),
                    "position": st.column_config.Column("Position", width="small"),
                    "value": st.column_config.NumberColumn("Value", width="small"),
                    "trend": st.column_config.NumberColumn("Trend", format="%.2f", width="small", help=HELP_TEXT_TREND),
                    "value_history": st.column_config.AreaChartColumn("Value History", width="large"),
                },
                use_container_width=True,
                hide_index=True,
            )

    # LLM assistance data
    with st.expander("LLM Assistance Data", expanded=False):
        llm_league = {
            "league": league.model_dump(mode="json"),
            "my_team": (
                roster_df.filter(pl.col("owner_name") == current_username).select("full_name").to_series().to_list()
            ),
            "players_by_owner": {
                owner: roster_df.filter(pl.col("owner_name") == owner).select("full_name").to_series().to_list()
                for owner in owners
                if owner != current_username
            },
        }
        st.code(dumps(llm_league, indent=2), language="json")


def main() -> None:
    """Run the team analysis page."""
    render_home_nav()

    user_input = get_user_input()
    if user_input:
        render_team_analysis(user_input)
    else:
        st.info("Please enter your Sleeper username in the sidebar to get started.")

    dump_cookies()


if __name__ == "__main__":
    main()
