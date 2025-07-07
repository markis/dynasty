"""
LLM Prompt Generator Page.

This page generates contextual fantasy football prompts that can be used with
external LLMs like ChatGPT, Perplexity, Claude, etc. to get AI-powered fantasy advice
with your specific league context and data.
"""

from typing import Final

import polars as pl
import streamlit as st

from pages.shared_utils import (
    POSITIONS,
    UserInput,
    dump_cookies,
    get_processed_data,
    get_user_input,
    render_home_nav,
)

st.set_page_config("LLM Prompts", ":robot_face:", layout="wide")

TREND_UP_THRESHOLD: Final = 0.05
TREND_DOWN_THRESHOLD: Final = -0.05


def get_league_context(user_input: UserInput) -> str:
    """Generate league context string for prompts."""
    _, current_username, league, ranking_set, _, _, _ = user_input

    context = f"""
LEAGUE CONTEXT:
- League Name: {league.name}
- League Type: {league.league_type.value}
- Scoring: {league.scoring_type.value}
- Teams: {league.team_count}
- Roster Positions: {", ".join(league.roster_positions)}
- My Team: {current_username}
- Data Source: {ranking_set.value} rankings
"""
    return context.strip()


def _safe_format_value(value: float | None) -> int:
    """Safely format a value, handling None cases."""
    if value is None:
        return 0
    try:
        return int(value)
    except (ValueError, TypeError):
        return 0


def _safe_format_trend(trend: float | None) -> float:
    """Safely format a trend value, handling None cases."""
    if trend is None:
        return 0.0
    try:
        return float(trend)
    except (ValueError, TypeError):
        return 0.0


def get_player_context(roster_df: pl.DataFrame, player_names: list[str]) -> str:
    """Generate player context for specific players."""
    if not player_names:
        return ""

    player_data = roster_df.filter(pl.col("full_name").is_in(player_names))

    if player_data.is_empty():
        return ""

    # Create trend arrows using vectorized operations if trend column exists
    if "trend" in player_data.columns:
        trend_arrows = (
            pl.when(pl.col("trend") > TREND_UP_THRESHOLD)
            .then(pl.lit("📈"))
            .when(pl.col("trend") < TREND_DOWN_THRESHOLD)
            .then(pl.lit("📉"))
            .otherwise(pl.lit("➡️"))
            .alias("trend_arrow")
        )
    else:
        trend_arrows = pl.lit("➡️").alias("trend_arrow")

    # Create owner status using vectorized operations if owner_name column exists
    if "owner_name" in player_data.columns:
        owner_status = (
            pl.when(pl.col("owner_name").is_not_null())
            .then(pl.format("Owned by {}", pl.col("owner_name")))
            .otherwise(pl.lit("AVAILABLE FREE AGENT"))
            .alias("owner_status")
        )
    else:
        owner_status = pl.lit("AVAILABLE FREE AGENT").alias("owner_status")

    # Add the computed columns
    player_data = player_data.with_columns([trend_arrows, owner_status])

    # Format the context string using the compute once approach
    context = "\nPLAYER DATA:\n"
    context += "\n".join(
        [
            f"- {row['full_name']} ({row.get('position', 'N/A')}): Value {_safe_format_value(row.get('value')):,}, Trend {_safe_format_trend(row.get('trend')):.3f} {row['trend_arrow']}, {row['owner_status']}"
            for row in player_data.to_dicts()
        ]
    )

    return context


def get_roster_context(roster_df: pl.DataFrame, username: str, *, include_all_teams: bool = False) -> str:
    """Generate roster context for analysis."""
    context_parts = []

    if include_all_teams:
        # Get all team rosters
        teams_df = roster_df.filter(pl.col("owner_name").is_not_null())
        teams = teams_df.get_column("owner_name").unique().to_list()
        context_parts.append("\nALL TEAM ROSTERS:\n")

        for team in sorted(teams):
            team_roster = roster_df.filter(pl.col("owner_name") == team).sort("value", descending=True)
            total_value = team_roster.get_column("value").sum()
            context_parts.append(f"\n{team} (Total Value: {total_value:,}):\n")

            # Process top 15 players per team
            top_players = team_roster.head(15)

            # Add starter status column if is_starter column exists
            if "is_starter" in top_players.columns:
                starter_status = (
                    pl.when(pl.col("is_starter")).then(pl.lit(" [STARTER]")).otherwise(pl.lit("")).alias("starter_text")
                )
                top_players = top_players.with_columns(starter_status)
            else:
                top_players = top_players.with_columns(pl.lit("").alias("starter_text"))

            team_entries = [
                f"  - {row['full_name']} ({row['position']}): {_safe_format_value(row.get('value')):,}{row['starter_text']}"
                for row in top_players.to_dicts()
            ]
            context_parts.append("\n".join(team_entries))
    else:
        # Just user's roster
        user_roster = roster_df.filter(pl.col("owner_name") == username).sort("value", descending=True)
        if not user_roster.is_empty():
            total_value = user_roster.get_column("value").sum()
            context_parts.append(f"\nMY ROSTER ({username}) - Total Value: {total_value:,}:\n")

            # Create status column using vectorized operations
            if "is_starter" in user_roster.columns:
                user_roster = user_roster.with_columns(
                    pl.when(pl.col("is_starter")).then(pl.lit("STARTER")).otherwise(pl.lit("BENCH")).alias("status")
                )
            else:
                user_roster = user_roster.with_columns(pl.lit("BENCH").alias("status"))

            roster_entries = [
                f"- {row['full_name']} ({row['position']}): {_safe_format_value(row.get('value')):,}, {row['status']}"
                for row in user_roster.to_dicts()
            ]
            context_parts.append("\n".join(roster_entries))

    return "".join(context_parts)


