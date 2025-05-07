# AI-Powered Market Research Agent

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)
![Rust](https://img.shields.io/badge/rust-optional-orange.svg)

A sophisticated CLI tool for generating comprehensive market research reports using advanced AI models. Featuring Rust acceleration for performance-critical operations and enhanced with real-time web search capabilities, this tool delivers professional-quality market analysis for any topic.

This project was developed by Sunny Devendrandh Karri as a final project for IS-170. I am grateful to Professor Choi for assigning this fascinating challenge. The project not only taught us how to work with AI agents but also helped us understand their importance and exposed us to career opportunities in this field.

![Market Research Agent Demo](docs/images/demo.gif)

## 🔑 Key Features

- **Multi-Agent AI Architecture**: Specialized AI agents work together to create comprehensive market research
- **AI Model Flexibility**: Choose between OpenAI GPT models, Anthropic Claude, or a balanced approach using both
- **Real-time Web Search**: Enhance reports with up-to-date information from Brave Search API
- **Beautiful TUI Interface**: Rich text-based UI with progress tracking, agent visualization, and interactive menus
- **Performance Acceleration**: Critical operations optionally accelerated with Rust for 10-46x faster processing
- **PDF Export**: Export your reports to beautifully formatted PDF documents
- **SMS Notifications**: Optional SMS delivery of report summaries via Twilio integration
- **Fully Customizable**: Configure every aspect of your market research reports

## 🤖 Agent System

The application uses a multi-agent approach where each section of the report is handled by a specialized "agent" with expertise in a specific area:

| Agent | Name | Role | Default Model | Key Activities |
|-------|------|------|--------------|----------------|
| **Agent 001** | Market Analyst | Analyzes market trends | OpenAI | Gathering historical data, identifying trends, analyzing growth patterns |
| **Agent 002** | Competitive Intelligence | Gathers competitor data | Claude | Identifying key players, analyzing strengths/weaknesses, evaluating market share |
| **Agent 003** | Demographics Specialist | Identifies target audience | OpenAI | Segmenting customers, creating personas, mapping customer journeys |
| **Agent 004** | Market Sizing Expert | Evaluates market size | Claude | Calculating TAM/SAM, analyzing regional distribution, projecting penetration rates |
| **Agent 005** | Growth Strategist | Analyzes growth potential | OpenAI | Identifying opportunities, evaluating expansion potential, forecasting scenarios |
| **Agent 006** | Risk Assessor | Identifies risks and challenges | Claude | Analyzing regulations, identifying barriers, evaluating competitive threats |
| **Agent 007** | Strategic Advisor | Generates recommendations | OpenAI | Synthesizing findings, formulating recommendations, developing implementation roadmap |
| **Agent 008** | Report Compiler | Generates executive summary | Claude | Reviewing sections, identifying key takeaways, creating concise summary |
| **Search Agent** | Web Researcher | Gathers real-time data | N/A | Querying Brave Search, processing results, enhancing AI context |

The agents work together in sequence, with each one specializing in a specific aspect of market research. You can customize which AI model (OpenAI or Claude) is used for each agent, or use the balanced approach which assigns the most appropriate model to each agent based on their strengths.

## 🚀 Installation

### Prerequisites

- Python 3.8 or newer
- Rust (optional, automatically installed by setup scripts if not present)
- OpenAI API key (required)
- Anthropic Claude API key (optional, for Claude model access)
- Brave Search API key (optional, for web search enhancement)
- Twilio account credentials (optional, for SMS delivery)

### Quick Install

```bash
# Clone the repository
git clone https://github.com/yourusername/ai-market-research-agent.git
cd ai-market-research-agent

# Run the setup script
# On macOS/Linux:
chmod +x setup.sh
./setup.sh

# On Windows:
setup.bat
```

### Setting Up API Keys

Create a `.env` file in the root directory with the following content:

```
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_claude_api_key_here
BRAVE_API_KEY=your_brave_search_api_key_here

# Optional Twilio integration for SMS
TWILIO_ACCOUNT_SID=your_twilio_account_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_PHONE_NUMBER=your_twilio_phone_number
```

## 📊 Usage

### Running the Application

```bash
# On macOS/Linux:
./run.sh

# On Windows:
run.bat
```

### Interactive Menu Options

The application features an intuitive interactive menu with the following options:

1. **Generate a new market research report**
   - Select a market category or custom topic
   - Choose research focus areas
   - Add custom queries for the report
   - Select detail level (Concise, Standard, Comprehensive)
   - Enable real-time web search (if configured)
   - Choose AI model strategy (Balanced, OpenAI Only, Claude Only)

2. **View existing reports**
   - Browse all generated reports
   - View reports with rich markdown formatting

3. **Export a report to PDF**
   - Convert markdown reports to professionally formatted PDF documents
   - Customize PDF output path
   - Automatically open after generation

4. **Delete a report**
   - Remove unwanted reports with confirmation

5. **Configure settings**
   - Set up API keys
   - Configure SMS notifications
   - Customize application behavior

6. **Help & AI model information**
   - Get detailed usage instructions
   - Learn about AI models and capabilities

7. **Exit**
   - Close the application

### Report Generation Process

When generating a report, you'll see a live interface showing:

- Current generation progress
- Active agent and its activities
- Report statistics (sections completed, approximate word count)
- A log of agent activities

The system will work through each section methodically, with specialized agents creating content for their areas of expertise.

## 📱 PDF Export

The application includes a robust PDF export feature that converts your markdown reports into beautifully formatted PDF documents:

### Features

- **Professional Formatting**: Clean typography, proper spacing, and consistent styling
- **Custom Paths**: Save PDFs to your preferred location
- **Auto-Open**: Option to automatically open PDFs after generation
- **Fallback Mechanisms**: Multiple PDF generation methods to ensure compatibility

### How to Use

1. Select "Export a report to PDF" from the main menu
2. Choose the report you want to export
3. Enter a custom output path or use the default location
4. Choose whether to automatically open the PDF after generation

The system uses ReportLab for PDF generation if available, with fallbacks to wkhtmltopdf or other methods if needed.

## 🔍 Web Search Integration

Enable real-time web search to enhance your reports with the latest information:

1. Obtain a Brave Search API key from the [Brave Search Developer Portal](https://brave.com/search/api/)
2. Add your API key to the `.env` file
3. Enable web search when generating reports

The search agent will query Brave Search for relevant information about your topic, which is then used by the AI models to create more accurate and up-to-date reports.

## 🗂️ Project Structure

```
ai-market-research-agent/
├── market_research_cli/           # Main CLI application
│   ├── market_research_core/      # Rust core implementation (optional)
│   │   ├── src/                   # Rust source code
│   │   ├── Cargo.toml             # Rust package configuration
│   │   ├── market_research_core_py/   # Python wrapper for Rust core
│   │   │   ├── __init__.py            # Python package initialization
│   │   │   ├── market_research_core_py.py # Python fallback implementations
│   │   │   ├── setup.py               # Python package setup
│   │   ├── web_search/                # Web search integration
│   │   │   ├── __init__.py            # Package initialization
│   │   │   ├── brave_search.py        # Brave Search API implementation
│   │   ├── fast_cli.py                # Main CLI entry point
│   ├── reports/                       # Directory for generated reports
│   ├── setup.sh                       # Unix/Linux/macOS setup script
│   ├── setup.bat                      # Windows setup script
│   ├── run.sh                         # Unix/Linux/macOS run script
│   ├── run.bat                        # Windows run script
│   ├── requirements.txt               # Python dependencies
│   └── README.md                      # This file
```

## ⚡ Performance

The optional Rust acceleration provides significant performance improvements:

| Operation               | Python | Rust  | Speedup |
| ----------------------- | ------ | ----- | ------- |
| Markdown Processing     | 230ms  | 5ms   | 46x     |
| Progress Tracking       | 1.2ms  | 1.0ms | 1.2x    |
| File Operations (large) | 12ms   | 3ms   | 4x      |

## 📝 Report Structure

Each generated report follows a comprehensive structure:

1. **Executive Summary**: Concise overview of key findings and recommendations
2. **Market Trends Analysis**: Examination of current and emerging trends
3. **Competitive Landscape**: Analysis of key players, strengths, weaknesses
4. **Target Audience Analysis**: Detailed customer personas and segments
5. **Market Size and Opportunity**: TAM, SAM, and market penetration analysis
6. **Growth Strategy and Potential**: Opportunities, constraints, and scenarios
7. **Risk Assessment and Challenges**: Regulatory landscape, barriers, threats
8. **Strategic Recommendations**: Actionable insights and implementation roadmap
9. **Methodology**: Explanation of research approach and data sources
10. **Custom Sections**: Additional areas based on your specific queries

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgements

- [OpenAI](https://openai.com/) for their powerful GPT models
- [Anthropic](https://www.anthropic.com/) for the Claude AI assistant
- [Brave](https://brave.com/) for their search API
- [Rich](https://github.com/Textualize/rich) for the beautiful terminal interface
- [ReportLab](https://www.reportlab.com/) for PDF generation capabilities
