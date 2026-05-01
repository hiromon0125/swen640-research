import marimo

__generated_with = "0.23.4"
app = marimo.App()

with app.setup:
    import os
    from datetime import datetime, timezone
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import re


    import duckdb
    import marimo as mo
    import requests
    from utils import check_access, download_dataset

    GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
    TOKENS = [GITHUB_TOKEN]
    count = 4
    for i in range(count - 1):
        TOKENS.append(os.environ.get(f"GITHUB_TOKEN_{i+2}", GITHUB_TOKEN))
    GRAPHQL_URL = "https://api.github.com/graphql"


@app.cell
def _():
    mo.ui.button(on_click=check_access, label="Check GitHub Access!")
    return


@app.cell
def _():
    con = duckdb.connect("data/repos.duckdb")


    def setup_repos(_):
        with mo.status.spinner(
            title="Loading Data", subtitle="Downloading dataset..."
        ) as _spinner:
            try:
                path = download_dataset(
                    "muhammadaqeelkabir/top-github-repositories"
                )
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
    clean_btn = mo.ui.button(
        on_click=cleanup_db, kind="danger", label="Cleanup table"
    )
    mo.hstack(
        [create_btn, clean_btn],
        justify="start",
    )
    return (con,)


@app.cell
def _(con, repos):
    _df = mo.sql(
        f"""
        SELECT * FROM repos
        """,
        engine=con
    )
    return


@app.cell
def _(clean_repos, con):
    _df = mo.sql(
        f"""
        SELECT * FROM clean_repos
        """,
        engine=con
    )
    return


@app.cell
def _(con):
    # copy clean_repos into skipped repos with reason of unprocessed
    def copy_unprocessed_repos():
        con.execute("DROP TABLE IF EXISTS task_repos")
        con.execute("""
            CREATE TABLE IF NOT EXISTS task_repos AS
            SELECT "Full Name", 'Unprocessed' as reason FROM clean_repos
            WHERE "Full Name" NOT IN (SELECT repo_name FROM prs)
        """)

    return (copy_unprocessed_repos,)


@app.cell
def _(copy_unprocessed_repos):
    mo.ui.button(
        label="reset skipped repos",
        kind="danger",
        on_click=lambda _: copy_unprocessed_repos(),
    )
    return


@app.cell
def _(con):
    # Create new prs table with unique issue number and repo to avoid duplicates
    def create_prs_table(original_table, table_name):
        if table_name.strip() == "":
            print("Please enter a valid table name.")
            return
        backup_name = f"{table_name}__backup"

        # If an existing target table exists, try to preserve it as a backup
        try:
            con.execute(f"DROP TABLE IF EXISTS {backup_name}")
            con.execute(f"ALTER TABLE {table_name} RENAME TO {backup_name}")
        except Exception:
            # If rename fails assume table did not exist and continue
            pass

        try:
            con.execute("BEGIN TRANSACTION")
            con.execute(f"DROP TABLE IF EXISTS {table_name}")
            con.execute(f"""
                CREATE TABLE {table_name} AS
                SELECT * FROM (
                    SELECT *, ROW_NUMBER() OVER (PARTITION BY repo_name, issue_number) as row_num
                    FROM {original_table}
                )
                WHERE row_num = 1
            """)
            con.execute(
                f"ALTER TABLE {table_name} ADD PRIMARY KEY (repo_name, issue_number)"
            )
            con.execute(f"ALTER TABLE {table_name} DROP COLUMN row_num")
            con.execute("COMMIT")

            # Creation succeeded; remove any backup
            try:
                con.execute(f"DROP TABLE IF EXISTS {backup_name}")
            except Exception:
                pass

        except Exception as e:
            # Rollback and attempt to restore the previous table
            try:
                con.execute("ROLLBACK")
            except Exception:
                pass
            print(
                f"Failed to create {table_name}: {e}. Reverting to backup if available."
            )
            try:
                con.execute(f"DROP TABLE IF EXISTS {table_name}")
                con.execute(f"ALTER TABLE {backup_name} RENAME TO {table_name}")
                print(f"Restored backup {backup_name} to {table_name}")
            except Exception as restore_err:
                print(f"Failed to restore backup {backup_name}: {restore_err}")
            return


    original_table_name_input = mo.ui.text(placeholder="table name")
    table_name_input = mo.ui.text(placeholder="table name")
    create_prs_btn = mo.ui.button(
        label="Create PRs Table",
        on_click=lambda _: create_prs_table(
            original_table_name_input.value, table_name_input.value
        ),
    )
    mo.hstack(
        [original_table_name_input, table_name_input, create_prs_btn],
        justify="start",
    )
    return (table_name_input,)