def get_league_ownership_summary(roster_df: pl.DataFrame) -> str:
    """Generate a summary of league ownership by team."""
    # Get only rows with owners and unique team names
    teams_df = roster_df.filter(pl.col("owner_name").is_not_null())
    if teams_df.is_empty():
        return "\nLEAGUE OWNERSHIP SUMMARY:\nNo teams found.\n\n"

    teams = teams_df.get_column("owner_name").unique().to_list()

    # Process all teams at once using group_by operations
    team_summary = (
        roster_df.filter(pl.col("owner_name").is_not_null() & pl.col("value").is_not_null())
        .group_by("owner_name")
        .agg(
            [
                pl.len().alias("player_count"),
                pl.col("value").sum().alias("total_value"),
                pl.struct(pl.col("full_name"), pl.col("value"))
                .sort_by("value", descending=True)
                .first()
                .alias("top_player"),
            ]
        )
    )

    # Generate the summary text
    summary_parts = ["\nLEAGUE OWNERSHIP SUMMARY:\n"]

    for team in sorted(teams):
        team_data = team_summary.filter(pl.col("owner_name") == team)

        if not team_data.is_empty():
            row = team_data.row(0, named=True)
            player_count = row["player_count"]
            total_value = row["total_value"] if row["total_value"] is not None else 0

            if player_count > 0 and row["top_player"] is not None:
                top_name = row["top_player"]["full_name"]
                top_value = _safe_format_value(row["top_player"]["value"])
                summary_parts.append(
                    f"- {team}: {player_count} players, {total_value:,} total value (Top: {top_name} {top_value:,})\n"
                )
            else:
                summary_parts.append(f"- {team}: No players with values\n")
        else:
            summary_parts.append(f"- {team}: No players with values\n")

    summary_parts.append("\n")
    return "".join(summary_parts)


def get_free_agents_context(roster_df: pl.DataFrame, position: str | None = None, top_n: int = 20) -> str:
    """Generate context for available free agents."""
    # Get rostered players
    rostered_players = roster_df.filter(pl.col("owner_name").is_not_null())
    rostered_player_ids = set(rostered_players.get_column("player_id").to_list())

    # Get free agents
    free_agents = roster_df.filter(~pl.col("player_id").is_in(list(rostered_player_ids)), pl.col("value").is_not_null())

    if position:
        free_agents = free_agents.filter(pl.col("position") == position)

    free_agents = free_agents.sort("value", descending=True).head(top_n)

    context = f"\nTOP AVAILABLE FREE AGENTS{f' ({position})' if position else ''}:\n"
    for row in free_agents.iter_rows(named=True):
        value = row.get("value") or 0
        trend_arrow = (
            "📈" if row["trend"] > TREND_UP_THRESHOLD else "📉" if row["trend"] < TREND_DOWN_THRESHOLD else "➡️"
        )
        injury_note = (
            f" ({row['injury_status']})"
            if row.get("injury_status") and row["injury_status"] not in [None, "Healthy", ""]
            else ""
        )
        context += (
            f"- {row['full_name']} ({row['position']}): Value {value:,}, Trend {trend_arrow}, AVAILABLE{injury_note}\n"
        )

    return context


def generate_trade_analysis_prompt(
    user_input: UserInput, roster_df: pl.DataFrame, my_players: list[str], their_players: list[str], their_team: str
) -> str:
    """Generate a trade analysis prompt."""
    base_prompt = """I need help analyzing a potential fantasy football trade. Please provide a detailed analysis covering value fairness, positional needs, trends, and strategic implications.

TRADE DETAILS:
"""

    base_prompt += f"I'm trading away: {', '.join(my_players) if my_players else 'None selected'}\n"
    base_prompt += f"I'm receiving: {', '.join(their_players) if their_players else 'None selected'}\n"
    base_prompt += f"Trading partner: {their_team}\n"

    # Add contexts
    base_prompt += get_league_context(user_input)
    base_prompt += get_player_context(roster_df, my_players + their_players)
    base_prompt += get_roster_context(roster_df, user_input.owner_name)

    # Add trading partner's roster context for better analysis
    if their_team:
        base_prompt += f"\nTRADING PARTNER'S ROSTER ({their_team}):\n"
        partner_roster_context = get_roster_context(roster_df, their_team)
        # Remove the header from partner context since we're adding our own
        partner_roster_clean = partner_roster_context.replace(f"\nMY ROSTER ({their_team}) - Total Value:", "\nTotal Value:")
        base_prompt += partner_roster_clean

    base_prompt += get_league_ownership_summary(roster_df)
    base_prompt += get_free_agents_context(roster_df, None, 15)  # Top 15 free agents for context

    base_prompt += """

Please analyze this trade considering both teams' rosters:
1. Value fairness - who wins/loses on paper?
2. Positional fit - does this address both teams' roster needs and weaknesses?
3. Team composition impact - how does this trade affect each team's depth and balance?
4. Trend analysis - who has better trajectory and why?
5. Risk assessment - injury, age, situation concerns for both sides?
6. Strategic timing - is this good timing for both teams' competitive windows?
7. Alternative players - are there better fits available from either roster?
8. Counter-offer suggestions - what adjustments would make this more balanced?
9. Overall recommendation: Accept, Decline, or Counter? Explain reasoning.
"""

    return base_prompt


def generate_waiver_pickup_prompt(
    user_input: UserInput, roster_df: pl.DataFrame, position: str, drop_player: str | None = None
) -> str:
    """Generate a waiver wire/free agent pickup prompt."""
    base_prompt = f"""I need help with waiver wire pickups in my fantasy football league. Please analyze the best available {position if position != "All" else ""} players and recommend pickup priorities.

"""

    # Add contexts
    base_prompt += get_league_context(user_input)
    base_prompt += get_roster_context(roster_df, user_input.owner_name)

    # Add free agents context based on position filter
    fa_position = None if position == "All" else position
    base_prompt += get_free_agents_context(roster_df, fa_position, 25)  # Top 25 free agents

    if drop_player:
        base_prompt += f"\nPotential drop candidate: {drop_player}\n"

    base_prompt += """
Please provide:
1. Top 3-5 pickup recommendations with rationale
2. Prioritization based on my roster needs
3. Drop candidates from my roster if needed
4. Timing considerations (bye weeks, matchups)
5. Long-term vs short-term value assessment
6. Waiver wire budget/FAAB suggestions if applicable
"""

    return base_prompt


