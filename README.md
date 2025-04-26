# Rust-Accelerated Market Research CLI

![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)

A high-performance CLI tool for generating comprehensive market research reports, accelerated by Rust for performance-critical operations and enhanced with real-time web search capabilities.

## Overview

This CLI tool combines the ease and flexibility of Python with the speed and efficiency of Rust to generate comprehensive market research reports for any topic. It uses AI models (OpenAI GPT and Anthropic Claude) to create high-quality, well-structured reports while leveraging Rust's performance advantages for data processing, markdown operations, and file handling.

## Key Features

- **Rust Acceleration**: Critical operations are 10-46x faster with Rust backend
- **AI-Powered Reports**: Generate professional market research reports using OpenAI GPT and Claude models
- **Real-time Web Search**: Enhance reports with up-to-date information from Brave Search API
- **Flexible Model Selection**: Choose between OpenAI, Claude, or a balanced approach using both
- **Modern TUI Interface**: Rich text-based UI with progress tracking and interactive menus
- **Hybrid Architecture**: Seamless fallback to Python implementations when Rust is unavailable
- **SMS Notification**: Optional SMS delivery of report summaries via Twilio integration

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

3. **AI Model Orchestration**: The application intelligently selects between OpenAI and Claude models based on your preferences and the specific needs of each report section.

4. **Web Search Integration**: The application can query the Brave Search API to enhance reports with real-time information, making your reports more accurate and up-to-date.

5. **Report Structure**: Each report follows a comprehensive structure covering market trends, competitor analysis, target audience, market size, growth potential, risks, and strategic recommendations.

## Installation

### Prerequisites

- Python 3.8 or newer
- Rust (automatically installed by setup scripts if not present)
- OpenAI API key (required)
- Anthropic Claude API key (optional, for Claude model access)
- Brave Search API key (optional, for web search enhancement)
- Twilio account credentials (optional, for SMS delivery)

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
# Basic interactive mode
./run.sh

# With web search enabled
./run.sh --use-web-search

# Headless mode with specific topic and web search
./run.sh --topic "AI in Healthcare" --headless --use-web-search

# Specify model preference and output directory
./run.sh --topic "Renewable Energy" --model claude --out-dir "./custom_reports"
```

#### Windows:

```batch
# Basic interactive mode
run.bat

# With web search enabled
run.bat --use-web-search

# Headless mode with specific topic and web search
run.bat --topic "AI in Healthcare" --headless --use-web-search

# Specify model preference and output directory
run.bat --topic "Renewable Energy" --model claude --out-dir "./custom_reports"
```

### Command-line Arguments

| Argument               | Description                                                                          |
| ---------------------- | ------------------------------------------------------------------------------------ |
| `--headless`           | Run in non-interactive mode                                                          |
| `--topic TEXT`         | Topic for market research (required in headless mode)                                |
| `--category TEXT`      | Category for market research (default: "Custom")                                     |
| `--model TEXT`         | AI model strategy: "balanced", "openai", or "claude" (default: "balanced")           |
| `--length TEXT`        | Report detail level: "Concise", "Standard", or "Comprehensive" (default: "Standard") |
| `--out-dir TEXT`       | Custom output directory for reports (default: "./reports")                           |
| `--use-web-search, -w` | Enable real-time web search                                                          |

### API Keys

The CLI will prompt you for API keys on first run. You can also set them in a `.env` file:

```
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_claude_api_key_here
BRAVE_API_KEY=your_brave_search_api_key_here
TWILIO_ACCOUNT_SID=your_twilio_account_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_PHONE_NUMBER=your_twilio_phone_number
```

## Web Search Integration

The CLI uses the Brave Search API to enhance reports with real-time information:

1. **How It Works**:

   - The application queries Brave Search for the top 10 results related to your topic
   - These results are formatted and injected into the AI prompts
   - The AI models are instructed to use facts from these sources, reducing hallucination

2. **Setup**:

   - Obtain a Brave Search API key from the [Brave Search Developer Portal](https://brave.com/search/api/)
   - Add your API key to the `.env` file or configure it through the settings menu

3. **Benefits**:

   - More accurate and current information in your reports
   - Reduced AI hallucination with factual grounding
   - Better insights on emerging trends and recent developments

4. **Extension**: The system uses a modular design that can be extended to other search providers beyond Brave Search.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
