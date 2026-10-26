@echo off
setlocal
cd /d "%~dp0"

title Veritas Multimodal AI Forensic Suite - Server
color 09

echo ===============================================================================
echo      VERITAS MULTIMODAL FAKE NEWS AND AI MEDIA FORENSIC SUITE v4.0
echo               Explainable AI - Forensics - Virality - Datasets
echo ===============================================================================
echo.

rem 1. Check if virtual environment exists
if not exist ".venv\Scripts\python.exe" (
    color 0E
    echo [!] Virtual environment not found at: %~dp0.venv
    echo [*] Running setup.bat first to configure your environment...
    echo.
    call "%~dp0setup.bat"
    if %ERRORLEVEL% neq 0 (
        color 0C
        echo [ERROR] Setup failed!
        pause
        exit /b 1
    )
)

rem 2. Default host and port configuration
set "HOST=127.0.0.1"
set "PORT=8000"

rem 3. Read custom host and port from .env if present
if exist ".env" (
    for /f "usebackq tokens=1,2 delims==" %%A in (".env") do (
        if "%%A"=="SERVER_HOST" set "HOST=%%B"
        if "%%A"=="SERVER_PORT" set "PORT=%%B"
    )
)

rem Remove any accidental whitespace around host/port
set "HOST=%HOST: =%"
set "PORT=%PORT: =%"

echo [+] Server Host: http://%HOST%:%PORT%
echo [*] Initializing AI models and launching Veritas...
echo.
echo ===============================================================================
echo     Application URL: http://%HOST%:%PORT%
echo     Swagger Docs:    http://%HOST%:%PORT%/docs
echo     Press Ctrl+C to stop the server
echo ===============================================================================
echo.

rem 4. Check if port is already in use by a previous process and clean if needed
netstat -ano | findstr /R /C:":%PORT% .*LISTENING" >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo [!] Port %PORT% is currently occupied by an existing process.
    echo [*] Cleaning previous instance on port %PORT%...
    for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":%PORT% .*LISTENING"') do (
        taskkill /F /PID %%P >nul 2>&1
    )
    timeout /t 1 /nobreak >nul
)

rem 5. Automatically open web browser as soon as the server starts listening
start "" /b powershell -NoProfile -Command ^
    "for ($i=0; $i -lt 40; $i++) { try { $c = New-Object System.Net.Sockets.TcpClient; $c.Connect('%HOST%', %PORT%); if ($c.Connected) { $c.Close(); Start-Process 'http://%HOST%:%PORT%'; break } } catch { Start-Sleep -Milliseconds 250 } }"

rem 6. Run FastAPI Application via Uvicorn using the virtual environment Python
".venv\Scripts\python.exe" -m uvicorn app.main:app --host %HOST% --port %PORT%

if %ERRORLEVEL% neq 0 (
    echo.
    color 0C
    echo [ERROR] Server stopped with error code %ERRORLEVEL%.
    pause
)
