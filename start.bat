@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion
pushd "%~dp0"

echo ============================================
echo   AgentTranslation - Starting...
echo ============================================
echo.

:: === Check Python ===
python --version >nul 2>&1
if errorlevel 1 (
    echo [Setup] Python not found, installing...
    winget install Python.Python.3.12 --accept-package-agreements --accept-source-agreements --silent
    if errorlevel 1 (
        echo [Setup] winget failed, trying direct download...
        powershell -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe' -OutFile $env:TEMP\python_setup.exe"
        if errorlevel 1 (
            echo [ERROR] Cannot download Python.
            echo Please install manually: https://www.python.org/downloads/
            goto :fail
        )
        echo [Setup] Installing Python...
        "%TEMP%\python_setup.exe" /quiet InstallAllUsers=0 PrependPath=1 Include_pip=1
        del "%TEMP%\python_setup.exe" >nul 2>&1
    )
    :: Refresh PATH
    for /f "tokens=2*" %%A in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v Path 2^>nul') do set "SYS_PATH=%%B"
    for /f "tokens=2*" %%A in ('reg query "HKCU\Environment" /v Path 2^>nul') do set "USR_PATH=%%B"
    set "PATH=!SYS_PATH!;!USR_PATH!;%LOCALAPPDATA%\Microsoft\WindowsApps"
)
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python still not available. Please restart computer and run again.
    goto :fail
)
echo [OK] Python found:
python --version

:: === Check Node.js ===
node --version >nul 2>&1
if errorlevel 1 (
    echo [Setup] Node.js not found, installing...
    winget install OpenJS.NodeJS.LTS --accept-package-agreements --accept-source-agreements --silent
    if errorlevel 1 (
        echo [Setup] winget failed, trying direct download...
        powershell -Command "Invoke-WebRequest -Uri 'https://nodejs.org/dist/v22.16.0/node-v22.16.0-x64.msi' -OutFile $env:TEMP\node_setup.msi"
        if errorlevel 1 (
            echo [ERROR] Cannot download Node.js.
            echo Please install manually: https://nodejs.org/
            goto :fail
        )
        echo [Setup] Installing Node.js...
        msiexec /i "%TEMP%\node_setup.msi" /quiet /norestart
        del "%TEMP%\node_setup.msi" >nul 2>&1
    )
    :: Refresh PATH
    for /f "tokens=2*" %%A in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v Path 2^>nul') do set "SYS_PATH=%%B"
    for /f "tokens=2*" %%A in ('reg query "HKCU\Environment" /v Path 2^>nul') do set "USR_PATH=%%B"
    set "PATH=!SYS_PATH!;!USR_PATH!;%LOCALAPPDATA%\Microsoft\WindowsApps;C:\Program Files\nodejs"
)
node --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js still not available. Please restart computer and run again.
    goto :fail
)
echo [OK] Node.js found:
node --version
echo.

:: === Setup Python venv ===
if not exist .venv-win\Scripts\activate.bat (
    if exist .venv-win (
        echo [Setup] Removing incompatible venv, recreating for Windows...
        rmdir /s /q .venv-win
    )
    echo [Setup] Creating Python virtual environment...
    python -m venv .venv-win
)
call .venv-win\Scripts\activate.bat

if not exist .venv-win\.deps_installed (
    echo [Setup] Installing Python dependencies, first time may take a few minutes...
    pip install --upgrade pip
    pip install -r requirements.txt
    echo. > .venv-win\.deps_installed
)
echo [OK] Python dependencies ready

:: === Setup frontend ===
if not exist frontend\node_modules (
    echo [Setup] Installing frontend dependencies...
    pushd frontend
    call npm install
    popd
)
if not exist frontend\dist\index.html (
    echo [Setup] Building frontend...
    pushd frontend
    call npm run build
    popd
)
echo [OK] Frontend ready

:: === Load .env ===
if exist .env (
    for /f "usebackq eol=# tokens=*" %%L in (".env") do (
        set "%%L"
    )
)

:: === Start server ===
echo.
echo ============================================
echo   Server starting at http://localhost:8000
echo   Press Ctrl+C to stop
echo ============================================
echo.

:: Open browser after short delay
start "" http://localhost:8000

if not exist .venv-win\Scripts\python.exe (
    echo [ERROR] Python venv is corrupted. Delete .venv-win folder and try again.
    goto :fail
)
.venv-win\Scripts\python.exe -m uvicorn src.server:app --host 127.0.0.1 --port 8000
if errorlevel 1 goto :fail
pause
goto :eof

:fail
echo.
echo ============================================
echo   Startup FAILED! See error messages above.
echo ============================================
echo.
pause
exit /b 1
