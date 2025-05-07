@echo off
setlocal enabledelayedexpansion

echo ========================================================
echo   Setting up AI Market Research Agent
echo ========================================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [X] Error: Python not found. Please install Python 3.8 or newer.
    exit /b 1
)

REM Check Python version
for /f "tokens=2" %%I in ('python --version 2^>^&1') do set PYVER=%%I
for /f "tokens=1,2 delims=." %%A in ("%PYVER%") do (
    set PYMAJOR=%%A
    set PYMINOR=%%B
)
if "%PYMAJOR%"=="2" (
    echo [X] Error: Python 3.8 or higher is required. Found Python %PYVER%
    exit /b 1
)
if %PYMAJOR%==3 if %PYMINOR% LSS 8 (
    echo [X] Error: Python 3.8 or higher is required. Found Python %PYVER%
    exit /b 1
)
echo [✓] Python %PYVER% detected

REM Check if Rust is installed
rustc --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [!] Rust not found. Installing Rust...
    echo This may take a few minutes...
    curl --proto '=https' --tlsv1.2 -sSf https://win.rustup.rs/x86_64 -o rustup-init.exe
    rustup-init.exe -y
    del rustup-init.exe
    set PATH=%USERPROFILE%\.cargo\bin;%PATH%
    echo [✓] Rust installation completed
) else (
    for /f "tokens=2" %%I in ('rustc --version 2^>^&1') do set RUSTVER=%%I
    echo [✓] Rust !RUSTVER! is installed
)

REM Remove existing virtual environment if it exists
if exist .venv (
    echo [!] Removing existing virtual environment...
    rmdir /s /q .venv
)

REM Create and activate virtual environment
echo [!] Creating Python virtual environment...
python -m venv .venv
call .venv\Scripts\activate

REM Install Python dependencies
echo [!] Installing Python dependencies...
python -m pip install --upgrade pip
pip install -r requirements.txt

REM Make sure key packages are installed
echo [!] Ensuring key packages are installed...
pip install anthropic --upgrade
pip install openai --upgrade
pip install python-dotenv --upgrade
pip install questionary --upgrade
pip install markdown --upgrade
pip install reportlab --upgrade

REM Build and install the Rust backend
echo [!] Building Rust performance backend...
if exist market_research_cli\market_research_core (
cd market_research_cli\market_research_core
    
    REM Check if maturin is installed
    pip show maturin >nul 2>&1
    if %ERRORLEVEL% NEQ 0 (
        echo [!] Installing Maturin build tool...
        pip install maturin
    )
    
    echo [!] Building Rust library...
maturin build --release
    
    echo [!] Installing Rust library...
pip install target\wheels\market_research_core-*-win_amd64.whl
cd ..\..
    echo [✓] Rust backend successfully built and installed
) else (
    echo [!] Rust core directory not found, skipping Rust backend build
    echo    The application will run in Python-only mode with reduced performance
)

REM Create .env file if it doesn't exist
if not exist .env (
    echo [!] Creating template .env file...
    (
        echo # API Keys for AI Market Research Agent
        echo # Replace the placeholder values with your actual API keys
        echo.
        echo # Required: OpenAI API Key (https://platform.openai.com/account/api-keys^)
        echo OPENAI_API_KEY=your_openai_api_key_here
        echo.
        echo # Optional: Anthropic Claude API Key (https://console.anthropic.com/account/keys^)
        echo ANTHROPIC_API_KEY=your_claude_api_key_here
        echo.
        echo # Optional: Brave Search API Key (https://brave.com/search/api/^)
        echo BRAVE_API_KEY=your_brave_search_api_key_here
        echo.
        echo # Optional: Twilio SMS Integration
        echo TWILIO_ACCOUNT_SID=your_twilio_account_sid
        echo TWILIO_AUTH_TOKEN=your_twilio_auth_token
        echo TWILIO_PHONE_NUMBER=your_twilio_phone_number
    ) > .env
    echo [✓] Template .env file created
    echo [!] Please edit the .env file with your actual API keys before running the application
) else (
    echo [✓] .env file already exists
)

REM Create reports directory if it doesn't exist
if not exist reports (
    echo [!] Creating reports directory...
    mkdir reports
    echo [✓] Reports directory created
) else (
    echo [✓] Reports directory already exists
)

echo.
echo ========================================================
echo   [✓] Setup Complete!
echo ========================================================
echo.
echo To run the AI Market Research Agent:
echo   1. Edit the .env file with your API keys
echo   2. Run the application with:
echo      run.bat
echo.
echo Enjoy generating comprehensive market research reports!

endlocal 