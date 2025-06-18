from collections.abc import Container, Iterable, Mapping, Sequence
from types import TracebackType
from typing import Final, Literal, NotRequired, Self, TypedDict

import requests

from dynasty.models import (
    InjuryStatus,
    League,
    LeagueType,
    Player,
    PlayerPosition,
    Roster,
    ScoringType,
    StatusType,
    Team,
    TEPScoringType,
)
from dynasty.util import generate_id, get_date, get_height, get_placement

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
    status: Literal["pre_draft", "drafting", "in_season"]
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


class SeasonMetaDict(TypedDict):
    week: int
    season_type: Literal["pre", "post", "regular"]
    season_start_date: str  # ISO date string, e.g., "2020-09-10"
    season: str
    previous_season: str
    leg: int
    league_season: str
    league_create_season: str
    display_week: int


class SleeperDraftSettingsDict(TypedDict):
    teams: int
    slots_wr: int
    slots_te: int
    slots_rb: int
    slots_qb: int
    slots_k: int
    slots_flex: int
    slots_def: int
    slots_bn: int
    rounds: int
    pick_timer: int


class SleeperDraftMetadataDict(TypedDict):
    scoring_type: str
    name: str
    description: str


class SleeperDraftDict(TypedDict):
    type: str
    status: str
    start_time: int
    sport: str
    settings: SleeperDraftSettingsDict
    season_type: str
    season: str
    metadata: SleeperDraftMetadataDict
    league_id: str
    last_picked: int
    last_message_time: int
    last_message_id: str
    draft_order: list[str] | None
    draft_id: str
    creators: list[str] | None
    created: int


class SleeperDraftPickMetadataDict(TypedDict):
    team: str
    status: str
    sport: str
    position: str
    player_id: str
    number: str
    news_updated: str
    last_name: str
    injury_status: str
    first_name: str


class SleeperDraftPickDict(TypedDict):
    player_id: str
    picked_by: str
    roster_id: str
    round: int | None
    draft_slot: int | None
    pick_no: int
    metadata: SleeperDraftPickMetadataDict
    is_keeper: bool | None
    draft_id: str


