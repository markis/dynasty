"""
Lineup Optimizer Page.

This page provides lineup optimization recommendations including optimal starting lineups,
start/sit advice, and strategic roster management insights.
"""

from collections.abc import Sequence
from typing import Optional

import plotly.express as px
import plotly.graph_objects as go
import polars as pl
import streamlit as st

from dynasty.models import PlayerPosition
from pages.shared_utils import (
    HELP_TEXT_TREND,
    POSITIONS,
    UserInput,
    get_processed_data,
    get_user_input,
    render_home_nav,
)

st.set_page_config("Lineup Optimizer", ":dart:", layout="wide")

# Constants
VALUE_IMPROVEMENT_THRESHOLD = 100
NEGATIVE_VALUE_THRESHOLD = -50
POSITION_DEPTH_THRESHOLD = 5


def parse_roster_positions(roster_positions: Sequence[PlayerPosition]) -> dict[str, int]:
    """Parse roster positions into position requirements."""
    position_counts = {}

    for pos in roster_positions:
        pos_str = str(pos)
        if pos_str in ["QB", "RB", "WR", "TE", "K", "DEF"]:
            position_counts[pos_str] = position_counts.get(pos_str, 0) + 1
        elif pos_str in ["FLEX", "SUPER_FLEX", "WRRB_FLEX", "REC_FLEX"]:
            # These are flex positions that can be filled by multiple position types
            position_counts[pos_str] = position_counts.get(pos_str, 0) + 1
        elif pos_str in ["BN", "BENCH"]:
            # Bench spots
            position_counts["BN"] = position_counts.get("BN", 0) + 1
        elif pos_str in ["IR"]:
            # IR spots
            position_counts["IR"] = position_counts.get("IR", 0) + 1

    return position_counts


