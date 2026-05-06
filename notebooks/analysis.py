import marimo

__generated_with = "0.23.4"
app = marimo.App(width="medium")


@app.cell
def _():
    import altair as alt

    alt.data_transformers.enable("vegafusion")
    import marimo as mo

    return alt, mo


@app.cell
def _(mo):
    import duckdb

    data_dir = "data/"
    con = duckdb.connect(data_dir + "repos.duckdb")


    def close_connection(_):
        con.close()
        print("DuckDB connection closed.")


    mo.ui.button(on_click=close_connection, label="Close DuckDB Connection")
    return (con,)


@app.cell
def _(con, mo, prs):
    duration_df = mo.sql(
        f"""
        SELECT AVG(FLOOR(EPOCH(closed_at - opened_at)/86400.0)) as avg_duration, AVG(num_files_changed) as avg_files_changed, AVG(num_lines_added + num_lines_deleted) as avg_lines_edited, repo_name 
            FROM prs
            GROUP BY repo_name
        	ORDER BY avg_duration DESC
        """,
        engine=con
    )
    return (duration_df,)


@app.cell
def _(alt, duration_df):
    step_size = 25
    # replace _df with your data source
    _chart = (
        alt.Chart(duration_df)
        .mark_line()
        .encode(
            x=alt.X(
                field="avg_duration",
                type="quantitative",
                bin={"step": step_size},
                sort="ascending",
            ),
            y=alt.Y(aggregate="count", type="quantitative"),
            tooltip=[
                alt.Tooltip(
                    field="avg_duration", format=",.2f", bin={"step": step_size}
                ),
                alt.Tooltip(aggregate="count"),
            ],
        )
        .properties(
            height=290, width="container", config={"axis": {"grid": False}}
        )
    )
    _chart
    return


@app.cell(hide_code=True)
def _(con, mo, prs):
    participants_df = mo.sql(
        f"""
        SELECT
            count(1) as num_prs,
            AVG(FLOOR(EPOCH(closed_at - opened_at)/86400.0)) as avg_duration,
            AVG(num_files_changed) as avg_files_changed,
            AVG(num_lines_added + num_lines_deleted) as avg_lines_edited,
            repo_name,
            AVG(array_length(STRING_SPLIT(participants, ','))) as avg_num_participants
        FROM
            prs
        GROUP BY
            repo_name
        HAVING
            AVG(num_lines_added + num_lines_deleted) < 2000000
        ORDER BY
            avg_duration DESC
        """,
        engine=con
    )
    return


@app.cell(hide_code=True)
def _(con, mo, prs):
    open_date_df = mo.sql(
        f"""
        SELECT
            year(opened_at) as open_year,
            month(opened_at) as open_month,
            num_files_changed,
            (num_lines_added + num_lines_deleted) as lines_edited,
            array_length(STRING_SPLIT(participants, ',')) as num_participants,
            FLOOR(EPOCH(closed_at - opened_at)/86400.0) as open_duration,
            strftime(opened_at, '%Y-%m') as open_month_year,
            participants LIKE '%Copilot%' AS has_copilot_participant, 
            (participants LIKE '%bot%' OR participants LIKE '%assistant%') AS has_bot_participant,
            CASE 
            	WHEN has_copilot_participant AND has_bot_participant THEN 'Bot & Copilot'
            	WHEN has_copilot_participant THEN 'Copilot'
            	WHEN has_bot_participant THEN 'Bot'
            	ELSE 'Likely Human'
            END AS participant_type,
            repo_name
        FROM
            prs
        """,
        engine=con
    )
    return (open_date_df,)


