from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
from pathlib import Path
from textwrap import dedent
from typing import Dict, Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from data_layer import load_sales_data
from query_pipeline import _load_local_env  # ensure .env is parsed early

try:
    import google.generativeai as genai
except Exception:
    genai = None


DB_PATH = Path(__file__).resolve().parent / "analytics.db"
TABLE_NAME = "sales"
CSV_SOURCE = Path(__file__).resolve().parent.parent / "backend" / "database" / "data" / "demo_sales.csv"


def _ensure_database() -> None:
    df = load_sales_data()
    conn = sqlite3.connect(DB_PATH)
    df.to_sql(TABLE_NAME, conn, if_exists="replace", index=False)
    conn.close()


def _translate_sql(sql: str) -> str:
    """Translate common warehouse SQL functions to SQLite-compatible expressions."""

    def _repl(match: re.Match) -> str:
        unit = match.group(1).lower()
        column = match.group(2).strip()
        fmt_map = {
            "day": "%Y-%m-%d",
            "date": "%Y-%m-%d",
            "month": "%Y-%m-01",
            "month_start": "%Y-%m-01",
            "year": "%Y-01-01",
        }
        fmt = fmt_map.get(unit, "%Y-%m-%d")
        return f"strftime('{fmt}', {column})"

    pattern = re.compile(r"DATE_TRUNC\(\s*'([^']+)'\s*,\s*([^)]+)\)")
    sql = pattern.sub(_repl, sql)

    def _repl_extract(match: re.Match) -> str:
        unit = match.group(1).lower()
        column = match.group(2).strip()
        fmt_map = {
            "year": "%Y",
            "month": "%m",
            "day": "%d",
        }
        fmt = fmt_map.get(unit)
        if fmt:
            return f"CAST(strftime('{fmt}', {column}) AS INTEGER)"
        return match.group(0)

    pattern_extract = re.compile(r"EXTRACT\(\s*([A-Za-z]+)\s+FROM\s+([^)]+)\)", re.IGNORECASE)
    return pattern_extract.sub(_repl_extract, sql)


