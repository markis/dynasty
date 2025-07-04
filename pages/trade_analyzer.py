"""
Trade Analyzer Page.

This page provides comprehensive trade analysis including value calculations,
fairness assessments, and trade recommendations based on player rankings.
"""

import plotly.graph_objects as go
import polars as pl
import streamlit as st

from pages.shared_utils import (
    HELP_TEXT_TREND,
    UserInput,
    get_processed_data,
    get_user_input,
    render_home_nav,
)

st.set_page_config("Trade Analyzer", ":arrows_counterclockwise:", layout="wide")

# Constants
MIN_TEAMS_FOR_TRADE = 2
VALUE_DIFFERENCE_THRESHOLD = 50
EXCELLENT_FAIRNESS_THRESHOLD = 90
GOOD_FAIRNESS_THRESHOLD = 75


def init_trade_session_state() -> None:
    """Initialize trade-specific session state."""
    if "selected_team_a" not in st.session_state:
        st.session_state.selected_team_a = None
    if "selected_team_b" not in st.session_state:
        st.session_state.selected_team_b = None
    if "selected_a_players" not in st.session_state:
        st.session_state.selected_a_players = []
    if "selected_b_players" not in st.session_state:
        st.session_state.selected_b_players = []
    if "analysis_ready" not in st.session_state:
        st.session_state.analysis_ready = False


def get_team_players(roster_df: pl.DataFrame, team_name: str) -> pl.DataFrame:
    """Get all players for a specific team."""
    return (
        roster_df.filter(pl.col("owner_name") == team_name)
        .filter(pl.col("value").is_not_null())
        .sort("value", descending=True)
    )


def calculate_trade_metrics(team_a_players: list, team_b_players: list, roster_df: pl.DataFrame) -> dict:
    """Calculate various trade metrics."""

    def get_player_values(player_names: list) -> tuple[list, int, float]:
        if not player_names:
            return [], 0, 0.0

        players_data = roster_df.filter(pl.col("full_name").is_in(player_names))
        values = players_data.get_column("value").to_list()
        trends = players_data.get_column("trend").to_list()

        total_value = sum(values) if values else 0
        avg_trend = sum(trends) / len(trends) if trends else 0.0

        return values, total_value, avg_trend

    team_a_values, team_a_total, team_a_trend = get_player_values(team_a_players)
    team_b_values, team_b_total, team_b_trend = get_player_values(team_b_players)

    # Calculate fairness score (0-100, where 100 is perfectly fair)
    if team_a_total == 0 and team_b_total == 0:
        fairness_score = 100
    elif min(team_a_total, team_b_total) == 0:
        fairness_score = 0
    else:
        value_ratio = min(team_a_total, team_b_total) / max(team_a_total, team_b_total)
        fairness_score = value_ratio * 100

    # Determine which side "wins"
    value_difference = team_a_total - team_b_total

    return {
        "team_a_total": team_a_total,
        "team_b_total": team_b_total,
        "team_a_trend": team_a_trend,
        "team_b_trend": team_b_trend,
        "value_difference": value_difference,
        "fairness_score": fairness_score,
        "team_a_values": team_a_values,
        "team_b_values": team_b_values,
    }


def suggest_alternatives(
    team_info: tuple[str, str],
    roster_df: pl.DataFrame,
    current_players: tuple[list, list],
    target_difference: int = 50,
) -> list:
    """Suggest alternative trades to balance the current trade."""
    selected_team_a, selected_team_b = team_info
    current_a_players, current_b_players = current_players

    if not current_a_players and not current_b_players:
        return []

    current_metrics = calculate_trade_metrics(current_a_players, current_b_players, roster_df)
    current_diff = abs(current_metrics["value_difference"])

    if current_diff <= target_difference:
        return []  # Trade is already fair

    # Determine which side needs to add value
    team_needing_value = selected_team_a if current_metrics["value_difference"] < 0 else selected_team_b
    team_giving_value = selected_team_b if team_needing_value == selected_team_a else selected_team_a

    # Get available players from both teams
    team_needing_players = get_team_players(roster_df, team_needing_value)
    team_giving_players = get_team_players(roster_df, team_giving_value)

    # Filter out already selected players
    current_selected = current_a_players + current_b_players
    team_needing_players = team_needing_players.filter(~pl.col("full_name").is_in(current_selected))
    team_giving_players = team_giving_players.filter(~pl.col("full_name").is_in(current_selected))

    suggestions = []

    # Option 1: Team needing value adds a player
    for player_row in team_needing_players.to_dicts():
        player_value = player_row.get("value", 0)
        player_name = player_row.get("full_name", "")
        new_diff = abs(current_diff - player_value)
        if new_diff < current_diff and new_diff <= target_difference:
            suggestions.append(
                {
                    "type": f"Add {player_name} to {team_needing_value}",
                    "player": player_name,
                    "value": player_value,
                    "new_difference": new_diff,
                    "action": "add_to_needing",
                }
            )

    # Option 2: Team giving value removes a player (if they have multiple selected)
    current_giving_players = current_a_players if team_giving_value == selected_team_a else current_b_players
    if len(current_giving_players) > 1:
        for player_name in current_giving_players:
            player_data = roster_df.filter(pl.col("full_name") == player_name)
            if len(player_data) > 0:
                player_value = player_data.get_column("value").to_list()[0]
                new_diff = abs(current_diff + player_value)
                if new_diff < current_diff and new_diff <= target_difference:
                    suggestions.append(
                        {
                            "type": f"Remove {player_name} from {team_giving_value}",
                            "player": player_name,
                            "value": player_value,
                            "new_difference": new_diff,
                            "action": "remove_from_giving",
                        }
                    )

    # Sort by how much they improve fairness
    suggestions.sort(key=lambda x: x["new_difference"])

    return suggestions[:5]  # Return top 5 suggestions


