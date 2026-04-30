import marimo

__generated_with = "0.23.4"
app = marimo.App()

with app.setup:
    import os
    from datetime import datetime, timezone

    import duckdb
    import marimo as mo
    import requests
    from utils import check_access, download_dataset

    GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
    GRAPHQL_URL = "https://api.github.com/graphql"


@app.cell
def _():
    mo.ui.button(on_click=check_access, label="Check GitHub Access!")
    return


@app.cell
def _():
    con = duckdb.connect("data/repos.duckdb")

    def setup_repos(_):
        with mo.status.spinner(title="Loading Data", subtitle="Downloading dataset...") as _spinner:
            try:
                path = download_dataset("muhammadaqeelkabir/top-github-repositories")
            except Exception as e:
                _spinner.update(subtitle=f"Error downloading dataset: {e}")
                print(
                    "Error downloading dataset(Make sure to set the environmental variable and \
                        restart the notbook server):",
                    e,
                )
                return
            _spinner.update(subtitle=f"Setting up table...(dataset path: {path})")
            con.execute(f"""
                CREATE TABLE IF NOT EXISTS repos AS
                SELECT * FROM read_csv_auto('{path}/github_top_repositories_V2.csv')
            """)
            _spinner.update("Data complete!")

    def cleanup_db(_):
        con.execute("DROP TABLE IF EXISTS repos")
        print("Table cleaned up!")

    create_btn = mo.ui.button(on_click=setup_repos, label="Create Table!")
    clean_btn = mo.ui.button(on_click=cleanup_db, kind="danger", label="Cleanup table")
    mo.hstack(
        [create_btn, clean_btn],
        justify="start",
    )
    return (con,)


@app.cell
def _(con, repos):
    _df = mo.sql(
        """
        SELECT * FROM repos
        """,
        engine=con,
    )
    return


@app.cell
def _(con, repos):
    _df = mo.sql(
        """
        DROP TABLE IF EXISTS clean_repos;
        -- Filter non-programming repositories
        CREATE TABLE IF NOT EXISTS clean_repos AS 
            SELECT * FROM repos WHERE "Primary Language" <> '0'
        """,
        engine=con,
    )
    return


@app.cell
def _(clean_repos, con):
    _df = mo.sql(
        """
        SELECT * FROM clean_repos
        """,
        engine=con,
    )
    return


@app.cell
def _(con):
    # copy clean_repos into skipped repos with reason of unprocessed
    def copy_unprocessed_repos():
        con.execute("DELETE TABLE IF EXISTS skipped_repos")
        con.execute("""
            CREATE TABLE IF NOT EXISTS skipped_repos AS
            SELECT "Full Name", 'Unprocessed' as reason FROM clean_repos
            WHERE "Full Name" NOT IN (SELECT repo_name FROM prs)
        """)

    return (copy_unprocessed_repos,)


@app.cell
def _(copy_unprocessed_repos):
    mo.ui.button(
        label="reset skipped repos", kind="danger", on_click=lambda _: copy_unprocessed_repos()
    )
    return


