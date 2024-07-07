import difflib
import io
import os
from itertools import product

import polars as pl
from github import Github, InputGitTreeElement
from sqlmodel.orm.session import Session

from dynasty.db import create_database, get_player_rankings
from dynasty.models import LeagueType, RankingSet

# GitHub credentials and repository details
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
REPO_NAME = "markis/dynasty"
BRANCH_NAME = "main"
COMMIT_MESSAGE = "chore: update data"


def update_files():
    engine = create_database()
    with Session(engine) as session:
        for league_type, ranking_set in product(LeagueType, RankingSet):
            rankings = (
                (str(ranking.player_id), ranking.date, ranking.value)
                for ranking in get_player_rankings(session, league_type, ranking_set)
            )
            path = f"data/{ranking_set.name}-{league_type.name}.csv".lower()
            df = pl.DataFrame(
                rankings,
                schema={"player_id": pl.String, "date": pl.Date, "value": pl.Int64},
            )

            df.write_csv(path)


def generate_diff(old_content: str, new_content: str, filename: str) -> str:
    old_lines = old_content.splitlines(keepends=True)
    new_lines = new_content.splitlines(keepends=True)
    diff = difflib.unified_diff(old_lines, new_lines, fromfile=filename, tofile=filename)
    return "".join(diff)


def update_github(token: str = GITHUB_TOKEN, repo_name: str = REPO_NAME, branch: str = BRANCH_NAME) -> None:
    if not token:
        raise ValueError("GitHub token is required to update the repository")
    if not repo_name:
        raise ValueError("GitHub repository name is required to update the repository")
    if not branch:
        raise ValueError("GitHub branch name is required to update the repository")

    elements: list[InputGitTreeElement] = []
    g = Github(token)
    repo = g.get_repo(repo_name)

    engine = create_database()
    with Session(engine) as session:
        for league_type, ranking_set in product(LeagueType, RankingSet):
            buffer = io.BytesIO()
            rankings = (
                (str(ranking.player_id), ranking.date, ranking.value)
                for ranking in get_player_rankings(session, league_type, ranking_set)
            )
            path = f"data/{ranking_set.name}-{league_type.name}.csv".lower()
            orig_df = pl.read_csv(path)
            new_df = pl.DataFrame(
                rankings,
                schema={"player_id": pl.String, "date": pl.Date, "value": pl.Int64},
            )
            df = (
                orig_df.join(new_df, on="player_id", how="left", suffix="_new")
                .with_columns(pl.coalesce([pl.col("value_new"), pl.col("value")]).alias("value"))
                .drop("value_new")
            )
            df.write_csv(path)

            _ = buffer.seek(0)
            new_content = buffer.getvalue().decode("utf-8")

            contents = repo.get_contents(path, ref=branch)
            if isinstance(contents, list):
                contents = contents[0]
            old_content = contents.decoded_content.decode("utf-8")

            diff_content = generate_diff(old_content, new_content, path)
            if diff_content:
                elements.append(InputGitTreeElement(path=path, mode="100644", type="blob", content=diff_content))

    if elements:
        commit_msg = COMMIT_MESSAGE
        master_ref = repo.get_git_ref(f"heads/{branch}")
        master_sha = master_ref.object.sha
        base_tree = repo.get_git_tree(master_sha)
        tree = repo.create_git_tree(elements, base_tree)
        parent = repo.get_git_commit(master_sha)
        commit = repo.create_git_commit(commit_msg, tree, [parent])
        master_ref.edit(commit.sha)


if __name__ == "__main__":
    update_files()
