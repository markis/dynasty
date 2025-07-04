"""
Dynasty Models module defines the core data models and enumerations.

It includes player information, league configurations, and various enums
for ranking sets, league types, scoring types, and player positions.
These models are used for database storage and data interchange between
different components of the application.
"""

import re
from collections.abc import Mapping, Sequence
from datetime import date
from enum import StrEnum
from typing import Final, Self, TypedDict
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class RankingSet(StrEnum):
    """
    Enumeration of available fantasy football ranking data sources.

    Represents the different services and websites that provide
    dynasty fantasy football player rankings and valuations.
    """

    KeepTradeCut = "Keep Trade Cut"
    DynastyProcess = "Dynasty Process"
    FantasyCalc = "Fantasy Calc"
    FantasyNavigator = "Fantasy Navigator"


class LeagueType(StrEnum):
    """
    Enumeration of fantasy football league formats.

    Defines the different quarterback configurations that affect
    player valuations and rankings in dynasty fantasy football.
    """

    Standard = "standard"
    SuperFlex = "superflex"


class ScoringType(StrEnum):
    """
    Enumeration of fantasy football scoring systems for receptions.

    Represents the different point values awarded for player receptions
    in fantasy football leagues.
    """

    PPR = "ppr"  # 1 point per reception
    HalfPPR = "half_ppr"  # 0.5 points per reception
    Standard = "standard"  # 0 points per reception

    @classmethod
    def from_value(cls, value: float) -> "ScoringType":
        """
        Convert a numeric reception scoring value to ScoringType enum.

        Args:
        ----
            value: The reception scoring value (1.0 for PPR, 0.5 for Half PPR, 0.0 for Standard)

        Returns:
        -------
            The corresponding ScoringType enum value

        Raises:
        ------
            ValueError: If the value doesn't match any known scoring type

        """
        scoring_thresholds = {1.0: cls.PPR, 0.5: cls.HalfPPR, 0.0: cls.Standard}

        for threshold, scoring_type in scoring_thresholds.items():
            if value >= threshold:
                return scoring_type

        err = f"Invalid scoring value: {value}. Expected one of {list(scoring_thresholds.keys())}."
        raise ValueError(err)


class TEPScoringType(StrEnum):
    """
    Enumeration of Tight End Premium (TEP) scoring systems.

    Represents bonus points awarded to tight end receptions in
    fantasy football leagues that use TEP scoring.
    """

    FullTEP = "full_tep"  # 1.0 bonus points for TE receptions
    HalfTEP = "half_tep"  # 0.5 bonus points for TE receptions

    @classmethod
    def from_value(cls, value: float) -> "TEPScoringType | None":
        """
        Convert a numeric TEP scoring value to TEPScoringType enum.

        Args:
        ----
            value: The TEP bonus scoring value (1.0 for Full TEP, 0.5 for Half TEP, 0.0 for None)

        Returns:
        -------
            The corresponding TEPScoringType enum value, or None if no TEP scoring

        Raises:
        ------
            ValueError: If the value doesn't match any known TEP scoring type

        """
        scoring_thresholds = {1.0: cls.FullTEP, 0.5: cls.HalfTEP, 0.0: None}

        for threshold, scoring_type in scoring_thresholds.items():
            if value >= threshold:
                return scoring_type

        err = f"Invalid scoring value: {value}. Expected one of {list(scoring_thresholds.keys())}."
        raise ValueError(err)


class StatusType(StrEnum):
    """
    Enumeration of fantasy football league status types.

    Represents the current state of a fantasy football league
    throughout the season lifecycle.
    """

    PreDraft = "pre_draft"  # League created but draft not started
    Drafting = "drafting"  # Draft is currently in progress
    InSeason = "in_season"  # Draft complete, regular season active

    @classmethod
    def from_str(cls, value: str) -> "StatusType":
        """
        Convert a string value to StatusType enum.

        Args:
        ----
            value: The status string to convert

        Returns:
        -------
            The corresponding StatusType enum value

        Raises:
        ------
            ValueError: If the value doesn't match any known status type

        """
        try:
            return cls(value)
        except ValueError as e:
            err = f"Invalid status type: {value}"
            raise ValueError(err) from e


# Mapping of alternate position abbreviations to standard forms.
# Used to normalize position strings from different data sources
# to consistent PlayerPosition enum values.
POS_MAP: Final[Mapping[str, str]] = {
    "PK": "K",
    "DEF": "DST",
    "D/ST": "DST",
    "RDPICK": "PICK",
    "RDP": "PICK",
    "K/P": "K",
    "SUPERFLEX": "SFLEX",
    "SUPER_FLEX": "SFLEX",
    "SF": "SFLEX",
}


