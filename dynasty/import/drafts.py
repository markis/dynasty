import logging
import os
from concurrent.futures import ThreadPoolExecutor

import requests
from sqlmodel import Session

from dynasty.db import create_database, record_picks
from dynasty.models import Pick
from dynasty.service.sleeper import SleeperDraftPickDict, SleeperService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    user_ids = os.getenv("SLEEPER_USER_IDS")
    if user_ids is None:
        logger.error("SLEEPER_USER_IDS environment variable is not set.")
        return

    season: int | None = None
    season_value = os.getenv("SLEEPER_SEASON")
    if season_value is not None:
        season = int(season_value)

    with SleeperService() as sleeper_service:
        drafts = [
            draft for user_id in user_ids.split(",") for draft in sleeper_service.get_drafts(user_id, season=season)
        ]

    with ThreadPoolExecutor() as executor:
        futures = [executor.submit(process_draft_picks, draft["league_id"], draft["draft_id"]) for draft in drafts]

        for draft, future in zip(drafts, futures, strict=False):
            result_count = future.result()
            logger.info(
                "Created %d picks for Draft ID: %s in League ID: %s",
                result_count,
                draft["draft_id"],
                draft["league_id"],
            )


def get_drafts(user_id: str) -> list[str]:
    """get_drafts retrieves the drafts for a given user ID from the Sleeper API."""
    url = f"https://api.sleeper.app/v1/user/{user_id}/drafts"
    response = requests.get(url, timeout=10)

    if not response.ok:
        logger.error("Failed to retrieve drafts for User ID: %s. Status Code: %s", user_id, response.status_code)
        return []

    return response.json()


def process_draft_picks(league_id: str, draft_id: str) -> int:
    """process_draft_picks retrieves and processes draft picks for a given league and draft ID."""
    pick_dicts = get_picks(draft_id)
    picks = [
        Pick(
            league_id=league_id,
            draft_id=draft_id,
            sleeper_id=pick["player_id"],
            round=pick["round"] or 0,
            pick_no=pick["pick_no"],
            picked_by=pick["picked_by"],
        )
        for pick in pick_dicts
    ]

    engine = create_database()
    with Session(engine) as session:
        return record_picks(session, picks)


def get_picks(draft_id: str) -> list[SleeperDraftPickDict]:
    """get_picks retrieves the draft picks for a given draft ID from the Sleeper API."""
    url = f"https://api.sleeper.app/v1/draft/{draft_id}/picks"
    response = requests.get(url, timeout=10)

    if not response.ok:
        logger.error("Failed to retrieve draft picks for Draft ID: %s. Status Code: %s", draft_id, response.status_code)
        return []

    return response.json()


if __name__ == "__main__":
    main()
