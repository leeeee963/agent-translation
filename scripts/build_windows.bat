@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0\.."

echo ============================================
echo   AgentTranslation Windows Build
echo ============================================
echo.

:: ============ Check and install Python ============
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
        "%TEMP%\python_setup.exe" /quiet InstallAllUsers=0 PrependPath=1 Include_pip=1
        del "%TEMP%\python_setup.exe" >nul 2>&1
    )
    echo [Setup] Updating PATH...
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

:: ============ Check and install Node.js ============
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
        msiexec /i "%TEMP%\node_setup.msi" /quiet /norestart
        del "%TEMP%\node_setup.msi" >nul 2>&1
    )
    echo [Setup] Updating PATH...
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

:: ============ Step 1: Install Python dependencies ============
echo === Step 1: Install Python dependencies (first time may take a few minutes) ===
pip install -r requirements.txt
if errorlevel 1 goto :fail
pip install pyinstaller pywebview
if errorlevel 1 goto :fail
echo [OK] Dependencies installed.
echo.

:: ============ Step 2: Build frontend ============
echo === Step 2: Build frontend ===
cd frontend
if exist node_modules (
    echo [Setup] Cleaning old node_modules...
    rmdir /s /q node_modules
)
call npm install
if errorlevel 1 (
    cd ..
    goto :fail
)
call npm run build
if errorlevel 1 (
    cd ..
    goto :fail
)
cd ..
echo [OK] Frontend built.
echo.

:: ============ Step 3: Build Windows executable ============
echo === Step 3: Build Windows executable ===
pyinstaller scripts\build_windows.spec --clean --noconfirm
if errorlevel 1 goto :fail

echo.
echo ============================================
echo   Build successful!
echo   Output: dist\AgentTranslation\AgentTranslation.exe
echo ============================================
echo.
pause
exit /b 0

:fail
echo.
echo ============================================
echo   Build FAILED! See error messages above.
echo ============================================
echo.
pause
exit /b 1