class PlayerPosition(StrEnum):
    """
    Enumeration of fantasy football player positions.

    Represents all possible roster positions in fantasy football,
    including standard positions and special roster slots.
    """

    QB = "QB"  # Quarterback
    RB = "RB"  # Running Back
    WR = "WR"  # Wide Receiver
    TE = "TE"  # Tight End
    DST = "DST"  # Defense/Special Teams
    K = "K"  # Kicker
    PICK = "PICK"  # Draft Pick
    FLEX = "FLEX"  # Flex position (RB/WR/TE)
    SFLEX = "SFLEX"  # Super Flex position (QB/RB/WR/TE)

    @classmethod
    def from_str(cls, value: str) -> Self | None:
        """
        Convert a string value to PlayerPosition enum.

        Normalizes the input string by removing whitespace and numbers,
        converting to uppercase, and mapping alternate abbreviations.

        Args:
        ----
            value: The position string to convert

        Returns:
        -------
            The corresponding PlayerPosition enum value, or None if not found

        """
        # strip any leading/trailing whitespace or numbers and convert to uppercase
        value = re.sub(r"^\d+|\s+|\d+$", "", value).upper()
        value = POS_MAP.get(value, value)
        try:
            return cls(value)
        except ValueError:
            return None


# Mapping of alternate injury status abbreviations to standard forms.
# Used to normalize injury status strings from different data sources
# to consistent InjuryStatus enum values.
INJURY_STATUS_MAP: Final[Mapping[str, str]] = {
    "PROBABLE": "P",
    "PROB": "P",
    "QUESTIONABLE": "Q",
    "QUESTION": "Q",
    "DOUBT": "D",
    "DOUBTFUL": "D",
    "OUT": "O",
    "SUSPENDED": "S",
    "SUSP": "S",
    "SUSPENSION": "S",
    "IR": "IR",
    "PUP": "PUP",
    "COVID": "COV",
    "COVID19": "COV",
    "COVID-19": "COV",
    "RESERVE/COVID-19": "COV",
}


class InjuryStatus(StrEnum):
    """
    Enumeration of player injury and availability status types.

    Represents the current health and availability status of NFL players
    for fantasy football purposes.
    """

    Probable = "P"  # Probable to play
    Questionable = "Q"  # Questionable to play
    Doubtful = "D"  # Doubtful to play
    Out = "O"  # Out for game
    Suspended = "S"  # Suspended
    IR = "IR"  # Injured Reserve
    PUP = "PUP"  # Physically Unable to Perform list
    Covid19 = "COV"  # COVID-19 related absence

    @classmethod
    def from_str(cls, value: str) -> Self | None:
        """
        Convert a string value to InjuryStatus enum.

        Normalizes the input string by removing whitespace and numbers,
        converting to uppercase, and mapping alternate abbreviations.

        Args:
        ----
            value: The injury status string to convert

        Returns:
        -------
            The corresponding InjuryStatus enum value, or None if not found

        """
        # Normalize input: strip whitespace, uppercase, map common aliases
        value = re.sub(r"^\d+|\s+|\d+$", "", value).upper()
        value = INJURY_STATUS_MAP.get(value, value)
        try:
            return cls(value)
        except ValueError:
            return None


# Mapping of alternate NFL team abbreviations to standard forms.
# Used to normalize team abbreviations from different data sources
# to consistent Team enum values.
TEAM_MAP: Final[Mapping[str, str]] = {
    "SFO": "SF",
    "TBB": "TB",
    "GBP": "GB",
    "NOS": "NO",
    "SD": "LAC",
    "KCC": "KC",
    "NEP": "NE",
    "OAK": "LV",
    "HST": "HOU",
    "BLT": "BAL",
    "JAC": "JAX",
    "ARZ": "ARI",
    "CLV": "CLE",
    "STL": "LAR",
    "SL": "LAR",
    "LVR": "LV",
    "PHX": "ARI",
    "NWE": "NE",
    "GNB": "GB",
    "NOR": "NO",
}


class Team(StrEnum):
    """
    Enumeration of NFL team abbreviations.

    Represents all 32 NFL teams plus Free Agent status
    for fantasy football player assignments.
    """

    FA = "FA"  # Free Agent

    ARI = "ARI"  # Arizona Cardinals
    ATL = "ATL"  # Atlanta Falcons
    BAL = "BAL"  # Baltimore Ravens
    BUF = "BUF"  # Buffalo Bills
    CAR = "CAR"  # Carolina Panthers
    CHI = "CHI"  # Chicago Bears
    CIN = "CIN"  # Cincinnati Bengals
    CLE = "CLE"  # Cleveland Browns
    DAL = "DAL"  # Dallas Cowboys
    DEN = "DEN"  # Denver Broncos
    DET = "DET"  # Detroit Lions
    GB = "GB"  # Green Bay Packers
    HOU = "HOU"  # Houston Texans
    IND = "IND"  # Indianapolis Colts
    JAX = "JAX"  # Jacksonville Jaguars
    KC = "KC"  # Kansas City Chiefs
    LAC = "LAC"  # Los Angeles Chargers
    LAR = "LAR"  # Los Angeles Rams
    LV = "LV"  # Las Vegas Raiders
    MIA = "MIA"  # Miami Dolphins
    MIN = "MIN"  # Minnesota Vikings
    NE = "NE"  # New England Patriots
    NO = "NO"  # New Orleans Saints
    NYG = "NYG"  # New York Giants
    NYJ = "NYJ"  # New York Jets
    PHI = "PHI"  # Philadelphia Eagles
    PIT = "PIT"  # Pittsburgh Steelers
    SEA = "SEA"  # Seattle Seahawks
    SF = "SF"  # San Francisco 49ers
    TB = "TB"  # Tampa Bay Buccaneers
    TEN = "TEN"  # Tennessee Titans
    WAS = "WAS"  # Washington Commanders

    @classmethod
    def from_str(cls, value: str) -> Self:
        """
        Convert a string value to Team enum.

        Normalizes the input string by trimming whitespace, converting to uppercase,
        and mapping alternate abbreviations to standard team codes.

        Args:
        ----
            value: The team string to convert

        Returns:
        -------
            The corresponding Team enum value

        """
        value = value.upper().strip()
        value = TEAM_MAP.get(value, value)
        return cls(value)


