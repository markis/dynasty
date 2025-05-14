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
    KeepTradeCut = "Keep Trade Cut"
    DynastyProcess = "Dynasty Process"
    FantasyCalc = "Fantasy Calc"
    FantasyNavigator = "Fantasy Navigator"


class LeagueType(StrEnum):
    Standard = "standard"
    SuperFlex = "superflex"


class ScoringType(StrEnum):
    PPR = "ppr"
    HalfPPR = "half_ppr"
    Standard = "standard"

    @classmethod
    def from_value(cls, value: float) -> "ScoringType":
        scoring_thresholds = {1.0: cls.PPR, 0.5: cls.HalfPPR, 0.0: cls.Standard}

        for threshold, scoring_type in scoring_thresholds.items():
            if value >= threshold:
                return scoring_type

        err = f"Invalid scoring value: {value}. Expected one of {list(scoring_thresholds.keys())}."
        raise ValueError(err)


class StatusType(StrEnum):
    PreDraft = "pre_draft"
    Drafting = "drafting"
    InSeason = "in_season"

    @classmethod
    def from_str(cls, value: str) -> "StatusType":
        try:
            return cls(value)
        except ValueError as e:
            err = f"Invalid status type: {value}"
            raise ValueError(err) from e


POS_MAP: Final[Mapping[str, str]] = {
    "PK": "K",
    "DEF": "DST",
    "D/ST": "DST",
    "RDPICK": "PICK",
    "RDP": "PICK",
    "K/P": "K",
}


class PlayerPosition(StrEnum):
    QB = "QB"
    RB = "RB"
    WR = "WR"
    TE = "TE"
    DST = "DST"
    K = "K"
    PICK = "PICK"

    @classmethod
    def from_str(cls, value: str) -> Self | None:
        # strip any leading/trailing whitespace or numbers and convert to uppercase
        value = re.sub(r"^\d+|\s+|\d+$", "", value).upper()
        value = POS_MAP.get(value, value)
        try:
            return cls(value)
        except ValueError:
            return None


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
    FA = "FA"  # Free Agent

    ARI = "ARI"
    ATL = "ATL"
    BAL = "BAL"
    BUF = "BUF"
    CAR = "CAR"
    CHI = "CHI"
    CIN = "CIN"
    CLE = "CLE"
    DAL = "DAL"
    DEN = "DEN"
    DET = "DET"
    GB = "GB"
    HOU = "HOU"
    IND = "IND"
    JAX = "JAX"
    KC = "KC"
    LAC = "LAC"
    LAR = "LAR"
    LV = "LV"
    MIA = "MIA"
    MIN = "MIN"
    NE = "NE"
    NO = "NO"
    NYG = "NYG"
    NYJ = "NYJ"
    PHI = "PHI"
    PIT = "PIT"
    SEA = "SEA"
    SF = "SF"
    TB = "TB"
    TEN = "TEN"
    WAS = "WAS"

    @classmethod
    def from_str(cls, value: str) -> Self:
        value = value.upper().strip()
        value = TEAM_MAP.get(value, value)
        return cls(value)


class Player(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("player_id"), UniqueConstraint("sleeper_id"))
    id: int | None = Field(default=None, primary_key=True)
    player_id: UUID = Field(index=True)
    first_name: str
    last_name: str
    full_name: str
    birth_date: date
    team: Team
    number: int | None
    college: str | None
    high_school: str | None
    position: PlayerPosition
    age: int
    height: int
    weight: int
    years_exp: int
    status: str | None
    active: bool
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
    __table_args__ = (UniqueConstraint("player_id", "league_type", "date"),)
    id: int | None = Field(default=None, primary_key=True)
    player_id: UUID = Field(default=None, foreign_key="player.player_id")
    league_type: LeagueType
    date: date
    value: int
    ranking_set: RankingSet
    is_pick: bool


class Pick(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("sleeper_id", "draft_id"),)
    id: int | None = Field(default=None, primary_key=True)
    sleeper_id: str = Field(foreign_key="player.sleeper_id", index=True)
    league_id: str
    draft_id: str
    round: int
    pick_no: int
    picked_by: str


class League(BaseModel):
    id: str
    league_type: LeagueType
    name: str
    team_count: int
    status: StatusType
    scoring_type: ScoringType


class SleeperRosterSettings(TypedDict):
    wins: int
    waiver_position: int
    waiver_budget_used: int
    total_moves: int
    ties: int
    losses: int
    fpts: int


class Roster(BaseModel):
    league_id: str
    owner_id: str
    roster_id: int
    name: str
    settings: SleeperRosterSettings
    starters: Sequence[int]
    players: Sequence[int]
    picks: Sequence[str]
