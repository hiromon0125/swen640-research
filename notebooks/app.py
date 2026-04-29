import marimo

__generated_with = "0.23.4"
app = marimo.App(width="medium")

with app.setup:
    import marimo as mo
    from utils import check_access, gh, download_dataset
    import duckdb


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
                    "Error downloading dataset(Make sure to set the environmental variable and restart the notbook server):",
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
def _(con, repos):
    _df = mo.sql(
        f"""
        DROP TABLE IF EXISTS clean_repos;
        -- Filter non-programming repositories
        CREATE TABLE IF NOT EXISTS clean_repos AS 
            SELECT * FROM repos WHERE "Primary Language" <> '0'
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
    import polars as pl
    from github import GithubException

    def process_single_repo(repo_full_name, g, progress):
        try:
            repo = g.get_repo(repo_full_name)
        except GithubException:
            progress.update(1)
            return
        
        prs = repo.get_pulls(state='all')
    
        rows = []
        for pr in prs:
            # Fetch reviews/events for detailed metrics
            reviews = list(pr.get_reviews())
            approvals = len([r for r in reviews if r.state == 'APPROVED'])
            change_requests = len([r for r in reviews if r.state == 'CHANGES_REQUESTED'])
        
            # Fetch unique participants
            participants = {pr.user.login}
            for comment in pr.get_issue_comments():
                participants.add(comment.user.login)
        
            rows.append((
                repo_full_name,
                pr.user.login,
                pr.number,
                pr.created_at,
                pr.closed_at,
                pr.reopened if hasattr(pr, 'reopened') else False,
                pr.merged,
                ",".join(participants),
                pr.commits,
                pr.comments,
                pr.additions,
                pr.deletions,
                pr.review_comments,
                approvals,
                change_requests,
                pr.changed_files
            ))
    
        if rows:
            con.executemany("""
                INSERT INTO prs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, rows)
        progress.update(1)

    def collect_repo_prs():
        repos = con.execute("SELECT 'Full Name' FROM clean_repos").fetchall()
    
        # Initialize the prs table
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
    
        # Process repositories sequentially
        with gh() as g:
            with mo.status.progress_bar(total=len(repos)) as progress:
                for repo_name in [r[0] for r in repos]:
                    process_single_repo(repo_name, g, progress)
    
        mo.call_on_hide(lambda: None) # placeholder to trigger UI update
        mo.alert("Data collection process has finished successfully!")

    collect_repo_prs()
    return


@app.cell
def _(con, prs):
    _df = mo.sql(
        f"""
        SELECT * FROM prs
        """,
        engine=con
    )
    return


if __name__ == "__main__":
    app.run()
