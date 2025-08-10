"""SleeperService will interact with the Sleeper API."""

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
    """
    Type definition for Sleeper API player data response.

    Represents the structure of player data returned from the Sleeper API,
    containing comprehensive player information including biographical data,
    physical attributes, and external service IDs.
    """

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
    injury_status: NotRequired[str | None]  # Injury status, if applicable
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
    """
    Type definition for Sleeper API roster settings data.

    Contains performance metrics and settings for a roster
    within a Sleeper fantasy football league.
    """

    wins: int
    waiver_position: int
    waiver_budget_used: int
    total_moves: int
    ties: int
    losses: int
    fpts: int


class SleeperRosterDict(TypedDict):
    """
    Type definition for Sleeper API roster data response.

    Represents the structure of roster data returned from the Sleeper API,
    containing team composition, ownership, and performance information.
    """

    taxi: None  # unused
    starters: list[str]
    settings: SleeperRosterSettings
    roster_id: int
    reserve: str | None
    players: list[str]
    player_map: dict[str, str]
    owner_id: str
    metadata: dict[str, str]  # unused
    league_id: str
    keepers: list[str]
    co_owners: list[str]  # unused


class SleeperLeagueDict(TypedDict):
    """
    Type definition for Sleeper API league data response.

    Represents the structure of league data returned from the Sleeper API,
    containing league configuration, settings, and status information.
    """

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
    """
    Type definition for Sleeper API user metadata.

    Contains optional user preferences and settings for notifications
    and other user-specific configurations.
    """

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
    """
    Type definition for Sleeper API user data response.

    Represents the structure of user data returned from the Sleeper API,
    containing user identification and display information.
    """

    user_id: str
    settings: dict[str, str] | None
    metadata: SleeperUserMetadataDict
    league_id: str
    is_owner: bool | None
    is_bot: bool
    display_name: str
    avatar: str


class SleeperTradedPickDict(TypedDict):
    """
    Type definition for Sleeper API traded pick data.

    Represents the structure of traded draft pick information,
    tracking ownership changes of future draft picks.
    """

    previous_owner_id: int
    owner_id: int
    roster_id: int
    season: str
    round: int


class SeasonMetaDict(TypedDict):
    """
    Type definition for Sleeper API season metadata.

    Contains current season information and timing data
    for the NFL season and fantasy football context.
    """

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
    """
    Type definition for Sleeper API draft settings.

    Contains draft configuration including roster slot requirements
    and draft timing settings.
    """

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
    """
    Type definition for Sleeper API draft metadata.

    Contains additional draft information including scoring type
    and descriptive information about the draft.
    """

    scoring_type: str
    name: str
    description: str