@app.cell(hide_code=True)
def _(con, table_name_input):
    _df = mo.sql(
        f"""
        SELECT * FROM {table_name_input.value or "prs"}
        """,
        engine=con
    )
    return


@app.cell
def _(con):
    # transfer back from pr2 to pr
    def transfer(overwrite_table, new_table):

        if overwrite_table.strip() == "" or new_table.strip() == "":
            print("Please enter valid table names.")
            return

        # Basic validation to avoid SQL injection via UI inputs
        if not re.match(r"^[A-Za-z0-9_]+$", overwrite_table) or not re.match(
            r"^[A-Za-z0-9_]+$", new_table
        ):
            print(
                "Table names may only contain letters, numbers, and underscores."
            )
            return

        backup_name = f"{overwrite_table}__backup"

        # Preserve existing overwrite_table as a backup (if it exists)
        try:
            con.execute(f"DROP TABLE IF EXISTS {backup_name}")
            con.execute(f"ALTER TABLE {overwrite_table} RENAME TO {backup_name}")
        except Exception:
            # ignore: table may not exist
            pass

        try:
            con.execute("BEGIN TRANSACTION")
            con.execute(f"DROP TABLE IF EXISTS {overwrite_table}")
            con.execute(f"ALTER TABLE {new_table} RENAME TO {overwrite_table}")
            con.execute("COMMIT")

            # Success; remove backup if present
            try:
                con.execute(f"DROP TABLE IF EXISTS {backup_name}")
            except Exception:
                pass
            print(f"Transferred {new_table} to {overwrite_table} successfully.")

        except Exception as e:
            # Attempt rollback and restore backup
            try:
                con.execute("ROLLBACK")
            except Exception:
                pass
            print(f"Transfer failed: {e}. Attempting to restore backup.")
            try:
                con.execute(f"DROP TABLE IF EXISTS {overwrite_table}")
                con.execute(
                    f"ALTER TABLE {backup_name} RENAME TO {overwrite_table}"
                )
                print(f"Restored backup {backup_name} to {overwrite_table}.")
            except Exception as restore_err:
                print(f"Failed to restore backup {backup_name}: {restore_err}")


    transfer_btn = mo.ui.button(
        label="Transfer PR2 to PR", on_click=lambda _: transfer("prs", "prs_2")
    )
    transfer_btn
    return


