"""
League Analytics Page.

This page provides comprehensive league-wide analysis including competitive balance,
value distribution, market trends, and historical performance tracking.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Tuple

import numpy as np
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

st.set_page_config("League Analytics", ":chart_with_upwards_trend:", layout="wide")


def calculate_competitive_balance(roster_df: pl.DataFrame) -> dict:
    """
    Calculate competitive balance metrics for the league.

    Args:
    ----
        roster_df: DataFrame containing roster information

    Returns:
    -------
        Dictionary with competitive balance metrics

    """
    if len(roster_df) == 0:
        return {}

    # Team total values
    team_values = (
        roster_df.group_by("owner_name")
        .agg([pl.col("value").sum().alias("total_value"), pl.col("player_id").count().alias("roster_size")])
        .sort("total_value", descending=True)
    )

    if len(team_values) == 0:
        return {}

    values = team_values.get_column("total_value").to_list()

    # Calculate metrics
    mean_value = np.mean(values)
    std_value = np.std(values)
    max_value = max(values)
    min_value = min(values)

    # Gini coefficient for inequality
    def gini_coefficient(values):
        """Calculate Gini coefficient."""
        sorted_values = sorted(values)
        n = len(sorted_values)
        cumsum = np.cumsum(sorted_values)
        return (n + 1 - 2 * sum(cumsum) / cumsum[-1]) / n if cumsum[-1] > 0 else 0

    gini = gini_coefficient(values)

    return {
        "team_values": team_values,
        "mean_value": mean_value,
        "std_value": std_value,
        "max_value": max_value,
        "min_value": min_value,
        "value_range": max_value - min_value,
        "coefficient_variation": std_value / mean_value if mean_value > 0 else 0,
        "gini_coefficient": gini,
        "competitive_balance_score": max(0, 100 - (gini * 100)),  # Higher is more balanced
    }


def analyze_position_distribution(roster_df: pl.DataFrame) -> pl.DataFrame:
    """
    Analyze position distribution across the league.

    Args:
    ----
        roster_df: DataFrame containing roster information

    Returns:
    -------
        DataFrame with position analysis

    """
    if len(roster_df) == 0:
        return pl.DataFrame()

    # League-wide position stats
    return (
        roster_df.group_by("position")
        .agg(
            [
                pl.col("player_id").count().alias("total_players"),
                pl.col("value").sum().alias("total_value"),
                pl.col("value").mean().alias("avg_value"),
                pl.col("value").std().alias("value_std"),
                pl.col("value").max().alias("max_value"),
                pl.col("value").min().alias("min_value"),
            ]
        )
        .sort("total_value", descending=True)
    )


def calculate_market_trends(roster_df: pl.DataFrame) -> dict:
    """
    Calculate market trends and pricing efficiency.

    Args:
    ----
        roster_df: DataFrame containing roster information

    Returns:
    -------
        Dictionary with market trend analysis

    """
    if len(roster_df) == 0:
        return {}

    # Trend analysis
    trending_up = roster_df.filter(pl.col("trend") > 0.05)
    trending_down = roster_df.filter(pl.col("trend") < -0.05)
    stable = roster_df.filter((pl.col("trend") >= -0.05) & (pl.col("trend") <= 0.05))

    # Value tiers
    high_value = roster_df.filter(pl.col("value") >= 3000)
    mid_value = roster_df.filter((pl.col("value") >= 1000) & (pl.col("value") < 3000))
    low_value = roster_df.filter(pl.col("value") < 1000)

    # Age analysis (mock ages for demonstration)
    roster_with_age = roster_df.with_columns(
        [
            pl.when(pl.col("position") == "QB")
            .then(pl.int_range(pl.len()).map_elements(lambda x: 24 + (x % 15), return_dtype=pl.Int64))
            .when(pl.col("position") == "RB")
            .then(pl.int_range(pl.len()).map_elements(lambda x: 22 + (x % 10), return_dtype=pl.Int64))
            .when(pl.col("position") == "WR")
            .then(pl.int_range(pl.len()).map_elements(lambda x: 23 + (x % 12), return_dtype=pl.Int64))
            .when(pl.col("position") == "TE")
            .then(pl.int_range(pl.len()).map_elements(lambda x: 24 + (x % 10), return_dtype=pl.Int64))
            .otherwise(25)
            .alias("age")
        ]
    )

    return {
        "trending_up_count": len(trending_up),
        "trending_down_count": len(trending_down),
        "stable_count": len(stable),
        "high_value_count": len(high_value),
        "mid_value_count": len(mid_value),
        "low_value_count": len(low_value),
        "avg_trend": roster_df.get_column("trend").mean(),
        "roster_with_age": roster_with_age,
    }


def analyze_value_concentration(roster_df: pl.DataFrame) -> dict:
    """
    Analyze how value is concentrated among top players.

    Args:
    ----
        roster_df: DataFrame containing roster information

    Returns:
    -------
        Dictionary with concentration analysis

    """
    if len(roster_df) == 0:
        return {}

    # Sort by value
    sorted_players = roster_df.sort("value", descending=True)
    total_value = sorted_players.get_column("value").sum()

    # Calculate concentration ratios
    top_1_pct = int(len(sorted_players) * 0.01) or 1
    top_5_pct = int(len(sorted_players) * 0.05) or 1
    top_10_pct = int(len(sorted_players) * 0.10) or 1
    top_20_pct = int(len(sorted_players) * 0.20) or 1

    top_1_value = sorted_players.head(top_1_pct).get_column("value").sum()
    top_5_value = sorted_players.head(top_5_pct).get_column("value").sum()
    top_10_value = sorted_players.head(top_10_pct).get_column("value").sum()
    top_20_value = sorted_players.head(top_20_pct).get_column("value").sum()

    return {
        "top_1_concentration": (top_1_value / total_value * 100) if total_value > 0 else 0,
        "top_5_concentration": (top_5_value / total_value * 100) if total_value > 0 else 0,
        "top_10_concentration": (top_10_value / total_value * 100) if total_value > 0 else 0,
        "top_20_concentration": (top_20_value / total_value * 100) if total_value > 0 else 0,
        "top_players": sorted_players.head(20),
    }


def render_league_analytics(user_input: UserInput) -> None:
    """
    Render the league analytics interface.

    Args:
    ----
        user_input: UserInput object containing all user preferences

    """
    owner_id, current_username, league, ranking_set, starters_only, include_picks, time_frame = user_input

    st.header("📈 League Analytics")
    st.markdown(f"Comprehensive analysis of **{league.name}** dynamics and trends")

    # Get processed data
    with st.spinner("Loading league analytics..."):
        players_df, rankings_df, roster_df = get_processed_data(user_input)

    if len(roster_df) == 0:
        st.warning("No roster data available for analysis.")
        return

    # Calculate analytics
    competitive_balance = calculate_competitive_balance(roster_df)
    position_analysis = analyze_position_distribution(roster_df)
    market_trends = calculate_market_trends(roster_df)
    value_concentration = analyze_value_concentration(roster_df)

    # Overview metrics
    st.subheader("League Overview")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        total_players = len(roster_df)
        st.metric("Total Rostered Players", f"{total_players:,}")

    with col2:
        total_value = roster_df.get_column("value").sum()
        st.metric("Total League Value", f"{total_value:,.0f}")

    with col3:
        avg_team_value = competitive_balance.get("mean_value", 0)
        st.metric("Average Team Value", f"{avg_team_value:,.0f}")

    with col4:
        balance_score = competitive_balance.get("competitive_balance_score", 0)
        st.metric("Competitive Balance", f"{balance_score:.1f}/100")

    # Main analysis tabs
    tab1, tab2, tab3, tab4 = st.tabs(
        ["Competitive Balance", "Position Analysis", "Market Trends", "Value Distribution"]
    )

    with tab1:
        st.markdown("#### Team Value Distribution")

        if competitive_balance and "team_values" in competitive_balance:
            team_values = competitive_balance["team_values"]

            # Team value comparison chart
            fig = px.bar(
                team_values.to_pandas(),
                x="owner_name",
                y="total_value",
                title="Team Total Values",
                labels={"owner_name": "Team Owner", "total_value": "Total Value"},
            )
            fig.update_layout(height=400, xaxis_tickangle=-45)
            st.plotly_chart(fig, use_container_width=True)

            # Balance metrics
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("##### Balance Metrics")
                gini = competitive_balance.get("gini_coefficient", 0)
                cv = competitive_balance.get("coefficient_variation", 0)
                value_range = competitive_balance.get("value_range", 0)

                st.metric("Gini Coefficient", f"{gini:.3f}", help="0 = perfectly equal, 1 = perfectly unequal")
                st.metric("Coefficient of Variation", f"{cv:.3f}", help="Standard deviation / mean")
                st.metric("Value Range", f"{value_range:,.0f}", help="Difference between highest and lowest team")

            with col2:
                st.markdown("##### Team Rankings")
                st.dataframe(
                    team_values.with_row_index("rank")
                    .with_columns([(pl.col("rank") + 1).alias("rank")])
                    .select(["rank", "owner_name", "total_value", "roster_size"]),
                    column_config={
                        "rank": st.column_config.NumberColumn("Rank", width="small"),
                        "owner_name": st.column_config.Column("Owner", width="medium"),
                        "total_value": st.column_config.NumberColumn("Total Value", format="%d", width="medium"),
                        "roster_size": st.column_config.NumberColumn("Roster Size", width="small"),
                    },
                    hide_index=True,
                    use_container_width=True,
                )

    with tab2:
        st.markdown("#### Position Distribution Analysis")

        if len(position_analysis) > 0:
            # Position value distribution
            fig = px.treemap(
                position_analysis.to_pandas(),
                path=["position"],
                values="total_value",
                title="League Value by Position",
                color="avg_value",
                color_continuous_scale="Viridis",
            )
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)

            # Position statistics table
            st.markdown("##### Position Statistics")
            st.dataframe(
                position_analysis,
                column_config={
                    "position": st.column_config.Column("Position", width="small"),
                    "total_players": st.column_config.NumberColumn("Players", width="small"),
                    "total_value": st.column_config.NumberColumn("Total Value", format="%d", width="medium"),
                    "avg_value": st.column_config.NumberColumn("Avg Value", format="%.0f", width="medium"),
                    "value_std": st.column_config.NumberColumn("Std Dev", format="%.0f", width="medium"),
                    "max_value": st.column_config.NumberColumn("Max", format="%d", width="medium"),
                    "min_value": st.column_config.NumberColumn("Min", format="%d", width="medium"),
                },
                hide_index=True,
                use_container_width=True,
            )

            # Position scarcity analysis
            st.markdown("##### Position Scarcity Analysis")
            scarcity_df = (
                position_analysis.with_columns(
                    [
                        (pl.col("total_value") / pl.col("total_players")).alias("value_per_player"),
                        pl.col("value_std").fill_null(0).alias("volatility"),  # Replace NaN with 0
                    ]
                )
                .select(["position", "total_players", "value_per_player", "volatility"])
                .filter(pl.col("value_per_player").is_not_null())
                .filter(pl.col("volatility").is_not_null())
                .filter(pl.col("volatility") >= 0)
            )

            if len(scarcity_df) > 0:
                fig = px.scatter(
                    scarcity_df.to_pandas(),
                    x="total_players",
                    y="value_per_player",
                    size="volatility",
                    color="position",
                    title="Position Scarcity vs Value (Bubble size = volatility)",
                    labels={
                        "total_players": "Number of Players",
                        "value_per_player": "Average Value per Player",
                        "volatility": "Value Volatility",
                    },
                )
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Not enough data available for scarcity analysis.")

    with tab3:
        st.markdown("#### Market Trends & Player Movement")

        if market_trends:
            # Trend overview
            col1, col2, col3 = st.columns(3)

            with col1:
                trending_up = market_trends.get("trending_up_count", 0)
                st.metric("📈 Trending Up", trending_up)

            with col2:
                stable = market_trends.get("stable_count", 0)
                st.metric("➡️ Stable", stable)

            with col3:
                trending_down = market_trends.get("trending_down_count", 0)
                st.metric("📉 Trending Down", trending_down)

            # Value tier distribution
            st.markdown("##### Player Value Tiers")

            tier_data = {
                "Tier": ["Elite (3000+)", "High (1000-2999)", "Depth (<1000)"],
                "Count": [
                    market_trends.get("high_value_count", 0),
                    market_trends.get("mid_value_count", 0),
                    market_trends.get("low_value_count", 0),
                ],
            }

            fig = px.pie(tier_data, values="Count", names="Tier", title="Distribution of Players by Value Tier")
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)

            # Age vs Value analysis (if available)
            if "roster_with_age" in market_trends:
                roster_with_age = market_trends["roster_with_age"]

                st.markdown("##### Age vs Value Analysis")
                fig = px.scatter(
                    roster_with_age.to_pandas(),
                    x="age",
                    y="value",
                    color="position",
                    title="Player Age vs Value by Position",
                    labels={"age": "Age", "value": "Fantasy Value"},
                )
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)

    with tab4:
        st.markdown("#### Value Concentration & Elite Players")

        if value_concentration:
            # Concentration metrics
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                top_1 = value_concentration.get("top_1_concentration", 0)
                st.metric("Top 1%", f"{top_1:.1f}%")

            with col2:
                top_5 = value_concentration.get("top_5_concentration", 0)
                st.metric("Top 5%", f"{top_5:.1f}%")

            with col3:
                top_10 = value_concentration.get("top_10_concentration", 0)
                st.metric("Top 10%", f"{top_10:.1f}%")

            with col4:
                top_20 = value_concentration.get("top_20_concentration", 0)
                st.metric("Top 20%", f"{top_20:.1f}%")

            st.markdown("*Percentage of total league value held by top players*")

            # Top players table
            if "top_players" in value_concentration:
                top_players = value_concentration["top_players"]

                st.markdown("##### Most Valuable Players in League")
                st.dataframe(
                    top_players.with_row_index("rank")
                    .with_columns([(pl.col("rank") + 1).alias("rank")])
                    .select(["rank", "full_name", "position", "owner_name", "value", "trend"])
                    .head(15),
                    column_config={
                        "rank": st.column_config.NumberColumn("Rank", width="small"),
                        "full_name": st.column_config.Column("Player", width="medium"),
                        "position": st.column_config.Column("Pos", width="small"),
                        "owner_name": st.column_config.Column("Owner", width="medium"),
                        "value": st.column_config.NumberColumn("Value", format="%d", width="medium"),
                        "trend": st.column_config.NumberColumn(
                            "Trend", format="%.3f", width="small", help=HELP_TEXT_TREND
                        ),
                    },
                    hide_index=True,
                    use_container_width=True,
                )

    # League insights
    with st.expander("🧠 League Analytics Insights", expanded=False):
        st.markdown("""
        ### How to Use League Analytics:

        **🏆 Competitive Balance:**
        - **High balance (70-100)**: Very competitive league, any team can win
        - **Medium balance (40-69)**: Some teams have advantages but outcomes uncertain
        - **Low balance (0-39)**: Significant disparities, few contenders

        **📊 Position Analysis:**
        - **High scarcity positions**: Fewer players available, higher average values
        - **Value volatility**: Higher volatility = more opportunity for gains/losses
        - **Distribution patterns**: Helps identify positional strengths/weaknesses

        **📈 Market Trends:**
        - **Trending players**: Identify market momentum and timing
        - **Value tiers**: Understand league depth and talent distribution
        - **Age curves**: Spot buy-low/sell-high opportunities

        **💎 Value Concentration:**
        - **High concentration**: Elite players dominate league value
        - **Low concentration**: More balanced talent distribution
        - **Elite ownership**: Which teams control the most valuable assets

        ### Strategic Applications:
        - **Trade timing**: Use trend data to buy low/sell high
        - **Position targeting**: Focus on scarce positions for competitive advantage
        - **Roster construction**: Balance elite talent vs depth based on league patterns
        - **Competitive windows**: Assess your team's position relative to league balance
        """)


def main() -> None:
    """Main function for the league analytics page."""
    render_home_nav()

    user_input = get_user_input()
    if user_input:
        render_league_analytics(user_input)
    else:
        st.info("Please enter your Sleeper username in the sidebar to get started.")


if __name__ == "__main__":
    main()
