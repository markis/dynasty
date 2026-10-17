"""Tests for the KeepTradeCut rankings service."""

import json
from datetime import UTC, date, datetime
from typing import Final

import pytest
from bs4 import BeautifulSoup

from dynasty.models import LeagueType
from dynasty.service.keeptradecut import KTCService
from dynasty.service.soup import SoupService

PLAYER: Final = {
    "playerName": "Jahmyr Gibbs",
    "playerID": 1415,
    "slug": "jahmyr-gibbs-1415",
    "position": "RB",
    "positionID": 2,
    "team": "DET",
    "rookie": False,
    "age": 24.5,
    "heightFeet": 5,
    "heightInches": 9,
    "weight": 200,
    "seasonsExperience": 3,
    "pickRound": 1,
    "pickNum": 12,
    "isFeatured": True,
    "isStartSitFeatured": False,
    "isTrending": False,
    "isDevyReturningToSchool": False,
    "isDevyYearDecrement": False,
    "oneQBValues": {
        "value": 9998,
        "rank": 2,
        "positionalRank": 1,
        "overallTier": 1,
        "positionalTier": 1,
        "startSitValue": 0,
        "overallTrend": 0,
        "positionalTrend": 0,
        "overall7DayTrend": 0,
        "positional7DayTrend": 0,
        "kept": 0,
        "traded": 0,
        "cut": 0,
        "diff": 0,
        "isOutThisWeek": False,
        "tep": {"value": 9998},
        "ttep": {"value": 9998},
        "tetep": {"value": 9998},
    },
    "superflexValues": {
        "value": 10500,
        "rank": 2,
        "positionalRank": 1,
        "overallTier": 1,
        "positionalTier": 1,
        "startSitValue": 0,
        "overallTrend": 0,
        "positionalTrend": 0,
        "overall7DayTrend": 0,
        "positional7DayTrend": 0,
        "kept": 0,
        "traded": 0,
        "cut": 0,
        "diff": 0,
        "isOutThisWeek": False,
        "tep": {"value": 10500},
        "ttep": {"value": 10500},
        "tetep": {"value": 10500},
    },
    "number": 26,
    "teamLongName": "Detroit Lions",
    "birthday": "2000-03-30",
    "draftYear": 2023,
    "college": "Alabama",
    "byeWeek": 5,
}


def page(scripts: list[tuple[dict[str, str], str]]) -> BeautifulSoup:
    """
    Build an HTML document with the given script tags.

    Args:
    ----
        scripts: List of (attributes, text) tuples for each script tag.

    Returns:
    -------
        Parsed BeautifulSoup document.

    """
    parts = ["<html><body>"]
    for attrs, text in scripts:
        attr_str = " ".join(f'{k}="{v}"' for k, v in attrs.items())
        parts.append(f"<script {attr_str}>{text}</script>")
    parts.append("</body></html>")
    return BeautifulSoup("".join(parts), "html.parser")


class FakeSoupService(SoupService):
    """SoupService that serves canned HTML pages instead of HTTP."""

    def __init__(self, pages: dict[str, BeautifulSoup]) -> None:
        """Initialize with a mapping of URL to parsed page."""
        super().__init__()
        self._pages = pages

    def get(self, url: str) -> BeautifulSoup:
        """Return the canned page for the given URL."""
        return self._pages[url]


def service(pages: dict[str, BeautifulSoup]) -> KTCService:
    """Build a KTCService backed by canned pages."""
    return KTCService(FakeSoupService(pages))


def test_get_data_from_page_new_json_element_format() -> None:
    """Variables assigned via JSON.parse(document.getElementById(...)) resolve."""
    pages = {
        "https://keeptradecut.com/dynasty-rankings?format=1": page(
            [
                # KeepTradeCut's current format: raw JSON in an
                # application/json script element, referenced by a later script.
                ({"type": "application/json", "id": "ktc-players"}, json.dumps([PLAYER])),
                (
                    {"type": "text/javascript"},
                    "var leagueType = 1;\nvar playersArray = JSON.parse(document.getElementById('ktc-players').textContent);",
                ),
            ]
        )
    }
    data = service(pages)._get_data_from_page("https://keeptradecut.com/dynasty-rankings?format=1", "playersArray")
    assert data is not None
    assert json.loads(data) == [PLAYER]


def test_get_data_from_page_new_format_double_quotes() -> None:
    """The JSON.parse reference works with double-quoted element ids."""
    pages = {
        "https://keeptradecut.com/dynasty-rankings?format=1": page(
            [
                ({"type": "application/json", "id": "ktc-players"}, json.dumps([PLAYER])),
                (
                    {"type": "text/javascript"},
                    'var playersArray = JSON.parse(document.getElementById("ktc-players").textContent);',
                ),
            ]
        )
    }
    data = service(pages)._get_data_from_page("https://keeptradecut.com/dynasty-rankings?format=1", "playersArray")
    assert data is not None
    assert json.loads(data) == [PLAYER]