@app.cell
def _(con):
    import time

    OLDEST_DATE = datetime(2022, 1, 1, tzinfo=timezone.utc)
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


    def process_single_repo(repo_full_name, skipped_repos, token, lock):
        owner, name = repo_full_name.split("/")
        headers = {"Authorization": f"Bearer {token}"}
        rows = []
        cursor = None
        has_next_page = True
        retry_delay = 1  # Initial delay in seconds

        def write_repo_status(reason):
            with lock:
                try:
                    con.execute(
                        "CREATE TABLE IF NOT EXISTS skipped_repos (repo_name VARCHAR, reason VARCHAR)"
                    )
                    con.execute(
                        "DELETE FROM skipped_repos WHERE repo_name = ?",
                        (repo_full_name,),
                    )
                    con.execute(
                        "INSERT INTO skipped_repos VALUES (?, ?)",
                        (repo_full_name, reason),
                    )
                except Exception as db_err:
                    print(
                        f"Failed to write repo status for {repo_full_name}: {db_err}"
                    )

        # Load existing PR numbers for this repo (if `prs` table exists) to skip duplicates
        try:
            with lock:
                existing_rows = con.execute(
                    "SELECT issue_number FROM prs WHERE repo_name = ?",
                    (repo_full_name,),
                ).fetchall()
            existing_prs = set(r[0] for r in existing_rows)
        except Exception:
            existing_prs = set()

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
                    retry_delay = min(
                        retry_delay * 2, 60
                    )  # Exponential backoff up to 60s
                    continue

                response.raise_for_status()
                retry_delay = 1  # Reset delay on success

                result = response.json()
                data = (
                    result.get("data", {})
                    .get("repository", {})
                    .get("pullRequests", {})
                )
                nodes = data.get("nodes", [])

                if not nodes:
                    break

                for pr in nodes:
                    pr_number = pr["number"]

                    # Skip PRs already present in the DB
                    if pr_number in existing_prs:
                        continue

                    created_at = datetime.fromisoformat(
                        pr["createdAt"].replace("Z", "+00:00")
                    )
                    if created_at < OLDEST_DATE:
                        has_next_page = False
                        break

                    approvals = sum(
                        1
                        for r in pr["reviews"]["nodes"]
                        if r["state"] == "APPROVED"
                    )
                    changes = sum(
                        1
                        for r in pr["reviews"]["nodes"]
                        if r["state"] == "CHANGES_REQUESTED"
                    )
                    participants = [
                        p["login"] for p in pr["participants"]["nodes"]
                    ]

                    rows.append(
                        (
                            repo_full_name,
                            pr["author"]["login"] if pr["author"] else "unknown",
                            pr_number,
                            created_at,
                            pr.get("closedAt"),
                            False,
                            pr.get("merged"),
                            ",".join(participants),
                            pr.get("commits", {}).get("totalCount"),
                            pr.get("comments", {}).get("totalCount"),
                            pr.get("additions"),
                            pr.get("deletions"),
                            0,
                            approvals,
                            changes,
                            pr.get("changedFiles"),
                        )
                    )

                cursor = data["pageInfo"]["endCursor"]
                has_next_page = data["pageInfo"]["hasNextPage"]

            except Exception as e:
                error_msg = e.__class__.__name__
                print(f"Error processing {repo_full_name}: {e}")
                # Record skipped repo immediately in DB and local list (for summary)
                with lock:
                    skipped_repos.append((repo_full_name, error_msg))
                write_repo_status(error_msg)
                return {
                    "repo": repo_full_name,
                    "status": "error",
                    "reason": error_msg,
                }

        if rows:
            # Insert under lock to avoid concurrent DB writes
            with lock:
                con.executemany(
                    "INSERT INTO prs (repo_name, pr_creator, issue_number, opened_at, closed_at, is_reopened, is_merged, participants, num_commits, num_comments, num_lines_added, num_lines_deleted, num_review_comments, num_approvals, num_change_requests, num_files_changed) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    rows,
                )
        write_repo_status("Processed")
        return {
            "repo": repo_full_name,
            "status": "processed",
            "reason": "Processed",
        }


    def collect_repo_prs():
        import threading

        repos = con.execute(
            "SELECT \"Full Name\" FROM task_repos WHERE reason <> 'Processed'"
        ).fetchall()
        skipped_repos = []
        lock = threading.Lock()

        with mo.status.progress_bar(
            total=len(repos), title="Fetching GitHub PR Data via GraphQL"
        ) as progress:

            def process_repo_with_token(repo_name, token_idx):
                token = TOKENS[token_idx % len(TOKENS)]
                return process_single_repo(repo_name, skipped_repos, token, lock)

            with ThreadPoolExecutor(max_workers=len(TOKENS)) as executor:
                futures = {
                    executor.submit(
                        process_repo_with_token, repo_name, idx
                    ): repo_name
                    for idx, repo_name in enumerate([r[0] for r in repos])
                }

                for future in as_completed(futures):
                    repo_name = futures[future]
                    try:
                        result = future.result()
                        if result and result.get("status") == "error":
                            progress.update(
                                1,
                                subtitle=f"Error processing {repo_name}: {result.get('reason', 'UnknownError')}",
                            )
                        else:
                            progress.update(1, subtitle=f"Processed {repo_name}")
                    except Exception as e:
                        error_msg = e.__class__.__name__
                        progress.update(
                            1,
                            subtitle=f"Error processing {repo_name}: {error_msg}",
                        )

        if skipped_repos:
            print(f"Finished. Skipped {len(skipped_repos)} repositories.")

    return (collect_repo_prs,)


@app.cell
def _(collect_repo_prs):
    mo.ui.button(
        label="Query PRs for unprocessed repos",
        on_change=lambda _: collect_repo_prs(),
    )
    return


@app.cell
def _(con, task_repos):
    _df = mo.sql(
        f"""
        SELECT * FROM task_repos WHERE reason <> 'Processed'
        """,
        engine=con
    )
    return


@app.cell(hide_code=True)
def _(con, prs):
    _df = mo.sql(
        f"""
        SELECT * FROM prs
        """,
        engine=con
    )
    return


@app.cell
def _(con):
    def update_task_repos_from_skipped():
        """
        Updates the task_repos table with the latest processing status
        from the skipped_repos table.
        """
        try:
            con.execute("BEGIN TRANSACTION")
        
            # Merge operation: 
            # Update existing records in task_repos that exist in skipped_repos
            con.execute("""
                UPDATE task_repos
                SET reason = s.reason
                FROM skipped_repos s
                WHERE task_repos."Full Name" = s.repo_name
            """)
        
            con.execute("COMMIT")
            print("Successfully updated task_repos with latest status from skipped_repos.")
        except Exception as e:
            con.execute("ROLLBACK")
            print(f"Failed to update task_repos: {e}")

    update_btn = mo.ui.button(
        label="Sync Status: Skipped to Task",
        on_click=lambda _: update_task_repos_from_skipped()
    )
    update_btn
    return


if __name__ == "__main__":
    app.run()