def generate_lineup_optimization_prompt(user_input: UserInput, roster_df: pl.DataFrame) -> str:
    """Generate a lineup optimization prompt."""
    base_prompt = """I need help optimizing my fantasy football lineup. Please analyze my roster and provide start/sit recommendations with detailed reasoning.

"""

    # Add contexts
    base_prompt += get_league_context(user_input)
    base_prompt += get_roster_context(roster_df, user_input.owner_name)
    base_prompt += get_free_agents_context(roster_df, None, 10)  # Top 10 free agents for potential pickups

    # Get current starters vs bench
    user_roster = roster_df.filter(pl.col("owner_name") == user_input.owner_name)

    # Check if is_starter column exists
    if "is_starter" in user_roster.columns:
        starters = user_roster.filter(pl.col("is_starter"))
        bench = user_roster.filter(~pl.col("is_starter"))
    else:
        # If no is_starter column, treat all players as bench
        starters = user_roster.filter(pl.lit(value=False))  # Empty dataframe
        bench = user_roster

    if len(starters) > 0:
        base_prompt += "\nCURRENT STARTERS:\n"
        for row in starters.iter_rows(named=True):
            value = _safe_format_value(row.get("value"))
            base_prompt += f"- {row['full_name']} ({row['position']}): {value:,}\n"

    if len(bench) > 0:
        base_prompt += "\nBENCH PLAYERS:\n"
        for row in bench.iter_rows(named=True):
            value = _safe_format_value(row.get("value"))
            base_prompt += f"- {row['full_name']} ({row['position']}): {value:,}\n"

    base_prompt += """
Please provide:
1. Optimal starting lineup based on value and matchups
2. Start/sit decisions with reasoning
3. Flex position recommendations
4. Boom/bust vs floor/ceiling considerations
5. Matchup-specific advice
6. Weather/game script factors to consider
7. Confidence level for each recommendation
"""

    return base_prompt


def generate_draft_strategy_prompt(user_input: UserInput, roster_df: pl.DataFrame) -> str:
    """Generate a draft strategy prompt."""
    base_prompt = """I need help developing a draft strategy for my dynasty fantasy football league. Please analyze my current roster and provide strategic guidance.

"""

    # Add contexts
    base_prompt += get_league_context(user_input)
    base_prompt += get_roster_context(roster_df, user_input.owner_name)
    base_prompt += get_free_agents_context(roster_df, None, 20)  # Top 20 available players for draft context

    # Add positional analysis
    user_roster = roster_df.filter(pl.col("owner_name") == user_input.owner_name)

    base_prompt += "\nPOSITIONAL BREAKDOWN:\n"
    for position in POSITIONS:
        position_players = user_roster.filter(pl.col("position") == position)
        count = len(position_players)
        total_value = _safe_format_value(position_players.get_column("value").sum() if count > 0 else 0)
        base_prompt += f"- {position}: {count} players, {total_value:,} total value\n"

    base_prompt += """
Please provide:
1. Roster strengths and weaknesses analysis
2. Draft position priorities (which positions to target)
3. Age/timeline considerations for dynasty
4. Trade recommendations before the draft
5. Draft round targets for different positions
6. Sleeper/value picks to watch for
7. Overall strategy: Compete now vs rebuild?
"""

    return base_prompt


def generate_who_to_draft_next_prompt(
    user_input: UserInput,
    roster_df: pl.DataFrame,
    draft_position: str | None = None,
    available_positions: list[str] | None = None,
) -> str:
    """Generate a who to draft next prompt."""
    base_prompt = """I need help deciding who to draft next in my fantasy football draft. Please analyze my current roster, available players, and provide specific draft recommendations.

"""

    # Add contexts
    base_prompt += get_league_context(user_input)
    base_prompt += get_roster_context(roster_df, user_input.owner_name)
    base_prompt += get_league_ownership_summary(roster_df)
    base_prompt += get_free_agents_context(roster_df, None, 30)  # Top 30 available players

    if draft_position:
        base_prompt += f"\nDraft Position: {draft_position}\n"

    if available_positions:
        base_prompt += f"\nPositions to Consider: {', '.join(available_positions)}\n"

    base_prompt += """
Please provide:
1. Top 5 draft recommendations with detailed rationale
2. Positional need analysis based on my current roster
3. Value vs need assessment for each recommendation
4. Best player available vs positional need discussion
5. Risk/reward analysis for each option
6. Alternative picks if top choices are taken
7. Draft strategy for next 2-3 rounds
8. Long-term dynasty implications of each choice
"""

    return base_prompt


def generate_season_strategy_prompt(user_input: UserInput, roster_df: pl.DataFrame) -> str:
    """Generate a season-long strategy prompt."""
    base_prompt = """I need help developing a season-long strategy for my dynasty fantasy football team. Please analyze my roster and competitive position.

"""

    # Add contexts
    base_prompt += get_league_context(user_input)
    base_prompt += get_league_ownership_summary(roster_df)
    base_prompt += get_roster_context(roster_df, user_input.owner_name, include_all_teams=True)

    base_prompt += """
Please provide:
1. Competitive assessment - am I a contender, middle-tier, or rebuilding?
2. Roster construction analysis - strengths/weaknesses
3. Trade strategy - who to target/shop
4. Age curve considerations - aging veterans to move
5. Draft pick value vs win-now moves
6. Positional priorities for improvement
7. Timeline - compete this year or build for future?
8. Specific actionable recommendations
"""

    return base_prompt


