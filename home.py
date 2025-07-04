"""
Dynasty Rankings Streamlit App - Home Page.

This app provides an interactive interface for analyzing player rankings in dynasty fantasy football leagues.
It allows users to view league information, player rankings, and roster details, including trends and values.
"""

import polars as pl
import streamlit as st

from pages.shared_utils import UserInput, get_processed_data, get_user_input

st.set_page_config("Dynasty Rankings", ":football:", layout="wide")


def render_home(user_input: UserInput) -> None:
    """
    Render the home dashboard with league overview.

    Args:
    ----
        user_input: UserInput object containing all user preferences

    """
    _, current_username, league, ranking_set, starters_only, include_picks, time_frame = user_input

    st.title("🏈 Dynasty Rankings Dashboard")
    st.markdown(f"## Welcome, {current_username}!")

    # League Overview
    st.header(f"League: {league.name}")

    with st.expander("League Details", expanded=True):
        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown(f"""
            **Basic Info:**
            - League ID: `{league.id}`
            - Teams: {league.team_count}
            - Status: {league.status.value}
            """)

        with col2:
            st.markdown(f"""
            **Scoring:**
            - Type: {league.league_type.value}
            - Scoring: {league.scoring_type.value}
            - Bonus TEP: {league.bonus_tep or "None"}
            """)

        with col3:
            st.markdown(f"""
            **Roster:**
            - Positions: {", ".join(league.roster_positions)}
            """)

    # Quick Stats
    st.header("Quick Stats")

    prog = st.progress(0)
    _, rankings_df, roster_df = get_processed_data(user_input)
    _ = prog.progress(100)
    _ = prog.empty()

    # Calculate basic stats
    total_players = len(rankings_df.filter(pl.col("value").is_not_null()))
    total_rostered = len(roster_df.filter(pl.col("owner_name").is_not_null()))
    free_agents = total_players - total_rostered

    # User's team stats
    user_roster = roster_df.filter(pl.col("owner_name") == current_username)
    user_total_value = user_roster.get_column("value").sum() if len(user_roster) > 0 else 0
    user_player_count = len(user_roster)

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Players", f"{total_players:,}")
    with col2:
        st.metric("Free Agents", f"{free_agents:,}")
    with col3:
        st.metric("Your Players", user_player_count)
    with col4:
        st.metric("Your Team Value", f"{user_total_value:,}")

    # Navigation
    st.header("Available Analysis Pages")

    # Update query params to ensure context is preserved
    st.query_params.update(
        {
            "sleeper": current_username,
            "league_id": league.id,
            "rankings_set": ranking_set.value,
            "starters_only": str(starters_only).lower(),
            "include_picks": str(include_picks).lower(),
            "trending_days": str(time_frame.days),
        }
    )

    render_nav()


def _render_nav_card(title: str, description: str, button_text: str, button_key: str, page_path: str) -> None:
    """Render a single navigation card with title, description, and button."""
    with st.container():
        st.markdown(f"### {title}")
        st.markdown(description)
        if st.button(button_text, key=button_key, use_container_width=True):
            st.switch_page(page_path)


def _render_nav_column_1() -> None:
    """Render the first column of navigation cards."""
    _render_nav_card(
        "🏈 Team Analysis",
        "Compare team valuations and roster breakdowns",
        "Go to Team Analysis →",
        "nav_team",
        "pages/team_analysis.py",
    )

    st.markdown("---")

    _render_nav_card(
        "🔄 Trade Analyzer",
        "Analyze potential trades and assess fairness",
        "Go to Trade Analyzer →",
        "nav_trade",
        "pages/trade_analyzer.py",
    )

    st.markdown("---")

    _render_nav_card(
        "🎯 Lineup Optimizer",
        "Optimize your starting lineup with strategic insights",
        "Go to Lineup Optimizer →",
        "nav_lineup",
        "pages/lineup_optimizer.py",
    )

    st.markdown("---")

    _render_nav_card(
        "🏥 IR Stash", "Discover injured players worth stashing", "Go to IR Stash →", "nav_ir", "pages/ir_stash.py"
    )


def _render_nav_column_2() -> None:
    """Render the second column of navigation cards."""
    _render_nav_card(
        "🏃 Free Agents", "Find valuable available players", "Go to Free Agents →", "nav_fa", "pages/free_agents.py"
    )

    st.markdown("---")

    _render_nav_card(
        "📊 Player Rankings",
        "Browse complete player rankings with filtering",
        "Go to Player Rankings →",
        "nav_rankings",
        "pages/player_rankings.py",
    )

    st.markdown("---")

    _render_nav_card(
        "📈 League Analytics",
        "Analyze league dynamics, competitive balance, and market trends",
        "Go to League Analytics →",
        "nav_analytics",
        "pages/league_analytics.py",
    )

    st.markdown("---")

    _render_nav_card(
        "🔍 Player Search & Compare",
        "Advanced player search with side-by-side comparisons",
        "Go to Player Search →",
        "nav_search",
        "pages/player_search.py",
    )

    st.markdown("---")

    _render_nav_card(
        "🤖 LLM Prompt Generator",
        "Generate contextual prompts for ChatGPT, Claude, and other AI assistants",
        "Go to LLM Prompts →",
        "nav_llm",
        "pages/llm_prompts.py",
    )


def _render_settings_tip() -> None:
    """Render the settings reminder tip box."""
    st.info("""
    💡 **Tip**: Use the sidebar to adjust your analysis settings:
    - Change ranking sources (KeepTradeCut, DynastyProcess, etc.)
    - Filter to starters only
    - Include/exclude draft picks
    - Adjust trending timeframe
    """)


def render_nav() -> None:
    """
    Render the navigation section with clickable cards for each analysis page.

    This function creates a two-column layout with styled navigation cards.
    Each card contains an icon, title, description, and navigation button.
    """
    # Create clickable navigation cards
    nav_col1, nav_col2 = st.columns(2)

    with nav_col1:
        _render_nav_column_1()

    with nav_col2:
        _render_nav_column_2()

    # Settings reminder
    _render_settings_tip()


def main() -> None:
    """Run the main home page."""
    user_input = get_user_input()
    if user_input:
        render_home(user_input)
    else:
        st.info("👋 Please enter your Sleeper username in the sidebar to get started.")
        st.markdown("""
        ### Getting Started

        1. Enter your **Sleeper username** in the sidebar
        2. Select your **league** from the dropdown
        3. Choose your **ranking source** and preferences
        4. Navigate to different analysis pages using the sidebar

        ### Features

        - **Team Analysis**: Compare all teams in your league with interactive charts
        - **Trade Analyzer**: Analyze potential trades and assess fairness
        - **Lineup Optimizer**: Optimize your starting lineup with strategic insights
        - **Free Agents**: Find the best available players with advanced filtering
        - **IR Stash**: Discover injured players worth picking up for future value
        - **Player Rankings**: Browse comprehensive player rankings with trend analysis
        - **League Analytics**: Analyze league dynamics, competitive balance, and market trends
        - **Player Search & Compare**: Advanced player search with side-by-side comparisons
        - **LLM Prompt Generator**: Generate contextual prompts for ChatGPT, Claude, and other AI assistants
        """)


if __name__ == "__main__":
    main()