class SleeperService:
    """Service for getting Sleeper api."""

    session: Final[requests.Session]
    BASE_URL: Final[str] = "https://api.sleeper.app/v1"
    __current_state: SeasonMetaDict | None = None

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

        injury_status = None
        if injury_status_val := player_dict.get("injury_status"):
            injury_status = InjuryStatus.from_str(injury_status_val)

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
            injury_status=injury_status,
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

        rec = league_dict["scoring_settings"]["rec"]
        bonus_rec_te = league_dict["scoring_settings"].get("bonus_rec_te", 0.0)
        scoring_type = ScoringType.from_value(rec)
        bonus_tep = TEPScoringType.from_value(bonus_rec_te)

        roster_positions = [
            pos for pos_str in league_dict["roster_positions"] if (pos := PlayerPosition.from_str(pos_str))
        ]

        return League(
            id=league_dict["league_id"],
            league_type=league_type,
            name=league_dict["name"],
            team_count=league_dict["total_rosters"],
            status=StatusType.from_str(league_dict["status"]),
            scoring_type=scoring_type,
            bonus_tep=bonus_tep,
            scoring_settings=SleeperService.convert_scoring_settings(league_dict["scoring_settings"], roster_positions),
            roster_positions=roster_positions,
        )

    @staticmethod
    def convert_scoring_settings(
        scoring_settings: dict[str, float], roster_positions: list[PlayerPosition]
    ) -> dict[str, dict[str, float]]:
        passing_keys = {
            "pass_yd",
            "pass_td",
            "pass_fd",
            "pass_2pt",
            "pass_int",
            "pass_cmp_40p",
            "pass_td_40p",
            "pass_td_50p",
        }
        rushing_keys = {
            "rush_yd",
            "rush_td",
            "rush_fd",
            "rush_2pt",
            "rush_40p",
            "rush_td_40p",
            "rush_td_50p",
        }
        receiving_keys = {
            "rec",
            "rec_yd",
            "rec_td",
            "rec_fd",
            "rec_2pt",
            "rec_40p",
            "rec_td_40p",
            "rec_td_50p",
            "bonus_rec_te",
        }
        kicking_keys = {
            "fgm_0_19",
            "fgm_20_29",
            "fgm_30_39",
            "fgm_40_49",
            "fgm_50_59",
            "fgm_60p",
            "xpm",
            "xpmiss",
            "fgmiss",
        }
        defense_keys = {
            "def_td",
            "pts_allow_0",
            "pts_allow_1_6",
            "pts_allow_7_13",
            "pts_allow_14_20",
            "pts_allow_21_27",
            "pts_allow_28_34",
            "pts_allow_35p",
            "sack",
            "int",
            "fum_rec",
            "safe",
            "ff",
            "blk_kick",
            "st_td",
            "st_ff",
            "st_fum_rec",
            "def_pr_yd",
            "def_kr_yd",
            "def_st_td",
            "def_st_ff",
            "def_st_fum_rec",
            "fum_rec_td",
            "fum",
        }
        misc_keys = {
            "fum_lost",
            "fum_rec_td",
        }

        # Mapping from JSON keys to labeled names
        json_to_label = {
            "sack": "sacks",
            "fgm_40_49": "fg made (40-49 yards)",
            "bonus_rec_te": "reception bonus - te",
            "pass_int": "pass intercepted",
            "pts_allow_0": "points allowed 0",
            "pass_2pt": "2-pt conversion passing",
            "st_td": "special teams td",
            "def_pr_yd": "punt return yards",
            "rec_td": "receiving td",
            "fgm_30_39": "fg made (30-39 yards)",
            "fgm_50_59": "fg made (50-59 yards)",
            "xpmiss": "pat missed",
            "rush_td_50p": "50+ yard rush td bonus",
            "rush_td": "rushing td",
            "def_kr_yd": "kick return yards",
            "pass_td_40p": "40+ yard pass td bonus",
            "rec_2pt": "2-pt conversion receiving",
            "rush_fd": "rushing 1st down",
            "st_fum_rec": "special teams fumble recovery",
            "fgmiss": "fg missed",
            "ff": "forced fumble",
            "rec": "reception",
            "pts_allow_14_20": "points allowed 14-20",
            "fgm_0_19": "fg made (0-19 yards)",
            "int": "interceptions",
            "def_st_fum_rec": "special teams player fumble recovery",
            "fum_lost": "fumble lost",
            "pts_allow_1_6": "points allowed 1-6",
            "rec_fd": "receiving 1st down",
            "kr_yd": "player kick return yards",
            "fgm_60p": "fg made (60+ yards)",
            "fgm_20_29": "fg made (20-29 yards)",
            "xpm": "pat made",
            "pass_td_50p": "50+ yard pass td bonus",
            "rec_40p": "40+ yard reception bonus",
            "rush_2pt": "2-pt conversion rushing",
            "fum_rec": "fumble recovery",
            "def_st_td": "special teams player td",
            "pass_cmp_40p": "40+ yard completion bonus",
            "def_td": "defense td",
            "pass_fd": "passing 1st down",
            "rec_td_40p": "40+ yard reception td bonus",
            "safe": "safety",
            "pass_yd": "passing yards",
            "rec_td_50p": "50+ yard reception td bonus",
            "blk_kick": "blocked kick",
            "pass_td": "passing td",
            "rush_yd": "rushing yards",
            "rush_40p": "40+ yard rush bonus",
            "pr_yd": "player punt return yards",
            "pts_allow_28_34": "points allowed 28-34",
            "pts_allow_35p": "points allowed 35+",
            "fum_rec_td": "fumble recovery td",
            "rec_yd": "receiving yards",
            "rush_td_40p": "40+ yard rush td bonus",
            "def_st_ff": "special teams player forced fumble",
            "pts_allow_7_13": "points allowed 7-13",
            "st_ff": "special teams forced fumble",
        }

        labeled_json: dict[str, dict[str, float]] = {}

        labeled_json["passing"] = passing = {}
        for key in passing_keys:
            label = json_to_label.get(key)
            if label and (value := scoring_settings.get(key)):
                passing[label] = value

        labeled_json["receiving"] = receiving = {}
        for key in receiving_keys:
            label = json_to_label.get(key)
            if label and (value := scoring_settings.get(key)):
                receiving[label] = value

        labeled_json["rushing"] = rushing = {}
        for key in rushing_keys:
            label = json_to_label.get(key)
            if label and (value := scoring_settings.get(key)):
                rushing[label] = value

        # Remove kicking stats if K not in roster
        if PlayerPosition.K in roster_positions:
            labeled_json["kicking"] = kicking = {}
            for key in kicking_keys:
                label = json_to_label.get(key)
                if label and (value := scoring_settings.get(key)):
                    kicking[label] = value

        # Remove defense/special teams if DST not in roster
        if PlayerPosition.DST in roster_positions:
            labeled_json["dst"] = dst = {}
            for key in defense_keys:
                label = json_to_label.get(key)
                if label and (value := scoring_settings.get(key)):
                    dst[label] = value

        labeled_json["misc"] = misc = {}
        for key in misc_keys:
            label = json_to_label.get(key)
            if label and (value := scoring_settings.get(key)):
                misc[label] = value

        # test = {
        #     "passing": {
        #         "2-pt conversion passing": 2.0,
        #         "passing yards": 0.04,
        #         "pass intercepted": -2.0,
        #         "passing td": 4.0,
        #     },
        #     "receiving": {
        #         "receiving 1st down": 0.5,
        #         "reception bonus - te": 1.0,
        #         "receiving yards": 0.1,
        #         "receiving td": 6.0,
        #         "2-pt conversion receiving": 2.0,
        #         "reception": 1.0,
        #     },
        #     "rushing": {
        #         "2-pt conversion rushing": 2.0,
        #         "rushing 1st down": 0.5,
        #         "rushing td": 6.0,
        #         "rushing yards": 0.1,
        #     },
        #     "misc": {"fumble lost": -1.0, "fumble recovery td": 6.0},
        # }

        return labeled_json

    def convert_roster_data(
        self,
        roster_dict: SleeperRosterDict,
        user_dict: SleeperUserDict,
        traded_picks: list[SleeperTradedPickDict],
        drafted: list[SleeperDraftPickDict],
    ) -> Roster:
        """Convert Sleeper league data to League model"""
        starters_data = roster_dict.get("starters") or []
        players_data = roster_dict.get("players") or []
        starters = [int(sleeper_id) for sleeper_id in starters_data if sleeper_id and sleeper_id.isnumeric()]
        players = [int(sleeper_id) for sleeper_id in players_data if sleeper_id and sleeper_id.isnumeric()]
        name = user_dict["display_name"]

        roster_picks: list[str] = []
        if traded_picks:
            season = self.get_current_season()
            next_undrafted_season = season + 1
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

        drafted_players: list[int] = []
        if drafted:
            drafted_players = [
                int(draft["player_id"]) for draft in drafted if draft["picked_by"] == roster_dict["owner_id"]
            ]
            players.extend(drafted_players)

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

    def _current_state(self) -> SeasonMetaDict:
        if self.__current_state:
            return self.__current_state

        url = f"{self.BASE_URL}/state/nfl"
        page = self.session.get(url)
        meta_data: SeasonMetaDict = page.json()
        return meta_data

    def get_current_season(self) -> int:
        state = self._current_state()
        return int(state["season"])

    def get_players(self) -> Iterable[Player]:
        url = f"{self.BASE_URL}/players/nfl"
        page = self.session.get(url)
        sleeper_players: Mapping[str, SleeperPlayerDict] = page.json()
        return (
            player
            for sleeper_id, player_dict in sleeper_players.items()
            if (player := self.convert_player_data(sleeper_id, player_dict))
        )

    def get_sleeper_id(self, username: str) -> str | None:
        url = f"{self.BASE_URL}/user/{username}/"
        page = self.session.get(url)
        user: dict[str, str] | None
        if user := page.json():
            return user["user_id"]
        return None

    def get_leagues(self, user_id: str, *, season: int | None = None) -> Iterable[League]:
        if not season:
            season = self.get_current_season()
        url = f"{self.BASE_URL}/user/{user_id}/leagues/nfl/{season}"
        page = self.session.get(url)
        leagues: list[SleeperLeagueDict] = page.json()
        return (league for league_dict in leagues if (league := self.convert_league_data(league_dict)))

    def get_drafts(
        self, user_id: str, *, season: int | None = None, draft_status: Container[str] = frozenset(["complete"])
    ) -> Iterable[SleeperDraftDict]:
        if not season:
            season = self.get_current_season()
        url = f"{self.BASE_URL}/user/{user_id}/drafts/nfl/{season}"
        page = self.session.get(url)
        drafts: list[SleeperDraftDict] = page.json()
        return (draft for draft in drafts if draft["status"] in draft_status)

    def get_rosters(
        self, league_id: str, *, include_picks: bool = True, include_drafted: bool = True
    ) -> Sequence[Roster]:
        url = f"{self.BASE_URL}/league/{league_id}/rosters"
        page = self.session.get(url)
        rosters: list[SleeperRosterDict] = page.json()

        url = f"{self.BASE_URL}/league/{league_id}/users"
        page = self.session.get(url)
        users: list[SleeperUserDict] = page.json()

        picks = []
        if include_picks:
            drafts_url = f"{self.BASE_URL}/league/{league_id}/traded_picks"
            drafts_response = self.session.get(drafts_url)
            picks: list[SleeperTradedPickDict] = drafts_response.json()

        drafted: list[SleeperDraftPickDict] = []
        if include_drafted:
            drafts_url = f"{self.BASE_URL}/league/{league_id}/drafts"
            drafts_response = self.session.get(drafts_url)
            drafts: list[SleeperDraftDict] = drafts_response.json()

            draft_url = f"{self.BASE_URL}/draft/{drafts[0]['draft_id']}/picks"
            draft_response = self.session.get(draft_url)
            drafted = draft_response.json()

        def get_user(roster: SleeperRosterDict) -> SleeperUserDict:
            for user in users:
                if user["user_id"] == roster["owner_id"]:
                    return user

            owner_id = roster["owner_id"]
            err = f"User {owner_id} not found"
            raise ValueError(err)

        return tuple(self.convert_roster_data(roster, get_user(roster), picks, drafted) for roster in rosters if roster)