def generate_keeper_cut_analysis_prompt(user_input: UserInput, roster_df: pl.DataFrame, cut_count: int = 5) -> str:
    """Generate a keeper/cut analysis prompt."""
    base_prompt = f"""I need help deciding which players to keep vs cut in my dynasty fantasy football league. Please analyze my roster and recommend which {cut_count} players to cut.

"""

    # Add contexts
    base_prompt += get_league_context(user_input)
    base_prompt += get_roster_context(roster_df, user_input.owner_name)
    base_prompt += get_free_agents_context(roster_df, None, 15)  # Available alternatives

    # Add age/contract info if available
    user_roster = roster_df.filter(pl.col("owner_name") == user_input.owner_name).sort("value", descending=False)

    base_prompt += f"""
Please provide:
1. Bottom {cut_count} cut candidates with reasoning
2. Dynasty value assessment for each player
3. Age curve and future outlook considerations
4. Replacement value available on waivers
5. Opportunity cost analysis
6. Keep/cut recommendations for each borderline player
7. Alternative roster construction strategies
"""

    return base_prompt


def generate_playoff_push_prompt(user_input: UserInput, roster_df: pl.DataFrame, weeks_remaining: int = 6) -> str:
    """Generate a playoff push strategy prompt."""
    base_prompt = f"""I need help with a playoff push strategy. With {weeks_remaining} weeks remaining in the regular season, please analyze my team's position and recommend actions to secure a playoff spot.

"""

    # Add contexts
    base_prompt += get_league_context(user_input)
    base_prompt += get_roster_context(roster_df, user_input.owner_name)
    base_prompt += get_league_ownership_summary(roster_df)
    base_prompt += get_free_agents_context(roster_df, None, 20)

    base_prompt += """
Please provide:
1. Playoff chances assessment based on current roster
2. Must-win vs nice-to-have game identification
3. Short-term roster moves to maximize wins
4. Trade targets for immediate impact
5. Waiver wire priorities for playoff push
6. Lineup optimization for each remaining week
7. Risk tolerance - how aggressive should I be?
8. Backup plan if playoff push fails
"""

    return base_prompt


def generate_rookie_evaluation_prompt(user_input: UserInput, roster_df: pl.DataFrame, rookie_names: list[str]) -> str:
    """Generate a rookie evaluation prompt."""
    base_prompt = """I need help evaluating rookie players for dynasty value. Please analyze these rookies and provide dynasty outlook and recommendations.

"""

    # Add contexts
    base_prompt += get_league_context(user_input)
    base_prompt += get_player_context(roster_df, rookie_names)
    base_prompt += get_roster_context(roster_df, user_input.owner_name)

    base_prompt += """
Please provide:
1. Dynasty outlook for each rookie (2-3 year projection)
2. Current vs future value assessment
3. Opportunity analysis (depth chart, situation)
4. Buy/sell/hold recommendations
5. Fair trade value in dynasty context
6. Comparison to similar rookie profiles historically
7. Red flags or concerns to monitor
8. Timeline for expected breakout or decline
"""

    return base_prompt


def generate_buy_low_sell_high_prompt(user_input: UserInput, roster_df: pl.DataFrame) -> str:
    """Generate a buy low/sell high analysis prompt."""
    base_prompt = """I need help identifying buy low and sell high opportunities in my league. Please analyze player values and trends to find trading opportunities.

"""

    # Add contexts
    base_prompt += get_league_context(user_input)
    base_prompt += get_roster_context(roster_df, user_input.owner_name)
    base_prompt += get_league_ownership_summary(roster_df)

    # Get trending players
    if "trend" in roster_df.columns:
        trending_up = roster_df.filter(pl.col("trend") > TREND_UP_THRESHOLD).sort("trend", descending=True).head(10)
        trending_down = roster_df.filter(pl.col("trend") < TREND_DOWN_THRESHOLD).sort("trend").head(10)

        if len(trending_up) > 0:
            base_prompt += "\nTRENDING UP PLAYERS:\n"
            for row in trending_up.iter_rows(named=True):
                owner = row.get("owner_name", "Available")
                value = _safe_format_value(row.get("value"))
                trend = _safe_format_trend(row.get("trend"))
                base_prompt += f"- {row['full_name']} ({row['position']}): Value {value:,}, Trend +{trend:.3f}, Owner: {owner}\n"

        if len(trending_down) > 0:
            base_prompt += "\nTRENDING DOWN PLAYERS:\n"
            for row in trending_down.iter_rows(named=True):
                owner = row.get("owner_name", "Available")
                value = _safe_format_value(row.get("value"))
                trend = _safe_format_trend(row.get("trend"))
                base_prompt += f"- {row['full_name']} ({row['position']}): Value {value:,}, Trend {trend:.3f}, Owner: {owner}\n"

    base_prompt += """
Please provide:
1. Top 5 buy low candidates with rationale
2. Top 5 sell high candidates from my roster
3. Market inefficiencies to exploit
4. Timing considerations for each move
5. Fair value ranges for buy/sell targets
6. Risk assessment for each recommendation
7. Alternative players with similar value profiles
"""

    return base_prompt


def generate_injury_impact_prompt(user_input: UserInput, roster_df: pl.DataFrame, injured_players: list[str]) -> str:
    """Generate an injury impact analysis prompt."""
    base_prompt = """I need help analyzing the impact of player injuries on my team and league. Please provide strategic recommendations for dealing with these injuries.

"""

    # Add contexts
    base_prompt += get_league_context(user_input)
    base_prompt += get_player_context(roster_df, injured_players)
    base_prompt += get_roster_context(roster_df, user_input.owner_name)
    base_prompt += get_free_agents_context(roster_df, None, 25)

    base_prompt += """
Please provide:
1. Injury severity and timeline assessment
2. Immediate replacement options (waivers/trades)
3. Long-term roster impact analysis
4. Handcuff pickups to prioritize
5. Trade opportunities created by injuries
6. Buy low opportunities on injured players
7. Lineup adjustments for affected weeks
8. Dynasty implications of each injury
"""

    return base_prompt


