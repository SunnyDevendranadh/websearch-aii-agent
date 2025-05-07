#!/usr/bin/env python3
import os
import json
import time
import random
import threading
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Union, Any, Callable
from pathlib import Path
import re
import subprocess
import tempfile
import shutil
import platform
import sys

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
from rich.align import Align
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
        clean_escape_sequences,
        RUST_CORE_AVAILABLE,
        export_to_pdf,
        open_file
    )
    is_rust_enabled = RUST_CORE_AVAILABLE
except ImportError:
    is_rust_enabled = False
    # Import the Python fallback for export_to_pdf
    try:
        from market_research_core_py.market_research_core_py import export_to_pdf, export_to_pdf_python, open_file, clean_escape_sequences
    except ImportError:
        # If we can't import directly, we'll define them below
        pass

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
            try:
                # Try to handle different versions of anthropic library
                import pkg_resources
                anthropic_version = pkg_resources.get_distribution("anthropic").version
                console.print(f"[cyan]Detected anthropic library version: {anthropic_version}[/cyan]")
                
                # Initialize client
                try:
                    claude_client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
                except TypeError as e:
                    if "proxies" in str(e):
                        # If error mentions proxies, import with older signature
                        console.print("[yellow]Detected proxies parameter issue, using compatible initialization...[/yellow]")
                        # Create client with only required parameters - find exactly what parameters are accepted
                        import inspect
                        init_params = inspect.signature(anthropic.Anthropic.__init__).parameters
                        if len(init_params) > 2:  # self and api_key are always present
                            console.print(f"[yellow]Found {len(init_params)-2} additional parameters in constructor[/yellow]")
                        # Always use the simplest form that should work across versions
                        claude_client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
                    else:
                        raise  # Re-raise if it's a different TypeError
            except (pkg_resources.DistributionNotFound, ImportError, Exception) as e:
                # If we can't check version, try direct initialization
                console.print(f"[yellow]Couldn't determine anthropic version: {str(e)}. Trying direct initialization...[/yellow]")
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
            """Save a report to disk"""
            path = self.dir / filename
            path.parent.mkdir(parents=True, exist_ok=True)
            
            # Clean any ANSI escape sequences that might be in the content
            try:
                # Always use the Python wrapper which has proper fallback handling
                content = clean_escape_sequences(content)
            except Exception as e:
                print(f"Warning: Could not use clean_escape_sequences: {e}. Using direct regex.")
                try:
                    # Handle text representations of ESC
                    import re
                    esc_pattern = re.compile(r'ESC\[(\d+;)*\d*[a-zA-Z]|ESC\[\d+m|ESC\[0m|ESC\[1m|ESC\[4m|ESC\[\d+;\d+m')
                    content = esc_pattern.sub('', content)
                    
                    # Handle actual ANSI escape sequences
                    ansi_pattern = re.compile(r'\x1B\[(\d+;)*\d*[a-zA-Z]|\x1B\[\d+m|\x1B\[0m|\x1B\[1m|\x1B\[4m|\x1B\[\d+;\d+m')
                    content = ansi_pattern.sub('', content)
                    
                    # Comprehensive pattern as final cleanup
                    escape_seq_pattern = re.compile(r'(?:\x1B|\bESC)(?:\[|\(|\))[^@-Z\\^_`a-z{|}~]*[@-Z\\^_`a-z{|}~]')
                    content = escape_seq_pattern.sub('', content)
                except Exception as inner_e:
                    print(f"Warning: Could not clean escape sequences: {inner_e}")
                
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
        # Clean any ANSI escape sequences that might be in the content
        try:
            # Try to use the Python wrapper function first
            content = clean_escape_sequences(content)
        except Exception as e:
            # Fallback if function not available
            escape_seq_pattern = re.compile(r'(?:\x1B|\bESC)(?:\[|\(|\))[^@-Z\\^_`a-z{|}~]*[@-Z\\^_`a-z{|}~]')
            content = escape_seq_pattern.sub('', content)
            
        return header + content

    # Fallback for PDF export if not imported
    if 'export_to_pdf' not in globals():
        # Check if ReportLab is available
        REPORTLAB_AVAILABLE = False
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib import colors
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
            from reportlab.lib.units import inch, cm
            REPORTLAB_AVAILABLE = True
        except ImportError:
            REPORTLAB_AVAILABLE = False
        
        def export_to_pdf(content, output_path):
            """Python fallback for PDF export if the imported version is not available"""
            # Clean any escape sequences
            escape_seq_pattern = re.compile(r'(?:\x1B|\bESC)(?:\[|\(|\))[^@-Z\\^_`a-z{|}~]*[@-Z\\^_`a-z{|}~]')
            cleaned_content = escape_seq_pattern.sub('', content)
            
            # Check if wkhtmltopdf is available
            wkhtmltopdf_available = False
            try:
                subprocess.run(['wkhtmltopdf', '--version'], 
                              check=True, 
                              stdout=subprocess.PIPE, 
                              stderr=subprocess.PIPE)
                wkhtmltopdf_available = True
            except (subprocess.SubprocessError, FileNotFoundError):
                wkhtmltopdf_available = False
            
            # If wkhtmltopdf is available, use it (better quality)
            if wkhtmltopdf_available:
                # Create temp HTML file
                with tempfile.NamedTemporaryFile(suffix='.html', delete=False, mode='w', encoding='utf-8') as f:
                    temp_html_path = f.name
                    
                    # Convert markdown to HTML
                    try:
                        import markdown
                        html_content = markdown.markdown(
                            cleaned_content, 
                            extensions=['tables', 'fenced_code']
                        )
                    except ImportError:
                        # Basic fallback if markdown module not available
                        html_content = cleaned_content.replace('\n', '<br>')
                        html_content = f"<pre>{html_content}</pre>"
                    
                    # Add CSS styling
                    full_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{
            font-family: Arial, sans-serif;
            line-height: 1.5;
            margin: 2cm;
        }}
        h1, h2, h3, h4, h5, h6 {{
            color: #333;
        }}
    </style>