@app.cell
def _(con):
    import time

    OLDEST_DATE = datetime(2022, 1, 1, tzinfo=timezone.utc)

    def process_single_repo(repo_full_name, progress, skipped_repos):
        owner, name = repo_full_name.split("/")
        headers = {"Authorization": f"Bearer {GITHUB_TOKEN}"}

        # GraphQL Query to fetch PRs, reviews, and participants in one request
        query = """
        query($owner: String!, $name: String!, $cursor: String) {
          repository(owner: $owner, name: $name) {
            pullRequests(first: 50, after: $cursor, states: CLOSED, orderBy: {field: CREATED_AT, direction: DESC}) {
              pageInfo { hasNextPage, endCursor }
              nodes {
                number
                author { login }
                createdAt
                closedAt
                isCrossRepository
                merged
                commits { totalCount }
                comments { totalCount }
                additions
                deletions
                changedFiles
                reviews(first: 10) { nodes { state } }
                participants(first: 20) { nodes { login } }
              }
            }
          }
        }
        """  # noqa: E501

        rows = []
        cursor = None
        has_next_page = True
        retry_delay = 1  # Initial delay in seconds

        while has_next_page:
            try:
                response = requests.post(
                    GRAPHQL_URL,
                    json={
                        "query": query,
                        "variables": {
                            "owner": owner,
                            "name": name,
                            "cursor": cursor,
                        },
                    },
                    headers=headers,
                )

                # Handle rate limiting (GitHub returns 403 for secondary rate limits or 429)
                if response.status_code in (403, 429):
                    print(f"Rate limited. Retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, 60)  # Exponential backoff up to 60s
                    continue

                response.raise_for_status()
                retry_delay = 1  # Reset delay on success

                result = response.json()
                data = result.get("data", {}).get("repository", {}).get("pullRequests", {})
                nodes = data.get("nodes", [])

                if not nodes:
                    break

                for pr in nodes:
                    created_at = datetime.fromisoformat(pr["createdAt"].replace("Z", "+00:00"))
                    if created_at < OLDEST_DATE:
                        has_next_page = False
                        break

                    approvals = sum(1 for r in pr["reviews"]["nodes"] if r["state"] == "APPROVED")
                    changes = sum(
                        1 for r in pr["reviews"]["nodes"] if r["state"] == "CHANGES_REQUESTED"
                    )
                    participants = [p["login"] for p in pr["participants"]["nodes"]]

                    rows.append(
                        (
                            repo_full_name,
                            pr["author"]["login"] if pr["author"] else "unknown",
                            pr["number"],
                            created_at,
                            pr["closedAt"],
                            False,
                            pr["merged"],
                            ",".join(participants),
                            pr["commits"]["totalCount"],
                            pr["comments"]["totalCount"],
                            pr["additions"],
                            pr["deletions"],
                            0,
                            approvals,
                            changes,
                            pr["changedFiles"],
                        )
                    )

                cursor = data["pageInfo"]["endCursor"]
                has_next_page = data["pageInfo"]["hasNextPage"]

            except Exception as e:
                error_msg = e.__class__.__name__
                print(f"Error processing {repo_full_name}: {error_msg}")
                skipped_repos.append((repo_full_name, error_msg))
                progress.update(subtitle=f"Error processing {repo_full_name}: {error_msg}")
                break

        if rows:
            con.executemany(
                "INSERT INTO prs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                rows,
            )
        progress.update(1, subtitle=f"Processed {repo_full_name}")

    def collect_repo_prs(force=False):
        repos = con.execute('SELECT "Full Name" FROM clean_repos').fetchall()
        skipped_repos = []
        if force:
            con.execute("DROP TABLE IF EXISTS prs")
            con.execute("DROP TABLE IF EXISTS skipped_repos")

        con.execute("""
            CREATE TABLE IF NOT EXISTS prs (
                repo_name VARCHAR, 
                pr_creator VARCHAR, 
                issue_number INTEGER, 
                opened_at TIMESTAMP,
                closed_at TIMESTAMP, 
                is_reopened BOOLEAN, 
                is_merged BOOLEAN, 
                participants VARCHAR,
                num_commits INTEGER, 
                num_comments INTEGER, 
                num_lines_added INTEGER,
                num_lines_deleted INTEGER, 
                num_review_comments INTEGER, 
                num_approvals INTEGER,
                num_change_requests INTEGER, 
                num_files_changed INTEGER
            )
        """)
        con.execute("CREATE TABLE IF NOT EXISTS skipped_repos (repo_name VARCHAR, reason VARCHAR)")

        with mo.status.progress_bar(
            total=len(repos), title="Fetching GitHub PR Data via GraphQL"
        ) as progress:
            for repo_name in [r[0] for r in repos]:
                process_single_repo(repo_name, progress, skipped_repos)

        if skipped_repos:
            con.executemany("INSERT INTO skipped_repos VALUES (?, ?)", skipped_repos)
            print(f"Finished. Skipped {len(skipped_repos)} repositories.")

    return (collect_repo_prs,)


@app.cell
def _():
    force_toggle = mo.ui.switch(label="Force toggle", value=False)
    return (force_toggle,)


@app.cell
def _(collect_repo_prs, force_toggle):
    mo.ui.button(
        label="Delete previous data",
        kind="danger",
        on_change=lambda _: collect_repo_prs(force=force_toggle.value),
    )
    return


@app.cell
def _(con, prs):
    _df = mo.sql(
        """
        SELECT * FROM prs
        """,
        engine=con,
    )
    return


if __name__ == "__main__":
    app.run()
