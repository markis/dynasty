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


def render_nav() -> None:
    """
    Render the navigation section with clickable cards for each analysis page.

    This function creates a two-column layout with styled navigation cards.
    Each card contains:
    - An icon and title
    - A short description of the page's purpose
    - A button that redirects to the corresponding Streamlit page

    The cards are organized into two columns with dividers between each card.
    A tip box is displayed at the bottom with reminders about sidebar settings.
    """
    # Create clickable navigation cards
    nav_col1, nav_col2 = st.columns(2)

    with nav_col1:
        with st.container():
            st.markdown("### 🏈 Team Analysis")
            st.markdown("Compare team valuations and roster breakdowns")
            if st.button("Go to Team Analysis →", key="nav_team", use_container_width=True):
                st.switch_page("pages/team_analysis.py")

        st.markdown("---")

        with st.container():
            st.markdown("### 🔄 Trade Analyzer")
            st.markdown("Analyze potential trades and assess fairness")
            if st.button("Go to Trade Analyzer →", key="nav_trade", use_container_width=True):
                st.switch_page("pages/trade_analyzer.py")

        st.markdown("---")

        with st.container():
            st.markdown("### 🎯 Lineup Optimizer")
            st.markdown("Optimize your starting lineup with strategic insights")
            if st.button("Go to Lineup Optimizer →", key="nav_lineup", use_container_width=True):
                st.switch_page("pages/lineup_optimizer.py")

        st.markdown("---")

        with st.container():
            st.markdown("### 🏥 IR Stash")
            st.markdown("Discover injured players worth stashing")
            if st.button("Go to IR Stash →", key="nav_ir", use_container_width=True):
                st.switch_page("pages/ir_stash.py")

    with nav_col2:
        with st.container():
            st.markdown("### 🏃 Free Agents")
            st.markdown("Find valuable available players")
            if st.button("Go to Free Agents →", key="nav_fa", use_container_width=True):
                st.switch_page("pages/free_agents.py")

        st.markdown("---")

        with st.container():
            st.markdown("### 📊 Player Rankings")
            st.markdown("Browse complete player rankings with filtering")
            if st.button("Go to Player Rankings →", key="nav_rankings", use_container_width=True):
                st.switch_page("pages/player_rankings.py")

        st.markdown("---")

        with st.container():
            st.markdown("### 📈 League Analytics")
            st.markdown("Analyze league dynamics, competitive balance, and market trends")
            if st.button("Go to League Analytics →", key="nav_analytics", use_container_width=True):
                st.switch_page("pages/league_analytics.py")

        st.markdown("---")

        with st.container():
            st.markdown("### 🔍 Player Search & Compare")
            st.markdown("Advanced player search with side-by-side comparisons")
            if st.button("Go to Player Search →", key="nav_search", use_container_width=True):
                st.switch_page("pages/player_search.py")

        st.markdown("---")

        with st.container():
            st.markdown("### 🤖 LLM Prompt Generator")
            st.markdown("Generate contextual prompts for ChatGPT, Claude, and other AI assistants")
            if st.button("Go to LLM Prompts →", key="nav_llm", use_container_width=True):
                st.switch_page("pages/llm_prompts.py")

    # Settings reminder
    st.info("""
    💡 **Tip**: Use the sidebar to adjust your analysis settings:
    - Change ranking sources (KeepTradeCut, DynastyProcess, etc.)
    - Filter to starters only
    - Include/exclude draft picks
    - Adjust trending timeframe
    """)


def main() -> None:
    """Main function for the home page."""
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