def test_get_data_from_page_legacy_inline_format() -> None:
    """Legacy format: a literal JSON array assigned directly to the variable."""
    pages = {
        "https://keeptradecut.com/dynasty-rankings?format=1": page(
            [
                # An unrelated first script, then the legacy literal in a later script.
                ({"type": "text/javascript"}, "var leagueType = 1;"),
                ({"type": "text/javascript"}, f"var playersArray = {json.dumps([PLAYER])};"),
            ]
        )
    }
    data = service(pages)._get_data_from_page("https://keeptradecut.com/dynasty-rankings?format=1", "playersArray")
    assert data is not None
    assert json.loads(data) == [PLAYER]


def test_get_data_from_page_missing_variable_returns_none() -> None:
    """A page without the requested variable returns None instead of raising."""
    pages = {
        "https://keeptradecut.com/dynasty-rankings?format=1": page(
            [({"type": "text/javascript"}, "var leagueType = 1;")]
        )
    }
    assert (
        service(pages)._get_data_from_page("https://keeptradecut.com/dynasty-rankings?format=1", "playersArray") is None
    )


def test_get_data_from_page_missing_json_element_returns_none() -> None:
    """A JSON.parse reference to a missing element returns None."""
    pages = {
        "https://keeptradecut.com/dynasty-rankings?format=1": page(
            [
                (
                    {"type": "text/javascript"},
                    "var playersArray = JSON.parse(document.getElementById('ktc-players').textContent);",
                )
            ]
        )
    }
    assert (
        service(pages)._get_data_from_page("https://keeptradecut.com/dynasty-rankings?format=1", "playersArray") is None
    )


def _today() -> date:
    return datetime.now(UTC).date()


def test_get_todays_rankings_new_format() -> None:
    """Rankings are extracted and converted for the current page format."""
    pages = {
        "https://keeptradecut.com/dynasty-rankings?format=1": page(
            [
                ({"type": "application/json", "id": "ktc-players"}, json.dumps([PLAYER])),
                (
                    {"type": "text/javascript"},
                    "var playersArray = JSON.parse(document.getElementById('ktc-players').textContent);",
                ),
            ]
        ),
        "https://keeptradecut.com/dynasty-rankings?format=2": page(
            [
                ({"type": "application/json", "id": "ktc-players"}, json.dumps([PLAYER])),
                (
                    {"type": "text/javascript"},
                    "var playersArray = JSON.parse(document.getElementById('ktc-players').textContent);",
                ),
            ]
        ),
    }
    with service(pages) as svc:
        standard = list(svc.get_todays_rankings(LeagueType.Standard))
        superflex = list(svc.get_todays_rankings(LeagueType.SuperFlex))

    assert len(standard) == 1
    assert standard[0].value == 9998
    assert standard[0].date == _today()
    assert len(superflex) == 1
    assert superflex[0].value == 10500


def test_get_todays_rankings_includes_url_in_error() -> None:
    """The failure message names the page URL to speed up diagnosis."""
    pages = {
        "https://keeptradecut.com/dynasty-rankings?format=1": page(
            [({"type": "text/javascript"}, "var leagueType = 1;")]
        )
    }
    with service(pages) as svc, pytest.raises(ValueError, match=r"dynasty-rankings\?format=1"):
        list(svc.get_todays_rankings(LeagueType.Standard))


@pytest.mark.parametrize(
    ("league_type", "element_id", "variable"),
    [
        (LeagueType.Standard, "pd-oneqb", "playerOneQB"),
        (LeagueType.SuperFlex, "pd-superflex", "playerSuperflex"),
    ],
)
def test_get_player_full_history_new_format(league_type: LeagueType, element_id: str, variable: str) -> None:
    """Player value history is extracted from the current page format."""
    player_url = "https://keeptradecut.com/dynasty-rankings/players/jahmyr-gibbs-1415"
    history = {
        "overallValue": [
            {"v": 9500, "d": "2026-09-15"},
            {"v": 9998, "d": "2026-09-16"},
        ]
    }
    rankings_url = (
        "https://keeptradecut.com/dynasty-rankings?format=2"
        if league_type == LeagueType.SuperFlex
        else "https://keeptradecut.com/dynasty-rankings?format=1"
    )
    pages = {
        rankings_url: page(
            [
                ({"type": "application/json", "id": "ktc-players"}, json.dumps([PLAYER])),
                (
                    {"type": "text/javascript"},
                    "var playersArray = JSON.parse(document.getElementById('ktc-players').textContent);",
                ),
            ]
        ),
        player_url: page(
            [
                ({"type": "application/json", "id": element_id}, json.dumps(history)),
                (
                    {"type": "text/javascript"},
                    f"var {variable} = JSON.parse(document.getElementById('{element_id}').textContent);",
                ),
            ]
        ),
    }
    with service(pages) as svc:
        rows = list(svc.get_player_full_history(league_type))

    assert [r.value for r in rows] == [9500, 9998]
    assert [r.date for r in rows] == [date(2026, 9, 15), date(2026, 9, 16)]
    assert rows[0].league_type == league_type