def _load_trade_data(user_input: UserInput) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    """Load and cache trade data."""
    if "trade_data" not in st.session_state:
        with st.spinner("Loading league data..."):
            players_df, rankings_df, roster_df = get_processed_data(user_input)
            st.session_state.trade_data = (players_df, rankings_df, roster_df)
    else:
        players_df, rankings_df, roster_df = st.session_state.trade_data
    return players_df, rankings_df, roster_df


def _get_team_owners(roster_df: pl.DataFrame) -> list[str]:
    """Get sorted list of team owners."""
    return sorted(
        [
            str(name)
            for name in roster_df.filter(pl.col("owner_name").is_not_null()).get_column("owner_name").unique().to_list()
        ],
        key=lambda x: x.lower(),
    )


def _render_team_selection(owners: list[str], current_username: str) -> None:
    """Render team selection form."""
    with st.form("team_selection"):
        st.subheader("Select Teams")
        col1, col2 = st.columns(2)

        with col1:
            team_a_index = owners.index(current_username) if current_username in owners else 0
            selected_team_a = st.selectbox(
                "Team A", options=owners, index=team_a_index, help="Select the first team in the trade"
            )

        with col2:
            other_owners = [owner for owner in owners if owner != selected_team_a]
            selected_team_b = st.selectbox("Team B", options=other_owners, help="Select the second team in the trade")

        teams_submitted = st.form_submit_button("Select Teams")

        if teams_submitted or (
            st.session_state.selected_team_a != selected_team_a or st.session_state.selected_team_b != selected_team_b
        ):
            st.session_state.selected_team_a = selected_team_a
            st.session_state.selected_team_b = selected_team_b
            # Reset player selections when teams change
            st.session_state.selected_a_players = []
            st.session_state.selected_b_players = []
            st.session_state.analysis_ready = False
            st.rerun()


def _render_team_player_selection(
    team_name: str, team_players: pl.DataFrame, selected_players: list[str], multiselect_key: str
) -> list[str]:
    """Render player selection for a single team."""
    st.markdown(f"### {team_name} Trading Away")

    if len(team_players) > 0:
        team_options = team_players.select(["full_name", "position", "value"]).to_dicts()
        team_display = [f"{p['full_name']} ({p['position']}) - {p['value']:,}" for p in team_options]
        team_names = [p["full_name"] for p in team_options]

        return st.multiselect(
            "Select players to trade away",
            options=team_names,
            default=selected_players,
            format_func=lambda x: next(
                display for display, name in zip(team_display, team_names, strict=False) if name == x
            ),
            key=multiselect_key,
        )
    st.info("No players available for this team")
    return []


def _render_player_selection(roster_df: pl.DataFrame) -> None:
    """Render player selection form."""
    # Get players for each team
    team_a_players = get_team_players(roster_df, st.session_state.selected_team_a)
    team_b_players = get_team_players(roster_df, st.session_state.selected_team_b)

    # Player selection form
    with st.form("player_selection"):
        st.subheader("Build Trade")
        col1, col2 = st.columns(2)

        with col1:
            selected_a_players = _render_team_player_selection(
                st.session_state.selected_team_a,
                team_a_players,
                st.session_state.selected_a_players,
                "team_a_multiselect",
            )

        with col2:
            selected_b_players = _render_team_player_selection(
                st.session_state.selected_team_b,
                team_b_players,
                st.session_state.selected_b_players,
                "team_b_multiselect",
            )

        analyze_submitted = st.form_submit_button("Analyze Trade", type="primary")

        if analyze_submitted:
            st.session_state.selected_a_players = selected_a_players
            st.session_state.selected_b_players = selected_b_players
            st.session_state.analysis_ready = True
            st.rerun()