</head>
<body>
    {html_content}
</body>
</html>"""
                    f.write(full_html)
                
                # Convert HTML to PDF
                try:
                    subprocess.run([
                        'wkhtmltopdf',
                        '--enable-local-file-access',
                        temp_html_path,
                        output_path
                    ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                except subprocess.SubprocessError as e:
                    raise RuntimeError(f"Failed to convert to PDF: {e}")
                finally:
                    # Clean up temp file
                    try:
                        os.unlink(temp_html_path)
                    except:
                        pass
            
            # If wkhtmltopdf not available but reportlab is, use it
            elif REPORTLAB_AVAILABLE:
                print("Using ReportLab for PDF generation (wkhtmltopdf not found)")
                
                # Extract metadata and title
                metadata = {}
                title = "Market Research Report"
                
                # Try to extract YAML front matter if present
                if cleaned_content.startswith('---'):
                    end_marker = cleaned_content.find('---', 3)
                    if end_marker != -1:
                        yaml_part = cleaned_content[3:end_marker].strip()
                        try:
                            import yaml
                            metadata = yaml.safe_load(yaml_part)
                            cleaned_content = cleaned_content[end_marker+3:].strip()
                        except:
                            pass
                
                # Try to find title from metadata or first heading
                if metadata and 'title' in metadata:
                    title = metadata['title']
                else:
                    import re
                    title_match = re.search(r"^#\s+(.*?)$", cleaned_content, re.MULTILINE)
                    if title_match:
                        title = title_match.group(1).strip()
                
                # Initialize PDF document
                doc = SimpleDocTemplate(
                    output_path,
                    pagesize=A4,
                    leftMargin=2*cm,
                    rightMargin=2*cm,
                    topMargin=2*cm,
                    bottomMargin=2*cm
                )
                
                # Get styles
                styles = getSampleStyleSheet()
                styles.add(ParagraphStyle(
                    name='Heading1',
                    parent=styles['Heading1'],
                    fontSize=24,
                    spaceAfter=20
                ))
                styles.add(ParagraphStyle(
                    name='Heading2',
                    parent=styles['Heading2'],
                    fontSize=18,
                    spaceAfter=15,
                    spaceBefore=20
                ))
                styles.add(ParagraphStyle(
                    name='Heading3',
                    parent=styles['Heading3'],
                    fontSize=14,
                    spaceAfter=10,
                    spaceBefore=15
                ))
                styles.add(ParagraphStyle(
                    name='Normal',
                    parent=styles['Normal'],
                    fontSize=11,
                    spaceAfter=8
                ))
                
                # Create elements for the document
                elements = []
                
                # Add title
                elements.append(Paragraph(title, styles['Heading1']))
                
                # Add metadata if available
                if metadata:
                    date = metadata.get('date', datetime.now().strftime("%B %d, %Y"))
                    report_id = metadata.get('id', 'N/A')
                    
                    meta_text = f"Generated on: {date}<br/>Report ID: {report_id}<br/>Confidential Document"
                    elements.append(Paragraph(meta_text, styles['Italic']))
                    elements.append(Spacer(1, 0.5*inch))
                
                # Simple processing of markdown content
                # Split by headings
                content_parts = re.split(r'(^#{1,6}\s+.*$)', cleaned_content, flags=re.MULTILINE)
                
                current_text = ""
                for part in content_parts:
                    if part.strip():
                        if re.match(r'^#{1,6}\s+', part):
                            # If we have accumulated text, add it as a paragraph
                            if current_text:
                                elements.append(Paragraph(current_text, styles['Normal']))
                                current_text = ""
                                
                            # Process heading
                            level = len(re.match(r'^(#+)', part).group(1))
                            heading_text = part[level:].strip()
                            
                            if level == 1:
                                elements.append(Paragraph(heading_text, styles['Heading1']))
                            elif level == 2:
                                elements.append(Paragraph(heading_text, styles['Heading2']))
                            else:
                                elements.append(Paragraph(heading_text, styles['Heading3']))
                        else:
                            # Accumulate text
                            current_text += part
                
                # Add any remaining text
                if current_text:
                    elements.append(Paragraph(current_text, styles['Normal']))
                
                # Build the PDF
                doc.build(elements)
            else:
                # Neither wkhtmltopdf nor reportlab is available
                raise RuntimeError(
                    "Unable to generate PDF: wkhtmltopdf not found and reportlab is not installed.\n\n"
                    "Please install one of the following:\n"
                    "1. wkhtmltopdf (recommended):\n"
                    "   - macOS: brew install wkhtmltopdf\n"
                    "   - Ubuntu/Debian: sudo apt-get install wkhtmltopdf\n"
                    "   - Windows: Download from https://wkhtmltopdf.org/downloads.html\n\n"
                    "2. ReportLab (alternative):\n"
                    "   - pip install reportlab\n"
                )
            
            # Check if PDF was created
            if not os.path.exists(output_path):
                raise RuntimeError("PDF file was not created successfully")
                
            return output_path
    
    # Fallback for opening files if not imported
    if 'open_file' not in globals():
        def open_file(file_path):
            """Python implementation to open a file with the default system application"""
            import platform
            try:
                if platform.system() == 'Windows':
                    os.startfile(file_path)
                elif platform.system() == 'Darwin':  # macOS
                    subprocess.run(['open', file_path], check=True)
                else:  # Linux/Unix
                    subprocess.run(['xdg-open', file_path], check=True)
                return True
            except Exception as e:
                raise RuntimeError(f"Failed to open file: {e}")
    
    # Fallback for cleaning escape sequences if not imported
    if 'clean_escape_sequences' not in globals():
        def clean_escape_sequences(content):
            """Enhanced Python fallback for cleaning ANSI escape sequences"""
            # First, handle text representations of ESC
            esc_pattern = re.compile(r'ESC\[(\d+;)*\d*[a-zA-Z]|ESC\[\d+m|ESC\[0m|ESC\[1m|ESC\[4m|ESC\[\d+;\d+m')
            content = esc_pattern.sub('', content)
            
            # Then handle actual ANSI escape sequences
            ansi_pattern = re.compile(r'\x1B\[(\d+;)*\d*[a-zA-Z]|\x1B\[\d+m|\x1B\[0m|\x1B\[1m|\x1B\[4m|\x1B\[\d+;\d+m')
            content = ansi_pattern.sub('', content)
            
            # More comprehensive pattern for any remaining escapes
            full_pattern = re.compile(r'(?:\x1B|\bESC)(?:\[|\(|\))[^@-Z\\^_`a-z{|}~]*[@-Z\\^_`a-z{|}~]')
            content = full_pattern.sub('', content)
            
            return content

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
    """Display a clean, simple title that renders reliably in CLI environments."""
    
    # Create a larger, centered title with no box outline
    title = Text("""
  ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
  ┃                                                         ┃
  ┃                 170 AI MARKET AGENT                     ┃
  ┃                                                         ┃
  ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
    """)
    
    # Apply gradient coloring to the title
    title.stylize("bold")
    for i in range(len(title)):
        if title.plain[i] not in [' ', '\n']:
            hue = (i % 360) / 360.0  # Create a rainbow effect
            title.stylize(f"rgb({int(255*(1-hue))},{int(255*hue)},{int(255*(0.5-abs(0.5-hue)*2))}", i, i+1)
    
    # Create subtitle with emoji and styling
    subtitle = Text("\n⚡️ Powered by Advanced AI & Rust ⚡️", style="bold cyan")
    
    # Create status indicator
    if is_rust_enabled:
        status = Text("\n🚀 ACCELERATED BY RUST", style="bold green")
    else:
        status = Text("\n⚠️ Standard Python Mode", style="bold yellow")
    
    # Combine all elements with better spacing
    full_title = Text.assemble(
        title,
        subtitle,
        "\n",
        status
    )
    
    # Display the combined title without a panel
    console.print(Align.center(full_title))


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
        try:
            # The format_report function is already imported at the top level
            # and handles both Python and Rust implementations
            console.print(f"[cyan]Generating report header for {topic.title()}...[/cyan]")
            report_header = format_report("", topic.title())
            report_sections.append(report_header)
        except Exception as e:
            console.print(f"[bold red]Error generating report header: {str(e)}[/bold red]")
            console.print_exception(show_locals=False)
            console.print("[bold yellow]Aborting report generation.[/bold yellow]")
            return None

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
                # Only cap progress at 99.9% if we're not on the last stage and last activity
                if i < len(stages) - 1 or j < len(activities) - 1:
                    activity_progress = min(activity_progress, 99.9) # Cap below 100 until final stage & activity
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

        # Clean any ANSI escape sequences that might be in the report
        try:
            # Always use the Python wrapper which has proper fallback handling
            full_report = clean_escape_sequences(full_report)
        except Exception as e:
            console.print(f"[yellow]Warning: Could not use clean_escape_sequences: {str(e)}. Using direct regex.[/yellow]")
            try:
                escape_seq_pattern = re.compile(r'(?:\x1B|\bESC)(?:\[|\(|\))[^@-Z\\^_`a-z{|}~]*[@-Z\\^_`a-z{|}~]')
                full_report = escape_seq_pattern.sub('', full_report)
            except Exception as inner_e:
                console.print(f"[yellow]Warning: Could not clean escape sequences: {str(inner_e)}[/yellow]")

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
        # Add a flag to try simple input if questionary fails
        use_simple_input = False
        
        while True:
            console.print("\n[bold cyan]------------------------------[/bold cyan]")
            choices = [
                "Generate a new market research report",
                "View existing reports",
                "Export a report to PDF",
                "Delete a report",
                "Configure settings",
                "Help & AI model information",
                "Exit"
            ]
            
            choice = None
            # Try questionary first unless we've already determined it doesn't work
            if not use_simple_input:
                try:
                    choice = questionary.select(
                        "What would you like to do?",
                        choices=choices,
                        qmark=">", # Custom marker
                        use_indicator=True,
                        use_shortcuts=True,
                        use_arrow_keys=True
                    ).ask()
                except Exception as e:
                    console.print(f"[yellow]Warning: Interactive selection failed: {str(e)}[/yellow]")
                    console.print("[yellow]Switching to simple input mode...[/yellow]")
                    use_simple_input = True
            
            # If questionary failed or we're in simple input mode, use basic input
            if choice is None or use_simple_input:
                # Show choices as a simple list for visibility
                for i, choice in enumerate(choices, 1):
                    console.print(f"  {i}. {choice}")
                console.print("Enter the number of your choice (1-7): ", end="")
                try:
                    user_input = input().strip()
                    if user_input.isdigit() and 1 <= int(user_input) <= 7:
                        idx = int(user_input) - 1
                        choice = choices[idx]
                    else:
                        console.print("[red]Invalid input. Please enter a number between 1 and 7.[/red]")
                        continue
                except EOFError:
                    console.print("[red]Input error. Exiting...[/red]")
                    return
                except Exception as e:
                    console.print(f"[red]Error reading input: {str(e)}. Exiting...[/red]")
                    return
            
            if choice == "Generate a new market research report" or choice == "1":
                self.generate_report()
            elif choice == "View existing reports" or choice == "2":
                self.list_reports()
            elif choice == "Export a report to PDF" or choice == "3":
                self.export_reports()
            elif choice == "Delete a report" or choice == "4":
                self.delete_report()
            elif choice == "Configure settings" or choice == "5":
                self.settings()
            elif choice == "Help & AI model information" or choice == "6":
                self.show_help()
            elif choice == "Exit" or choice == "7":
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
        """List all available reports."""
        reports = report_manager.get_all_reports()
        
        if not reports:
            console.print("\n[bold yellow]No reports found.[/bold yellow]")
            console.print("Generate a new report to get started.\n")
            return
        
        console.print("\n[bold blue]Available Market Research Reports:[/bold blue]\n")
        
        report_details = []
        
        # Process each report to extract metadata
        for i, report_filename in enumerate(reports, 1):
            try:
                report_path = REPORTS_DIR / report_filename
                content = report_path.read_text(encoding='utf-8')
                
                # Parse metadata with compatibility handling
                metadata_result = parse_report_metadata(content)
                
                # Handle both return types: Dict from Python implementation or (Dict, String) tuple from Rust
                if isinstance(metadata_result, tuple) and len(metadata_result) == 2:
                    # Rust implementation returns (metadata_dict, content_str)
                    metadata = metadata_result[0]
                else:
                    # Python implementation returns just the metadata dict
                    metadata = metadata_result
                
                title = metadata.get("title", report_filename)
                date = metadata.get("date", "Unknown Date")
                report_id = metadata.get("id", "N/A")
                
                report_details.append({
                    "index": i, 
                    "title": title, 
                    "date": date, 
                    "id": report_id,
                    "filename": report_filename
                })
                
                # Print report information
                console.print(f"[bold cyan]{i}.[/bold cyan] [green]{title}[/green]")
                console.print(f"   [dim]Generated:[/dim] [blue]{date}[/blue]")
                console.print(f"   [dim]ID:[/dim] [yellow]{report_id}[/yellow]")
                console.print(f"   [dim]File:[/dim] {report_filename}")
                console.print()
                
            except Exception as e:
                console.print(f"[yellow]Could not parse metadata for {report_filename}: {e}[/yellow]")
                # Add with defaults if parsing fails
                report_details.append({
                    "index": i, 
                    "title": report_filename, 
                    "date": "N/A", 
                    "id": "N/A",
                    "filename": report_filename
                })
                
                # Print minimal information
                console.print(f"[bold cyan]{i}.[/bold cyan] {report_filename}")
                console.print(f"   [dim]Error parsing metadata[/dim]")
                console.print()
        
        # Store report details for other methods to use
        self.report_details = report_details
        
        # Show options
        if reports:
            choice = questionary.text(
                "Enter the number of the report to view (or press Enter to go back):",
                validate=lambda text: text == "" or text.isdigit() and 1 <= int(text) <= len(reports)
            ).ask()
            
            if choice:
                self.view_report_by_index(int(choice))

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
             
    def export_reports(self) -> None:
        """Export reports to PDF."""
        try:
            reports = report_manager.get_all_reports()
        except Exception as e:
            console.print(f"[red]Error listing reports for export: {e}[/red]")
            return

        if not reports:
            console.print("[yellow]No reports found to export.[/yellow]")
            return
        
        # Check if PDF export is available - use try/except to detect reportlab
        reportlab_available = False
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib import colors
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
            from reportlab.lib.units import inch, cm
            reportlab_available = True
            console.print("[green]ReportLab is available for PDF export.[/green]")
        except ImportError:
            console.print("[yellow]ReportLab library not found. PDF export will attempt to use alternatives.[/yellow]")
            reportlab_available = False
        
        # Create a list of report options with index and title/date
        report_options = []
        for i, report_filename in enumerate(reports):
            try:
                content = report_manager.read_report(report_filename)
                
                # Clean escape sequences from content
                try:
                    content = clean_escape_sequences(content)
                except Exception:
                    # Continue without cleaning if it fails
                    pass
                
                # Handle potential tuple return from parse_report_metadata
                metadata_result = parse_report_metadata(content)
                if isinstance(metadata_result, tuple) and len(metadata_result) == 2:
                    # Rust implementation returns (metadata_dict, content_str)
                    metadata = metadata_result[0]
                else:
                    # Python implementation returns just the metadata dict
                    metadata = metadata_result
                    
                title = metadata.get("title", report_filename).replace(" Market Analysis", "")
                date = metadata.get("date", "Unknown Date")
                report_options.append(f"#{i+1}: {title} ({date}) - [{report_filename}]")
            except Exception as e:
                # On any error, add basic filename entry
                report_options.append(f"#{i+1}: {report_filename} (Error: {str(e)[:30]}...)")

        report_options.append("Cancel")

        choice = questionary.select(
            "Select a report to export to PDF:",
            choices=report_options
        ).ask()

        if choice is None or choice == "Cancel":
            console.print("Export cancelled.")
            return
            
        # Extract index from selection
        try:
            # Parse the index from the choice string (#X: ...)
            selection_idx = int(choice.split('#')[1].split(':')[0]) - 1
            report_filename = reports[selection_idx]
            report_path = Path(REPORTS_DIR) / report_filename
            self.export_single_report(report_path)
        except Exception as e:
            console.print(f"[red]Error exporting report: {e}[/red]")
    
    def export_single_report(self, report_path: Path) -> None:
        """Export a single report to PDF."""
        # Check if PDF export is available
        reportlab_available = False
        try:
            from reportlab.lib.pagesizes import A4
            reportlab_available = True
        except ImportError:
            reportlab_available = False
            
        try:
            # Read the report content
            content = report_path.read_text(encoding='utf-8')
            
            # Clean escape sequences from content
            try:
                content = clean_escape_sequences(content)
            except Exception as e:
                console.print(f"[yellow]Warning: Error cleaning escape sequences: {e}[/yellow]")
                
            # Default output path is in the same directory with .pdf extension
            output_path = report_path.with_suffix('.pdf')
            
            # Allow user to specify a different output path
            custom_path = questionary.text(
                "Enter output path for PDF (or press Enter for default):",
            ).ask()
            
            if custom_path:
                output_path = Path(custom_path)
                # Ensure the file has .pdf extension
                if output_path.suffix.lower() != '.pdf':
                    output_path = output_path.with_suffix('.pdf')
            
            # Export to PDF
            console.print(f"[yellow]Exporting to PDF: {output_path}[/yellow]")
            export_to_pdf(content, str(output_path))
            console.print(f"[green]✓ Report exported to: {output_path}[/green]")
            
            # Ask if user wants to open the PDF
            if questionary.confirm("Open the PDF file?").ask():
                try:
                    open_file(output_path)
                    console.print("[green]✓ Opening PDF viewer[/green]")
                except Exception as e:
                    console.print(f"[yellow]Could not open PDF automatically: {e}[/yellow]")
                    console.print(f"Please open manually: {output_path}")
                    
        except Exception as e:
            console.print(f"[red]Error exporting report to PDF: {e}[/red]")
            console.print(f"Details: {str(e)}")

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
                
                # Clean escape sequences from content
                try:
                    content = clean_escape_sequences(content)
                except Exception:
                    # Continue without cleaning if it fails
                    pass
                
                # Handle potential tuple return from parse_report_metadata
                metadata_result = parse_report_metadata(content)
                if isinstance(metadata_result, tuple) and len(metadata_result) == 2:
                    # Rust implementation returns (metadata_dict, content_str)
                    metadata = metadata_result[0]
                else:
                    # Python implementation returns just the metadata dict
                    metadata = metadata_result
                    
                title = metadata.get("title", report_filename).replace(" Market Analysis", "")
                date = metadata.get("date", "Unknown Date")
                report_options.append(f"#{i+1}: {title} ({date}) - [{report_filename}]")
            except Exception as e:
                # On any error, add basic filename entry
                report_options.append(f"#{i+1}: {report_filename} (Error: {str(e)[:30]}...)")

        report_options.append("Cancel")

        choice = questionary.select(
            "Select a report to delete:",
            choices=report_options
        ).ask()

        if choice is None or choice == "Cancel":
            console.print("Deletion cancelled.")
            return
            
        # Add the missing implementation for deleting a report
        try:
            # Parse the index from the choice string (#X: ...)
            selection_idx = int(choice.split('#')[1].split(':')[0]) - 1
            report_filename = reports[selection_idx]
            
            # Confirm deletion
            if questionary.confirm(f"Are you sure you want to delete '{report_filename}'?", default=False).ask():
                if report_manager.delete_report(report_filename):
                    console.print(f"[green]Report '{report_filename}' deleted successfully.[/green]")
                else:
                    console.print(f"[yellow]Failed to delete report '{report_filename}'.[/yellow]")
            else:
                console.print("Deletion cancelled.")
        except Exception as e:
            console.print(f"[red]Error during report deletion: {e}[/red]")
    
    def _send_report_sms(self, report_path: Path) -> None:
        """Send a summary of the report via SMS using Twilio."""
        if not TWILIO_ENABLED:
            console.print("[red]Twilio is not configured. Cannot send SMS.[/red]")
            return

        try:
            # Read the report content
            content = report_path.read_text(encoding='utf-8')
            
            # Clean escape sequences from content
            try:
                content = clean_escape_sequences(content)
            except Exception as e:
                console.print(f"[yellow]Warning: Error cleaning escape sequences: {e}[/yellow]")
                # Apply direct cleaning if clean_escape_sequences fails
                ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
                content = ansi_escape.sub('', content)
                
                # Also handle text representations of ESC
                esc_text = re.compile(r'ESC\[(?:\d+;)*\d*[a-zA-Z]')
                content = esc_text.sub('', content)
            
            # Extract title for SMS
            metadata_result = parse_report_metadata(content)
            if isinstance(metadata_result, tuple) and len(metadata_result) == 2:
                metadata, content = metadata_result
            else:
                metadata = metadata_result
            
            title = metadata.get("title", report_path.stem)
            
            # Prepare SMS message
            sms_message = f"New market research report available: {title}\n\n{content}"
            
            # Send SMS using Twilio
            try:
                client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
                message = client.messages.create(
                    to=TWILIO_PHONE_NUMBER,
                    from_=TWILIO_PHONE_NUMBER,
                    body=sms_message
                )
                console.print(f"[green]SMS sent successfully. SID: {message.sid}[/green]")
            except Exception as e:
                console.print(f"[red]Error sending SMS: {str(e)}[/red]")
        except Exception as e:
            console.print(f"[red]Error reading report for SMS: {str(e)}[/red]")

    def _configure_sms_settings(self) -> None:
        """Configure SMS settings using Twilio."""
        if not TWILIO_ENABLED:
            console.print("[red]Twilio is not configured. Cannot configure SMS settings.[/red]")
            return

        try:
            # Get current settings
            current_settings = {
                "Account SID": TWILIO_ACCOUNT_SID,
                "Auth Token": TWILIO_AUTH_TOKEN,
                "Phone Number": TWILIO_PHONE_NUMBER
            }
            console.print("\n[bold]Current SMS Settings:[/bold]")
            for key, value in current_settings.items():
                console.print(f"{key}: {value}")

            # Ask user for new settings
            new_account_sid = questionary.text("Enter new Account SID (leave blank to keep current):", default=TWILIO_ACCOUNT_SID).ask()
            new_auth_token = questionary.text("Enter new Auth Token (leave blank to keep current):", default=TWILIO_AUTH_TOKEN).ask()
            new_phone_number = questionary.text("Enter new Phone Number (leave blank to keep current):", default=TWILIO_PHONE_NUMBER).ask()

            # Update settings if provided
            if new_account_sid:
                TWILIO_ACCOUNT_SID = new_account_sid
            if new_auth_token:
                TWILIO_AUTH_TOKEN = new_auth_token
            if new_phone_number:
                TWILIO_PHONE_NUMBER = new_phone_number

            # Save settings to environment variables
            os.environ["TWILIO_ACCOUNT_SID"] = TWILIO_ACCOUNT_SID
            os.environ["TWILIO_AUTH_TOKEN"] = TWILIO_AUTH_TOKEN
            os.environ["TWILIO_PHONE_NUMBER"] = TWILIO_PHONE_NUMBER

            console.print("\n[bold green]SMS settings updated successfully![/bold green]")
        except Exception as e:
            console.print(f"[red]Error updating SMS settings: {str(e)}[/red]")

    def show_help(self) -> None:
        """Display help information about the tool and its usage."""
        console.print("\n[bold]Help & Information:[/bold]")
        console.print("This tool helps you generate market research reports using AI.")
        console.print("You can choose to use OpenAI or Claude for generating sections.")
        console.print("The tool will guide you through the process step-by-step.")
        console.print("Please ensure your API keys are configured correctly in the `.env` file.")
        console.print("For more information, please refer to the documentation.")

# Add view_report function at the top level before any usage
def view_report(report_path: Path, console: Any) -> None:
    """View a specific report file in the console using Markdown rendering.
    
    This is a standalone function that cleans escape sequences and displays formatted report content.
    
    Args:
        report_path: Path to the report file
        console: Rich console object for display
    """
    if not report_path.exists():
        console.print(f"[red]Error: Report file not found at {report_path}[/red]")
        return

    try:
        content = report_path.read_text(encoding='utf-8')
        
        # Clean any ANSI escape sequences in the content
        try:
            content = clean_escape_sequences(content)
        except Exception as e:
            console.print(f"[yellow]Warning: Error cleaning escape sequences: {str(e)}[/yellow]")
            # Apply direct cleaning if clean_escape_sequences fails
            ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
            content = ansi_escape.sub('', content)
            
            # Also handle text representations of ESC
            esc_text = re.compile(r'ESC\[(?:\d+;)*\d*[a-zA-Z]')
            content = esc_text.sub('', content)
        
        # Extract title for display
        metadata_result = parse_report_metadata(content)
        if isinstance(metadata_result, tuple) and len(metadata_result) == 2:
            metadata, content = metadata_result
        else:
            metadata = metadata_result
        
        title = metadata.get("title", report_path.stem)
        
        # Display the report with markdown formatting
        console.print("\n")
        console.rule(f"[bold blue]{title}[/bold blue]", style="blue")
        console.print("\n")
        
        # Display content with markdown formatting if available
        try:
            from rich.markdown import Markdown
            md = Markdown(content)
            console.print(md)
        except ImportError:
            # Fallback to simple printing if markdown formatter not available
            console.print(content)
            
        console.print("\n")
        console.rule(style="blue")
        console.print("\n")
        
    except Exception as e:
        console.print(f"[red]Error viewing report: {str(e)}[/red]")
        console.print(f"[yellow]Try using the test_view_report.py script as an alternative[/yellow]")

if __name__ == "__main__":
    print("=== Debug: Starting application ===")
    try:
        # Don't call app() directly, which causes Typer error
        # Instead, create a CLI instance and start interactive mode
        print("=== Debug: Creating CLI instance ===")
        cli_instance = FastCLI()
        print("=== Debug: Displaying welcome ===")
        cli_instance.display_welcome()
        print("=== Debug: Entering main menu ===")
        cli_instance.main_menu()
        print("=== Debug: Application completed normally ===")
    except Exception as e:
        print(f"=== Debug: Unhandled exception: {e} ===")
        import traceback
        traceback.print_exc()
    print("=== Debug: Reached end of file ===")
