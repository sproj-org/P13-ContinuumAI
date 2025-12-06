# MCP Demo (Vizro + Streamlit)

## What it does
- Streamlit app (`vizro_app2/continuum_v1/app.py`) that lets you pick a dataset from `vizro_app2/continuum_v1/data/`, profile it, and chat with an LLM to generate charts/KPIs.
- The LLM produces chart/dashboard plans; Vizro MCP validates the plans and returns runnable Vizro Python code plus a live preview server on port 8051.
- Chart data and KPI cards are cached so you can ask follow-up questions against the rendered visuals without re-querying the LLM.

## How it works (quick flow)
- **Dataset lane:** select a file → the app profiles columns/types/stats and stores metadata in session state for prompt grounding.
- **LLM lane:** prompts include the dataset summary; OpenAI responds with chart/KPI plans; plans are validated/executed through the Vizro MCP CLI (`vizro-mcp`).
- **Dashboard assembly:** validated components are composed into a Vizro dashboard; validation can be previewed in the browser via the MCP-generated code.

## Setup (Windows-friendly)
Run these from `Development/Sprint-1/RnD (Umer)`:
1) Create a virtual env  
   `python -m venv .venv`
2) Activate it  
   `.\.venv\Scripts\activate`
3) Install dependencies  
   `pip install -r requirements.txt`
4) Set your OpenAI key (PowerShell example)  
   `$env:OPENAI_API_KEY="sk-..."`  
   or add it to a `.env` alongside `app.py` if you prefer.
5) Start the app  
   `streamlit run vizro_app2/continuum_v1/app.py`

Notes:
- Datasets live in `vizro_app2/continuum_v1/data/` (CSV/XLSX/JSON/Parquet).
- `vizro-mcp` is installed via requirements; the app calls it directly for validation/preview.
- Preview opens at `http://localhost:8051` after a successful validation.