def render_llm_prompts(user_input: UserInput) -> None:
    """
    Render the LLM prompt generator interface.

    Args:
    ----
        user_input: UserInput object containing all user preferences

    """
    owner_id, current_username, league, ranking_set, starters_only, include_picks, time_frame = user_input

    st.header("🤖 LLM Prompt Generator")
    st.markdown("Generate contextual fantasy football prompts for ChatGPT, Perplexity, Claude, and other AI assistants")

    # Get processed data
    with st.spinner("Loading league data..."):
        players_df, rankings_df, roster_df = get_processed_data(user_input)

    if len(roster_df) == 0:
        st.warning("No roster data available.")
        return

    st.info(
        "💡 **Tip**: These prompts include your specific league context, roster data, and player values. Copy and paste them into any AI assistant for personalized fantasy advice!"
    )

    # Prompt type selection
    selected_prompt = _render_prompt_type_selection()

    # Handle prompt-specific logic
    _handle_prompt_generation(selected_prompt, user_input, roster_df, current_username)

    # Render help sections
    _render_usage_tips()

    dump_cookies()


def _render_prompt_type_selection() -> str:
    """Render the prompt type selection dropdown."""
    prompt_types = [
        "Trade Analysis",
        "Waiver Wire / Free Agents",
        "Who to Draft Next",
        "Lineup Optimization",
        "Draft Strategy",
        "Season Strategy",
        "Keeper/Cut Analysis",
        "Playoff Push Strategy",
        "Rookie Evaluation",
        "Buy Low/Sell High",
        "Injury Impact Analysis",
    ]
    return st.selectbox("Select Prompt Type", prompt_types)


def _handle_prompt_generation(
    selected_prompt: str, user_input: UserInput, roster_df: pl.DataFrame, current_username: str
) -> None:
    """Handle the generation of different prompt types."""
    if selected_prompt == "Trade Analysis":
        _render_trade_analysis_prompt(user_input, roster_df, current_username)
    elif selected_prompt == "Waiver Wire / Free Agents":
        _render_waiver_wire_prompt(user_input, roster_df, current_username)
    elif selected_prompt == "Who to Draft Next":
        _render_draft_decision_prompt(user_input, roster_df)
    elif selected_prompt == "Lineup Optimization":
        _render_lineup_optimization_prompt(user_input, roster_df)
    elif selected_prompt == "Draft Strategy":
        _render_draft_strategy_prompt(user_input, roster_df)
    elif selected_prompt == "Season Strategy":
        _render_season_strategy_prompt(user_input, roster_df)
    elif selected_prompt == "Keeper/Cut Analysis":
        _render_keeper_cut_prompt(user_input, roster_df)
    elif selected_prompt == "Playoff Push Strategy":
        _render_playoff_push_prompt(user_input, roster_df)
    elif selected_prompt == "Rookie Evaluation":
        _render_rookie_evaluation_prompt(user_input, roster_df)
    elif selected_prompt == "Buy Low/Sell High":
        _render_buy_low_sell_high_prompt(user_input, roster_df)
    elif selected_prompt == "Injury Impact Analysis":
        _render_injury_impact_prompt(user_input, roster_df)


def _render_trade_analysis_prompt(user_input: UserInput, roster_df: pl.DataFrame, current_username: str) -> None:
    """Render the trade analysis prompt interface."""
    st.subheader("🔄 Trade Analysis Setup")

    # Get available teams and initialize session state
    other_teams = _get_other_teams(roster_df, current_username)
    _initialize_trade_session_state(other_teams)

    # Render player selection interface
    trading_partner, my_players, their_players = _render_player_selection(roster_df, current_username, other_teams)

    # Show current trade summary
    _render_trade_summary(my_players, their_players)

    # Render action buttons
    _render_trade_action_buttons(user_input, roster_df, my_players, their_players, trading_partner)


def _initialize_trade_session_state(other_teams: list[str]) -> None:
    """Initialize session state for trade analysis."""
    if "trade_partner" not in st.session_state:
        st.session_state.trade_partner = other_teams[0] if other_teams else ""
    if "my_players" not in st.session_state:
        st.session_state.my_players = []
    if "their_players" not in st.session_state:
        st.session_state.their_players = []


def _render_player_selection(roster_df: pl.DataFrame, current_username: str, other_teams: list[str]) -> tuple[str, list[str], list[str]]:
    """Render player selection interface and return selections."""
    col1, col2 = st.columns(2)

    with col1:
        # Trading partner selection
        trading_partner = st.selectbox(
            "Trading Partner",
            options=other_teams,
            index=other_teams.index(st.session_state.trade_partner) if st.session_state.trade_partner in other_teams else 0,
            key="trade_partner_select"
        )

        # Update session state if partner changed
        if trading_partner != st.session_state.trade_partner:
            st.session_state.trade_partner = trading_partner
            st.session_state.their_players = []  # Reset their players when partner changes

        # My players selection
        my_players = _get_my_players_selection(roster_df, current_username)

    with col2:
        # Their players selection (only if trading partner is selected)
        if trading_partner:
            their_players = _get_their_players_selection(roster_df, trading_partner)
        else:
            their_players = []
            st.info("Select a trading partner to choose their players")

    return trading_partner, my_players, their_players