class SleeperDraftDict(TypedDict):
    """
    Type definition for Sleeper API draft data response.

    Represents the structure of draft data returned from the Sleeper API,
    containing draft configuration, status, and metadata.
    """

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
    """
    Type definition for Sleeper API draft pick metadata.

    Contains detailed information about a specific draft pick,
    including player information at the time of selection.
    """

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
    """
    Type definition for Sleeper API draft pick data response.

    Represents the structure of individual draft pick data,
    containing selection details and player information.
    """

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
    """
    Service class for interacting with the Sleeper fantasy football API.

    Provides methods to retrieve player data, league information, roster details,
    and draft information from the Sleeper platform. Handles data conversion
    from Sleeper's API format to the application's internal data models.

    Attributes
    ----------
        session: HTTP session for making API requests
        BASE_URL: Base URL for the Sleeper API

    """

    session: Final[requests.Session]
    BASE_URL: Final[str] = "https://api.sleeper.app/v1"
    __current_state: SeasonMetaDict | None = None

    # Draft configuration settings
    DEFAULT_FUTURE_YEARS: Final[int] = 3  # Number of future years to generate picks for
    DEFAULT_ROUNDS_PER_YEAR: Final[int] = 4  # Number of draft rounds per year

    def __init__(
        self,
        session: requests.Session | None = None,
        *,
        future_years: int = DEFAULT_FUTURE_YEARS,
        rounds_per_year: int = DEFAULT_ROUNDS_PER_YEAR,
    ) -> None:
        """
        Initialize the SleeperService with an optional HTTP session.

        Args:
        ----
            session: Optional HTTP session for making requests. If None, a new session is created.
            future_years: Number of future years to generate draft picks for
            rounds_per_year: Number of draft rounds per year

        """
        if session is None:
            session = requests.Session()
        self.session = session
        self.future_years = future_years
        self.rounds_per_year = rounds_per_year

    def __enter__(self) -> Self:
        """
        Enter the context manager and return the service instance.

        Returns
        -------
            Self instance for use in context manager

        """
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """
        Exit the context manager and close the session.

        Args:
        ----
            exc_type: Exception type if an exception occurred
            exc_val: Exception value if an exception occurred
            exc_tb: Exception traceback if an exception occurred

        """
        self.close()

    def close(self) -> None:
        """Close the HTTP session to free resources."""
        self.session.close()

    @staticmethod
    def convert_player_data(sleeper_id: str, player_dict: SleeperPlayerDict) -> Player | None:
        """
        Convert Sleeper API player data to internal Player model.

        Transforms player data from Sleeper's format into the application's
        Player model, handling data validation and normalization.

        Args:
        ----
            sleeper_id: The Sleeper platform ID for the player
            player_dict: Player data from Sleeper API

        Returns:
        -------
            Player model instance, or None if data is invalid or should be ignored

        """
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
    def convert_league_data(league_dict: SleeperLeagueDict, season: int) -> League | None:
        """
        Convert Sleeper API league data to internal League model.

        Transforms league data from Sleeper's format into the application's
        League model, determining league type and scoring settings.

        Args:
        ----
            league_dict: League data from Sleeper API
            season: The season year for this league

        Returns:
        -------
            League model instance, or None if data is invalid

        """
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
            name=league_dict["name"],
            season=season,
            league_type=league_type,
            team_count=league_dict["total_rosters"],
            status=StatusType.from_str(league_dict["status"]),
            scoring_type=scoring_type,
            bonus_tep=bonus_tep,
            scoring_settings=SleeperService.convert_scoring_settings(league_dict["scoring_settings"], roster_positions),
            roster_positions=roster_positions,
        )

    @staticmethod
    def convert_scoring_settings(
        scoring_settings: dict[str, float],
        roster_positions: list[PlayerPosition],
    ) -> dict[str, dict[str, float]]:
        """
        Convert Sleeper scoring settings to a categorized dictionary.

        Organizes scoring settings by category (passing, rushing, receiving, etc.)
        and provides human-readable labels for each scoring rule.

        Args:
        ----
            scoring_settings: Raw scoring settings from Sleeper API
            roster_positions: List of roster positions to determine applicable categories

        Returns:
        -------
            Dictionary organized by scoring category with labeled scoring rules

        """
        # Mapping from JSON keys to labeled names
        json_to_label = {
            "sack": "sacks",
            "fgm_40_49": "field goal made (40-49 yards)",
            "bonus_rec_te": "reception bonus - tightend",
            "pass_int": "pass intercepted",
            "pts_allow_0": "points allowed 0",
            "pass_2pt": "2-pt conversion passing",
            "st_td": "special teams touchdown",
            "def_pr_yd": "punt return yards",
            "rec_td": "receiving touchdown",
            "fgm_30_39": "field goal made (30-39 yards)",
            "fgm_50_59": "field goal made (50-59 yards)",
            "xpmiss": "point after touchdown missed",
            "rush_td_50p": "50+ yard rush touchdown bonus",
            "rush_td": "rushing touchdown",
            "def_kr_yd": "kick return yards",
            "pass_td_40p": "40+ yard pass touchdown bonus",
            "rec_2pt": "2-pt conversion receiving",
            "rush_fd": "rushing 1st down",
            "st_fum_rec": "special teams fumble recovery",
            "fgmiss": "field goal missed",
            "ff": "forced fumble",
            "rec": "reception",
            "pts_allow_14_20": "points allowed 14-20",
            "fgm_0_19": "field goal made (0-19 yards)",
            "int": "interceptions",
            "def_st_fum_rec": "special teams player fumble recovery",
            "fum_lost": "fumble lost",
            "pts_allow_1_6": "points allowed 1-6",
            "rec_fd": "receiving 1st down",
            "kr_yd": "player kick return yards",
            "fgm_60p": "field goal made (60+ yards)",
            "fgm_20_29": "field goal made (20-29 yards)",
            "xpm": "point after touchdown made",
            "pass_td_50p": "50+ yard pass touchdown bonus",
            "rec_40p": "40+ yard reception bonus",
            "rush_2pt": "2-pt conversion rushing",
            "fum_rec": "fumble recovery",
            "def_st_td": "special teams player touchdown",
            "pass_cmp_40p": "40+ yard completion bonus",
            "def_td": "defense touchdown",
            "pass_fd": "passing 1st down",
            "rec_td_40p": "40+ yard reception touchdown bonus",
            "safe": "safety",
            "pass_yd": "passing yards",
            "rec_td_50p": "50+ yard reception touchdown bonus",
            "blk_kick": "blocked kick",
            "pass_td": "passing touchdown",
            "rush_yd": "rushing yards",
            "rush_40p": "40+ yard rush bonus",
            "pr_yd": "player punt return yards",
            "pts_allow_28_34": "points allowed 28-34",
            "pts_allow_35p": "points allowed 35+",
            "fum_rec_td": "fumble recovery touchdown",
            "rec_yd": "receiving yards",
            "rush_td_40p": "40+ yard rush touchdown bonus",
            "def_st_ff": "special teams player forced fumble",
            "pts_allow_7_13": "points allowed 7-13",
            "st_ff": "special teams forced fumble",
        }

        # Define categories with their respective keys
        categories = {
            "passing": {
                "pass_yd",
                "pass_td",
                "pass_fd",
                "pass_2pt",
                "pass_int",
                "pass_cmp_40p",
                "pass_td_40p",
                "pass_td_50p",
            },
            "rushing": {
                "rush_yd",
                "rush_td",
                "rush_fd",
                "rush_2pt",
                "rush_40p",
                "rush_td_40p",
                "rush_td_50p",
            },
            "receiving": {
                "rec",
                "rec_yd",
                "rec_td",
                "rec_fd",
                "rec_2pt",
                "rec_40p",
                "rec_td_40p",
                "rec_td_50p",
                "bonus_rec_te",
            },
            "misc": {
                "fum_lost",
                "fum_rec_td",
            },
        }

        # Conditionally add categories based on roster positions
        roster_positions_set = set(roster_positions)
        if PlayerPosition.K in roster_positions_set:
            categories["kicking"] = {
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

        if PlayerPosition.DST in roster_positions_set:
            categories["dst"] = {
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

        # Process all categories with the same logic
        labeled_json = {}

        # Pre-filter scoring_settings to only include keys with values
        valid_settings = {k: v for k, v in scoring_settings.items() if v}

        for category_name, keys in categories.items():
            # Find intersection between valid settings keys and category keys
            valid_keys = keys.intersection(valid_settings)

            if valid_keys:
                category_dict = {}
                for key in valid_keys:
                    if label := json_to_label.get(key):
                        category_dict[label] = valid_settings[key]

                if category_dict:
                    labeled_json[category_name] = category_dict

        return labeled_json

    @staticmethod
    def _safe_convert_sleeper_ids(sleeper_ids: list[str]) -> list[int]:
        """
        Safely convert sleeper ID strings to integers.

        Args:
        ----
            sleeper_ids: List of sleeper ID strings from API

        Returns:
        -------
            List of valid integer IDs, skipping any invalid ones

        """
        result = []
        for sleeper_id in sleeper_ids:
            if sleeper_id and sleeper_id.isnumeric():
                try:
                    result.append(int(sleeper_id))
                except ValueError:
                    # Skip invalid IDs
                    continue
        return result

    def _process_traded_picks(
        self,
        roster_dict: SleeperRosterDict,
        traded_picks: list[SleeperTradedPickDict],
    ) -> list[str]:
        """
        Process traded picks to generate roster pick list.

        Args:
        ----
            roster_dict: Roster data from Sleeper API
            traded_picks: List of traded draft picks

        Returns:
        -------
            List of pick strings for this roster

        """
        roster_picks: list[str] = []
        if not traded_picks:
            return roster_picks

        season = self.get_current_season()
        next_undrafted_season = season + 1

        # Add picks owned by this roster
        roster_picks = [
            f"{pick['season']} Mid {get_placement(pick['round'])}"
            for pick in traded_picks
            if pick["owner_id"] == roster_dict["roster_id"] and int(pick["season"]) >= next_undrafted_season
        ]

        # Calculate lost picks
        lost_picks: set[str] = {
            f"{pick['season']} Mid {get_placement(pick['round'])}"
            for pick in traded_picks
            if pick["roster_id"] == roster_dict["roster_id"] and int(pick["season"]) >= next_undrafted_season
        }

        # Generate future draft picks based on configuration
        for season in range(next_undrafted_season, next_undrafted_season + self.future_years):
            for round_ in range(1, self.rounds_per_year + 1):
                pick = f"{season} Mid {get_placement(round_)}"
                if pick not in lost_picks:
                    roster_picks.append(pick)

        return roster_picks

    def _process_drafted_players(
        self,
        roster_dict: SleeperRosterDict,
        drafted: list[SleeperDraftPickDict],
    ) -> list[int]:
        """
        Process drafted players for this roster.

        Args:
        ----
            roster_dict: Roster data from Sleeper API
            drafted: List of drafted players

        Returns:
        -------
            List of drafted player IDs for this roster

        """
        drafted_players: list[int] = []
        if not drafted:
            return drafted_players

        for draft in drafted:
            if draft["picked_by"] == roster_dict["owner_id"]:
                player_id = draft["player_id"]
                if player_id and str(player_id).isnumeric():
                    try:
                        drafted_players.append(int(player_id))
                    except ValueError:
                        # Skip invalid player IDs
                        continue
        return drafted_players

    def convert_roster_data(
        self,
        roster_dict: SleeperRosterDict,
        user_dict: SleeperUserDict,
        traded_picks: list[SleeperTradedPickDict],
        drafted: list[SleeperDraftPickDict],
    ) -> Roster:
        """
        Convert Sleeper API roster data to internal Roster model.

        Transforms roster data from Sleeper's format into the application's
        Roster model, including traded picks and drafted players.

        Args:
        ----
            roster_dict: Roster data from Sleeper API
            user_dict: User data for the roster owner
            traded_picks: List of traded draft picks
            drafted: List of drafted players

        Returns:
        -------
            Roster model instance with converted data

        """
        starters_data = roster_dict.get("starters") or []
        players_data = roster_dict.get("players") or []

        # Safely convert sleeper IDs to integers with validation
        starters = self._safe_convert_sleeper_ids(starters_data)
        players = self._safe_convert_sleeper_ids(players_data)

        name = user_dict["display_name"]

        # Process traded picks
        roster_picks = self._process_traded_picks(roster_dict, traded_picks)

        # Process drafted players
        drafted_players = self._process_drafted_players(roster_dict, drafted)
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
        """
        Get the current NFL season state from Sleeper API.

        Retrieves and caches the current season metadata including
        week, season type, and other timing information.

        Returns
        -------
            Season metadata dictionary from Sleeper API

        """
        if self.__current_state:
            return self.__current_state

        url = f"{self.BASE_URL}/state/nfl"
        page = self.session.get(url)
        meta_data: SeasonMetaDict = page.json()
        return meta_data

    def get_current_season(self) -> int:
        """
        Get the current NFL season year from Sleeper API.

        Returns
        -------
            The current NFL season as an integer year

        """
        state = self._current_state()
        return int(state["season"])

    def get_players(self) -> Iterable[Player]:
        """
        Get all NFL players from Sleeper API.

        Retrieves the complete player database from Sleeper and converts
        each player to the internal Player model format.

        Returns
        -------
            Iterable of Player model instances

        """
        url = f"{self.BASE_URL}/players/nfl"
        page = self.session.get(url)
        sleeper_players: Mapping[str, SleeperPlayerDict] = page.json()
        return (
            player
            for sleeper_id, player_dict in sleeper_players.items()
            if (player := self.convert_player_data(sleeper_id, player_dict))
        )

    def get_sleeper_id(self, username: str) -> str | None:
        """
        Get the Sleeper user ID for a given username.

        Args:
        ----
            username: The Sleeper username to look up

        Returns:
        -------
            The Sleeper user ID, or None if user not found

        """
        url = f"{self.BASE_URL}/user/{username}/"
        page = self.session.get(url)
        user: dict[str, str] | None
        if user := page.json():
            return str(user["user_id"])
        return None

    def get_leagues(self, user_id: str, *, season: int | None = None) -> Iterable[League]:
        """
        Get all leagues for a user from Sleeper API.

        Retrieves all leagues that a user is participating in for a given season
        and converts them to the internal League model format.

        Args:
        ----
            user_id: The Sleeper user ID
            season: The season year (defaults to current season)

        Returns:
        -------
            Iterable of League model instances

        """
        if not season:
            season = self.get_current_season()
        url = f"{self.BASE_URL}/user/{user_id}/leagues/nfl/{season}"
        page = self.session.get(url)
        leagues: list[SleeperLeagueDict] = page.json()
        return (league for league_dict in leagues if (league := self.convert_league_data(league_dict, season)))

    def get_drafts(
        self,
        user_id: str,
        *,
        season: int | None = None,
        draft_status: Container[str] = frozenset(["complete"]),
    ) -> Iterable[SleeperDraftDict]:
        """
        Get all drafts for a user from Sleeper API.

        Retrieves draft information for all leagues a user participated in
        for a given season, filtered by draft status.

        Args:
        ----
            user_id: The Sleeper user ID
            season: The season year (defaults to current season)
            draft_status: Set of draft statuses to include (defaults to "complete")

        Returns:
        -------
            Iterable of draft dictionaries matching the status filter

        """
        if not season:
            season = self.get_current_season()
        url = f"{self.BASE_URL}/user/{user_id}/drafts/nfl/{season}"
        page = self.session.get(url)
        drafts: list[SleeperDraftDict] = page.json()
        return (draft for draft in drafts if draft["status"] in draft_status)

    def get_rosters(
        self,
        league_id: str,
        *,
        include_picks: bool = True,
        include_drafted: bool = True,
    ) -> Sequence[Roster]:
        """
        Get all rosters for a league from Sleeper API.

        Retrieves roster information for all teams in a league, optionally
        including traded picks and drafted players.

        Args:
        ----
            league_id: The Sleeper league ID
            include_picks: Whether to include traded draft picks
            include_drafted: Whether to include drafted players

        Returns:
        -------
            Sequence of Roster model instances for all teams in the league

        """
        url = f"{self.BASE_URL}/league/{league_id}/rosters"
        page = self.session.get(url)
        rosters: list[SleeperRosterDict] = page.json()

        url = f"{self.BASE_URL}/league/{league_id}/users"
        page = self.session.get(url)
        users: list[SleeperUserDict] = page.json()

        picks: list[SleeperTradedPickDict] = []
        if include_picks:
            drafts_url = f"{self.BASE_URL}/league/{league_id}/traded_picks"
            drafts_response = self.session.get(drafts_url)
            picks = drafts_response.json()

        drafted: list[SleeperDraftPickDict] = []
        if include_drafted:
            drafts_url = f"{self.BASE_URL}/league/{league_id}/drafts"
            drafts_response = self.session.get(drafts_url)
            drafts: list[SleeperDraftDict] = drafts_response.json()

            draft_url = f"{self.BASE_URL}/draft/{drafts[0]['draft_id']}/picks"
            draft_response = self.session.get(draft_url)
            drafted = draft_response.json()

        def get_user(roster: SleeperRosterDict) -> SleeperUserDict:
            """
            Find user data for a roster owner.

            Args:
            ----
                roster: The roster dictionary

            Returns:
            -------
                User dictionary for the roster owner

            Raises:
            ------
                ValueError: If the user is not found

            """
            for user in users:
                if user["user_id"] == roster["owner_id"]:
                    return user

            owner_id = roster["owner_id"]
            err = f"User {owner_id} not found"
            raise ValueError(err)

        return tuple(self.convert_roster_data(roster, get_user(roster), picks, drafted) for roster in rosters if roster)