def _render_team_trade_summary(team_name: str, selected_players: list[str], roster_df: pl.DataFrame) -> None:
    """Render trade summary for a single team."""
    if selected_players:
        st.markdown(f"**{team_name} trading:**")
        for player in selected_players:
            player_data = roster_df.filter(pl.col("full_name") == player).select(["position", "value"])
            if len(player_data) > 0:
                pos = player_data.get_column("position").to_list()[0]
                val = player_data.get_column("value").to_list()[0]
                st.write(f"• {player} ({pos}) - {val:,}")
    else:
        st.markdown(f"**{team_name}:** No players selected")


def _render_current_trade_summary(roster_df: pl.DataFrame) -> None:
    """Render current trade summary."""
    st.subheader("Current Trade")
    col1, col2 = st.columns(2)

    with col1:
        _render_team_trade_summary(st.session_state.selected_team_a, st.session_state.selected_a_players, roster_df)

    with col2:
        _render_team_trade_summary(st.session_state.selected_team_b, st.session_state.selected_b_players, roster_df)


def _render_trade_metrics(metrics: dict) -> None:
    """Render trade metrics summary."""
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            f"{st.session_state.selected_team_a} Gets",
            f"{metrics['team_b_total']:,} pts",
            delta=f"{metrics['team_b_trend']:+.2f} trend" if metrics["team_b_trend"] != 0 else None,
        )

    with col2:
        st.metric(
            f"{st.session_state.selected_team_b} Gets",
            f"{metrics['team_a_total']:,} pts",
            delta=f"{metrics['team_a_trend']:+.2f} trend" if metrics["team_a_trend"] != 0 else None,
        )

    with col3:
        difference = abs(metrics["value_difference"])
        winner = (
            st.session_state.selected_team_a if metrics["value_difference"] > 0 else st.session_state.selected_team_b
        )
        st.metric(
            "Value Difference",
            f"{difference:,} pts",
            delta=f"{winner} wins" if difference > VALUE_DIFFERENCE_THRESHOLD else "Fair trade",
        )

    with col4:
        st.metric(
            "Fairness Score",
            f"{metrics['fairness_score']:.0f}/100",
            delta="Excellent"
            if metrics["fairness_score"] >= EXCELLENT_FAIRNESS_THRESHOLD
            else "Good"
            if metrics["fairness_score"] >= GOOD_FAIRNESS_THRESHOLD
            else "Needs work",
        )


def _render_trade_chart(metrics: dict) -> None:
    """Render trade comparison chart."""
    if metrics["team_a_total"] > 0 or metrics["team_b_total"] > 0:
        # Create trade comparison chart
        fig = go.Figure()

        fig.add_trace(
            go.Bar(
                name=f"{st.session_state.selected_team_a} Receives",
                x=[st.session_state.selected_team_a],
                y=[metrics["team_b_total"]],
                marker_color="lightblue",
            )
        )

        fig.add_trace(
            go.Bar(
                name=f"{st.session_state.selected_team_b} Receives",
                x=[st.session_state.selected_team_b],
                y=[metrics["team_a_total"]],
                marker_color="lightcoral",
            )
        )

        fig.update_layout(title="Trade Value Comparison", yaxis_title="Total Value", barmode="group", height=400)

        st.plotly_chart(fig, use_container_width=True)


def _render_team_breakdown(team_name: str, selected_players: list[str], roster_df: pl.DataFrame) -> None:
    """Render detailed breakdown for a single team."""
    if selected_players:
        st.markdown(f"#### {team_name} Trading Away:")
        trade_away = roster_df.filter(pl.col("full_name").is_in(selected_players))
        st.dataframe(
            trade_away.select(["full_name", "position", "value", "trend"]),
            column_config={
                "full_name": st.column_config.Column("Player", width="medium"),
                "position": st.column_config.Column("Position", width="small"),
                "value": st.column_config.NumberColumn("Value", width="small"),
                "trend": st.column_config.NumberColumn("Trend", format="%.2f", width="small", help=HELP_TEXT_TREND),
            },
            hide_index=True,
            use_container_width=True,
        )


def _render_trade_breakdown(roster_df: pl.DataFrame) -> None:
    """Render detailed trade breakdown."""
    col1, col2 = st.columns(2)

    with col1:
        _render_team_breakdown(st.session_state.selected_team_a, st.session_state.selected_a_players, roster_df)

    with col2:
        _render_team_breakdown(st.session_state.selected_team_b, st.session_state.selected_b_players, roster_df)