def _render_trade_summary(my_players: list[str], their_players: list[str]) -> None:
    """Render the current trade summary."""
    if not my_players and not their_players:
        return

    st.markdown("### 📋 Current Trade Summary")
    col_summary1, col_summary2 = st.columns(2)

    with col_summary1:
        if my_players:
            st.markdown(f"**📤 Trading Away ({len(my_players)} players):**")
            for player in my_players:
                st.markdown(f"- {player}")
        else:
            st.markdown("**📤 Trading Away:** *No players selected*")

    with col_summary2:
        if their_players:
            st.markdown(f"**📥 Receiving ({len(their_players)} players):**")
            for player in their_players:
                st.markdown(f"- {player}")
        else:
            st.markdown("**📥 Receiving:** *No players selected*")


def _render_trade_action_buttons(
    user_input: UserInput, roster_df: pl.DataFrame, my_players: list[str], their_players: list[str], trading_partner: str
) -> None:
    """Render trade action buttons."""
    col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 2])

    with col_btn1:
        if st.button("🔄 Reset Selections", key="reset_trade_selections"):
            st.session_state.my_players = []
            st.session_state.their_players = []
            st.rerun()

    with col_btn2:
        if st.button("Generate Trade Analysis Prompt", type="primary", key="generate_trade_prompt"):
            if not my_players and not their_players:
                st.warning("Please select at least one player from either side of the trade.")
            else:
                prompt = generate_trade_analysis_prompt(user_input, roster_df, my_players, their_players, trading_partner)
                _display_generated_prompt(prompt, "trade_prompt")


def _render_waiver_wire_prompt(user_input: UserInput, roster_df: pl.DataFrame, current_username: str) -> None:
    """Render the waiver wire prompt interface."""
    st.subheader("🏃 Waiver Wire Setup")

    col1, col2 = st.columns(2)

    with col1:
        position_filter = st.selectbox("Position Focus", ["All", *list(POSITIONS)], key="waiver_position_filter")

    with col2:
        drop_player = _get_drop_candidate_selection(roster_df, current_username)

    if st.button("Generate Waiver Wire Prompt", type="primary", key="generate_waiver_prompt"):
        prompt = generate_waiver_pickup_prompt(user_input, roster_df, position_filter, drop_player)
        _display_generated_prompt(prompt, "waiver_prompt")


def _render_draft_decision_prompt(user_input: UserInput, roster_df: pl.DataFrame) -> None:
    """Render the draft decision prompt interface."""
    st.subheader("🎯 Draft Decision Setup")

    col1, col2 = st.columns(2)

    with col1:
        draft_position = st.text_input("Current Draft Position (optional)", placeholder="e.g., Round 3, Pick 7", key="draft_position_input")

    with col2:
        position_focus = st.multiselect(
            "Positions to Consider", list(POSITIONS), help="Leave empty to consider all positions", key="draft_position_focus"
        )

    if st.button("Generate Draft Decision Prompt", type="primary", key="generate_draft_prompt"):
        available_positions = position_focus if position_focus else None
        prompt = generate_who_to_draft_next_prompt(user_input, roster_df, draft_position or None, available_positions)
        _display_generated_prompt(prompt, "draft_decision_prompt")


def _render_lineup_optimization_prompt(user_input: UserInput, roster_df: pl.DataFrame) -> None:
    """Render the lineup optimization prompt interface."""
    st.subheader("🎯 Lineup Optimization")
    st.markdown("This prompt will analyze your current lineup and provide start/sit recommendations.")

    if st.button("Generate Lineup Optimization Prompt", type="primary", key="generate_lineup_prompt"):
        prompt = generate_lineup_optimization_prompt(user_input, roster_df)
        _display_generated_prompt(prompt, "lineup_prompt")


def _render_draft_strategy_prompt(user_input: UserInput, roster_df: pl.DataFrame) -> None:
    """Render the draft strategy prompt interface."""
    st.subheader("🎯 Draft Strategy")
    st.markdown("This prompt will analyze your roster and provide draft strategy recommendations.")

    if st.button("Generate Draft Strategy Prompt", type="primary", key="generate_draft_strategy_prompt"):
        prompt = generate_draft_strategy_prompt(user_input, roster_df)
        _display_generated_prompt(prompt, "draft_strategy_prompt")


def _render_season_strategy_prompt(user_input: UserInput, roster_df: pl.DataFrame) -> None:
    """Render the season strategy prompt interface."""
    st.subheader("📈 Season Strategy")
    st.markdown("This prompt will provide comprehensive season-long strategic analysis including all team rosters.")
    st.warning("⚠️ This prompt includes all team rosters and will be quite long.")

    if st.button("Generate Season Strategy Prompt", type="primary", key="generate_season_strategy_prompt"):
        prompt = generate_season_strategy_prompt(user_input, roster_df)
        _display_generated_prompt(prompt, "season_strategy_prompt")


def _render_keeper_cut_prompt(user_input: UserInput, roster_df: pl.DataFrame) -> None:
    """Render the keeper/cut analysis prompt interface."""
    st.subheader("✂️ Keeper/Cut Analysis")
    st.markdown("This prompt will help you decide which players to keep vs cut in dynasty.")

    cut_count = st.number_input("Number of players to cut", min_value=1, max_value=20, value=5, key="cut_count_input")

    if st.button("Generate Keeper/Cut Analysis Prompt", type="primary", key="generate_keeper_cut_prompt"):
        prompt = generate_keeper_cut_analysis_prompt(user_input, roster_df, cut_count)
        _display_generated_prompt(prompt, "keeper_cut_prompt")


def _render_playoff_push_prompt(user_input: UserInput, roster_df: pl.DataFrame) -> None:
    """Render the playoff push strategy prompt interface."""
    st.subheader("🏆 Playoff Push Strategy")
    st.markdown("This prompt will help you strategize for making the playoffs.")

    weeks_remaining = st.number_input("Weeks remaining in regular season", min_value=1, max_value=17, value=6, key="weeks_remaining_input")

    if st.button("Generate Playoff Push Prompt", type="primary", key="generate_playoff_push_prompt"):
        prompt = generate_playoff_push_prompt(user_input, roster_df, weeks_remaining)
        _display_generated_prompt(prompt, "playoff_push_prompt")


