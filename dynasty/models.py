import re
from collections.abc import Mapping
from datetime import date
from enum import IntEnum, StrEnum
from typing import Final, Self
from uuid import UUID

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class LeagueType(IntEnum):
    Standard = 1
    SuperFlex = 2


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
    __table_args__ = (UniqueConstraint("player_id"),)
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
    sleeper_id: str | None = Field(index=True)
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


class League(SQLModel):
    id: str
    league_type: LeagueType
    name: str
