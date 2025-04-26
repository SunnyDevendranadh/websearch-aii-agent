#!/usr/bin/env python3
import os
import json
import time
import random
import threading
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path

# Load environment variables first
from dotenv import load_dotenv
load_dotenv()

# Rich library for console UI
import questionary
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn
from rich.panel import Panel
from rich import print as rprint
from rich.markdown import Markdown
from rich.live import Live
from rich.layout import Layout
from rich.text import Text
import typer

# OpenAI API
from openai import OpenAI

# Add the web_search module import
try:
    from web_search import BraveSearch, BraveSearchError, format_search_results_for_prompt, get_search_provider
    WEB_SEARCH_AVAILABLE = True
except ImportError:
    WEB_SEARCH_AVAILABLE = False

# Import our Rust-accelerated core module
try:
    from market_research_core_py import (
        ProgressTracker,
        ReportManager,
        process_markdown,
        format_report,
        parse_report_metadata,
        RUST_CORE_AVAILABLE
    )
    is_rust_enabled = RUST_CORE_AVAILABLE
except ImportError:
    is_rust_enabled = False

# Import Twilio if available
try:
    from twilio.rest import Client as TwilioClient
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False

# Initialize Rich console
console = Console()

# --- Custom Exceptions for Model Failures ---
class ModelGenerationError(Exception):
    """Base class for errors during AI model generation."""
    pass

class OpenAIError(ModelGenerationError):
    """Indicates an error occurred specifically with the OpenAI API."""
    pass

class ClaudeError(ModelGenerationError):
    """Indicates an error occurred specifically with the Claude API."""
    pass

class ConfigurationError(Exception):
    """Indicates an error due to missing configuration (e.g., API keys, libraries)."""
    pass

# Set up OpenAI API key from environment
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Check if OpenAI API key is available
if not OPENAI_API_KEY:
    console.print("[yellow]⚠ OpenAI API key not found - OpenAI models will be unavailable.[/yellow]")
else:
    console.print("[green]✓ OpenAI API key found[/green]")

# Initialize Claude client variables
CLAUDE_AVAILABLE = False
CLAUDE_MESSAGES_API_AVAILABLE = False
claude_client = None
CLAUDE_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Try to import and initialize Anthropic's Claude API
if CLAUDE_API_KEY:
    try:
        import anthropic

        # Check if we can initialize the client
        try:
            # Modern client initialization
            claude_client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
            CLAUDE_AVAILABLE = True

            # Check if Messages API is available (primary method)
            if hasattr(claude_client, "messages") and callable(getattr(claude_client.messages, "create", None)):
                CLAUDE_MESSAGES_API_AVAILABLE = True
                console.print("[green]✓ Claude API (with Messages support) successfully initialized[/green]")
            else:
                console.print("[yellow]⚠ Claude API initialized but Messages API not detected. Upgrade needed for Claude usage.[/yellow]")
        except Exception as e:
            console.print(f"[yellow]⚠ Error initializing Claude client: {str(e)}[/yellow]")
            CLAUDE_AVAILABLE = False
    except ImportError:
        console.print("[yellow]⚠ Claude API library ('anthropic') not installed. Claude models unavailable.[/yellow]")
else:
    console.print("[yellow]⚠ Claude API key not found in environment variables. Claude models unavailable.[/yellow]")


# Constants
REPORTS_DIR = Path("reports")
REPORTS_DIR.mkdir(exist_ok=True)

# Initialize our Rust-accelerated report manager (if available)
# Default to a basic implementation if Rust core is not available
if is_rust_enabled:
    report_manager = ReportManager(str(REPORTS_DIR))
else:
    # Basic Python fallback for ReportManager functionality
    class BasicReportManager:
        def __init__(self, directory):
            self.dir = Path(directory)
            self.dir.mkdir(exist_ok=True)

        def save_report(self, filename, content):
            path = self.dir / filename
            path.write_text(content, encoding='utf-8')
            return str(path)

        def read_report(self, filename):
            path = self.dir / filename
            if path.exists():
                return path.read_text(encoding='utf-8')
            raise FileNotFoundError(f"Report {filename} not found.")

        def delete_report(self, filename):
            path = self.dir / filename
            if path.exists():
                path.unlink()
                return True
            return False

        def get_all_reports(self):
            return sorted([f.name for f in self.dir.glob("*.md")])

    report_manager = BasicReportManager(str(REPORTS_DIR))

    # Basic Python fallback for other Rust functions (if needed)
    def format_report(content, title):
        """Basic Python implementation for formatting report header."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        report_id = f"REP-{random.randint(1000, 9999)}" # Simple ID
        header = f"""---
id: {report_id}
title: {title} Market Analysis
date: {timestamp}
---

# {title} Market Analysis
Generated on: {timestamp}

"""
        return header + content

    def parse_report_metadata(content):
         """Basic Python implementation for parsing metadata."""
         metadata = {"title": "Unknown Report", "date": "Unknown", "id": "N/A"}
         try:
             if content.startswith("---"):
                 end_marker = content.find("---", 3)
                 if end_marker != -1:
                     yaml_part = content[3:end_marker]
                     import yaml # Lazy import
                     data = yaml.safe_load(yaml_part)
                     metadata["title"] = data.get("title", metadata["title"])
                     metadata["date"] = data.get("date", metadata["date"])
                     metadata["id"] = data.get("id", metadata["id"])
         except Exception:
             pass # Ignore parsing errors, return defaults
         return metadata

    class BasicProgressTracker:
        """Basic Python implementation for progress tracking."""
        def __init__(self):
            self.reset()

        def reset(self):
            self.start_time = time.time()
            self.percentage = 0.0
            self.stage = "Initializing"
            self.agent = "System"
            self.activity = "Starting process"

        def update(self, percentage, stage, agent, activity):
            self.percentage = max(0.0, min(100.0, percentage))
            self.stage = stage
            self.agent = agent
            self.activity = activity

        def get_progress(self):
            elapsed = time.time() - self.start_time
            return {
                "percentage": self.percentage,
                "stage": self.stage,
                "agent": self.agent,
                "activity": self.activity,
                "elapsed_seconds": elapsed
            }
    # Note: ProgressTracker instance is created within FastCLI

# Check for Twilio credentials
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
TWILIO_ENABLED = TWILIO_AVAILABLE and TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_PHONE_NUMBER

# Initialize typer app
app = typer.Typer()

# --- Generation Functions (Modified for Strict Error Handling) ---

def generate_section_with_openai(topic: str, section_type: str, web_search_results=None) -> str:
    """Generate a section of the market research report using OpenAI.
    Raises OpenAIError if generation fails or ConfigurationError if not configured."""
    if not OPENAI_API_KEY:
         raise ConfigurationError("OpenAI API key is not configured.")

    try:
        # Create a system prompt
        if section_type == "Analyzing market trends":
            prompt = f"You are a market research expert. Provide a comprehensive analysis of current and emerging trends in the {topic} market. Include data points, growth trends, and market adoption cycles. Format your response in markdown."
        elif section_type == "Gathering competitor data":
            prompt = f"You are a competitive intelligence analyst. Identify and analyze key players in the {topic} market. Discuss their strengths, weaknesses, market positioning, and market share. Format your response in markdown."
        elif section_type == "Identifying target audience":
            prompt = f"You are a demographics specialist. Segment and analyze the target audience for {topic}. Create detailed customer personas and discuss their needs, preferences, and behaviors. Format your response in markdown."
        elif section_type == "Evaluating market size":
            prompt = f"You are a market sizing expert. Calculate and analyze the Total Addressable Market (TAM) and Serviceable Available Market (SAM) for {topic}. Include regional distribution and market penetration rates. Format your response in markdown."
        elif section_type == "Analyzing growth potential":
            prompt = f"You are a growth strategist. Identify and evaluate growth opportunities in the {topic} market. Discuss expansion potential, constraints, and forecast different growth scenarios. Format your response in markdown."
        elif section_type == "Identifying risks and challenges":
            prompt = f"You are a risk assessment expert. Analyze the regulatory landscape, market entry barriers, competitive threats, and technological disruptions in the {topic} market. Format your response in markdown."
        elif section_type == "Generating recommendations":
            prompt = f"You are a strategic advisor. Based on a comprehensive analysis of the {topic} market, provide strategic recommendations. Prioritize action items and develop an implementation roadmap. Format your response in markdown."
        else: # Includes "Finalizing report"
            prompt = f"You are a market research expert. Please provide detailed information about {section_type.lower()} for the {topic} market. Format your response in markdown."

        # Prepare user content
        if web_search_results:
            search_content = format_search_results_for_prompt(web_search_results)
            user_content = f"Please generate the {section_type} section for a {topic} market research report.\n\nUse the following web search results for context:\n{search_content}"
        else:
            user_content = f"Please generate the {section_type} section for a {topic} market research report."

        # Initialize OpenAI client
        client = OpenAI()

        # Try using the recommended model first (GPT-4 Turbo)
        try:
            console.print(f"[cyan]Attempting OpenAI API with gpt-4-turbo-preview...[/cyan]")
            completion = client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user_content}
                ],
                max_tokens=1500,
                temperature=0.7,
            )
            return completion.choices[0].message.content.strip()

        except Exception as e_gpt4:
            console.print(f"[yellow]Warning: Could not use GPT-4 Turbo: {str(e_gpt4)}. Falling back to GPT-3.5 Turbo.[/yellow]")

            # Fall back to GPT-3.5 Turbo
            try:
                console.print(f"[cyan]Attempting OpenAI API with gpt-3.5-turbo...[/cyan]")
                completion = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": user_content}
                    ],
                    max_tokens=1000,
                    temperature=0.7,
                )
                return completion.choices[0].message.content.strip()
            except Exception as e_gpt35:
                # If both models fail, raise our custom error
                error_message = f"Both GPT-4 Turbo and GPT-3.5 Turbo failed. Last error: {str(e_gpt35)}"
                console.print(f"[red]OpenAI API Error: {error_message}[/red]")
                raise OpenAIError(error_message) from e_gpt35

    except Exception as e:
        # Catch any other unexpected error during setup or execution
        error_message = f"Unexpected error during OpenAI generation setup or call: {str(e)}"
        console.print(f"[red]{error_message}[/red]")
        raise OpenAIError(error_message) from e


def generate_section_with_claude(topic: str, section_type: str, web_search_results=None) -> str:
    """Generate a section of the market research report using Claude API.
    Raises ClaudeError if generation fails or ConfigurationError if not configured."""

    # Check configuration *before* attempting API calls
    if not CLAUDE_AVAILABLE:
        raise ConfigurationError("Claude (anthropic library) is not installed. Cannot use Claude.")
    if not CLAUDE_API_KEY:
        raise ConfigurationError("Claude API key is not configured. Cannot use Claude.")
    if claude_client is None:
         raise ConfigurationError("Claude client failed to initialize. Cannot use Claude.")
    if not hasattr(claude_client, "messages") or not callable(getattr(claude_client.messages, "create", None)):
         raise ConfigurationError("Installed 'anthropic' library version is too old or Messages API is not available. Please upgrade: pip install --upgrade anthropic")

    try:
        # Create a system prompt
        if section_type == "Analyzing market trends":
            system_prompt = f"You are a market research expert. Provide a comprehensive analysis of current and emerging trends in the {topic} market. Include data points, growth trends, and market adoption cycles. Format your response in markdown."
        elif section_type == "Gathering competitor data":
            system_prompt = f"You are a competitive intelligence analyst. Identify and analyze key players in the {topic} market. Discuss their strengths, weaknesses, market positioning, and market share. Format your response in markdown."
        elif section_type == "Identifying target audience":
            system_prompt = f"You are a demographics specialist. Segment and analyze the target audience for {topic}. Create detailed customer personas and discuss their needs, preferences, and behaviors. Format your response in markdown."
        elif section_type == "Evaluating market size":
            system_prompt = f"You are a market sizing expert. Calculate and analyze the Total Addressable Market (TAM) and Serviceable Available Market (SAM) for {topic}. Include regional distribution and market penetration rates. Format your response in markdown."
        elif section_type == "Analyzing growth potential":
            system_prompt = f"You are a growth strategist. Identify and evaluate growth opportunities in the {topic} market. Discuss expansion potential, constraints, and forecast different growth scenarios. Format your response in markdown."
        elif section_type == "Identifying risks and challenges":
            system_prompt = f"You are a risk assessment expert. Analyze the regulatory landscape, market entry barriers, competitive threats, and technological disruptions in the {topic} market. Format your response in markdown."
        elif section_type == "Generating recommendations":
             system_prompt = f"You are a strategic advisor. Based on a comprehensive analysis of the {topic} market, provide strategic recommendations. Prioritize action items and develop an implementation roadmap. Format your response in markdown."
        else: # Includes "Finalizing report"
             system_prompt = f"You are a market research expert. Please provide detailed information about {section_type.lower()} for the {topic} market. Format your response in markdown."

        # Format user message
        if web_search_results:
            search_content = format_search_results_for_prompt(web_search_results)
            user_message = f"Please generate the {section_type} section for a {topic} market research report.\n\nUse the following web search results for context:\n{search_content}"
        else:
            user_message = f"Please generate the {section_type} section for a {topic} market research report."

        # Use the claude-3-opus-20240229 model with system prompt as top-level parameter
        response = claude_client.messages.create(
            model="claude-3-opus-20240229",
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_message}
            ],
            max_tokens=1500,
            temperature=0.7,
        )

        # Extract content from response
        if response.content and isinstance(response.content, list) and len(response.content) > 0:
            if hasattr(response.content[0], 'text'):
                return response.content[0].text
            else:
                raise ClaudeError("Unexpected response structure from Claude Messages API (missing text).")
        else:
            raise ClaudeError("Empty or unexpected content in Claude Messages API response.")

    except Exception as e:
        error_message = f"Claude API Error: {str(e)}"
        console.print(f"[red]{error_message}[/red]")
        raise ClaudeError(error_message) from e


def generate_fallback_content(topic: str, section_type: str) -> str:
    """Generate fallback content ONLY when no APIs are configured/available from the start."""
    # This function should ideally NOT be called during generation if a model preference was set.
    # It's a last resort if *no* API could even be attempted.
    console.print("[bold yellow]Warning: Generating fallback content as no valid API configuration was found or specified preference failed configuration checks.[/bold yellow]")
    return f"""### {section_type} for {topic}