def _render_rookie_evaluation_prompt(user_input: UserInput, roster_df: pl.DataFrame) -> None:
    """Render the rookie evaluation prompt interface."""
    st.subheader("👶 Rookie Evaluation")
    st.markdown("This prompt will help you evaluate rookie players for dynasty value.")

    # Get all players for selection
    all_players = sorted(roster_df.get_column("full_name").unique().to_list())

    rookie_players = st.multiselect(
        "Select rookie players to evaluate",
        options=all_players,
        help="Select one or more rookie players for analysis",
        key="rookie_players_select"
    )

    if st.button("Generate Rookie Evaluation Prompt", type="primary", key="generate_rookie_evaluation_prompt"):
        if not rookie_players:
            st.warning("Please select at least one rookie player to evaluate.")
        else:
            prompt = generate_rookie_evaluation_prompt(user_input, roster_df, rookie_players)
            _display_generated_prompt(prompt, "rookie_evaluation_prompt")


def _render_buy_low_sell_high_prompt(user_input: UserInput, roster_df: pl.DataFrame) -> None:
    """Render the buy low/sell high prompt interface."""
    st.subheader("📈📉 Buy Low/Sell High Analysis")
    st.markdown("This prompt will identify trading opportunities based on player value trends.")

    if st.button("Generate Buy Low/Sell High Prompt", type="primary", key="generate_buy_low_sell_high_prompt"):
        prompt = generate_buy_low_sell_high_prompt(user_input, roster_df)
        _display_generated_prompt(prompt, "buy_low_sell_high_prompt")


def _render_injury_impact_prompt(user_input: UserInput, roster_df: pl.DataFrame) -> None:
    """Render the injury impact analysis prompt interface."""
    st.subheader("🏥 Injury Impact Analysis")
    st.markdown("This prompt will help you analyze the impact of player injuries on your team.")

    # Get all players for selection
    all_players = sorted(roster_df.get_column("full_name").unique().to_list())

    injured_players = st.multiselect(
        "Select injured players to analyze",
        options=all_players,
        help="Select one or more injured players for impact analysis",
        key="injured_players_select"
    )

    if st.button("Generate Injury Impact Prompt", type="primary", key="generate_injury_impact_prompt"):
        if not injured_players:
            st.warning("Please select at least one injured player to analyze.")
        else:
            prompt = generate_injury_impact_prompt(user_input, roster_df, injured_players)
            _display_generated_prompt(prompt, "injury_impact_prompt")


def _get_other_teams(roster_df: pl.DataFrame, current_username: str) -> list[str]:
    """Get list of other team names for trading."""
    return sorted(
        [
            name
            for name in roster_df.filter(pl.col("owner_name").is_not_null()).get_column("owner_name").unique().to_list()
            if name != current_username
        ]
    )


def _get_my_players_selection(roster_df: pl.DataFrame, current_username: str) -> list[str]:
    """Get my players selection for trade analysis."""
    my_roster = roster_df.filter(pl.col("owner_name") == current_username)
    my_player_options = sorted(my_roster.get_column("full_name").to_list())

    # Filter session state to only include players available in current league
    current_selections = st.session_state.my_players if hasattr(st.session_state, "my_players") else []
    valid_selections = [p for p in current_selections if p in my_player_options]

    # Use session state to maintain selections
    selected = st.multiselect(
        "My Players (trading away)",
        options=my_player_options,
        default=valid_selections,
        key="my_players_select"
    )

    # Update session state
    st.session_state.my_players = selected
    return selected


def _get_their_players_selection(roster_df: pl.DataFrame, trading_partner: str) -> list[str]:
    """Get their players selection for trade analysis."""
    their_roster = roster_df.filter(pl.col("owner_name") == trading_partner)
    their_player_options = sorted(their_roster.get_column("full_name").to_list())

    # Filter session state to only include players available for this partner
    current_selections = st.session_state.their_players if hasattr(st.session_state, "their_players") else []
    valid_selections = [p for p in current_selections if p in their_player_options]

    # Use session state to maintain selections
    selected = st.multiselect(
        f"Their Players (receiving from {trading_partner})",
        options=their_player_options,
        default=valid_selections,
        key="their_players_select"
    )

    # Update session state
    st.session_state.their_players = selected
    return selected


def _get_drop_candidate_selection(roster_df: pl.DataFrame, current_username: str) -> str | None:
    """Get drop candidate selection for waiver wire."""
    my_roster = roster_df.filter(pl.col("owner_name") == current_username)
    drop_options = ["None", *sorted(my_roster.get_column("full_name").to_list())]
    drop_candidate = st.selectbox("Potential Drop Candidate", drop_options, key="drop_candidate_select")
    return drop_candidate if drop_candidate != "None" else None


def _display_generated_prompt(prompt: str, key: str) -> None:
    """Display the generated prompt in text area and code block."""
    st.subheader("📋 Generated Prompt")
    st.text_area("Copy this prompt to your AI assistant:", prompt, height=400, key=key)
    st.code(prompt, language=None)


