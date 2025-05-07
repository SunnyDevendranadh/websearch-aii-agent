@echo off
setlocal enabledelayedexpansion

REM Set text colors (Windows equivalent with color codes)
set "GREEN=[92m"
set "YELLOW=[93m"
set "RED=[91m"
set "BLUE=[94m"
set "NC=[0m"

REM Print banner
echo %BLUE%
echo ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
echo ┃                                                         ┃
echo ┃                 AI MARKET AGENT                         ┃
echo ┃                                                         ┃
echo ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
echo %NC%

REM Check if virtual environment exists
if not exist .venv (
    echo %YELLOW%Virtual environment not found. Running setup script first.%NC%
    call setup.bat
)

REM Check if .env file exists
if not exist .env (
    echo %YELLOW%Warning: .env file not found. The application may not work correctly without API keys.%NC%
    echo You should create a .env file with at least your OpenAI API key.
    echo.
    
    REM Ask if user wants to create a basic .env file
    set /p create_env="Would you like to create a basic .env file now? (y/n): "
    if /i "!create_env!"=="y" (
        echo Creating .env file...
        set /p openai_key="Enter your OpenAI API key: "
        
        REM Create .env file with OpenAI key
        (
            echo # API Keys for AI Market Research Agent
            echo OPENAI_API_KEY=!openai_key!
            echo.
            echo # Optional: Anthropic Claude API Key
            echo ANTHROPIC_API_KEY=
            echo.
            echo # Optional: Brave Search API Key
            echo BRAVE_API_KEY=
            echo.
            echo # Optional: Twilio SMS Integration
            echo TWILIO_ACCOUNT_SID=
            echo TWILIO_AUTH_TOKEN=
            echo TWILIO_PHONE_NUMBER=
        ) > .env
        echo %GREEN%Basic .env file created successfully!%NC%
    ) else (
        echo %YELLOW%Continuing without .env file. You may need to configure API keys in the application.%NC%
    )
)

REM Activate virtual environment
echo %GREEN%Activating virtual environment...%NC%
call .venv\Scripts\activate

REM Create reports directory if it doesn't exist
if not exist reports (
    echo %YELLOW%Reports directory not found. Creating it now...%NC%
    mkdir reports
)

echo %GREEN%Starting AI Market Research Agent...%NC%

REM Run the CLI with error handling
python market_research_cli\fast_cli.py %* 
if %ERRORLEVEL% NEQ 0 (
    echo %RED%Application exited with error. Exit code: %ERRORLEVEL%%NC%
    echo %YELLOW%Check the error message above for details.%NC%
    
    REM Provide troubleshooting help
    echo.
    echo %BLUE%Troubleshooting Tips:%NC%
    echo 1. Ensure your API keys are correctly set in the .env file
    echo 2. Check your internet connection
    echo 3. Make sure all dependencies are installed (run setup.bat again)
    echo 4. If using Rust features, ensure Rust is properly installed
    echo 5. Check if the Python packages are up to date
    
    exit /b 1
)

endlocal 