def _render_trade_recommendations(metrics: dict, roster_df: pl.DataFrame) -> None:
    """Render trade recommendations."""
    if abs(metrics["value_difference"]) > VALUE_DIFFERENCE_THRESHOLD:
        st.subheader("💡 Trade Suggestions")

        suggestions = suggest_alternatives(
            (st.session_state.selected_team_a, st.session_state.selected_team_b),
            roster_df,
            (st.session_state.selected_a_players, st.session_state.selected_b_players),
        )

        if suggestions:
            st.markdown("To make this trade more fair, consider:")

            for i, suggestion in enumerate(suggestions):
                with st.expander(
                    f"Option {i + 1}: {suggestion['type']} (Improves fairness by {abs(metrics['value_difference']) - suggestion['new_difference']:.0f} points)"
                ):
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.markdown(f"**Player:** {suggestion['player']}")
                    with col2:
                        st.markdown(f"**Value:** {suggestion['value']:,}")
                    with col3:
                        st.markdown(f"**New Difference:** {suggestion['new_difference']:.0f}")
        else:
            st.info(
                "No simple adjustments found to balance this trade. Consider larger changes to the player selection."
            )

    elif metrics["fairness_score"] >= GOOD_FAIRNESS_THRESHOLD:
        st.success("✅ This looks like a fair trade! Both teams receive similar value.")


def _render_trade_tips() -> None:
    """Render trade analysis tips."""
    with st.expander("💡 Trade Analysis Tips", expanded=False):
        st.markdown("""
        ### How to Use the Trade Analyzer:

        **🎯 Fairness Guidelines:**
        - **90-100**: Excellent trade, very fair for both sides
        - **75-89**: Good trade, reasonable for both teams
        - **60-74**: Acceptable trade, slight advantage to one side
        - **Below 60**: Unbalanced trade, needs adjustment

        **📊 What to Consider:**
        - **Total Value**: Overall fantasy points value exchange
        - **Trend Analysis**: Are players rising or falling in value?
        - **Positional Needs**: Does the trade address roster weaknesses?
        - **Age & Longevity**: Dynasty value beyond current season
        - **Injury Risk**: Consider player health and durability

        **🔄 Trade Strategy:**
        - Target teams with complementary needs
        - Consider packaging multiple players for a star
        - Factor in upcoming draft picks if included
        - Think long-term for dynasty leagues
        - Don't just focus on immediate value
        """)


def render_trade_analyzer(user_input: UserInput) -> None:
    """
    Render the trade analyzer interface.

    Args:
    ----
        user_input: UserInput object containing all user preferences

    """
    owner_id, current_username, league, ranking_set, starters_only, include_picks, time_frame = user_input

    # Initialize trade-specific session state
    init_trade_session_state()

    st.header("🔄 Trade Analyzer")
    st.markdown("Analyze potential trades between teams in your league")

    # Load data
    players_df, rankings_df, roster_df = _load_trade_data(user_input)

    # Get team owners
    owners = _get_team_owners(roster_df)

    if len(owners) < MIN_TEAMS_FOR_TRADE:
        st.error("Need at least 2 teams to analyze trades")
        return

    # Team selection
    _render_team_selection(owners, current_username)

    # Only show player selection if teams are selected
    if st.session_state.selected_team_a and st.session_state.selected_team_b:
        # Player selection
        _render_player_selection(roster_df)

        # Show current selections
        if st.session_state.selected_a_players or st.session_state.selected_b_players:
            _render_current_trade_summary(roster_df)

        # Trade Analysis (only show if analysis is ready)
        if st.session_state.analysis_ready and (
            st.session_state.selected_a_players or st.session_state.selected_b_players
        ):
            st.subheader("Trade Analysis")

            metrics = calculate_trade_metrics(
                st.session_state.selected_a_players, st.session_state.selected_b_players, roster_df
            )

            # Main trade summary
            _render_trade_metrics(metrics)

            # Visual trade analysis
            _render_trade_chart(metrics)

            # Detailed breakdown
            _render_trade_breakdown(roster_df)

            # Trade recommendations
            _render_trade_recommendations(metrics, roster_df)

        elif st.session_state.selected_team_a and st.session_state.selected_team_b:
            st.info("👆 Select players from both teams and click 'Analyze Trade' to see the analysis")

    # Trade tips
    _render_trade_tips()


def main() -> None:
    """Run the trade analyzer page."""
    render_home_nav()

    user_input = get_user_input()
    if user_input:
        render_trade_analyzer(user_input)
    else:
        st.info("Please enter your Sleeper username in the sidebar to get started.")


if __name__ == "__main__":
    main()