def _render_usage_tips() -> None:
    """Render the usage tips expander."""
    with st.expander("💡 Usage Tips & Best Practices", expanded=False):
        st.markdown("""
        ### How to Use Generated Prompts:

        **🤖 Compatible AI Assistants:**
        - ChatGPT (OpenAI)
        - Claude (Anthropic)
        - Perplexity AI
        - Google Bard/Gemini
        - Microsoft Copilot
        - Any other conversational AI

        **🎯 Available Prompt Types:**
        - **Trade Analysis** - Evaluate potential trades with full context
        - **Waiver Wire/Free Agents** - Get pickup recommendations
        - **Who to Draft Next** - Get draft decision help with available players
        - **Lineup Optimization** - Start/sit decisions with reasoning
        - **Draft Strategy** - Overall draft planning and roster building
        - **Season Strategy** - Comprehensive team analysis and planning
        - **Keeper/Cut Analysis** - Dynasty roster management decisions
        - **Playoff Push Strategy** - Mid-season moves to secure playoffs
        - **Rookie Evaluation** - Dynasty value assessment for rookies
        - **Buy Low/Sell High** - Identify trading opportunities based on trends
        - **Injury Impact Analysis** - Strategic response to player injuries

        **📋 Copy & Paste Instructions:**
        1. Click "Generate [Prompt Type] Prompt"
        2. Copy the text from the text area or code block
        3. Paste into your preferred AI assistant
        4. Get personalized fantasy advice!

        **✨ Pro Tips:**
        - **Follow up questions**: Ask for clarification or dive deeper into specific aspects
        - **Weekly updates**: Re-generate prompts with fresh data each week
        - **Multiple perspectives**: Try the same prompt with different AI assistants
        - **Combine insights**: Use different prompt types together for comprehensive analysis

        **🔄 Keep Prompts Fresh:**
        - Player values and trends update regularly
        - Roster changes affect recommendations
        - Weekly matchups influence decisions
        - Re-generate prompts for the most current advice

        **🎯 Maximize Value:**
        - Be specific in follow-up questions
        - Ask for confidence levels on recommendations
        - Request alternative scenarios
        - Get explanations for counter-intuitive advice
        """)

    # Sample prompts section
    with st.expander("📝 Sample Generated Prompts", expanded=False):
        st.markdown("""
        ### Sample Trade Analysis Prompt:
        ```
        I need help analyzing a potential fantasy football trade...

        LEAGUE CONTEXT:
        - League Name: Dynasty League 2024
        - League Type: Dynasty, PPR Scoring
        - Teams: 12, Roster: QB,RB,RB,WR,WR,TE,FLEX...

        TRADE DETAILS:
        I'm trading away: Ja'Marr Chase, 2024 1st
        I'm receiving: Josh Allen, D'Andre Swift
        Trading partner: TheirTeam

        PLAYER DATA:
        - Ja'Marr Chase (WR): Value 4,850, Trend 0.125 📈, Owned by MyTeam
        - Josh Allen (QB): Value 3,200, Trend -0.050 📉, Owned by TheirTeam
        - D'Andre Swift (RB): Value 2,100, Trend 0.075 📈, Owned by TheirTeam

        MY ROSTER (MyTeam) - Total Value: 32,450:
        - Christian McCaffrey (RB): 4,200, STARTER
        - Ja'Marr Chase (WR): 4,850, STARTER
        - Dak Prescott (QB): 2,100, BENCH
        ...

        TRADING PARTNER'S ROSTER (TheirTeam):
        Total Value: 28,900:
        - Josh Allen (QB): 3,200, STARTER
        - D'Andre Swift (RB): 2,100, STARTER
        - Mike Evans (WR): 2,800, STARTER
        - Kyle Pitts (TE): 1,900, BENCH
        ...

        LEAGUE OWNERSHIP SUMMARY:
        - MyTeam: 18 players, 32,450 total value (Top: CMC 4,200)
        - TheirTeam: 17 players, 28,900 total value (Top: Josh Allen 3,200)
        - Team3: 16 players, 31,200 total value (Top: Travis Kelce 3,800)
        ...

        TOP AVAILABLE FREE AGENTS:
        - Tank Dell (WR): Value 1,250, Trend 📈, AVAILABLE
        - Jaylen Warren (RB): Value 980, Trend ➡️, AVAILABLE
        - Tyler Boyd (WR): Value 750, Trend 📉, AVAILABLE
        ...
        ```

        ### Sample Who to Draft Next Prompt:
        ```
        I need help deciding who to draft next...

        Draft Position: Round 3, Pick 7
        Positions to Consider: RB, WR

        MY ROSTER:
        - Josh Allen (QB): 3,200, STARTER
        - Saquon Barkley (RB): 3,800, STARTER
        - Cooper Kupp (WR): 2,900, STARTER
        ...

        LEAGUE OWNERSHIP SUMMARY:
        - MyTeam: 8 players, 18,450 total value (Top: Saquon 3,800)
        - Team2: 12 players, 22,100 total value (Top: Josh Jacobs 3,400)
        - Team3: 10 players, 19,800 total value (Top: Davante Adams 3,100)
        ...

        TOP AVAILABLE FREE AGENTS:
        - Breece Hall (RB): Value 4,500, Trend 📈, AVAILABLE
        - Garrett Wilson (WR): Value 3,200, Trend 📈, AVAILABLE
        - David Montgomery (RB): Value 2,100, Trend ➡️, AVAILABLE
        ...
        ```

        ### Sample Keeper/Cut Analysis Prompt:
        ```
        I need help deciding which players to keep vs cut...

        MY ROSTER:
        - Christian McCaffrey (RB): 4,200, STARTER
        - D'Andre Swift (RB): 2,100, BENCH
        - Darrell Henderson (RB): 450, BENCH
        - Boston Scott (RB): 250, BENCH
        ...

        TOP AVAILABLE FREE AGENTS:
        - Tank Dell (WR): Value 1,250, Trend 📈, AVAILABLE
        - Jaylen Warren (RB): Value 980, Trend ➡️, AVAILABLE
        ...
        ```

        All prompts now include your specific roster, team ownership data, top free agents, and comprehensive league context for much more accurate AI advice!
        """)

    dump_cookies()


def main() -> None:
    """LLM prompts page."""
    render_home_nav()

    user_input = get_user_input()
    if user_input:
        render_llm_prompts(user_input)
    else:
        st.info("Please enter your Sleeper username in the sidebar to get started.")

    dump_cookies()


if __name__ == "__main__":
    main()
