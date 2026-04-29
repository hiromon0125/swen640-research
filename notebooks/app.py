import marimo

__generated_with = "0.23.4"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    from github import Github, Auth
    import os
    from contextlib import contextmanager


    @contextmanager
    def gh():
        access_token = os.getenv("GITHUB_TOKEN")
        if not access_token:
            raise ValueError(
                "GITHUB_TOKEN environment variable not set. Please set it before running the script. `cp example.env .env` and edit the .env file to add your GitHub token."
            )

        auth = Auth.Token(access_token)
        g = Github(auth=auth)
        try:
            yield g
        finally:
            g.close()


    def check(_):
        with gh() as g:
            # Check for access
            try:
                user = g.get_user()
                print(f"Authenticated as: {user.login}")
                print("You are good to continue!")
            except Exception as e:
                print(f"Authentication failed: {e}")


    mo.ui.button(on_click=check, label="Check GitHub Access!")
    return


@app.cell
def _():
    import duckdb

    con = duckdb.connect("data/repos.duckdb")
    con.execute("CREATE TABLE test AS SELECT 1 AS id, 'hello' AS name")
    return (con,)


@app.cell
def _(con, mo, test):
    _df = mo.sql(
        f"""
        SELECT * FROM test
        """,
        engine=con,
    )
    return


if __name__ == "__main__":
    app.run()
