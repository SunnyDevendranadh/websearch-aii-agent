# Web Search Feature Guide

This guide explains how to use the new real-time web search integration with Brave Search API.

## Setup

1. **Get a Brave Search API Key**

   - Visit the [Brave Search API Developer Portal](https://brave.com/search/api/)
   - Sign up and obtain your API key

2. **Configure Your API Key**
   - Create a `.env` file in the project root (or copy from `example.env`)
   - Add your Brave Search API key:
     ```
     BRAVE_API_KEY=your_brave_search_api_key_here
     ```

## Usage

### Command Line Usage

To use web search from the command line:

```bash
# With web search enabled
./run.sh --use-web-search

# Specify a topic with web search in headless mode
./run.sh --topic "AI in Healthcare" --headless --use-web-search
```

### Interactive Usage

1. Run the CLI normally:

   ```bash
   ./run.sh
   ```

2. Select "Generate a new market research report" from the main menu

3. Follow the prompts to specify your topic and other options

4. When asked "Enrich report with real-time web search data?", select "Yes"

## How It Works

The web search feature:

1. Queries the Brave Search API for the top 10 results related to your topic
2. Formats these results into a structured prompt
3. Instructs the AI model to incorporate factual information from these sources
4. Generates a more accurate and up-to-date market research report

## Troubleshooting

If you encounter issues with the web search feature:

- **"Web search failed" error**: Check your API key is correct in the `.env` file
- **No search results**: Try a more general topic, as specific topics may not have enough results
- **Rate limit errors**: Brave Search API may have usage limits; try again later

## Extending to Other Search Providers

The implementation is modular and can be extended to other search providers:

1. Create a new implementation of `AbstractSearchProvider` in `web_search/`
2. Add the new provider to the `get_search_provider()` factory function
3. Update the CLI to support selecting different search providers