This section would normally contain a detailed analysis of {section_type.lower()} for the {topic} market.
Due to API limitations or configuration issues, we're providing this placeholder content.

To generate actual content, please ensure your API keys (OpenAI and/or Claude) are configured correctly in the `.env` file or settings menu, and the necessary libraries ('openai', 'anthropic') are installed.
"""


def convert_stage_to_title(stage: str) -> str:
    """Convert a stage name to a proper section title."""
    mapping = {
        "Analyzing market trends": "Market Trends Analysis",
        "Gathering competitor data": "Competitive Landscape",
        "Identifying target audience": "Target Audience Analysis",
        "Evaluating market size": "Market Size and Opportunity",
        "Analyzing growth potential": "Growth Strategy and Potential",
        "Identifying risks and challenges": "Risk Assessment and Challenges",
        "Generating recommendations": "Strategic Recommendations",
        "Finalizing report": "Executive Summary", # Often generated near the end
    }
    return mapping.get(stage, stage)


def display_ascii_title():
    """Display an ASCII art title."""
    title = r"""
__  __            _        _     ___                               _
|  \/  | __ _ _ __| | _____| |   |_ _|_ __ ___  _ __ ___   ___ _ __ | |_ ___
| |\/| |/ _` | '__| |/ / _ \ __|   | || '_ ` _ \| '_ ` _ \ / _ \ '_ \| __/ _ \
| |  | | (_| | |  |   <  __/ |     | || | | | | | | | | | |  __/ | | | || (_) |
|_|  |_|\__,_|_|  |_|\_\___|\__|___|___|_| |_| |_|_| |_| |_|\___|_| |_|\__\___/

""" + "\n" + "=" * 80
    console.print(f"[bold blue]{title}[/bold blue]")
    acceleration_status = "[bold green]ACCELERATED BY RUST[/bold green]" if is_rust_enabled else "[yellow]Standard Python Mode[/yellow]"
    console.print(f"\n{acceleration_status}\n")


# --- Core Report Generation Orchestrator (Modified for Strict Error Handling) ---

def generate_market_research_report(topic: str, progress_callback=None, model_preference="balanced", use_web_search=False) -> Optional[str]:
    """
    Generate a comprehensive market research report on the given topic.
    Uses the OpenAI and/or Claude APIs based on preference. Fails strictly if the chosen model encounters an error.

    Args:
        topic: The market research topic
        progress_callback: Optional callback function to report progress
        model_preference: The preferred model strategy ("balanced", "openai", or "claude")
        use_web_search: Whether to use web search

    Returns:
        str: Markdown formatted report if successful.
        None: If generation fails due to model error or configuration issues.
    """
    try:
        # --- Web Search Logic ---
        web_search_results = []
        if use_web_search and WEB_SEARCH_AVAILABLE:
            try:
                if progress_callback:
                    progress_callback(5, "Web Search", "Search Agent", "Querying Brave Search API")

                search_provider = get_search_provider("brave") # Assumes this function exists
                web_search_results = search_provider.search(topic, limit=10)

                if progress_callback:
                    progress_callback(10, "Web Search", "Search Agent", "Processing search results")

                if web_search_results:
                    console.print(f"[green]✓ Retrieved {len(web_search_results)} search results[/green]")
                else:
                    console.print("[yellow]⚠ No search results found[/yellow]")

            except BraveSearchError as e:
                 console.print(f"[yellow]⚠ Brave Search API error: {str(e)}. Continuing without web search...[/yellow]")
            except Exception as e:
                 console.print(f"[yellow]⚠ Web search failed: {str(e)}. Continuing without web search...[/yellow]")
        elif use_web_search and not WEB_SEARCH_AVAILABLE:
             console.print("[yellow]⚠ Web search requested but module is not available.[/yellow]")


        # --- Stages Definition ---
        stages = [
            {
                "name": "Analyzing market trends",
                "agent": "Agent 001: Market Analyst",
                "activities": [
                    "Gathering historical market data", "Identifying emerging trends",
                    "Analyzing growth patterns", "Evaluating market adoption cycles"
                ],
                "preferred_model": "openai" # Default model preference
            },
            {
                "name": "Gathering competitor data",
                "agent": "Agent 002: Competitive Intelligence",
                "activities": [
                    "Identifying key market players", "Analyzing competitor strengths/weaknesses",
                    "Mapping competitive positioning", "Evaluating market share"
                ],
                "preferred_model": "claude"
            },
            {
                "name": "Identifying target audience",
                "agent": "Agent 003: Demographics Specialist",
                "activities": [
                    "Segmenting customer base", "Analyzing demographic patterns",
                    "Identifying key customer personas", "Mapping customer journey"
                ],
                "preferred_model": "openai"
            },
            {
                "name": "Evaluating market size",
                "agent": "Agent 004: Market Sizing Expert",
                "activities": [
                    "Calculating TAM", "Determining SAM",
                    "Analyzing regional distribution", "Projecting penetration rates"
                ],
                "preferred_model": "claude"
            },
            {
                "name": "Analyzing growth potential",
                "agent": "Agent 005: Growth Strategist",
                "activities": [
                    "Identifying market opportunities", "Evaluating expansion potential",
                    "Analyzing growth constraints", "Forecasting growth scenarios"
                ],
                "preferred_model": "openai"
            },
            {
                "name": "Identifying risks and challenges",
                "agent": "Agent 006: Risk Assessor",
                "activities": [
                    "Analyzing regulatory landscape", "Identifying entry barriers",
                    "Evaluating competitive threats", "Assessing tech disruption risks"
                ],
                "preferred_model": "claude"
            },
            {
                "name": "Generating recommendations",
                "agent": "Agent 007: Strategic Advisor",
                "activities": [
                    "Synthesizing key findings", "Formulating strategic recommendations",
                    "Prioritizing action items", "Developing implementation roadmap"
                ],
                "preferred_model": "openai"
            },
             { # Changed "Finalizing report" to "Executive Summary" generation stage
                "name": "Generating Executive Summary", # Renamed stage
                "agent": "Agent 008: Report Compiler",
                "activities": [
                    "Reviewing all sections", "Identifying key takeaways",
                    "Drafting concise summary", "Formatting summary"
                ],
                "preferred_model": "claude" # Or OpenAI, depending on desired style
            }
        ]

        # --- Model Availability Pre-checks based on Preference ---
        openai_needed = model_preference == "openai" or \
                        (model_preference == "balanced" and any(s.get("preferred_model") == "openai" for s in stages))
        claude_needed = model_preference == "claude" or \
                       (model_preference == "balanced" and any(s.get("preferred_model") == "claude" for s in stages))

        if model_preference == "openai" and not OPENAI_API_KEY:
            console.print("[bold red]Error: OpenAI model preference selected, but OpenAI API Key is not configured.[/bold red]")
            return None # Fail early
        if model_preference == "claude":
            if not CLAUDE_API_KEY:
                 console.print("[bold red]Error: Claude model preference selected, but Claude API Key is not configured.[/bold red]")
                 return None
            if not CLAUDE_AVAILABLE:
                 console.print("[bold red]Error: Claude model preference selected, but 'anthropic' library is not installed or failed to initialize.[/bold red]")
                 return None
            # Check if Messages API is usable (important for Claude preference)
            if not hasattr(claude_client, "messages") or not callable(getattr(claude_client.messages, "create", None)):
                 console.print("[bold red]Error: Claude model preference selected, but installed 'anthropic' library is too old. Please upgrade.[/bold red]")
                 return None

        if model_preference == "balanced":
            if openai_needed and not OPENAI_API_KEY:
                 console.print("[bold red]Error: Balanced mode requires OpenAI for some stages, but OpenAI API Key is not configured.[/bold red]")
                 return None
            if claude_needed:
                if not CLAUDE_API_KEY:
                     console.print("[bold red]Error: Balanced mode requires Claude for some stages, but Claude API Key is not configured.[/bold red]")
                     return None
                if not CLAUDE_AVAILABLE:
                     console.print("[bold red]Error: Balanced mode requires Claude for some stages, but 'anthropic' library is not installed or failed to initialize.[/bold red]")
                     return None
                # Check Messages API usability if Claude needed in balanced
                if not hasattr(claude_client, "messages") or not callable(getattr(claude_client.messages, "create", None)):
                     console.print("[bold red]Error: Balanced mode requires Claude, but installed 'anthropic' library is too old. Please upgrade.[/bold red]")
                     return None

        # --- Report Generation Loop ---
        report_sections = []
        # Create the header using format_report (Rust or Python version)
        report_header = format_report("", topic.title()) # Pass empty content for header generation
        report_sections.append(report_header)

        for i, stage in enumerate(stages):
            stage_name = stage["name"]
            agent_name = stage["agent"]
            activities = stage["activities"]

            # Determine which model to STRICTLY use for this stage
            model_to_use = None
            stage_preferred = stage.get("preferred_model", "openai") # Default preference if missing

            if model_preference == "openai":
                model_to_use = "openai"
            elif model_preference == "claude":
                model_to_use = "claude"
            elif model_preference == "balanced":
                # Use stage preference directly - availability checked above
                model_to_use = stage_preferred
            else: # Should not happen with UI, but handle defensively
                 console.print(f"[bold red]Internal Error: Unknown model preference '{model_preference}'. Aborting.[/bold red]")
                 return None

            # --- Progress Reporting ---
            base_progress = (i / len(stages)) * 100
            # Adjust progress start point slightly if web search happened
            base_progress = max(10, base_progress) if use_web_search and i == 0 else base_progress
            progress_per_activity = (1 / len(stages)) * (100 / len(activities))
            if progress_callback:
                # Report start of stage progress
                progress_callback(base_progress, stage_name, agent_name, activities[0])

            for j, activity in enumerate(activities):
                # Simulate work / actual processing delay
                time.sleep(0.2 + random.random() * 0.5 if is_rust_enabled else 0.4 + random.random() * 0.8) # Slightly faster simulation
                activity_progress = base_progress + ((j + 1) / len(activities)) * (100 / len(stages)) # More accurate activity progress scaling
                activity_progress = min(activity_progress, 99.9) # Cap below 100 until final step
                if progress_callback:
                    progress_callback(activity_progress, stage_name, agent_name, activity)

            # --- Generate Section Content (Strict Error Handling) ---
            section_content = ""
            try:
                console.print(f"\n[bold]Generating section: '{stage_name}' using {model_to_use.upper()}...[/bold]")
                if model_to_use == "claude":
                     # Configuration should be okay based on pre-checks, but call can still fail
                     section_content = generate_section_with_claude(topic, stage_name, web_search_results if use_web_search and web_search_results else None)
                elif model_to_use == "openai":
                     # Configuration should be okay based on pre-checks
                     section_content = generate_section_with_openai(topic, stage_name, web_search_results if use_web_search and web_search_results else None)
                else:
                    # This case should be prevented by earlier checks
                    raise ConfigurationError(f"Invalid model '{model_to_use}' determined for stage '{stage_name}'.")

                section_title = convert_stage_to_title(stage_name)
                # Add extra newline for spacing
                report_sections.append(f"\n## {section_title}\n\n{section_content.strip()}\n")

            except (OpenAIError, ClaudeError, ConfigurationError) as e:
                # Catch specific errors from generation functions or config issues during the call
                console.print(f"[bold red]Failed to generate section: '{stage_name}' using {model_to_use.upper()}.[/bold red]")
                # Error message should have been printed by the failing function too
                console.print(f"[red]Reason: {str(e)}[/red]")
                console.print("[bold yellow]Aborting report generation.[/bold yellow]")
                return None # Signal failure
            except Exception as e:
                 # Catch any other unexpected errors during the loop
                 console.print(f"[bold red]An unexpected error occurred during stage '{stage_name}': {str(e)}[/bold red]")
                 console.print_exception(show_locals=False) # Show traceback for debugging
                 console.print("[bold yellow]Aborting report generation.[/bold yellow]")
                 return None # Signal failure


        # --- Finalize Report (if loop completes successfully) ---
        if progress_callback:
            # Ensure 100% completion is reported
            progress_callback(100, "Report completed", "System", "Finalizing document")

        # Add Methodology/Appendix
        report_sections.append(
"""

## Methodology
This market research report was prepared using a multi-faceted research methodology:
* **AI Model Synthesis:** Leveraging advanced language models (OpenAI GPT and/or Anthropic Claude) for analysis, data interpretation, and content generation based on provided context and training data.
* **Real-time Data Enrichment (Optional):** Incorporation of current web search results via Brave Search API to enhance timeliness and relevance.
* **Structured Analysis Framework:** Following a defined sequence of research stages, including market trends, competitive landscape, target audience, market sizing, growth potential, and risk assessment.
* **Expert Prompts:** Utilizing specialized prompts designed to elicit detailed and relevant information for each research section.

## Disclaimer
This report is generated with AI assistance. While efforts are made to ensure accuracy, the information is based on the AI models' knowledge up to their last training cut-off and real-time search data (if used). All data, insights, and recommendations should be independently verified before making critical business decisions.
"""
)

        full_report = "".join(report_sections)

        # Optional Rust final processing (if you implement specific formatting there)
        if is_rust_enabled:
            # Example: return process_markdown(full_report) # If Rust fn exists
            return full_report # For now, just return
        else:
            return full_report

    except Exception as e:
        # Catch errors during setup (e.g., initial web search, stage definition issues)
        console.print(f"[bold red]Error during report generation setup: {str(e)}[/bold red]")
        console.print_exception(show_locals=False)
        return None # Signal failure


# --- CLI Class ---

class FastCLI:
    """A command-line interface for market research generation with Rust acceleration."""

    def __init__(self):
        """Initialize the CLI."""
        # Use Rust or Python tracker based on availability
        self.tracker = ProgressTracker() if is_rust_enabled else BasicProgressTracker()

    def display_welcome(self):
        """Display a welcome message and API status."""
        display_ascii_title() # Display ASCII art first

        console.print("\n[bold]Welcome to the Market Research Generator![/bold]")
        console.print("This tool helps you create market research reports using AI.")

        if is_rust_enabled:
            console.print("[green]✓ Rust acceleration enabled[/green]")
        else:
            console.print("[yellow]⚠ Running in standard Python mode[/yellow]")

        # Display LLM availability clearly
        console.print("\n[bold underline]AI Model Status:[/bold underline]")
        if OPENAI_API_KEY:
            console.print("✅ [bold green]OpenAI:[/bold green] API Key Found")
        else:
            console.print("❌ [bold red]OpenAI:[/bold red] API Key Not Found (Set OPENAI_API_KEY in .env)")

        if CLAUDE_API_KEY:
            if CLAUDE_AVAILABLE:
                 # Further check for Messages API usability
                 if hasattr(claude_client, "messages") and callable(getattr(claude_client.messages, "create", None)):
                      console.print("✅ [bold cyan]Claude:[/bold cyan] API Key Found & Library OK (Messages API detected)")
                 else:
                      console.print("⚠️ [bold yellow]Claude:[/bold yellow] API Key Found, but Library too old (Messages API missing). Run: pip install --upgrade anthropic")
            else:
                 console.print("⚠️ [bold yellow]Claude:[/bold yellow] API Key Found, but 'anthropic' library NOT installed or failed init. Run: pip install anthropic")
        else:
            console.print("❌ [bold red]Claude:[/bold red] API Key Not Found (Set ANTHROPIC_API_KEY in .env)")

        if WEB_SEARCH_AVAILABLE:
             if os.getenv("BRAVE_API_KEY"):
                  console.print("✅ [bold blue]Web Search:[/bold blue] Brave API Key Found")
             else:
                  console.print("⚠️ [bold yellow]Web Search:[/bold yellow] Module available, but BRAVE_API_KEY not found in .env")
        else:
             console.print("❌ [bold red]Web Search:[/bold red] Module not available (web_search.py missing or install failed)")

        console.print("-" * 30) # Separator


    def main_menu(self) -> None:
        """Display the main menu and handle user input."""
        while True:
            choice = questionary.select(
                "What would you like to do?",
                choices=[
                    "Generate a new market research report",
                    "View existing reports",
                    "Delete a report",
                    "Configure settings",
                    "Help & AI model information",
                    "Exit"
                ],
                qmark=">" # Custom marker
            ).ask()

            if choice is None: # Handle Ctrl+C
                 choice = "Exit"

            if choice == "Generate a new market research report":
                self.generate_report()
            elif choice == "View existing reports":
                self.list_reports() # Changed to list first, then optionally view
            elif choice == "Delete a report":
                self.delete_report()
            elif choice == "Configure settings":
                self.settings()
            elif choice == "Help & AI model information":
                self.show_help()
            elif choice == "Exit":
                console.print("\n[bold green]Exiting Market Research Generator. Goodbye![/bold green]")
                return # Exit the loop and the program

    def generate_report(self) -> None:
        """Guides user through report generation options and initiates the process."""
        # --- Report Generation Banner ---
        report_banner = """
    ╔═══════════════════════════════════════════════════╗
    ║          R E P O R T   G E N E R A T O R         ║
    ╚═══════════════════════════════════════════════════╝
        """
        console.print(f"[bold blue]{report_banner}[/bold blue]")

        # --- User Input Gathering ---
        # (Category, Topic, Focus, Custom Queries - keep existing questionary logic)
        market_categories = [
            "Technology", "Healthcare", "Finance", "Retail", "Energy",
            "Entertainment", "Education", "Manufacturing", "Transportation", "Custom"
        ]
        category = questionary.select("Select a market category:", choices=market_categories).ask()
        if category is None: return # Handle Ctrl+C

        # Get specific topic based on category or custom input
        # ... (keep logic for topic selection/input) ...
        topic = "" # Placeholder - needs the existing logic here
        if category == "Custom":
             topic = questionary.text("Enter the market topic to research:", validate=lambda t: len(t) > 2).ask()
        else:
             # Simplified example - add your topic suggestions back here
             suggestions = {"Technology": ["AI", "Cloud", "Custom"], "Healthcare": ["Telemedicine", "Custom"]}
             choices = suggestions.get(category, []) + ["Custom"]
             topic_choice = questionary.select(f"Choose a topic in {category}:", choices=choices).ask()
             if topic_choice is None: return
             if topic_choice == "Custom":
                  topic = questionary.text(f"Enter custom {category} topic:", validate=lambda t: len(t) > 2).ask()
             else:
                  topic = topic_choice
        if not topic:
             console.print("[yellow]Topic selection cancelled or empty. Returning to menu.[/yellow]")
             return

        # Research Focus
        focus_approach = questionary.select(
             "Research focus:",
             choices=["Comprehensive (all areas)", "Custom (select areas)"]
             ).ask()
        if focus_approach is None: return
        research_focus = ["All of the above"]
        if focus_approach == "Custom (select areas)":
             focus_options = [
                 "Market size and growth potential", "Competitive landscape",
                 "Consumer trends and preferences", "Regulatory environment",
                 "Investment opportunities", "Technological innovations",
             ]
             custom_focus = questionary.checkbox("Select areas to focus on:", choices=focus_options).ask()
             research_focus = custom_focus if custom_focus else ["All of the above"]


        # Custom Queries
        custom_queries = []
        if questionary.confirm("Add specific questions for the report?", default=False).ask():
             while True:
                  query = questionary.text("Enter question (or press Enter to finish):").ask()
                  if not query: break
                  custom_queries.append(query)
                  if len(custom_queries) >= 5 and not questionary.confirm("Add another?", default=False).ask():
                       break

        # --- Report Customization ---
        console.print("\n[bold]Report Customization:[/bold]")
        # Report Length (Note: This currently doesn't directly impact generation logic length)
        report_length = questionary.select("Select approximate report detail level:", choices=["Concise", "Standard", "Comprehensive"]).ask()
        if report_length is None: return

        # Web Search Option
        use_web_search = False
        if WEB_SEARCH_AVAILABLE and os.getenv("BRAVE_API_KEY"):
             use_web_search = questionary.confirm("Use real-time web search (Brave)?", default=True).ask()
        elif WEB_SEARCH_AVAILABLE:
             console.print("[yellow]Web search module available, but Brave API Key not set.[/yellow]")

        # Model Preference (Crucial for strict logic)
        model_options = []
        # Determine available options based on configured keys AND libraries
        openai_is_usable = bool(OPENAI_API_KEY)
        # Claude usability check (key, library installed, and Messages API capability)
        claude_is_usable = (
             bool(CLAUDE_API_KEY) and
             CLAUDE_AVAILABLE and
             hasattr(claude_client, "messages") and
             callable(getattr(claude_client.messages, "create", None))
        )

        if openai_is_usable and claude_is_usable:
            model_options.extend([
                "Balanced (Recommended: Uses best model per stage)",
                "OpenAI Only (Strict: Fails if OpenAI has issues)",
                "Claude Only (Strict: Fails if Claude has issues)"
            ])
        elif openai_is_usable:
            model_options.append("OpenAI Only (Strict: Fails if OpenAI has issues)")
        elif claude_is_usable:
            model_options.append("Claude Only (Strict: Fails if Claude has issues)")
        else:
            # No usable models! Cannot generate.
            console.print("[bold red]Error: Neither OpenAI nor a compatible Claude setup is configured.[/bold red]")
            console.print("[yellow]Please configure API keys/libraries in Settings. Returning to main menu.[/yellow]")
            time.sleep(2)
            return

        model_selection = questionary.select(
            "Select AI model strategy:",
            choices=model_options
        ).ask()
        if model_selection is None: return

        # Map selection to preference key
        model_preference = "balanced" # Default
        if "OpenAI Only" in model_selection:
            model_preference = "openai"
        elif "Claude Only" in model_selection:
            model_preference = "claude"

        # --- Generation Process with Live Display (Modified Error Handling) ---
        console.print(f"\n[bold]Generating market research report on: [green]{topic}[/green] (using {model_preference} strategy)[/bold]\n")

        self.tracker.reset()
        layout = Layout() # Keep your existing layout definition
        layout.split_column(
             Layout(name="header", size=5),
             Layout(name="stats", size=3),
             Layout(name="progress", size=5),
             Layout(name="agents", size=10),
             Layout(name="log", size=10)
        )

        # Log messages, stats - Keep your definitions
        log_messages = []
        report_stats = {"sections_completed": 0, "words_generated": 0, "data_points": 0, "charts": 0}
        spinner_frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        spinner_idx = 0
        current_model_display = "N/A" # For display
        
        # Define the display-only version of stages for UI updates
        # This is only used for UI display purposes, not for actual report generation
        display_stages = [
            {"name": "Analyzing market trends", "preferred_model": "openai"},
            {"name": "Gathering competitor data", "preferred_model": "claude"},
            {"name": "Identifying target audience", "preferred_model": "openai"},
            {"name": "Evaluating market size", "preferred_model": "claude"},
            {"name": "Analyzing growth potential", "preferred_model": "openai"},
            {"name": "Identifying risks and challenges", "preferred_model": "claude"},
            {"name": "Generating recommendations", "preferred_model": "openai"},
            {"name": "Generating Executive Summary", "preferred_model": "claude"}
        ]

        # Define progress update callback (keep existing logic, maybe add model info)
        def update_progress(percentage, stage, agent, activity):
            nonlocal current_model_display # Allow modification
            self.tracker.update(percentage, stage, agent, activity)

            # Determine which model is likely being used for display purposes
            # Note: This is just for display, the actual model used is determined in generate_market_research_report
            stage_pref = "openai" # Find the stage pref if needed for display
            for s in display_stages: # Use the local display_stages instead of the global stages
                 if s["name"] == stage:
                      stage_pref = s.get("preferred_model", "openai")
                      break

            if model_preference == "openai": current_model_display = "OpenAI"
            elif model_preference == "claude": current_model_display = "Claude"
            else: current_model_display = stage_pref.capitalize() # Balanced uses stage pref

            # Simulate stats updates (keep existing logic)
            if stage != "Initializing":
                 report_stats["sections_completed"] = int((percentage / 100) * len(display_stages)) # Use display_stages length
                 report_stats["words_generated"] = int((percentage / 100) * 2500) + random.randint(-100, 100)
                 report_stats["data_points"] = int((percentage / 100) * 45) + random.randint(-3, 3)
                 report_stats["charts"] = int((percentage / 100) * 7) # Placeholder

            # Add log messages (keep existing logic)
            if random.random() < 0.15 and percentage < 99:
                 log_messages.append(f"[{datetime.now().strftime('%H:%M:%S')}] {agent}: {activity[:50]}...")
                 if len(log_messages) > 6: log_messages.pop(0)

        # Start the live display
        report_content = None
        generation_failed = False
        live_display_active = False # Flag to manage stopping live display

        try: # Wrap the Live context manager call
             with Live(layout, refresh_per_second=10, console=console) as live:
                  live_display_active = True # Mark live display as active

                  # Define display update thread (keep existing layout/formatting logic)
                  def update_display_thread():
                       nonlocal spinner_idx
                       while live_display_active: # Use flag to control loop
                            progress_data = self.tracker.get_progress()
                            percentage = progress_data["percentage"]
                            stage = progress_data["stage"]
                            agent = progress_data["agent"]
                            activity = progress_data["activity"]
                            elapsed = progress_data["elapsed_seconds"]

                            # Header
                            spinner_idx = (spinner_idx + 1) % len(spinner_frames)
                            spinner = spinner_frames[spinner_idx]
                            accel = "[Rust]" if is_rust_enabled else "[Py]"
                            model_tag = f"[{current_model_display}]"
                            header_text = f"[bold blue]{spinner} Generating: [green]{topic}[/green] {accel} {model_tag}[/bold blue]\n"
                            header_text += f"[cyan]Focus: {', '.join(research_focus) if research_focus != ['All of the above'] else 'Comprehensive'}[/cyan] | "
                            header_text += f"[cyan]Detail: {report_length}[/cyan]"
                            layout["header"].update(Panel(header_text, border_style="blue"))

                            # Stats
                            stats_text = f"[b]Sections:[/b] {report_stats['sections_completed']}/{len(display_stages)} | [b]Words:[/b] ~{report_stats['words_generated']} | [b]Data:[/b] {report_stats['data_points']} | [b]Charts:[/b] {report_stats['charts']}"
                            layout["stats"].update(Text.from_markup(stats_text))

                            # Progress Bar
                            # ... (keep your progress bar logic) ...
                            progress_text = Text.from_markup(f"[bold]{percentage:.1f}%[/bold] | Elapsed: [b]{int(elapsed)}s[/b]")
                            bar_width = 60
                            filled = int((percentage / 100) * bar_width)
                            bar = "[" + "■" * filled + "□" * (bar_width - filled) + "]"
                            progress_bar = Text(bar, style="bold green" if percentage > 70 else ("bold yellow" if percentage > 30 else "bold red"))
                            layout["progress"].update(Panel.fit(progress_text + "\n" + progress_bar, title="Progress", border_style="blue"))


                            # Agents
                            # ... (keep your agent display logic) ...
                            agents = {"Agent 001": "👨‍💻","Agent 002": "👩‍💼","Agent 003": "🧑‍🔬", # Emojis
                                      "Agent 004": "📚","Agent 005": "🧠","Agent 006": "🔎",
                                      "Agent 007": "📊","Agent 008": "📝", "System": "⚙️", "Search Agent": "🌐"}
                            agent_avatar = agents.get(agent.split(":")[0].strip(), "🤖")
                            agent_text = f"[b]Stage:[/b] {stage}\n[b]Agent:[/b] {agent_avatar} {agent}\n[b]Activity:[/b] {activity}"
                            layout["agents"].update(Panel(agent_text, title="Active Agents", border_style="green"))


                            # Log
                            log_text = "\n".join(log_messages) if log_messages else "Initializing..."
                            layout["log"].update(Panel(log_text, title="Activity Log", border_style="yellow"))

                            # Exit condition for thread
                            if percentage >= 100 or generation_failed:
                                 time.sleep(0.5) # Allow final update to show
                                 break # Exit loop

                            time.sleep(0.1) # Refresh rate

                  # Start display thread
                  display_thread = threading.Thread(target=update_display_thread, daemon=True)
                  display_thread.start()

                  # --- Start the actual report generation ---
                  report_content = generate_market_research_report(
                       topic, update_progress, model_preference, use_web_search
                  )

                  # --- Check for Failure ---
                  if report_content is None:
                       generation_failed = True
                       # Error message printed by generate_market_research_report
                       console.print("\n[bold red]Report generation failed due to model or configuration error.[/bold red]")
                       # Stop live display and thread before exiting 'with' block
                       live_display_active = False
                       display_thread.join(timeout=1.0) # Wait briefly for thread exit
                       live.stop() # Explicitly stop live display
                       return # Exit generate_report method

                  # --- Add Custom Content (Only if successful) ---
                  if custom_queries or (research_focus and "All of the above" not in research_focus):
                      custom_section_content = "\n\n---\n" # Separator
                      if research_focus and "All of the above" not in research_focus:
                           custom_section_content += "\n## Focused Analysis Areas\n"
                           for focus in research_focus:
                                custom_section_content += f"\n### {focus}\n\n"
                                # Placeholder - ideally, this would trigger focused re-generation or synthesis
                                custom_section_content += f"*(Detailed analysis focusing on {focus.lower()} for the {topic} market would be presented here.)*\n"

                      if custom_queries:
                           custom_section_content += "\n## Custom Query Responses\n"
                           for query in custom_queries:
                                custom_section_content += f"\n### Query: {query}\n\n"
                                # Placeholder - AI would answer this based on generated report
                                custom_section_content += "*(AI-generated response addressing this specific query based on the market analysis would be presented here.)*\n"

                      # Append before Methodology
                      appendix_pos = report_content.find("\n## Methodology")
                      if appendix_pos != -1:
                           report_content = report_content[:appendix_pos] + custom_section_content + report_content[appendix_pos:]
                      else:
                           report_content += custom_section_content


                  # Ensure progress hits 100% if successful
                  if not generation_failed and self.tracker.get_progress()["percentage"] < 100:
                       update_progress(100, "Report completed", "System", "Finalizing document")

                  # Wait for display thread to finish naturally
                  live_display_active = False # Signal thread to stop
                  display_thread.join(timeout=2.0) # Wait for clean exit

        except Exception as e:
             # Catch unexpected errors outside the generation loop but within 'with Live'
             generation_failed = True
             if live_display_active:
                  live_display_active = False
                  if 'live' in locals(): live.stop() # Stop if possible
             console.print(f"\n[bold red]An unexpected critical error occurred: {str(e)}[/bold red]")
             console.print_exception(show_locals=False)
             return # Exit generate_report method

        finally:
             # Ensure live is stopped if an error occurred before or during context exit
             if live_display_active and 'live' in locals():
                  live_display_active = False
                  live.stop()
             # Ensure thread is joined if it's still running somehow
             if 'display_thread' in locals() and display_thread.is_alive():
                  display_thread.join(timeout=0.5)


        # === Post-Generation (Only runs if generation_failed is False) ===
        if generation_failed or report_content is None:
            console.print("[yellow]Returning to main menu due to generation failure.[/yellow]")
            time.sleep(1)
            return

        # --- Save Report ---
        console.print("\n[bold green]✓ Report generation completed successfully![/bold green]")
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        file_name = f"{topic.lower().replace(' ', '_').replace('/','_')}_{timestamp}.md"
        file_path_str = None
        try:
            file_path_str = report_manager.save_report(file_name, report_content)
            console.print(f"[bold green]Report saved to:[/bold green] {file_path_str}")
        except Exception as e:
            console.print(f"[bold red]Error saving report: {str(e)}[/bold red]")

        # --- Completion Animation ---
        with Progress(
            SpinnerColumn(), TextColumn("[bold green]Finalizing..."), BarColumn(), TaskProgressColumn(), transient=True,
        ) as progress:
            task = progress.add_task("", total=100)
            for i in range(101):
                progress.update(task, completed=i)
                time.sleep(0.01)

        # --- Post-generation Options ---
        post_options = []
        file_path = Path(file_path_str) if file_path_str else None

        if file_path and file_path.exists():
            post_options.append("View the report")
            if TWILIO_ENABLED:
                post_options.append("Send summary via SMS") # Clarify it's a summary
            elif TWILIO_AVAILABLE:
                post_options.append("Configure SMS (Twilio)")

        post_options.extend([
            "Generate another report",
            "Return to main menu"
        ])

        prompt_message = "What would you like to do next?"
        if not file_path:
            prompt_message = "Report generated but failed to save. What next?"

        post_action = questionary.select(
            prompt_message,
            choices=post_options
        ).ask()

        if post_action == "View the report" and file_path:
            view_report(file_path, console) # Call standalone view function
        elif post_action == "Send summary via SMS" and file_path:
            self._send_report_sms(file_path)
        elif post_action == "Configure SMS (Twilio)":
            self._configure_sms_settings()
        elif post_action == "Generate another report":
            self.generate_report() # Recurse or loop back

        # Implicitly returns to main menu if "Return to main menu" or no action taken


    def list_reports(self) -> None:
        """List available reports and offer viewing."""
        try:
            reports = report_manager.get_all_reports()
        except Exception as e:
             console.print(f"[red]Error listing reports: {e}[/red]")
             return

        if not reports:
            console.print("[yellow]No reports found in the 'reports' directory.[/yellow]")
            return

        console.print("\n[bold underline]Available Market Research Reports:[/bold underline]\n")
        table = Table(show_header=True, header_style="bold magenta", border_style="dim")
        table.add_column("#", style="dim", width=3)
        table.add_column("Report Title", style="cyan", min_width=20)
        table.add_column("Date Generated", style="green", width=20)
        table.add_column("File Name", style="blue", no_wrap=True)

        report_details = []
        for i, report_filename in enumerate(reports, 1):
            try:
                content = report_manager.read_report(report_filename)
                # Use Rust/Python parse_report_metadata
                metadata = parse_report_metadata(content)
                title = metadata.get("title", "Unknown Title").replace(" Market Analysis", "")
                date = metadata.get("date", "Unknown Date")
                report_details.append({"index": i, "title": title, "date": date, "filename": report_filename})
                table.add_row(str(i), title, date, report_filename)
            except Exception as e:
                console.print(f"[yellow]Could not parse metadata for {report_filename}: {e}[/yellow]")
                # Add row with defaults if parsing fails
                report_details.append({"index": i, "title": report_filename, "date": "N/A", "filename": report_filename})
                table.add_row(str(i), report_filename, "N/A", report_filename)


        console.print(table)

        # Ask if the user wants to view a report
        if questionary.confirm("View a report by entering its # number?", default=True).ask():
            report_num_str = questionary.text(
                 "Enter report number to view (or press Enter to cancel):",
                 validate=lambda text: text.isdigit() and 1 <= int(text) <= len(reports) or text == ""
                 ).ask()

            if report_num_str:
                 try:
                      report_index = int(report_num_str) - 1
                      selected_report_filename = report_details[report_index]["filename"]
                      report_path = Path(REPORTS_DIR) / selected_report_filename
                      view_report(report_path, console) # Call standalone view function
                 except (ValueError, IndexError):
                      console.print("[red]Invalid report number.[/red]")
            else:
                 console.print("View cancelled.")


    def view_report_by_index(self, index: int) -> None: # Kept for potential direct calling
        """View a specific report by its index from the last listing."""
        # Note: This relies on the state of the last list_reports call.
        # It's generally better to re-list and select.
        # The implementation within list_reports is preferred.
        try:
            reports = report_manager.get_all_reports()
            if 0 <= index < len(reports):
                report_filename = reports[index]
                report_path = Path(REPORTS_DIR) / report_filename
                view_report(report_path, console)
            else:
                 console.print("[red]Invalid report index.[/red]")
        except Exception as e:
             console.print(f"[red]Error viewing report: {e}[/red]")


    def delete_report(self) -> None:
        """Allows the user to select and delete a report."""
        try:
             reports = report_manager.get_all_reports()
        except Exception as e:
             console.print(f"[red]Error listing reports for deletion: {e}[/red]")
             return

        if not reports:
            console.print("[yellow]No reports found to delete.[/yellow]")
            return

        # Create a list of report options with index and title/date
        report_options = []
        for i, report_filename in enumerate(reports):
            try:
                content = report_manager.read_report(report_filename)
                metadata = parse_report_metadata(content)
                title = metadata.get("title", report_filename).replace(" Market Analysis", "")
                date = metadata.get("date", "Unknown Date")
                report_options.append(f"#{i+1}: {title} ({date}) - [{report_filename}]")
            except Exception:
                 report_options.append(f"#{i+1}: {report_filename}")

        report_options.append("Cancel")

        choice = questionary.select(
            "Select a report to delete:",
            choices=report_options
        ).ask()

        if choice is None or choice == "Cancel":
            console.print("Deletion cancelled.")
            return

        try:
            # Extract index from choice string (e.g., "#1: ...")
            report_index = int(choice.split(":")[0][1:]) - 1
            if 0 <= report_index < len(reports):
                 report_filename_to_delete = reports[report_index]
                 display_name = choice.split(" - [")[0] # Get the display part for confirm message

                 if questionary.confirm(f"Are you sure you want to delete '{display_name}'?").ask():
                      success = report_manager.delete_report(report_filename_to_delete)
                      if success:
                           console.print(f"[bold green]Report '{report_filename_to_delete}' deleted successfully.[/bold green]")
                      else:
                           # Should not happen if file existed unless permissions issue
                           console.print(f"[bold red]Failed to delete report '{report_filename_to_delete}'. File might already be gone or permissions denied.[/bold red]")
            else:
                 console.print("[red]Invalid selection index.[/red]")

        except (ValueError, IndexError):
             console.print("[red]Could not parse selection. Deletion failed.[/red]")
        except Exception as e:
             console.print(f"[red]An error occurred during deletion: {e}[/red]")


    def settings(self) -> None:
        """Configure application settings."""
        global CLAUDE_AVAILABLE, CLAUDE_API_KEY, CLAUDE_MESSAGES_API_AVAILABLE, claude_client
        global TWILIO_AVAILABLE, TWILIO_ENABLED, TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER
        
        while True:
            options = []
            # OpenAI
            openai_key = os.getenv("OPENAI_API_KEY")
            openai_status = "[green]Set[/green]" if openai_key else "[yellow]Not Set[/yellow]"
            options.append(f"OpenAI API Key ({openai_status})")

            # Claude
            claude_key = os.getenv("ANTHROPIC_API_KEY")
            claude_lib_status = "[green]Installed[/green]" if CLAUDE_AVAILABLE else "[red]Not Installed[/red]"
            claude_key_status = "[green]Set[/green]" if claude_key else "[yellow]Not Set[/yellow]"
            options.append(f"Claude API Key ({claude_key_status}, Lib: {claude_lib_status})")
            
            # Add dedicated option for installing Anthropic library
            anthropic_install_option = "Install Anthropic Library" if not CLAUDE_AVAILABLE else "Update Anthropic Library"
            options.append(f"{anthropic_install_option} (Current: {claude_lib_status})")

            # Brave Search
            brave_key = os.getenv("BRAVE_API_KEY")
            brave_status = "[green]Set[/green]" if brave_key else "[yellow]Not Set[/yellow]"
            brave_lib_status = "[green]Available[/green]" if WEB_SEARCH_AVAILABLE else "[red]Not Available[/red]"
            options.append(f"Brave Search API Key ({brave_status}, Module: {brave_lib_status})")

            # Twilio SMS
            twilio_lib_status = "[green]Installed[/green]" if TWILIO_AVAILABLE else "[red]Not Installed[/red]"
            twilio_configured = "[green]Configured[/green]" if TWILIO_ENABLED else "[yellow]Not Configured[/yellow]"
            options.append(f"SMS Configuration (Twilio: {twilio_lib_status}, {twilio_configured})")

            options.append("Back to Main Menu")

            choice = questionary.select(
                "Configure Settings:",
                choices=options
            ).ask()

            if choice is None or choice == "Back to Main Menu":
                return

            # --- Handle Setting Updates ---
            if choice.startswith("OpenAI API Key"):
                self._update_api_key("OPENAI_API_KEY", "OpenAI")
                global OPENAI_API_KEY
                OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") # Refresh global var

            elif choice.startswith("Claude API Key"):
                if not CLAUDE_AVAILABLE:
                     if questionary.confirm("Claude library ('anthropic') not installed. Install now?", default=True).ask():
                          self._install_anthropic_package()
                          # Re-check availability after install attempt
                          try:
                               import anthropic
                        
                               CLAUDE_AVAILABLE = True
                          except ImportError: pass # Stay unavailable if install fails
                     else:
                          console.print("[yellow]Skipping Claude configuration as library is missing.[/yellow]")
                          continue # Go back to settings menu

                # Proceed with key update if library is available
                self._update_api_key("ANTHROPIC_API_KEY", "Claude")
                global CLAUDE_API_KEY, claude_client, CLAUDE_MESSAGES_API_AVAILABLE
                CLAUDE_API_KEY = os.getenv("ANTHROPIC_API_KEY")
                # Re-initialize client if key was set/changed
                if CLAUDE_API_KEY and CLAUDE_AVAILABLE:
                     try:
                          claude_client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
                          CLAUDE_MESSAGES_API_AVAILABLE = hasattr(claude_client, "messages") and callable(getattr(claude_client.messages, "create", None))
                          console.print("[green]Claude client re-initialized.[/green]")
                     except Exception as e:
                          console.print(f"[red]Failed to re-initialize Claude client: {e}[/red]")
                          claude_client = None
                          CLAUDE_MESSAGES_API_AVAILABLE = False
                else:
                     claude_client = None # Clear client if key removed or lib unavailable
                     CLAUDE_MESSAGES_API_AVAILABLE = False

            elif choice.startswith("Install Anthropic Library") or choice.startswith("Update Anthropic Library"):
                # Direct option to install/update the Anthropic library
                self._install_anthropic_package()
                # After installation, check if we need to initialize the client
                if CLAUDE_AVAILABLE and CLAUDE_API_KEY and not claude_client:
                    try:
                        import anthropic
                        claude_client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
                        CLAUDE_MESSAGES_API_AVAILABLE = hasattr(claude_client, "messages") and callable(getattr(claude_client.messages, "create", None))
                        console.print("[green]Claude client initialized after package installation.[/green]")
                    except Exception as e:
                        console.print(f"[red]Could not initialize Claude client after installation: {e}[/red]")

            elif choice.startswith("Brave Search API Key"):
                 if not WEB_SEARCH_AVAILABLE:
                      console.print("[yellow]Web Search module not found. Cannot configure Brave key.[/yellow]")
                      continue
                 self._update_api_key("BRAVE_API_KEY", "Brave Search")
                 # No global vars to update here, module uses env directly

            elif choice.startswith("SMS Configuration"):
                 if not TWILIO_AVAILABLE:
                      console.print("[yellow]Twilio library not installed. Please run: pip install twilio[/yellow]")
                      continue
                 self._configure_sms_settings()

    def _update_api_key(self, env_var_name: str, service_name: str):
        """Helper to update a specific API key."""
        current_key = os.getenv(env_var_name) or ""
        masked_key = "****" + current_key[-4:] if len(current_key) > 4 else ("Set" if current_key else "Not Set")

        console.print(f"\nCurrent {service_name} API Key Status: [cyan]{masked_key}[/cyan]")

        new_key = questionary.password(f"Enter new {service_name} API Key (leave blank to keep current, type 'REMOVE' to unset):").ask()

        if new_key is None: # Handle Ctrl+C
             console.print("Update cancelled.")
             return

        if new_key.strip().upper() == "REMOVE":
             self._update_env_var(env_var_name, "") # Set to empty string
             console.print(f"[bold yellow]{service_name} API Key removed.[/bold yellow]")
        elif new_key.strip() == "":
             console.print(f"{service_name} API Key unchanged.")
        else:
             self._update_env_var(env_var_name, new_key.strip())
             console.print(f"[bold green]{service_name} API Key updated successfully.[/bold green]")


    def _update_env_var(self, key: str, value: str) -> None:
        """Update or add an environment variable in the .env file."""
        env_path = Path(".env")
        lines = []
        key_found = False

        if env_path.exists():
            lines = env_path.read_text().splitlines()
            for i, line in enumerate(lines):
                stripped_line = line.strip()
                if not stripped_line or stripped_line.startswith("#"):
                    continue
                # Basic parsing, handles keys without explicit '=' if value is empty
                if stripped_line.startswith(f"{key}=") or (not value and stripped_line == key):
                    lines[i] = f"{key}={value}" # Update existing line
                    key_found = True
                    break

        if not key_found:
            lines.append(f"{key}={value}") # Add new line

        # Filter out potential empty lines caused by removal if needed
        lines = [line for line in lines if line.strip()]

        try:
             env_path.write_text("\n".join(lines) + "\n") # Ensure trailing newline
             os.environ[key] = value # Update live environment
        except Exception as e:
             console.print(f"[red]Error writing to .env file: {e}[/red]")


    def _configure_sms_settings(self) -> None:
        """Configure Twilio SMS settings."""
        if not TWILIO_AVAILABLE: # Should be checked before calling, but double-check
             console.print("[red]Twilio library not found.[/red]")
             return

        console.print("\n[bold underline]Twilio SMS Configuration[/bold underline]")
        account_sid = os.getenv("TWILIO_ACCOUNT_SID") or ""
        auth_token = os.getenv("TWILIO_AUTH_TOKEN") or ""
        phone_number = os.getenv("TWILIO_PHONE_NUMBER") or ""

        masked_sid = "****" + account_sid[-4:] if len(account_sid) > 4 else ("Set" if account_sid else "Not Set")
        masked_token = "****" + auth_token[-4:] if len(auth_token) > 4 else ("Set" if auth_token else "Not Set")

        console.print(f"Account SID:       [cyan]{masked_sid}[/cyan]")
        console.print(f"Auth Token:        [cyan]{masked_token}[/cyan]")
        console.print(f"Twilio Phone No.:  [cyan]{phone_number or 'Not Set'}[/cyan]")

        if questionary.confirm("Update Twilio settings?", default=False).ask():
            new_sid = questionary.text("Enter Account SID:", default=account_sid).ask()
            new_token = questionary.password("Enter Auth Token (leave blank to keep current):")
            new_phone = questionary.text("Enter Twilio Phone Number (e.g., +15551234567):", default=phone_number).ask()

            # Update only if values are provided or changed
            if new_sid is not None: self._update_env_var("TWILIO_ACCOUNT_SID", new_sid)
            if new_token: self._update_env_var("TWILIO_AUTH_TOKEN", new_token) # Only update token if provided
            if new_phone is not None: self._update_env_var("TWILIO_PHONE_NUMBER", new_phone)

            console.print("[bold green]Twilio settings updated.[/bold green]")

            # Refresh global Twilio status
            global TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER, TWILIO_ENABLED
            TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
            TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
            TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
            TWILIO_ENABLED = TWILIO_AVAILABLE and TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_PHONE_NUMBER


    def _send_report_sms(self, report_path: Path) -> None:
        """Send a report summary via SMS."""
        if not TWILIO_ENABLED:
            console.print("[yellow]SMS functionality is not configured. Please set up Twilio in settings.[/yellow]")
            return

        phone_number = questionary.text(
             "Enter recipient's phone number (e.g., +1234567890):",
             validate=lambda p: (p.startswith('+') and len(p) > 7 and p[1:].isdigit()) or p == ""
             ).ask()

        if not phone_number:
            console.print("SMS sending cancelled.")
            return

        console.print(f"[bold]Sending report summary to {phone_number}...[/bold]")
        success, message = send_report_via_sms(report_path, phone_number) # Call standalone function

        if success:
            console.print(f"[bold green]✓ SMS summary sent successfully to {phone_number}.[/bold green]")
            console.print(f"   (Twilio SID: {message})")
        else:
            console.print(f"[bold red]✗ Failed to send SMS: {message}[/bold red]")


    def _install_anthropic_package(self):
        """Attempt to install the Anthropic (Claude) package."""
        global CLAUDE_AVAILABLE, CLAUDE_API_KEY, CLAUDE_MESSAGES_API_AVAILABLE, claude_client
        
        console.print("\n[bold cyan]===== Anthropic Library Installation =====")
        console.print("[yellow]This will install or update the 'anthropic' Python package required for Claude AI.[/yellow]")
        
        # Display current status
        try:
            import pkg_resources
            try:
                current_version = pkg_resources.get_distribution("anthropic").version
                console.print(f"[cyan]Current installed version: v{current_version}[/cyan]")
            except pkg_resources.DistributionNotFound:
                console.print("[yellow]Status: Not currently installed[/yellow]")
        except ImportError:
            console.print("[yellow]Status: Package information unavailable[/yellow]")
            
        console.print("[cyan]Attempting to install 'anthropic' library using pip...[/cyan]")
        try:
            import subprocess
            import sys
            
            # Show installation progress
            console.print("[cyan]Running: pip install -U anthropic[/cyan]")
            
            # Use check_call to raise error if install fails
            result = subprocess.check_call([sys.executable, "-m", "pip", "install", "-U", "anthropic"]) # -U to upgrade
            
            # Check the installed version after installation
            try:
                import pkg_resources
                import importlib
                # Reload if it was already imported
                if "anthropic" in sys.modules:
                    importlib.reload(sys.modules["anthropic"])
                new_version = pkg_resources.get_distribution("anthropic").version
                console.print(f"[bold green]✓ Successfully installed/updated 'anthropic' package to v{new_version}![/bold green]")
            except Exception:
                console.print("[bold green]✓ Successfully installed/updated 'anthropic' package![/bold green]")
                
            # Import anthropic to check if it works
            try:
                import anthropic
                console.print("[green]✓ Successfully imported 'anthropic' module[/green]")
                CLAUDE_AVAILABLE = True
                
                # Check for the Messages API capabilities
                if hasattr(anthropic, "Anthropic"):
                    console.print("[green]✓ Modern Anthropic client detected[/green]")
                    if CLAUDE_API_KEY:
                        console.print("[cyan]Attempting to initialize client with your API key...[/cyan]")
                        try:
                            claude_client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
                            if hasattr(claude_client, "messages") and callable(getattr(claude_client.messages, "create", None)):
                                CLAUDE_MESSAGES_API_AVAILABLE = True
                                console.print("[bold green]✓ Claude Messages API is available and ready to use![/bold green]")
                            else:
                                console.print("[yellow]⚠ Claude Messages API not detected. You may need a newer version.[/yellow]")
                        except Exception as e:
                            console.print(f"[yellow]⚠ Could not initialize Claude client: {e}[/yellow]")
                    else:
                        console.print("[yellow]⚠ Claude API key not set. Please set it to use Claude.[/yellow]")
                else:
                    console.print("[yellow]⚠ Unexpected Anthropic library structure. Check for updates.[/yellow]")
                    
            except ImportError:
                console.print("[yellow]⚠ Package installed but import failed. This is unexpected.[/yellow]")
                CLAUDE_AVAILABLE = False
                
            console.print("[yellow]You may need to restart the application for changes to take full effect.[/yellow]")
            time.sleep(1) # Pause to let user read

        except subprocess.CalledProcessError as e:
            console.print(f"[bold red]Failed to install 'anthropic': Pip command failed with error code {e.returncode}[/bold red]")
            console.print(f"[red]Error details: {e}[/red]")
            if e.returncode == 1:
                console.print("[yellow]This might be due to network issues, permissions, or PyPI being unavailable.[/yellow]")
        except Exception as e:
            console.print(f"[bold red]An unexpected error occurred during installation: {str(e)}[/bold red]")
            console.print("[yellow]You may need to install it manually with: pip install --upgrade anthropic[/yellow]")
            
        # Wait for user acknowledgment before returning
        questionary.press_any_key_to_continue(message="Press any key to return to settings...").ask()


    def show_help(self) -> None:
        """Display help information and AI model comparison."""
        help_title = "[bold blue]Market Research Generator - Help & Information[/bold blue]"

        model_comparison = """
[bold underline]AI Model Strategies[/bold underline]
This tool leverages powerful AI models for report generation. You can choose a strategy:

[bold]Balanced (Recommended):[/bold]
• Uses the most suitable AI (OpenAI or Claude) for each research stage.
• Aims for the highest quality by combining model strengths.
• [i]Requires both OpenAI and Claude to be configured.[/i]
• If the preferred model for a stage fails, generation stops.

[bold]OpenAI Only (Strict):[/bold]
• Uses OpenAI (GPT-4/GPT-3.5) for all stages.
• Good for strong data analysis and structured summaries.
• [i]Requires OpenAI to be configured.[/i]
• If OpenAI fails at any point, generation stops.

[bold]Claude Only (Strict):[/bold]
• Uses Claude (Claude 3 Sonnet) for all stages.
• Excels at nuanced analysis, risk assessment, and context-rich explanations.
• [i]Requires a correctly configured Claude setup (API key + up-to-date library).[/i]
• If Claude fails at any point, generation stops.

[bold yellow]Strict Failure:[/bold yellow] With 'OpenAI Only' or 'Claude Only', or if a model fails in 'Balanced' mode, the report generation will halt immediately to ensure adherence to your preference and prevent incomplete reports with mixed/fallback content.
"""

        usage_help = """
[bold underline]Getting Started[/bold underline]
1.  [bold]Configure APIs:[/bold] Go to 'Settings' and add your API keys for OpenAI and/or Claude. Install libraries if prompted. Brave Search key is optional for web enrichment.
2.  [bold]Generate Report:[/bold] Select 'Generate...', choose category/topic, focus, and your preferred AI model strategy.
3.  [bold]View/Manage:[/bold] Use 'View' or 'Delete' options for saved reports (in the 'reports' folder).
4.  [bold]SMS (Optional):[/bold] Configure Twilio in 'Settings' to send report summaries.
"""

        console.print(Panel(model_comparison, title=help_title, border_style="blue", expand=False))
        console.print(Panel(usage_help, title="[bold cyan]How to Use[/bold cyan]", border_style="cyan", expand=False))

        # Show current configuration status again for context
        self.display_welcome() # Re-display welcome which includes status

        questionary.press_any_key_to_continue(message="Press any key to return to the main menu...").ask()


# --- Standalone Functions ---

def view_report(report_path: Path, console: Console) -> None:
    """View a specific report file in the console using Markdown rendering."""
    if not report_path.exists():
        console.print(f"[red]Error: Report file not found at {report_path}[/red]")
        return

    try:
        content = report_path.read_text(encoding='utf-8')
        metadata = parse_report_metadata(content) # Use Rust/Python parser
        title = metadata.get("title", report_path.stem)
        date = metadata.get("date", "N/A")
        report_id = metadata.get("id", "N/A")

        # Display header info
        console.print(f"\n[bold blue]--- Viewing Report ---[/bold blue]")
        console.print(f"[bold]Title:[/bold] [green]{title}[/green]")
        console.print(f"[bold]Generated:[/bold] {date}")
        console.print(f"[bold]ID:[/bold] {report_id}")
        console.print(f"[bold]File:[/bold] {report_path.name}")
        console.print("-" * 20)

        # Render Markdown content within a pager
        md = Markdown(content)
        # Use console.pager for long content
        with console.pager(styles=True):
             console.print(md)

        console.print("[bold blue]--- End of Report ---[/bold blue]")

    except Exception as e:
        console.print(f"[bold red]Error reading or displaying report {report_path.name}: {str(e)}[/bold red]")


def send_report_via_sms(report_path: Path, phone_number: str) -> tuple[bool, str]:
    """Sends a summary of the report via SMS using Twilio."""
    if not TWILIO_ENABLED:
        return False, "Twilio is not configured or enabled."

    try:
        # Initialize Twilio client
        client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

        # Read report and extract metadata/summary
        content = report_manager.read_report(report_path.name)
        metadata = parse_report_metadata(content)
        title = metadata.get("title", report_path.stem)

        # Create a concise summary message (simple version)
        # In a real app, you might use an AI to summarize the executive summary section
        summary = f"Market Research Summary: {title}\n\n"
        # Find Executive Summary section if it exists
        exec_summary_start = content.find("## Executive Summary")
        if exec_summary_start != -1:
             next_section_start = content.find("\n## ", exec_summary_start + 20)
             summary_text = content[exec_summary_start + 20 : next_section_start if next_section_start != -1 else None].strip()
             # Limit length for SMS
             max_len = 1500 # Approximate max length for multi-part SMS
             if len(summary_text) > max_len:
                  summary_text = summary_text[:max_len] + "..."
             summary += summary_text + "\n\n(Full report available)"
        else:
             summary += "(Full report available in generated file.)"


        # Send the SMS
        message = client.messages.create(
            body=summary,
            from_=TWILIO_PHONE_NUMBER,
            to=phone_number
        )
        return True, message.sid # Return success and message SID

    except Exception as e:
        console.print_exception(show_locals=False) # Log full error for debugging
        return False, f"Twilio API error: {str(e)}"


# --- Typer CLI Command and Main Execution ---

# Note: The Typer command `cli` below is designed for non-interactive execution.
# The main interactive loop is handled by `FastCLI` instances called from `main()`.
@app.command()
def run(headless: bool = typer.Option(False, "--headless", help="Run in headless mode (non-interactive)"),
        topic: str = typer.Option(None, "--topic", help="Topic for market research (required in headless)"),
        category: str = typer.Option("Custom", "--category", help="Category for market research"),
        focus: str = typer.Option("all", "--focus", help="Research focus areas (comma-separated, e.g., 'Market size,Competitive landscape') or 'all'"),
        model: str = typer.Option("balanced", "--model", help="AI model strategy (balanced, openai, claude)"),
        length: str = typer.Option("Standard", "--length", help="Report detail level (Concise, Standard, Comprehensive) - currently informational"),
        out_dir: str = typer.Option(None, "--out-dir", help="Output directory for reports (defaults to './reports')"),
        use_web_search: bool = typer.Option(False, "--use-web-search", "-w", help="Enable real-time web search")):
    """
    Market Research Generator CLI.

    Run without arguments for interactive mode.
    Use --headless with --topic for automated generation.
    """
    global REPORTS_DIR, report_manager # Allow modification of global report path

    if out_dir:
        reports_path = Path(out_dir)
        try:
             reports_path.mkdir(parents=True, exist_ok=True)
             REPORTS_DIR = reports_path
             # Re-initialize report manager with the new path
             if is_rust_enabled:
                  report_manager = ReportManager(str(REPORTS_DIR))
             else:
                  report_manager = BasicReportManager(str(REPORTS_DIR))
             console.print(f"[info]Using output directory: {REPORTS_DIR}[/info]")
        except Exception as e:
             console.print(f"[red]Error setting output directory '{out_dir}': {e}. Using default './reports'.[/red]")
             REPORTS_DIR = Path("reports") # Fallback
             REPORTS_DIR.mkdir(exist_ok=True)
             # Initialize with default path again
             if is_rust_enabled: report_manager = ReportManager(str(REPORTS_DIR))
             else: report_manager = BasicReportManager(str(REPORTS_DIR))
    else:
        REPORTS_DIR.mkdir(exist_ok=True) # Ensure default exists


    if headless:
        # --- Headless Mode Execution ---
        if not topic:
            console.print("[bold red]Error: In headless mode, --topic is required.[/bold red]")
            raise typer.Exit(code=1)

        console.print("[bold]Running in headless mode[/bold]")
        console.print(f"[info]Topic: {topic}, Category: {category}, Model: {model}, WebSearch: {use_web_search}[/info]")

        # Validate model choice based on availability
        model_preference = model.lower()
        if model_preference not in ["balanced", "openai", "claude"]:
             console.print(f"[yellow]Warning: Invalid model preference '{model}'. Using 'balanced'.[/yellow]")
             model_preference = "balanced"

        # Check if chosen model is usable
        if model_preference == "openai" and not OPENAI_API_KEY:
            console.print("[bold red]Error: Headless mode chose 'openai', but key is missing.[/bold red]")
            raise typer.Exit(code=1)
        if model_preference == "claude" and (not CLAUDE_API_KEY or not CLAUDE_AVAILABLE or not hasattr(claude_client, "messages")):
             console.print("[bold red]Error: Headless mode chose 'claude', but it's not configured or library is incompatible.[/bold red]")
             raise typer.Exit(code=1)
        # Add balanced check if needed


        # Simple progress callback for headless stdout
        def headless_progress(percentage, stage, agent, activity):
            console.print(f"PROGRESS: {percentage:.1f}% | Stage: {stage} | Agent: {agent} | Activity: {activity}")

        # Generate report directly
        report_content = generate_market_research_report(
            topic=topic,
            progress_callback=headless_progress,
            model_preference=model_preference,
            use_web_search=use_web_search
        )

        if report_content is None:
            console.print("[bold red]Headless report generation failed.[/bold red]")
            raise typer.Exit(code=1)
        else:
            # Save the report
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            file_name = f"{category.lower()}_{topic.lower().replace(' ', '_').replace('/','_')}_{timestamp}.md"
            try:
                 file_path = report_manager.save_report(file_name, report_content)
                 console.print(f"\n[bold green]Report successfully generated and saved to:[/bold green] {file_path}")
            except Exception as e:
                 console.print(f"[bold red]Report generated but failed to save: {e}[/bold red]")
                 # Optionally print content to stdout if saving fails?
                 # rprint(Panel(Markdown(report_content), title="Generated Report Content"))
                 raise typer.Exit(code=1) # Exit with error if save fails

    else:
        # --- Interactive Mode Execution ---
        cli_instance = FastCLI()
        cli_instance.display_welcome()
        cli_instance.main_menu()


if __name__ == "__main__":
    app()