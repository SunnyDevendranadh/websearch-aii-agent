#!/bin/bash
# Setup script for AI Market Research Agent

# Exit on error
set -e

echo "========================================================"
echo "  Setting up AI Market Research Agent"
echo "========================================================"
echo ""

# Check if Python is installed
python_cmd=""
if command -v python3 &>/dev/null; then
    python_cmd="python3"
elif command -v python &>/dev/null; then
    python_cmd="python"
else
    echo "❌ Error: Python not found. Please install Python 3.8 or newer."
    exit 1
fi

# Check Python version
version=$($python_cmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
required_version="3.8"
if [ "$(printf '%s\n' "$required_version" "$version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "❌ Error: Python $required_version or higher is required. Found Python $version"
    exit 1
else
    echo "✅ Python $version detected"
fi

# Check if Rust is installed
if ! command -v rustc &>/dev/null; then
    echo "🔍 Rust not found. Installing Rust..."
    echo "⏳ This may take a few minutes..."
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    source "$HOME/.cargo/env"
    echo "✅ Rust installation completed"
else
    rust_version=$(rustc --version | cut -d' ' -f2)
    echo "✅ Rust $rust_version is installed"
fi

# Create virtual environment directory if it doesn't exist
if [ -d ".venv" ]; then
    echo "🔄 Removing existing virtual environment..."
    rm -rf .venv
fi

# Create and activate virtual environment
echo "🔧 Creating Python virtual environment..."
$python_cmd -m venv .venv
source .venv/bin/activate

# Install Python dependencies
echo "📦 Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Make sure key packages are installed
echo "🔍 Ensuring key packages are installed..."
pip install anthropic --upgrade
pip install openai --upgrade
pip install python-dotenv --upgrade
pip install questionary --upgrade
pip install markdown --upgrade
pip install reportlab --upgrade

# Build and install the Rust backend
echo "🔨 Building Rust performance backend..."
if [ -d "market_research_cli/market_research_core" ]; then
cd market_research_cli/market_research_core
    # Check if maturin is installed
    if ! command -v maturin &>/dev/null; then
        echo "📦 Installing Maturin build tool..."
        pip install maturin
    fi
    
    echo "🚀 Building Rust library..."
maturin build --release
    
    echo "📦 Installing Rust library..."
pip install target/wheels/market_research_core-*.whl
cd ../..
    echo "✅ Rust backend successfully built and installed"
else
    echo "⚠️ Rust core directory not found, skipping Rust backend build"
    echo "   The application will run in Python-only mode with reduced performance"
fi

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "📝 Creating template .env file..."
    cat > .env << EOF
# API Keys for AI Market Research Agent
# Replace the placeholder values with your actual API keys

# Required: OpenAI API Key (https://platform.openai.com/account/api-keys)
OPENAI_API_KEY=your_openai_api_key_here

# Optional: Anthropic Claude API Key (https://console.anthropic.com/account/keys)
ANTHROPIC_API_KEY=your_claude_api_key_here

# Optional: Brave Search API Key (https://brave.com/search/api/)
BRAVE_API_KEY=your_brave_search_api_key_here

# Optional: Twilio SMS Integration
TWILIO_ACCOUNT_SID=your_twilio_account_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_PHONE_NUMBER=your_twilio_phone_number
EOF
    echo "✅ Template .env file created"
    echo "⚠️ Please edit the .env file with your actual API keys before running the application"
else
    echo "✅ .env file already exists"
fi

# Create reports directory if it doesn't exist
if [ ! -d "reports" ]; then
    echo "📁 Creating reports directory..."
    mkdir -p reports
    echo "✅ Reports directory created"
else
    echo "✅ Reports directory already exists"
fi

echo ""
echo "========================================================"
echo "  ✅ Setup Complete!"
echo "========================================================"
echo ""
echo "To run the AI Market Research Agent:"
echo "  1. Edit the .env file with your API keys"
echo "  2. Run the application with:"
echo "     ./run.sh"
echo ""
echo "Enjoy generating comprehensive market research reports!" 