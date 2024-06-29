import codecs
import csv
import io
import os
from collections.abc import Iterable
from types import TracebackType
from typing import Self, TypedDict, TypeGuard

import git
import requests

from dynasty.models import LeagueType, PlayerRanking, RankingSet
from dynasty.util import convert_date, generate_id

LATEST_RANKINGS = "https://raw.githubusercontent.com/dynastyprocess/data/master/files/values.csv"
RANKINGS_GIT = "https://github.com/dynastyprocess/data.git"
RANKINGS_PATH = "files/values.csv"

DYNASTY_PROCESS_GIT_PATH = os.getenv("DYNASTY_PROCESS_GIT_PATH", "")


class DynastyProcessRow(TypedDict):
    player: str
    scrape_date: str
    value_1qb: str
    value_2qb: str
    pos: str


def is_dynasty_process_row(row: dict[str, str]) -> TypeGuard[DynastyProcessRow]:
    return all(key in row for key in ["player", "scrape_date", "value_1qb", "value_2qb", "pos"])


class DynastyProcess:
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

    def get_latest_rankings(self) -> Iterable[DynastyProcessRow] | None:
        response = self.session.get(LATEST_RANKINGS)
        response.raise_for_status()

        csv_reader = csv.DictReader(codecs.iterdecode(response.iter_lines(), "utf-8"))
        return (row for row in csv_reader if is_dynasty_process_row(row))

    def get_rankings_from_git(self) -> Iterable[DynastyProcessRow] | None:
        """
        Get the latest rankings from the DynastyProcess GitHub repository.
        """
        repo = git.Repo(DYNASTY_PROCESS_GIT_PATH)
        commits = repo.iter_commits(paths=RANKINGS_PATH)

        for commit in commits:
            blob = commit.tree.join(RANKINGS_PATH)
            file_content = str(blob.data_stream.read().decode("utf-8"))
            io_contents = io.StringIO(file_content)
            csv_reader = csv.DictReader(io_contents)
            for row in csv_reader:
                if is_dynasty_process_row(row):
                    yield row

    def get_rankings(self, *, back_fill: bool = False) -> Iterable[PlayerRanking]:
        rows = self.get_latest_rankings() if not back_fill else self.get_rankings_from_git()

        if rows is None:
            return []

        return (
            PlayerRanking(
                player_id=generate_id(row["player"]),
                league_type=league_type,
                date=convert_date(row["scrape_date"]),
                value=int(row["value_1qb"]) if league_type == LeagueType.Standard else int(row["value_2qb"]),
                ranking_set=RankingSet.DynastyProcess,
                is_pick=row["pos"] == "PICK",
            )
            for row in rows
            for league_type in (LeagueType.Standard, LeagueType.SuperFlex)
        )
