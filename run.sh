#!/bin/bash
# Run script for AI Market Research Agent

# Set text colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print banner
echo -e "${BLUE}"
echo "┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓"
echo "┃                                                         ┃"
echo "┃                 AI MARKET AGENT                         ┃"
echo "┃                                                         ┃"
echo "┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛"
echo -e "${NC}"

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}Virtual environment not found. Running setup script first.${NC}"
    chmod +x setup.sh
    ./setup.sh
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}Warning: .env file not found. The application may not work correctly without API keys.${NC}"
    echo -e "You should create a .env file with at least your OpenAI API key."
    echo
    # Ask if user wants to create a basic .env file
    read -p "Would you like to create a basic .env file now? (y/n): " create_env
    if [[ $create_env == "y" || $create_env == "Y" ]]; then
        echo "Creating .env file..."
        read -p "Enter your OpenAI API key: " openai_key
        
        # Create .env file with OpenAI key
        cat > .env << EOF
# API Keys for AI Market Research Agent
OPENAI_API_KEY=$openai_key

# Optional: Anthropic Claude API Key
ANTHROPIC_API_KEY=

# Optional: Brave Search API Key
BRAVE_API_KEY=

# Optional: Twilio SMS Integration
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_PHONE_NUMBER=
EOF
        echo -e "${GREEN}Basic .env file created successfully!${NC}"
    else
        echo -e "${YELLOW}Continuing without .env file. You may need to configure API keys in the application.${NC}"
    fi
fi

# Activate virtual environment
echo -e "${GREEN}Activating virtual environment...${NC}"
source .venv/bin/activate

# Create reports directory if it doesn't exist
if [ ! -d "reports" ]; then
    echo -e "${YELLOW}Reports directory not found. Creating it now...${NC}"
    mkdir -p reports
fi

echo -e "${GREEN}Starting AI Market Research Agent...${NC}"

# Run the CLI with error handling to see any crashes
python -u market_research_cli/fast_cli.py "$@" || { 
    echo -e "${RED}Application exited with error. Exit code: $?${NC}"
    echo -e "${YELLOW}Check the error message above for details.${NC}"
    
    # Provide troubleshooting help
    echo -e "\n${BLUE}Troubleshooting Tips:${NC}"
    echo "1. Ensure your API keys are correctly set in the .env file"
    echo "2. Check your internet connection"
    echo "3. Make sure all dependencies are installed (run setup.sh again)"
    echo "4. If using Rust features, ensure Rust is properly installed"
    echo "5. Check if the Python packages are up to date"
    
    exit 1
} 