def get_optimal_lineup(
    user_roster: pl.DataFrame, roster_positions: Sequence[PlayerPosition]
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """
    Calculate the optimal starting lineup based on player values.

    Args:
    ----
        user_roster: DataFrame of user's players
        roster_positions: List of required roster positions

    Returns:
    -------
        Tuple of (optimal_starters, bench_players)

    """
    if len(user_roster) == 0:
        return pl.DataFrame(), pl.DataFrame()

    # Parse position requirements
    pos_requirements = parse_roster_positions(roster_positions)

    # Filter out injured/unavailable players from consideration for starting lineup
    available_players = user_roster.filter(~pl.col("injury_status").is_in(["IR", "O", "D", "S"])).sort(
        "value", descending=True
    )

    if len(available_players) == 0:
        return pl.DataFrame(), user_roster

    selected_starters = []
    remaining_players = available_players.clone()

    # Fill required positions first (QB, RB, WR, TE, K, DEF)
    for position in ["QB", "RB", "WR", "TE", "K", "DEF"]:
        required_count = pos_requirements.get(position, 0)

        if required_count > 0:
            position_players = remaining_players.filter(pl.col("position") == position).head(required_count)

            if len(position_players) > 0:
                selected_starters.append(position_players)
                # Remove selected players from remaining pool
                selected_ids = position_players.get_column("player_id").to_list()
                remaining_players = remaining_players.filter(~pl.col("player_id").is_in(selected_ids))

    # Fill FLEX positions with best remaining skill position players
    flex_count = pos_requirements.get("FLEX", 0)
    if flex_count > 0:
        flex_eligible = remaining_players.filter(pl.col("position").is_in(["RB", "WR", "TE"])).head(flex_count)
        if len(flex_eligible) > 0:
            selected_starters.append(flex_eligible)
            selected_ids = flex_eligible.get_column("player_id").to_list()
            remaining_players = remaining_players.filter(~pl.col("player_id").is_in(selected_ids))

    # Fill SUPER_FLEX positions (QB, RB, WR, TE eligible)
    super_flex_count = pos_requirements.get("SUPER_FLEX", 0)
    if super_flex_count > 0:
        super_flex_eligible = remaining_players.filter(pl.col("position").is_in(["QB", "RB", "WR", "TE"])).head(
            super_flex_count
        )
        if len(super_flex_eligible) > 0:
            selected_starters.append(super_flex_eligible)
            selected_ids = super_flex_eligible.get_column("player_id").to_list()
            remaining_players = remaining_players.filter(~pl.col("player_id").is_in(selected_ids))

    # Combine all selected starters
    optimal_starters = pl.concat(selected_starters) if selected_starters else pl.DataFrame()

    # Remaining players go to bench
    bench_players = remaining_players

    return optimal_starters, bench_players


def analyze_start_sit_decisions(
    optimal_lineup: pl.DataFrame, current_starters: pl.DataFrame, _bench_players: pl.DataFrame
) -> list[dict]:
    """Analyze start/sit decisions and provide recommendations."""
    recommendations = []

    if len(optimal_lineup) == 0 or len(current_starters) == 0:
        return recommendations

    # Get current starter IDs
    current_starter_ids = set(current_starters.get_column("player_id").to_list())
    optimal_starter_ids = set(optimal_lineup.get_column("player_id").to_list())

    # Find players who should be started but aren't
    should_start = optimal_starter_ids - current_starter_ids
    if should_start:
        for player_id in should_start:
            player_data = optimal_lineup.filter(pl.col("player_id") == player_id)
            if len(player_data) > 0:
                player_info = player_data.to_dicts()[0]
                recommendations.append(
                    {
                        "type": "START",
                        "player": player_info["full_name"],
                        "position": player_info["position"],
                        "value": player_info["value"],
                        "trend": player_info.get("trend", 0),
                        "reason": f"Higher value ({player_info['value']:,}) suggests starting",
                    }
                )

    # Find players who are started but shouldn't be
    should_bench = current_starter_ids - optimal_starter_ids
    if should_bench:
        for player_id in should_bench:
            player_data = current_starters.filter(pl.col("player_id") == player_id)
            if len(player_data) > 0:
                player_info = player_data.to_dicts()[0]
                recommendations.append(
                    {
                        "type": "SIT",
                        "player": player_info["full_name"],
                        "position": player_info["position"],
                        "value": player_info["value"],
                        "trend": player_info.get("trend", 0),
                        "reason": f"Lower value ({player_info['value']:,}) suggests benching",
                    }
                )

    return recommendations


def get_position_depth_analysis(user_roster: pl.DataFrame) -> dict:
    """Analyze roster depth by position."""
    if len(user_roster) == 0:
        return {}

    depth_analysis = {}

    for position in ["QB", "RB", "WR", "TE"]:
        pos_players = user_roster.filter(pl.col("position") == position).sort("value", descending=True)

        if len(pos_players) > 0:
            total_value = pos_players.get_column("value").sum()
            avg_value = pos_players.get_column("value").mean()
            count = len(pos_players)
            top_player = pos_players.head(1).to_dicts()[0] if count > 0 else None

            depth_analysis[position] = {
                "count": count,
                "total_value": total_value,
                "avg_value": avg_value,
                "top_player": top_player,
                "players": pos_players.to_dicts(),
            }
        else:
            depth_analysis[position] = {"count": 0, "total_value": 0, "avg_value": 0, "top_player": None, "players": []}

    return depth_analysis


def _load_optimizer_data(
    user_input: UserInput,
) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    """Load and prepare data for lineup optimizer."""
    owner_id, current_username, league, ranking_set, starters_only, include_picks, time_frame = user_input

    # Get processed data
    with st.spinner("Loading your roster data..."):
        players_df, rankings_df, roster_df = get_processed_data(user_input)

    # Get user's roster
    user_roster = roster_df.filter(pl.col("owner_name") == current_username)

    if len(user_roster) == 0:
        st.error(f"No roster found for user '{current_username}'. Please check your username.")
        return players_df, rankings_df, pl.DataFrame(), pl.DataFrame(), pl.DataFrame()

    # Get current starters and bench
    current_starters = user_roster.filter(pl.col("is_starter"))
    current_bench = user_roster.filter(~pl.col("is_starter"))

    return players_df, rankings_df, user_roster, current_starters, current_bench


def _render_roster_overview(
    user_roster: pl.DataFrame, current_starters: pl.DataFrame, optimal_starters: pl.DataFrame
) -> None:
    """Render the roster overview metrics."""
    st.subheader("Roster Overview")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        total_value = user_roster.get_column("value").sum()
        st.metric("Total Roster Value", f"{total_value:,}")

    with col2:
        starter_value = current_starters.get_column("value").sum() if len(current_starters) > 0 else 0
        st.metric("Current Starters Value", f"{starter_value:,}")

    with col3:
        optimal_value = optimal_starters.get_column("value").sum() if len(optimal_starters) > 0 else 0
        st.metric("Optimal Lineup Value", f"{optimal_value:,}")

    with col4:
        value_improvement = optimal_value - starter_value
        st.metric("Potential Improvement", f"{value_improvement:+,}", delta=f"{value_improvement:+,}")


def _render_current_vs_optimal_tab(current_starters: pl.DataFrame, optimal_starters: pl.DataFrame) -> None:
    """Render the current vs optimal lineup comparison tab."""
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Current Starting Lineup")
        if len(current_starters) > 0:
            st.dataframe(
                current_starters.select(["full_name", "position", "value", "trend"]).sort("value", descending=True),
                column_config={
                    "full_name": st.column_config.Column("Player", width="medium"),
                    "position": st.column_config.Column("Position", width="small"),
                    "value": st.column_config.NumberColumn("Value", width="small"),
                    "trend": st.column_config.NumberColumn("Trend", format="%.2f", width="small", help=HELP_TEXT_TREND),
                },
                hide_index=True,
                use_container_width=True,
            )
        else:
            st.info("No current starters found")

    with col2:
        st.markdown("#### Optimal Starting Lineup")
        if len(optimal_starters) > 0:
            st.dataframe(
                optimal_starters.select(["full_name", "position", "value", "trend"]).sort("value", descending=True),
                column_config={
                    "full_name": st.column_config.Column("Player", width="medium"),
                    "position": st.column_config.Column("Position", width="small"),
                    "value": st.column_config.NumberColumn("Value", width="small"),
                    "trend": st.column_config.NumberColumn("Trend", format="%.2f", width="small", help=HELP_TEXT_TREND),
                },
                hide_index=True,
                use_container_width=True,
            )
        else:
            st.info("Unable to generate optimal lineup")


def _render_start_sit_recommendations_tab(
    optimal_starters: pl.DataFrame,
    current_starters: pl.DataFrame,
    current_bench: pl.DataFrame,
    user_roster: pl.DataFrame,
) -> None:
    """Render the start/sit recommendations tab."""
    st.markdown("#### Start/Sit Recommendations")

    recommendations = analyze_start_sit_decisions(optimal_starters, current_starters, current_bench)

    if recommendations:
        for rec in recommendations:
            if rec["type"] == "START":
                st.success(f"▲ **START {rec['player']}** ({rec['position']}) - {rec['reason']}")
            else:
                st.warning(f"▼ **SIT {rec['player']}** ({rec['position']}) - {rec['reason']}")
    else:
        st.success("✅ Your current lineup appears to be optimal!")

    # Show injured/unavailable players
    injured_players = user_roster.filter(pl.col("injury_status").is_in(["IR", "O", "D", "S"]))
    if len(injured_players) > 0:
        st.subheader("⚠️ Injured/Unavailable Players")
        st.dataframe(
            injured_players.select(["full_name", "position", "injury_status", "value"]),
            column_config={
                "full_name": st.column_config.Column("Player", width="medium"),
                "position": st.column_config.Column("Position", width="small"),
                "injury_status": st.column_config.Column("Status", width="small"),
                "value": st.column_config.NumberColumn("Value", width="small"),
            },
            hide_index=True,
            use_container_width=True,
        )


def _render_depth_analysis_tab(user_roster: pl.DataFrame) -> None:
    """Render the depth analysis tab."""
    st.markdown("#### Positional Depth Analysis")

    depth_analysis = get_position_depth_analysis(user_roster)

    # Create depth chart visualization
    positions = ["QB", "RB", "WR", "TE"]
    pos_counts = [depth_analysis.get(pos, {}).get("count", 0) for pos in positions]
    pos_values = [depth_analysis.get(pos, {}).get("total_value", 0) for pos in positions]

    fig = go.Figure()

    fig.add_trace(go.Bar(name="Player Count", x=positions, y=pos_counts, yaxis="y", marker_color="lightblue"))

    fig.add_trace(go.Bar(name="Total Value", x=positions, y=pos_values, yaxis="y2", marker_color="lightcoral"))

    fig.update_layout(
        title="Roster Depth by Position",
        xaxis_title="Position",
        yaxis={"title": "Player Count", "side": "left"},
        yaxis2={"title": "Total Value", "side": "right", "overlaying": "y"},
        barmode="group",
        height=400,
    )

    st.plotly_chart(fig, use_container_width=True)

    # Detailed depth breakdown
    col1, col2 = st.columns(2)

    for i, position in enumerate(positions):
        col = col1 if i % 2 == 0 else col2

        with col:
            st.markdown(f"##### {position} Depth")
            depth_data = depth_analysis.get(position, {})

            if depth_data.get("count", 0) > 0:
                st.write(f"**Players:** {depth_data['count']}")
                st.write(f"**Total Value:** {depth_data['total_value']:,}")
                st.write(f"**Avg Value:** {depth_data['avg_value']:.0f}")

                if depth_data.get("top_player"):
                    top = depth_data["top_player"]
                    st.write(f"**Top Player:** {top['full_name']} ({top['value']:,})")
            else:
                st.write("No players at this position")

            st.markdown("---")


def _render_strategic_insights(
    user_roster: pl.DataFrame, current_starters: pl.DataFrame, optimal_starters: pl.DataFrame
) -> None:
    """Render the strategic insights section."""
    with st.expander("🧠 Strategic Insights", expanded=False):
        st.markdown("### Lineup Optimization Tips:")

        insights = []

        # Calculate value improvement
        starter_value = current_starters.get_column("value").sum() if len(current_starters) > 0 else 0
        optimal_value = optimal_starters.get_column("value").sum() if len(optimal_starters) > 0 else 0
        value_improvement = optimal_value - starter_value

        # Value-based insights
        if value_improvement > VALUE_IMPROVEMENT_THRESHOLD:
            insights.append(
                f"💡 You could improve your lineup value by {value_improvement:,} points by making optimal start/sit decisions"
            )
        elif value_improvement < NEGATIVE_VALUE_THRESHOLD:
            insights.append(
                "⚠️ Your current lineup may be overvaluing certain players - consider the optimal suggestions"
            )
        else:
            insights.append("✅ Your current lineup is very close to optimal from a value perspective")

        # Depth insights
        depth_analysis = get_position_depth_analysis(user_roster)
        for position in ["QB", "RB", "WR", "TE"]:
            count = depth_analysis.get(position, {}).get("count", 0)
            if count == 0:
                insights.append(f"🚨 No {position}s on roster - major weakness")
            elif count == 1:
                insights.append(f"⚠️ Only 1 {position} on roster - consider adding depth")
            elif count >= POSITION_DEPTH_THRESHOLD:
                insights.append(f"📈 Strong {position} depth ({count} players) - potential trade assets")

        # Trend insights
        rising_players = user_roster.filter(pl.col("trend") > 1.0).sort("trend", descending=True)
        falling_players = user_roster.filter(pl.col("trend") < -1.0).sort("trend")

        if len(rising_players) > 0:
            top_riser = rising_players.head(1).to_dicts()[0]
            insights.append(f"📈 {top_riser['full_name']} is your biggest riser (trend: +{top_riser['trend']:.1f})")

        if len(falling_players) > 0:
            top_faller = falling_players.head(1).to_dicts()[0]
            insights.append(f"📉 {top_faller['full_name']} is declining in value (trend: {top_faller['trend']:.1f})")

        for insight in insights:
            st.markdown(f"- {insight}")


def _render_weekly_checklist() -> None:
    """Render the weekly preparation checklist."""
    with st.expander("📋 Weekly Preparation Checklist", expanded=False):
        st.markdown("""
        ### Before Setting Your Lineup:

        **🏥 Injury Report**
        - [ ] Check latest injury reports for all starters
        - [ ] Verify player availability for game day
        - [ ] Consider backup options for questionable players

        **📊 Matchup Analysis**
        - [ ] Review opponent defensive rankings
        - [ ] Consider weather conditions for outdoor games
        - [ ] Check for potential game script advantages

        **📈 Value Trends**
        - [ ] Review recent performance trends
        - [ ] Consider players with positive momentum
        - [ ] Monitor usage rate changes

        **🔄 Roster Moves**
        - [ ] Check waiver wire for upgrades
        - [ ] Consider trade opportunities
        - [ ] Plan for upcoming bye weeks

        **⚡ Last-Minute Checks**
        - [ ] Confirm no late scratches
        - [ ] Verify game times
        - [ ] Submit lineup before lock
        """)


def render_lineup_optimizer(user_input: UserInput) -> None:
    """
    Render the lineup optimizer interface.

    Args:
    ----
        user_input: UserInput object containing all user preferences

    """
    owner_id, current_username, league, ranking_set, starters_only, include_picks, time_frame = user_input

    st.header("🎯 Lineup Optimizer")
    st.markdown("Optimize your starting lineup and get strategic roster recommendations")

    # Load data
    players_df, rankings_df, user_roster, current_starters, current_bench = _load_optimizer_data(user_input)

    if len(user_roster) == 0:
        return

    # Calculate optimal lineup
    optimal_starters, optimal_bench = get_optimal_lineup(user_roster, league.roster_positions)

    # Render roster overview
    _render_roster_overview(user_roster, current_starters, optimal_starters)

    # Lineup comparison tabs
    st.subheader("Lineup Comparison")
    tab1, tab2, tab3 = st.tabs(["Current vs Optimal", "Start/Sit Recommendations", "Depth Analysis"])

    with tab1:
        _render_current_vs_optimal_tab(current_starters, optimal_starters)

    with tab2:
        _render_start_sit_recommendations_tab(optimal_starters, current_starters, current_bench, user_roster)

    with tab3:
        _render_depth_analysis_tab(user_roster)

    # Strategic insights and checklist
    _render_strategic_insights(user_roster, current_starters, optimal_starters)
    _render_weekly_checklist()


def main() -> None:
    """Run the lineup optimizer page."""
    render_home_nav()

    user_input = get_user_input()
    if user_input:
        render_lineup_optimizer(user_input)
    else:
        st.info("Please enter your Sleeper username in the sidebar to get started.")


if __name__ == "__main__":
    main()
