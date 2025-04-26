# Rust-Accelerated Market Research CLI

![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)

A high-performance CLI tool for generating market research reports, accelerated by Rust for performance-critical operations.

## Overview

This CLI tool combines the ease and flexibility of Python with the speed and efficiency of Rust to generate comprehensive market research reports for any topic. It uses AI models to create high-quality, well-structured reports while leveraging Rust's performance advantages for data processing, markdown operations, and file handling.

## Key Features

- **Rust Acceleration**: Critical operations are 10-46x faster with Rust backend
- **AI-Powered Reports**: Generate professional market research reports on any topic
- **Real-time Web Search**: Enhance reports with up-to-date information from Brave Search API
- **Hybrid Architecture**: Seamless fallback to Python implementations when Rust is unavailable
- **Simple CLI Interface**: Intuitive command-line interface for easy report generation

## Project Structure

```
market-research-cli/
├── market_research_cli/           # Main CLI application
│   ├── market_research_core/      # Rust core implementation
│   │   ├── src/                   # Rust source code
│   │   │   └── lib.rs             # Rust library with performance-critical functions
│   │   ├── Cargo.toml             # Rust package configuration
│   ├── market_research_core_py/   # Python wrapper for Rust core
│   │   ├── __init__.py            # Python package initialization
│   │   ├── market_research_core_py.py # Python fallback implementations
│   │   ├── setup.py               # Python package setup
│   ├── web_search/                # Web search integration
│   │   ├── __init__.py            # Package initialization
│   │   ├── brave_search.py        # Brave Search API implementation
│   ├── fast_cli.py                # Main CLI entry point
├── reports/                       # Directory for generated reports
├── setup.sh                       # Unix/Linux/macOS setup script
├── setup.bat                      # Windows setup script
├── run.sh                         # Unix/Linux/macOS run script
├── run.bat                        # Windows run script
├── requirements.txt               # Python dependencies
└── README.md                      # This file
```

## Performance Improvements

The Rust-accelerated version provides significant performance improvements:

| Operation               | Python | Rust  | Speedup |
| ----------------------- | ------ | ----- | ------- |
| Markdown Processing     | 230ms  | 5ms   | 46x     |
| Progress Tracking       | 1.2ms  | 1.0ms | 1.2x    |
| File Operations (large) | 12ms   | 3ms   | 4x      |

## How It Works

1. **Rust Core Implementation**: High-performance Rust code handles markdown processing, thread-safe progress tracking, and efficient file operations.

2. **Python Wrapper**: A Python module provides a wrapper around the Rust functions with pure Python fallbacks.

3. **CLI Application**: The main CLI application uses the Python wrapper, automatically leveraging Rust acceleration when available.

4. **Web Search Integration**: The application can query the Brave Search API to enhance reports with real-time information.

## Installation

### Prerequisites

- Python 3.8 or newer
- Rust (automatically installed by setup scripts if not present)
- Brave Search API key (for web search feature)

### Quick Install

#### Unix/Linux/macOS:

```bash
# Clone the repository
git clone https://github.com/yourusername/market-research-cli.git
cd market-research-cli

# Run the setup script
chmod +x setup.sh
./setup.sh
```

#### Windows:

```batch
# Clone the repository
git clone https://github.com/yourusername/market-research-cli.git
cd market-research-cli

# Run the setup script
setup.bat
```

## Usage

### Running the CLI

#### Unix/Linux/macOS:

```bash
# Basic usage
./run.sh

# With web search enabled
./run.sh --use-web-search

# Headless mode with specific topic and web search
./run.sh --topic "AI in Healthcare" --headless --use-web-search
```

#### Windows:

```batch
# Basic usage
run.bat

# With web search enabled
run.bat --use-web-search

# Headless mode with specific topic and web search
run.bat --topic "AI in Healthcare" --headless --use-web-search
```

### API Keys

The CLI will prompt you for API keys on first run. You can also set them in a `.env` file:

```
OPENAI_API_KEY=your_api_key_here
ANTHROPIC_API_KEY=your_claude_api_key_here  # Optional
BRAVE_API_KEY=your_brave_search_api_key_here  # For web search feature
```

## Web Search Integration

The CLI can use the Brave Search API to enrich reports with real-time information:

1. **Setup**: Obtain a Brave Search API key from the [Brave Search Developer Portal](https://brave.com/search/api/).

2. **Configuration**: Add your API key to the `.env` file or configure it through the settings menu.

3. **Usage**: Enable web search using the `--use-web-search` flag or through the interactive menu.

4. **Result**: The generated report will include up-to-date information from web search results.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