class Player(SQLModel, table=True):
    """
    Database model representing an NFL player.

    Contains comprehensive player information including biographical data,
    physical attributes, team affiliation, and external service IDs for
    cross-referencing with various fantasy football platforms.
    """

    __table_args__ = (UniqueConstraint("player_id"), UniqueConstraint("sleeper_id"))

    id: int | None = Field(default=None, primary_key=True)
    player_id: UUID = Field(index=True)  # Generated UUID based on normalized name
    first_name: str
    last_name: str
    full_name: str
    birth_date: date
    team: Team
    number: int | None  # Jersey number
    college: str | None
    high_school: str | None
    position: PlayerPosition
    age: int
    height: int  # Height in inches
    weight: int  # Weight in pounds
    years_exp: int  # Years of NFL experience
    status: str | None  # Current roster status
    injury_status: InjuryStatus | None
    active: bool  # Active on NFL roster

    # External service IDs for cross-referencing
    espn_id: int | None
    fantasy_data_id: int | None
    gsis_id: str | None
    oddsjam_id: str | None
    rotowire_id: int | None
    rotoworld_id: int | None
    sleeper_id: str | None = Field(index=True, unique=True)
    sportradar_id: str | None
    stats_id: int | None
    swish_id: int | None
    yahoo_id: int | None


class PlayerRanking(SQLModel, table=True):
    """
    Database model representing a player's ranking/value at a specific point in time.

    Stores historical ranking data from various fantasy football services,
    allowing for trend analysis and value tracking over time.
    """

    __table_args__ = (UniqueConstraint("player_id", "league_type", "date"),)

    id: int | None = Field(default=None, primary_key=True)
    player_id: UUID = Field(default=None, foreign_key="player.player_id")
    league_type: LeagueType  # Standard or SuperFlex
    date: date  # Date of this ranking
    value: int  # Ranking value/score
    ranking_set: RankingSet  # Source of the ranking
    is_pick: bool  # Whether this represents a draft pick


class Pick(SQLModel, table=True):
    """
    Database model representing a draft pick selection.

    Tracks draft picks made in fantasy football leagues,
    including the player selected, round, and pick number.
    """

    __table_args__ = (UniqueConstraint("sleeper_id", "draft_id"),)

    id: int | None = Field(default=None, primary_key=True)
    sleeper_id: str = Field(foreign_key="player.sleeper_id", index=True)
    league_id: str
    draft_id: str
    round: int  # Draft round
    pick_no: int  # Overall pick number
    picked_by: str  # ID of team/owner making the pick


class League(BaseModel):
    """
    Model representing a fantasy football league configuration.

    Contains league settings, scoring configuration, and roster requirements
    used for player valuation and ranking analysis.
    """

    id: str
    name: str
    season: int
    team_count: int
    status: StatusType
    league_type: LeagueType
    scoring_type: ScoringType
    bonus_tep: TEPScoringType | None  # Tight End Premium bonus
    scoring_settings: dict[str, dict[str, float]]  # Detailed scoring configuration
    roster_positions: Sequence[PlayerPosition]  # Required roster positions


class SleeperRosterSettings(TypedDict):
    """
    Type definition for Sleeper roster performance metrics.

    Contains season statistics and settings for a specific roster
    in a Sleeper fantasy football league.
    """

    wins: int
    waiver_position: int
    waiver_budget_used: int
    total_moves: int
    ties: int
    losses: int
    fpts: int  # Fantasy points scored


class Roster(BaseModel):
    """
    Model representing a fantasy football team roster.

    Contains roster composition, ownership information, and performance data
    for a specific team within a fantasy football league.
    """

    league_id: str
    owner_id: str
    roster_id: int
    name: str
    settings: SleeperRosterSettings
    starters: Sequence[int]  # Player IDs in starting lineup
    players: Sequence[int]  # All player IDs on roster
    picks: Sequence[str]  # Draft picks owned
