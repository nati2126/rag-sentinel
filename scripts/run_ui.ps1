# Start the Streamlit dashboard on http://localhost:8501. The API must be running (scripts\run_api.ps1).
# Usage: .\scripts\run_ui.ps1 [-ApiUrl http://127.0.0.1:8000]
param([string]$ApiUrl = "")
Set-Location (Split-Path $PSScriptRoot -Parent)
if ($ApiUrl) { $env:SENTINEL_API_URL = $ApiUrl }
.venv\Scripts\python.exe -m streamlit run ui/app.py --server.port 8501
