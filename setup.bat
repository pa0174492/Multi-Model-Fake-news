@echo off
setlocal
cd /d "%~dp0"

title Veritas Forensic Suite - Setup and Installation
color 0B

echo ===============================================================================
echo      VERITAS MULTIMODAL FAKE NEWS AND AI MEDIA FORENSIC SUITE v4.0
echo                   Automated Environment Setup and Installer
echo ===============================================================================
echo.

rem 1. Check if virtual environment already exists
if exist ".venv\Scripts\python.exe" goto VENV_EXISTS

rem 2. Find Python executable
set "PY_CMD="

where python >nul 2>&1
if %ERRORLEVEL% equ 0 (
    set "PY_CMD=python"
    goto FOUND_PY
)

where py >nul 2>&1
if %ERRORLEVEL% equ 0 (
    set "PY_CMD=py"
    goto FOUND_PY
)

if exist "C:\Python312\python.exe" (
    set "PY_CMD=C:\Python312\python.exe"
    goto FOUND_PY
)

if exist "C:\Python311\python.exe" (
    set "PY_CMD=C:\Python311\python.exe"
    goto FOUND_PY
)

color 0C
echo [ERROR] Python was not found in your system PATH!
echo Please install Python 3.10, 3.11, or 3.12 from https://www.python.org/
echo Make sure to check the option: "Add Python to PATH" during installation.
echo.
pause
exit /b 1

:FOUND_PY
echo [*] Checking Python executable: %PY_CMD%
%PY_CMD% --version
if %ERRORLEVEL% neq 0 (
    color 0C
    echo [ERROR] Python command failed to execute!
    pause
    exit /b 1
)
echo.

echo [*] Creating virtual environment (.venv)...
%PY_CMD% -m venv .venv
if %ERRORLEVEL% neq 0 (
    color 0C
    echo [ERROR] Failed to create virtual environment!
    pause
    exit /b 1
)
echo [+] Virtual environment created successfully.
echo.

:VENV_EXISTS
echo [+] Virtual environment verified at: %~dp0.venv
echo.

rem 3. Upgrade Pip using virtual environment python
echo [*] Upgrading pip...
".venv\Scripts\python.exe" -m pip install --upgrade pip --quiet
echo [+] Pip upgraded.
echo.

rem 4. Install Dependencies
echo [*] Installing required packages from requirements.txt...
echo     Please wait, this ensures all PyTorch, Transformers, and ML libraries are ready.
echo.
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if %ERRORLEVEL% neq 0 (
    color 0C
    echo.
    echo [ERROR] Package installation failed!
    echo Please check the error messages above.
    pause
    exit /b 1
)
echo.
echo [+] All dependencies verified and installed successfully!
echo.

rem 5. Setup .env configuration file if missing
if exist ".env" goto ENV_EXISTS
echo [*] Creating default .env configuration file...
(
    echo # Veritas Multimodal AI Configuration
    echo.
    echo # MongoDB Connection URI
    echo MONGODB_URI=mongodb://localhost:27017/veritas_db
    echo MONGODB_DB_NAME=veritas_db
    echo.
    echo # Google Gemini API Key - Optional for online internet fact-checking
    echo GEMINI_API_KEY=
    echo.
    echo # Server Port and Host Configuration
    echo SERVER_HOST=127.0.0.1
    echo SERVER_PORT=8000
) > .env
echo [+] Default .env configuration created.
goto DONE_ENV

:ENV_EXISTS
echo [+] Configuration file .env detected.

:DONE_ENV
echo.
color 0A
echo ===============================================================================
echo [+] SETUP COMPLETE! The Veritas Forensic Suite is ready to run.
echo.
echo You can start the application at any time by double-clicking:
echo     run.bat
echo ===============================================================================
echo.
set /p START_CHOICE="Start the application now? (Y/N): "
if /i "%START_CHOICE%"=="Y" (
    echo [*] Starting Veritas...
    call "%~dp0run.bat"
) else (
    echo.
    echo Setup finished. Run run.bat when you are ready.
    pause
)
