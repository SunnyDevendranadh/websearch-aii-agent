@echo off
REM Run script for Market Research Generator CLI

REM Check if virtual environment exists
if not exist .venv (
    echo Virtual environment not found. Please run setup.bat first.
    exit /b 1
)

REM Activate virtual environment
call .venv\Scripts\activate

REM Run the CLI
python market_research_cli\fast_cli.py %* 