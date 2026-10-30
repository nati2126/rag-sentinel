# Start the RAG Sentinel API on http://127.0.0.1:8000 (reads settings from .env).
# Usage: .\scripts\run_api.ps1 [-DataDir data/kb] [-Port 8000]
param([string]$DataDir = "", [int]$Port = 8000)
Set-Location (Split-Path $PSScriptRoot -Parent)
if ($DataDir) { $env:SENTINEL_DATA_DIR = $DataDir }
.venv\Scripts\python.exe -m uvicorn rag_sentinel.api.main:app --host 127.0.0.1 --port $Port
