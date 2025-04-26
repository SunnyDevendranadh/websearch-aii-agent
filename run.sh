#!/bin/bash
# Run script for Market Research Generator CLI

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "Virtual environment not found. Please run setup.sh first."
    exit 1
fi

# Activate virtual environment
source .venv/bin/activate


# Run the CLI
python market_research_cli/fast_cli.py $@ 