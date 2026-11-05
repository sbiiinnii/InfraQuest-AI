@echo off
rem InfraQuest AI - first-time setup (run once)
cd /d "%~dp0"

echo [1/3] Creating Python environment and installing backend packages...
if not exist backend\.venv python -m venv backend\.venv
backend\.venv\Scripts\python -m pip install -q -r backend\requirements.txt
if errorlevel 1 goto fail

echo [2/3] Installing frontend packages...
cd frontend
call npm install
if errorlevel 1 goto fail
cd ..

echo [3/3] Preparing the API key file...
if not exist backend\.env (
  copy backend\.env.example backend\.env >nul
  echo Created backend\.env  -- open it and put your ANTHROPIC_API_KEY in it.
) else (
  echo backend\.env already exists. Leaving it as it is.
)

echo.
echo Setup finished. Next: put your key in backend\.env, then double-click start.bat
pause
exit /b 0

:fail
echo.
echo Setup failed. Please read the message above.
pause
exit /b 1
