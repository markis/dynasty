from collections.abc import Iterable, Mapping, Sequence
from types import TracebackType
from typing import Final, NotRequired, Self, TypedDict

import requests

from dynasty.models import League, LeagueType, Player, PlayerPosition, Roster, Team
from dynasty.util import generate_id, get_date, get_height, get_placement

CURRENT_YEAR = 2024
SLEEPER_IDS_TO_IGNORE = {
    "4634",  # not "Kenneth Walker III"
    "232",  # not "Frank Gore Jr"
    "748",  # not "Mike Williams"
}


class SleeperPlayerDict(TypedDict):
    player_id: str
    first_name: str
    last_name: str
    full_name: str
    search_first_name: str
    search_last_name: str
    search_full_name: str
    search_rank: int
    hashtag: str
    birth_date: str | None
    team: str
    number: int
    sport: str
    college: str
    high_school: str
    position: str
    fantasy_positions: list[str]
    depth_chart_position: str
    depth_chart_order: int
    age: int
    height: str
    weight: str
    years_exp: int
    status: str
    active: bool
    fantasy_data_id: int
    sportradar_id: str
    rotowire_id: int
    swish_id: int
    stats_id: int
    rotoworld_id: int
    oddsjam_id: str
    espn_id: int
    gsis_id: str
    yahoo_id: NotRequired[int | None]


class SleeperRosterSettings(TypedDict):
    wins: int
    waiver_position: int
    waiver_budget_used: int
    total_moves: int
    ties: int
    losses: int
    fpts: int


class SleeperRosterDict(TypedDict):
    # taxi: None
    starters: list[str]
    settings: SleeperRosterSettings
    roster_id: int
    reserve: str | None
    players: list[str]
    # player_map: dict[str, str]
    owner_id: str
    # metadata: dict[str, str]
    league_id: str
    keepers: list[str]
    # co_owners: list[str]


class SleeperLeagueDict(TypedDict):
    last_transaction_id: None
    total_rosters: int
    roster_positions: list[str]
    loser_bracket_id: None
    bracket_id: None
    group_id: None
    previous_league_id: None
    league_id: str
    draft_id: str
    last_read_id: str
    last_pinned_message_id: None
    last_message_time: int
    last_message_text_map: None
    last_message_attachment: None
    last_author_is_bot: bool
    last_author_id: str
    last_author_display_name: str
    last_author_avatar: None
    display_order: int
    last_message_id: str
    scoring_settings: dict[str, float]
    sport: str
    season_type: str
    season: str
    shard: int
    company_id: None
    avatar: None
    settings: dict[str, str]
    status: str
    name: str


class SleeperUserMetadataDict(TypedDict, total=False):
    mention_pn: str
    archived: str | None
    allow_pn: str
    team_name: str | None
    avatar: str | None
    user_message_pn: str | None
    transaction_waiver: str | None
    transaction_trade: str | None
    transaction_free_agent: str | None
    transaction_commissioner: str | None
    trade_block_pn: str | None
    team_name_update: str | None
    player_nickname_update: str | None
    player_like_pn: str | None
    mascot_message: str | None
    league_report_pn: str | None
    allow_sms: str | None


class SleeperUserDict(TypedDict):
    user_id: str
    settings: dict[str, str] | None
    metadata: SleeperUserMetadataDict
    league_id: str
    is_owner: bool | None
    is_bot: bool
    display_name: str
    avatar: str


class SleeperTradedPickDict(TypedDict):
    previous_owner_id: int
    owner_id: int
    roster_id: int
    season: str
    round: int


