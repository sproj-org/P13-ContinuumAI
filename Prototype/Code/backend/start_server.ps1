# Start FastAPI Server
Set-Location $PSScriptRoot
python -m uvicorn app.main:app --reload