@app.cell
def _(alt, open_date_df):
    # replace _df with your data source
    _chart = (
        alt.Chart(open_date_df)
        .mark_bar()
        .encode(
            x=alt.X(
                field="open_month_year",
                type="nominal",
                title="PR Open Date (Year-Month)",
                sort="ascending",
            ),
            y=alt.Y(
                field="num_files_changed",
                type="quantitative",
                title="Files Edited",
                stack=True,
                aggregate="sum",
                sort="ascending",
            ),
            color=alt.Color(field="participant_type", type="nominal"),
            tooltip=[
                alt.Tooltip(
                    field="open_month_year", title="PR Open Date (Year-Month)"
                ),
                alt.Tooltip(
                    field="num_files_changed",
                    aggregate="sum",
                    format=",.0f",
                    title="Files Edited",
                ),
                alt.Tooltip(field="participant_type"),
            ],
        )
        .properties(
            title="Number of Files Edited Over Time", height=290, width="container", config={"axis": {"grid": False}}
        )
    )
    _chart
    return


@app.cell
def _(alt, open_date_df):
    # replace _df with your data source
    _chart = (
        alt.Chart(open_date_df)
        .mark_bar()
        .encode(
            x=alt.X(
                field="open_month_year",
                type="nominal",
                title="PR Open Date (Year-Month)",
            ),
            y=alt.Y(
                field="lines_edited",
                type="quantitative",
                title="Lines Edited",
                aggregate="mean",
            ),
            tooltip=[
                alt.Tooltip(
                    field="open_month_year", title="PR Open Date (Year-Month)"
                ),
                alt.Tooltip(
                    field="lines_edited",
                    aggregate="mean",
                    format=",.0f",
                    title="Lines Edited",
                ),
            ],
        )
        .properties(
            height=290, width="container", config={"axis": {"grid": False}}
        )
    )
    _chart
    return


@app.cell
def _(alt, open_date_df):
    # replace _df with your data source
    _chart = (
        alt.Chart(open_date_df)
        .mark_bar()
        .encode(
            x=alt.X(
                field="open_month_year",
                type="nominal",
                title="PR Open Date (Year-Month)",
            ),
            y=alt.Y(
                field="open_duration",
                type="quantitative",
                title="Open duration (days)",
                aggregate="mean",
            ),
            tooltip=[
                alt.Tooltip(
                    field="open_month_year", title="PR Open Date (Year-Month)"
                ),
                alt.Tooltip(
                    field="open_duration",
                    aggregate="mean",
                    format=",.2f",
                    title="Open duration (days)",
                ),
            ],
        )
        .properties(
            height=290, width="container", config={"axis": {"grid": False}}
        )
    )
    _chart
    return


@app.cell(hide_code=True)
def _(con, mo, participants):
    participant_contributions_df = mo.sql(
        f"""
        SELECT
            count(1) as num_contributions,
            participant,
            (participant='Copilot') as is_copilot,
            (participant LIKE '%bot%' OR participant LIKE '%assistant%') AS is_bot,
            CASE 
            	WHEN is_copilot THEN 'Copilot'
            	WHEN is_bot THEN 'Bot'
            	ELSE 'Likely Human'
            END AS participant_type
        FROM
            participants
        WHERE participant <> ''
        GROUP BY
            participant
        ORDER BY
            num_contributions DESC
        LIMIT 25
        """,
        engine=con
    )
    return (participant_contributions_df,)


@app.cell
def _(alt, participant_contributions_df):
    # replace _df with your data source
    _chart = (
        alt.Chart(participant_contributions_df)
        .mark_bar()
        .encode(
            x=alt.X(field="participant", type="nominal", sort="-y"),
            y=alt.Y(
                field="num_contributions",
                type="quantitative",
                stack=True,
                aggregate="mean",
            ),
            color=alt.Color(field="participant_type", type="nominal"),
            tooltip=[
                alt.Tooltip(field="participant"),
                alt.Tooltip(
                    field="num_contributions", aggregate="mean", format=",.0f"
                ),
                alt.Tooltip(field="participant_type"),
            ],
        )
        .properties(
            height=290, width="container", config={"axis": {"grid": False}}
        )
    )
    _chart
    return


