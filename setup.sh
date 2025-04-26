#!/bin/bash
# Setup script for Market Research Generator CLI

echo "========================================================"
echo "  Setting up Market Research Generator CLI"
echo "========================================================"
echo ""

# Check if Python is installed
python_cmd=""
if command -v python3 &>/dev/null; then
    python_cmd="python3"
elif command -v python &>/dev/null; then
    python_cmd="python"
else
    echo "Error: Python not found. Please install Python 3.8 or newer."
    exit 1
fi

# Check Python version
version=$($python_cmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
required_version="3.8"
if [ "$(printf '%s\n' "$required_version" "$version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "Error: Python $required_version or higher is required. Found Python $version"
    exit 1
fi

# Check if Rust is installed
if ! command -v rustc &>/dev/null; then
    echo "Rust not found. Installing Rust..."
    echo "This may take a few minutes..."
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    source "$HOME/.cargo/env"
else
    echo "✓ Rust is installed"
fi

# Create and activate virtual environment
echo "Creating Python virtual environment..."
$python_cmd -m venv .venv
source .venv/bin/activate

# Install Python dependencies
echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
pip install anthropic
pip install --upgrade anthropic
pip install --upgrade openai
# Build and install the Rust backend
echo "Building Rust performance backend..."
cd market_research_cli/market_research_core
maturin build --release
pip install target/wheels/market_research_core-*.whl
cd ../..

echo ""
echo "========================================================"
echo "  Setup Complete!"
echo "========================================================"
echo ""
echo "To run the Market Research Generator CLI:"
echo "  1. Activate the virtual environment:"
echo "     source .venv/bin/activate"
echo "  2. Run the CLI:"
echo "     python market_research_cli/fast_cli.py"
echo ""
echo "To use Claude's AI capabilities (optional):"
echo "  pip install anthropic"
echo ""
echo "Enjoy your accelerated market research experience!" 