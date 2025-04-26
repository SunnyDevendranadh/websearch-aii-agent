@echo off
echo ========================================================
echo   Setting up Market Research Generator CLI
echo ========================================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Error: Python not found. Please install Python 3.8 or newer.
    exit /b 1
)

REM Check Python version
for /f "tokens=2" %%I in ('python --version 2^>^&1') do set PYVER=%%I
for /f "tokens=1,2 delims=." %%A in ("%PYVER%") do (
    set PYMAJOR=%%A
    set PYMINOR=%%B
)
if "%PYMAJOR%"=="2" (
    echo Error: Python 3.8 or higher is required. Found Python %PYVER%
    exit /b 1
)
if %PYMAJOR%==3 if %PYMINOR% LSS 8 (
    echo Error: Python 3.8 or higher is required. Found Python %PYVER%
    exit /b 1
)

REM Check if Rust is installed
rustc --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Rust not found. Installing Rust...
    echo This may take a few minutes...
    curl --proto '=https' --tlsv1.2 -sSf https://win.rustup.rs/x86_64 -o rustup-init.exe
    rustup-init.exe -y
    del rustup-init.exe
    set PATH=%USERPROFILE%\.cargo\bin;%PATH%
) else (
    echo [✓] Rust is installed
)

REM Create and activate virtual environment
echo Creating Python virtual environment...
python -m venv .venv
call .venv\Scripts\activate

REM Install Python dependencies
echo Installing Python dependencies...
python -m pip install --upgrade pip
pip install -r requirements.txt

REM Build and install the Rust backend
echo Building Rust performance backend...
cd market_research_cli\market_research_core
maturin build --release
pip install target\wheels\market_research_core-*-win_amd64.whl
cd ..\..

echo.
echo ========================================================
echo   Setup Complete!
echo ========================================================
echo.
echo To run the Market Research Generator CLI:
echo   1. Activate the virtual environment:
echo      .venv\Scripts\activate
echo   2. Run the CLI:
echo      python market_research_cli\fast_cli.py
echo.
echo To use Claude's AI capabilities (optional):
echo   pip install anthropic
echo.
echo Enjoy your accelerated market research experience! 