class SleeperService:
    """Service for getting Sleeper api."""

    session: Final[requests.Session]
    BASE_URL: Final[str] = "https://api.sleeper.app/v1"

    def __init__(self, session: requests.Session | None = None) -> None:
        if session is None:
            session = requests.Session()
        self.session = session

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        self.session.close()

    @staticmethod
    def convert_player_data(sleeper_id: str, player_dict: SleeperPlayerDict) -> Player | None:
        """Convert Sleeper player data to Player model"""
        if sleeper_id in SLEEPER_IDS_TO_IGNORE:
            return None
        if not (full_name := player_dict.get("full_name")):
            return None
        if not (birth_date := get_date(player_dict["birth_date"])):
            return None

        team = Team.from_str(player_dict["team"]) if player_dict["team"] else Team.FA
        height = get_height(player_dict["height"])
        weight = int(player_dict["weight"]) if player_dict["weight"] else None
        position = PlayerPosition.from_str(player_dict["position"]) if player_dict["position"] else None
        if not position or not height or not weight:
            return None

        return Player(
            player_id=generate_id(full_name),
            first_name=player_dict["first_name"],
            last_name=player_dict["last_name"],
            full_name=full_name,
            birth_date=birth_date,
            team=team,
            number=player_dict["number"],
            college=player_dict["college"],
            high_school=player_dict["high_school"],
            position=position,
            age=player_dict["age"],
            height=height,
            weight=weight,
            years_exp=player_dict["years_exp"],
            status=player_dict["status"],
            active=player_dict["active"],
            sleeper_id=sleeper_id,
            fantasy_data_id=player_dict["fantasy_data_id"],
            sportradar_id=player_dict["sportradar_id"],
            rotowire_id=player_dict["rotowire_id"],
            swish_id=player_dict["swish_id"],
            stats_id=player_dict["stats_id"],
            rotoworld_id=player_dict["rotoworld_id"],
            oddsjam_id=player_dict["oddsjam_id"],
            espn_id=player_dict["espn_id"],
            gsis_id=player_dict["gsis_id"],
            yahoo_id=player_dict.get("yahoo_id"),
        )

    @staticmethod
    def convert_league_data(league_dict: SleeperLeagueDict) -> League | None:
        """Convert Sleeper league data to League model"""
        is_super_flex = "SUPER_FLEX" in league_dict["roster_positions"]
        league_type: LeagueType = LeagueType.SuperFlex if is_super_flex else LeagueType.Standard

        return League(
            id=league_dict["league_id"],
            league_type=league_type,
            name=league_dict["name"],
            team_count=league_dict["total_rosters"],
        )

    @staticmethod
    def convert_roster_data(
        roster_dict: SleeperRosterDict, user_dict: SleeperUserDict, traded_picks: list[SleeperTradedPickDict]
    ) -> Roster:
        """Convert Sleeper league data to League model"""
        starters = [int(sleeper_id) for sleeper_id in roster_dict["starters"] if sleeper_id and sleeper_id.isnumeric()]
        players = [int(sleeper_id) for sleeper_id in roster_dict["players"] if sleeper_id and sleeper_id.isnumeric()]
        name = user_dict["display_name"]

        roster_picks: list[str] = []
        if traded_picks:
            # TODO: year/round should come from the league settings
            next_undrafted_season = CURRENT_YEAR + 1
            roster_picks = [
                f"{pick['season']} Mid {get_placement(pick['round'])}"
                for pick in traded_picks
                if pick["owner_id"] == roster_dict["roster_id"] and int(pick["season"]) >= next_undrafted_season
            ]
            lost_picks: set[str] = {
                f"{pick['season']} Mid {get_placement(pick['round'])}"
                for pick in traded_picks
                if pick["roster_id"] == roster_dict["roster_id"] and int(pick["season"]) >= next_undrafted_season
            }

            # TODO: year/round should come from the league settings
            for season in range(next_undrafted_season, next_undrafted_season + 3):
                for round_ in range(1, 4):
                    pick = f"{season} Mid {get_placement(round_)}"
                    if pick not in lost_picks:
                        roster_picks.append(pick)

        return Roster(
            league_id=roster_dict["league_id"],
            name=name,
            owner_id=roster_dict["owner_id"],
            settings=roster_dict["settings"],
            roster_id=roster_dict["roster_id"],
            starters=starters,
            players=players,
            picks=roster_picks,
        )

    def get_players(self) -> Iterable[Player]:
        url = f"{self.BASE_URL}/players/nfl"
        page = self.session.get(url)
        sleeper_players: Mapping[str, SleeperPlayerDict] = page.json()

        for sleeper_id, player_dict in sleeper_players.items():
            player = self.convert_player_data(sleeper_id, player_dict)
            if player:
                yield player

    def get_sleeper_id(self, username: str) -> str | None:
        url = f"{self.BASE_URL}/user/{username}/"
        page = self.session.get(url)
        user: dict[str, str] | None = page.json()
        if not user:
            return None
        return user["user_id"]

    def get_leagues(self, user_id: str) -> list[League]:
        url = f"{self.BASE_URL}/user/{user_id}/leagues/nfl/{CURRENT_YEAR}"
        page = self.session.get(url)
        leagues: list[SleeperLeagueDict] = page.json()
        result: list[League] = []
        for league_dict in leagues:
            league = self.convert_league_data(league_dict)
            if league:
                result.append(league)

        return result

    def get_rosters(self, league_id: str, *, include_picks: bool = True) -> Sequence[Roster]:
        url = f"{self.BASE_URL}/league/{league_id}/rosters"
        page = self.session.get(url)
        rosters: list[SleeperRosterDict] = page.json()

        url = f"{self.BASE_URL}/league/{league_id}/users"
        page = self.session.get(url)
        users: list[SleeperUserDict] = page.json()

        picks = []
        if include_picks:
            picks_url = f"{self.BASE_URL}/league/{league_id}/traded_picks"
            picks_response = self.session.get(picks_url)
            picks: list[SleeperTradedPickDict] = picks_response.json()

        def get_user(roster: SleeperRosterDict) -> SleeperUserDict:
            for user in users:
                if user["user_id"] == roster["owner_id"]:
                    return user

            owner_id = roster["owner_id"]
            err = f"User {owner_id} not found"
            raise ValueError(err)

        return tuple(self.convert_roster_data(roster, get_user(roster), picks) for roster in rosters if roster)