class SQLQueryPipeline:
    """Translate natural language asks into SQL, execute, and build Vizro-friendly figures."""

    def __init__(self):
        self._logger = logging.getLogger("vizro.sql_pipeline")
        _ensure_database()
        self._columns = self._load_columns()
        self._column_lookup = {col["name"].lower(): col["name"] for col in self._columns}
        self._text_columns = {col["name"] for col in self._columns if col["type"].lower().startswith("text")}
        self._numeric_columns = {
            col["name"]
            for col in self._columns
            if any(token in col["type"].lower() for token in ("int", "real", "num", "double", "float"))
        }
        self._schema_json = json.dumps(self._columns, indent=2)
        self._schema = ", ".join(f"{col['name']} ({col['type']})" for col in self._columns)
        self._model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        self._api_key = os.getenv("GEMINI_API_KEY")
        self._llm_ready = bool(self._api_key and genai)
        if self._llm_ready:
            genai.configure(api_key=self._api_key)
            self._logger.info("Using Gemini model %s for NL->SQL", self._model_name)
        else:
            reason = "missing API key" if not self._api_key else "google-generativeai not installed"
            self._logger.warning("LLM unavailable (%s); using heuristic templates.", reason)

    def _load_columns(self) -> list[dict[str, str]]:
        conn = sqlite3.connect(DB_PATH)
        info = pd.read_sql_query(f"PRAGMA table_info({TABLE_NAME});", conn)
        conn.close()
        columns = []
        for _, row in info.iterrows():
            columns.append({"name": row["name"], "type": row["type"]})
        return columns

    def run(self, message: str) -> Dict[str, object]:
        self._logger.info("Received query: %s", message)
        plan = None
        if self._llm_ready:
            plan = self._llm_plan(message)
            if plan and self._has_missing_columns(plan):
                plan = self._rerun_with_schema_feedback(message, plan)
        if not plan:
            plan = self._keyword_plan(message)
            self._logger.info("Using fallback plan: %s", plan)
        else:
            self._logger.info("LLM plan: %s", plan)

        sql = plan.get("sql")
        if not sql:
            summary = plan.get("summary") or "Request could not be fulfilled with the available columns."
            msg_fig = self._build_message_card(summary)
            return {
                "figure": msg_fig,
                "detail_figure": self._build_table(pd.DataFrame()),
                "data": pd.DataFrame(),
                "summary": summary,
                "chart_type": plan.get("chart_type") or "table",
                "sql": None,
            }

        try:
            df = self._execute(sql)
        except MissingColumnError as exc:
            summary = (
                plan.get("summary")
                or f"The query referred to missing columns: {', '.join(exc.columns)}. Please adjust your request."
            )
            msg_fig = self._build_message_card(summary)
            return {
                "figure": msg_fig,
                "detail_figure": None,
                "data": pd.DataFrame(),
                "summary": summary,
                "chart_type": "table",
                "sql": None,
            }
        self._logger.debug("Executed SQL (%d rows): %s", len(df), sql)

        chart_type = plan.get("chart_type") or self._infer_chart(df)
        figure, detail = self._build_figures(df, chart_type)
        summary = plan.get("summary") or f"Query executed: {sql}"

        return {
            "figure": figure,
            "detail_figure": detail,
            "data": df,
            "summary": summary,
            "chart_type": chart_type,
            "sql": sql,
        }

    def _execute(self, sql: str) -> pd.DataFrame:
        safe_sql = self._sanitize_sql(sql.strip().rstrip(";"))
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(f"SELECT name FROM pragma_table_info('{TABLE_NAME}')")
        available_columns = {row[0] for row in cursor.fetchall()}
        cursor.close()
        try:
            df = pd.read_sql_query(f"SELECT * FROM ({safe_sql}) LIMIT 500;", conn)
        finally:
            conn.close()
        if df.empty:
            self._logger.warning("SQL returned zero rows: %s", safe_sql)
        return df

    def _sanitize_sql(self, sql: str) -> str:
        sql = _translate_sql(sql)
        for col in self._text_columns:
            pattern = re.compile(
                rf'(?<!LOWER\()(?<!\w)("?(?:{re.escape(col)})"?\b)\s*=\s*(\'[^\']+\')',
                re.IGNORECASE,
            )

            def repl(match: re.Match) -> str:
                identifier = match.group(1).strip('"')
                literal = match.group(2)
                actual = self._column_lookup.get(identifier.lower())
                if not actual:
                    return match.group(0)
                return f'LOWER("{actual}") = LOWER({literal})'

            sql = pattern.sub(repl, sql)
        return sql

    def _build_prompt(self, message: str) -> str:
        return dedent(
            f"""
            You are a helpful BI assistant. Translate the user's request into a SQL SELECT query over the table `{TABLE_NAME}`.
            Table schema (JSON): {self._schema_json}

            Return ONLY JSON with keys:
            - sql: runnable SQL string
            - chart_type: one of ["line","bar","table"]
            - summary: short description of the result

            Rules:
            - Use column names exactly as shown (case-sensitive) and wrap them in double quotes when unsure.
            - Alias every aggregate column with a descriptive snake_case name (e.g., total_sales).
            - For string comparisons, use case-insensitive matching: LOWER("column") = LOWER('value').
            - Prefer SQLite-safe functions (e.g., strftime) for date operations.
            - If a requested field does not exist, respond with {{"sql": null, "chart_type": "table", "summary": "Reason"}}.
            - Choose chart_type based on the data you expect: use "line" for time series, "bar" for categorical breakdown, "table" otherwise.

            User query: {message}
            """
        ).strip()

    def _llm_plan(self, message: str) -> Optional[Dict[str, str]]:
        try:
            generation_config = {"response_mime_type": "application/json"}
            model = genai.GenerativeModel(self._model_name, generation_config=generation_config)
            resp = model.generate_content(self._build_prompt(message))
            text = getattr(resp, "text", "")
            if not text:
                try:
                    candidates = getattr(resp, "candidates", [])
                    parts = candidates[0].content.parts if candidates else []
                    text = "".join(getattr(part, "text", "") for part in parts)
                except Exception:
                    text = ""
            if not text:
                self._logger.error("Gemini returned empty response: %s", resp)
                return None
            self._logger.debug("Raw Gemini response: %s", text)
            return json.loads(text)
        except Exception as exc:
            self._logger.exception("Failed to build plan via Gemini: %s", exc)
            return None

    def _keyword_plan(self, message: str) -> Dict[str, str]:
        text = (message or "").lower()
        measure = self._find_measure_column()
        date_col = self._find_column(["date", "day"])
        region_col = self._find_column(["region"])
        product_col = self._find_column(["product", "item"])

        if "region" in text and region_col:
            sql = (
                f'SELECT "{region_col}" as region, SUM("{measure}") as total '
                f'FROM {TABLE_NAME} GROUP BY "{region_col}" ORDER BY total DESC'
            )
            chart = "bar"
        elif "product" in text and product_col:
            sql = (
                f'SELECT "{product_col}" as product, SUM("{measure}") as total '
                f'FROM {TABLE_NAME} GROUP BY "{product_col}" ORDER BY total DESC LIMIT 10'
            )
            chart = "bar"
        elif date_col:
            sql = (
                f'SELECT "{date_col}" as date_col, SUM("{measure}") as total '
                f'FROM {TABLE_NAME} GROUP BY "{date_col}" ORDER BY "{date_col}"'
            )
            chart = "line"
        else:
            sql = f"SELECT * FROM {TABLE_NAME} LIMIT 100"
            chart = "table"
        return {"sql": sql, "chart_type": chart, "summary": "Showing results based on heuristic template."}

    def _find_column(self, keywords: list[str]) -> Optional[str]:
        for keyword in keywords:
            for col in self._columns:
                if keyword in col["name"].lower():
                    return col["name"]
        return None

    def _find_measure_column(self) -> str:
        preferred = self._find_column(["sales", "revenue", "amount", "value"])
        if preferred:
            return preferred
        if self._numeric_columns:
            return next(iter(self._numeric_columns))
        return self._columns[0]["name"]

    def _infer_chart(self, df: pd.DataFrame) -> str:
        cols = df.columns.tolist()
        if len(cols) >= 2 and "date" in df.columns:
            return "line"
        if len(cols) == 2:
            num_cols = [c for c in cols if pd.api.types.is_numeric_dtype(df[c])]
            if len(num_cols) == 1:
                return "bar"
        return "table"

    def _build_figures(self, df: pd.DataFrame, chart_type: str):
        detail = self._build_table(df) if not df.empty and chart_type != "table" else None
        main = self._build_chart(df, chart_type)
        return main, detail

    def _build_chart(self, df: pd.DataFrame, chart_type: str):
        if df.empty:
            return self._build_table(df)

        numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
        datetime_col = self._find_datetime_column(df)
        working_df = df

        if datetime_col and not pd.api.types.is_datetime64_any_dtype(working_df[datetime_col]):
            try:
                working_df = working_df.copy()
                working_df[datetime_col] = pd.to_datetime(working_df[datetime_col], errors="coerce")
            except Exception:
                pass

        if (chart_type == "line" or (chart_type == "table" and datetime_col and numeric_cols)) and datetime_col:
            y = numeric_cols[0] if numeric_cols else None
            if y:
                return px.line(working_df.dropna(subset=[datetime_col]), x=datetime_col, y=y, markers=True, title="Trend")

        if chart_type == "bar" or (chart_type != "line" and len(numeric_cols) == 1 and len(df.columns) >= 2):
            y = numeric_cols[0]
            candidates = [c for c in df.columns if c != y]
            if candidates:
                x = candidates[0]
                return px.bar(working_df, x=x, y=y, title="Breakdown")

        if len(numeric_cols) == 1 and len(df) == 1:
            value = df[numeric_cols[0]].iloc[0]
            return self._build_indicator(numeric_cols[0], value)

        return self._build_table(df)

    def _build_table(self, df: pd.DataFrame):
        if df.empty:
            header = dict(values=["message"], fill_color="paleturquoise", align="left")
            cells = dict(values=[["No data returned for this query."]], fill_color="lavender", align="left")
        else:
            header = dict(values=list(df.columns), fill_color="paleturquoise", align="left")
            cells = dict(values=[df[col] for col in df.columns], fill_color="lavender", align="left")
        fig = go.Figure(data=[go.Table(header=header, cells=cells)])
        fig.update_layout(title="Result Table")
        return fig

    def _build_indicator(self, name: str, value: float):
        return go.Figure(
            go.Indicator(
                mode="number",
                value=value,
                number={"valueformat": ",.0f"},
                title={"text": name.replace("_", " ").title()},
            )
        )

    def _build_message_card(self, message: str):
        return go.Figure(
            go.Indicator(
                mode="number",
                value=0,
                number={"font": {"color": "rgba(0,0,0,0)"}},
                title={"text": message},
            )
        )

    def _find_datetime_column(self, df: pd.DataFrame) -> Optional[str]:
        for col in df.columns:
            series = df[col]
            if pd.api.types.is_datetime64_any_dtype(series):
                return col
            if pd.api.types.is_string_dtype(series):
                try:
                    pd.to_datetime(series.dropna().head(5))
                    return col
                except Exception:
                    continue
        return None
