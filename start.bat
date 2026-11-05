@echo off
rem InfraQuest AI - start backend and frontend in two windows
cd /d "%~dp0"

if not exist backend\.venv (
  echo Please run setup.bat first.
  pause
  exit /b 1
)

start "InfraQuest backend (keep open)" cmd /k "cd /d %~dp0backend && .venv\Scripts\python -m uvicorn main:app --port 8000"
start "InfraQuest frontend (keep open)" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo Two windows were opened. Wait a few seconds, then open the address
echo shown in the "frontend" window (usually http://localhost:5173).
echo If 5173 is already used by another program, it shows 5174 or similar. Use that one.
echo To stop: close both windows.
pause
