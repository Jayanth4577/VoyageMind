@echo off
REM VoyageMind local dev starter — run after reboot (needs Docker Desktop running for Postgres).
REM Usage: double-click, or run `scripts\start-local.bat` from the repo root.

setlocal
cd /d "%~dp0.."

echo [1/3] Making sure Postgres is up (Docker Desktop must be running)...
docker compose up -d postgres
if errorlevel 1 (
    echo.
    echo  Docker is not reachable. Start Docker Desktop first, then re-run this script.
    pause
    exit /b 1
)

echo [2/3] Starting MCP gateway, backend and frontend in separate windows...
start "VoyageMind MCP gateway (8001)" cmd /k "cd travel-mcp-server && set TRAVEL_MCP_DEMO_MODE=1 && .venv\Scripts\python -m uvicorn travel_mcp.server:app --host 0.0.0.0 --port 8001"
start "VoyageMind backend (8000)"    cmd /k "cd backend && set TRAVEL_MCP_URL=http://localhost:8001 && .venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"
start "VoyageMind frontend (3000)"   cmd /k "cd frontend && npm run dev"

echo [3/3] Done — opening http://localhost:3000 in a few seconds...
timeout /t 12 >nul
start http://localhost:3000
endlocal