@app.cell(hide_code=True)
def _(con, mo, prs):
    df_gt_24 = mo.sql(
        f"""
        SELECT
            year(opened_at) as open_year,
            month(opened_at) as open_month,
            num_files_changed,
            (num_lines_added + num_lines_deleted) as lines_edited,
            array_length(STRING_SPLIT(participants, ',')) as num_participants,
            FLOOR(EPOCH(closed_at - opened_at)/86400.0) as open_duration,
            strftime(opened_at, '%Y-%m') as open_month_year,
            participants LIKE '%Copilot%' AS has_copilot_participant, 
            (participants LIKE '%bot%' OR participants LIKE '%assistant%') AS has_bot_participant,
            CASE 
            	WHEN has_copilot_participant AND has_bot_participant THEN 'Bot & Copilot'
            	WHEN has_copilot_participant THEN 'Copilot'
            	WHEN has_bot_participant THEN 'Bot'
            	ELSE 'Likely Human'
            END AS participant_type,
            repo_name
        FROM
            prs
        WHERE 
            open_month_year >= '2025-02'
        """,
        engine=con
    )
    return (df_gt_24,)


@app.cell
def _(alt, df_gt_24):
    _line = (
        alt.Chart(df_gt_24)
        .mark_line()
        .encode(
            x=alt.X(field='open_month_year', type='nominal'),
            y=alt.Y(field='open_duration', type='quantitative', stack=False, aggregate='median'),
            color=alt.Color(field='participant_type', type='nominal'),
        )
    )

    _band = (
        alt.Chart(df_gt_24)
        .mark_area(opacity=0.2)
        .encode(
            x=alt.X(field='open_month_year', type='nominal'),
            y=alt.Y(field='open_duration', type='quantitative', aggregate='q3'),
            y2=alt.Y2(field='open_duration', aggregate='q1'),
            color=alt.Color(field='participant_type', type='nominal'),
        )
    )

    _chart = (_band + _line).properties(height=290, width='container')
    _chart
    return


@app.cell
def _(con, mo, prs):
    def get_prs():
        return mo.sql(
            f"""
            SELECT
                repo_name,
                1 as event,
                opened_at,
                closed_at,
                num_files_changed,
                (num_lines_added + num_lines_deleted) as lines_edited,
                FLOOR(EPOCH(closed_at - opened_at)/86400.0) as open_duration,
                participants LIKE '%Copilot%' AS has_copilot_participant, 
                (participants LIKE '%bot%' OR participants LIKE '%assistant%') AS has_bot_participant,
                CASE 
                    WHEN has_copilot_participant AND has_bot_participant THEN 'Bot & Copilot'
                    WHEN has_copilot_participant THEN 'Copilot'
                    WHEN has_bot_participant THEN 'Bot'
                    ELSE 'Likely Human'
                END AS participant_type
            FROM
                prs
            """,
            engine=con
        )

    def cox_model():
        from lifelines import CoxPHFitter
        import polars as pl
    
        df = get_prs()

        # feature engineering
        df = df.with_columns([
            pl.col("lines_edited").log1p().alias("log_lines_edited"),
            pl.col("num_files_changed").log1p().alias("log_files_changed"),
        ])
        df = df.with_columns([
            (pl.col("has_copilot_participant") * pl.col("log_lines_edited")).alias("copilot_x_log_lines")
        ])
        

        # Check for nulls
        if df.select(pl.col("open_duration").is_null().any()).item():
            print("Warning: Null values found in 'open_duration'. These rows will be dropped.")
            df = df.filter(pl.col("open_duration").is_not_null())
    
        # Convert to pandas for lifelines compatibility
        df_pd = df.to_pandas()
    
        cph = CoxPHFitter()
        cph.fit(df_pd[[
            'repo_name',
            'event',
            'open_duration', 
            'log_files_changed', 
            'log_lines_edited', 
            "has_copilot_participant",
            "has_bot_participant",
            "copilot_x_log_lines"
        ]], duration_col='open_duration', event_col="event", strata="repo_name")
        sum = cph.summary
        print(sum)
        return sum

    mo.ui.button(on_click=lambda _: cox_model(), label="Run Cox Model")
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
