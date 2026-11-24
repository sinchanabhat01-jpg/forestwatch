@echo off
setlocal EnableExtensions
title ForestWatch AI - Launcher
cd /d "%~dp0"

echo.
echo  ==========================================
echo       FORESTWATCH AI - LOCAL LAUNCHER
echo  ==========================================
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo ERROR: Python 3.11 or newer is required.
  echo Install from https://www.python.org/downloads/ and enable Add Python to PATH.
  pause
  exit /b 1
)
where node >nul 2>nul
if errorlevel 1 (
  echo ERROR: Node.js 18 or newer is required.
  echo Install from https://nodejs.org/
  pause
  exit /b 1
)

python -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)"
if errorlevel 1 (
  echo ERROR: Python 3.11 or newer is required.
  pause
  exit /b 1
)

node -e "process.exit(Number(process.versions.node.split('.')[0]) >= 18 ? 0 : 1)"
if errorlevel 1 (
  echo ERROR: Node.js 18 or newer is required.
  pause
  exit /b 1
)

if not exist "backend\.env" (
  echo Creating local configuration...
  for /f %%i in ('python -c "import secrets; print(secrets.token_hex(32))"') do set JWT=%%i
  >"backend\.env" echo DATABASE_URL=sqlite:///./forestwatch_dev.db
  >>"backend\.env" echo JWT_SECRET=%JWT%
  >>"backend\.env" echo CORS_ORIGINS=http://localhost:5173
  >>"backend\.env" echo SH_PROVIDER=cdse
  >>"backend\.env" echo SH_CLIENT_ID=
  >>"backend\.env" echo SH_CLIENT_SECRET=
  >>"backend\.env" echo GFW_API_KEY=
  >>"backend\.env" echo IMAGE_DIR=./data/images
)

if not exist "backend\.venv\Scripts\python.exe" (
  echo Creating Python environment...
  python -m venv backend\.venv
  if errorlevel 1 (
    echo ERROR: Could not create Python environment.
    pause
    exit /b 1
  )
)

echo Installing/checking backend packages...
"backend\.venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r backend\requirements.txt
if errorlevel 1 (
  echo ERROR: Backend package installation failed. Check your internet connection.
  pause
  exit /b 1
)

if not exist "frontend\node_modules\vite\bin\vite.js" (
  echo Installing frontend packages...
  pushd frontend
  call npm install --no-audit --no-fund
  if errorlevel 1 (
    popd
    echo ERROR: Frontend package installation failed. Check your internet connection.
    pause
    exit /b 1
  )
  popd
)

echo.
echo Starting backend...
start "ForestWatch Backend" /D "%~dp0backend" cmd /k ".venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000"

echo Starting frontend...
start "ForestWatch Frontend" /D "%~dp0frontend" cmd /k "npm run dev -- --host 127.0.0.1"

echo.
echo Waiting for ForestWatch services...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ok=$false; for($i=0;$i -lt 40;$i++){ try{$a=Invoke-WebRequest -UseBasicParsing http://127.0.0.1:5173 -TimeoutSec 2; if($a.StatusCode -eq 200){$ok=$true;break}}catch{}; Start-Sleep -Seconds 2 }; if(-not $ok){exit 1}"
if errorlevel 1 (
  echo WARNING: The website did not respond yet. Keep both server windows open and check for errors.
  echo You can retry at http://localhost:5173 after the servers finish starting.
) else (
  echo Opening ForestWatch AI...
  where chrome >nul 2>nul
  if not errorlevel 1 (
    start "" chrome http://localhost:5173
  ) else (
    start "" http://localhost:5173
  )
)

echo.
echo Website: http://localhost:5173
echo API health: http://localhost:8000/api/health
echo API documentation: http://localhost:8000/docs
echo Keep both server windows open while using ForestWatch.
echo Close the server windows to stop it.
pause
