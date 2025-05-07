"""
Market Research Core Python Module

This module provides a wrapper around the Rust-based market_research_core module,
with Python fallbacks if the Rust implementation is not available.
"""

import os
import json
import time
import datetime
import re
import subprocess
import tempfile
import shutil
import platform
import io
from pathlib import Path
from typing import Dict, List, Optional, Any, Union

# Try to import reportlab for pure Python PDF generation
try:
    print("Attempting to import ReportLab modules...")
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    from reportlab.lib.units import inch, cm
    REPORTLAB_AVAILABLE = True
    print("✅ Successfully imported ReportLab modules, REPORTLAB_AVAILABLE =", REPORTLAB_AVAILABLE)
except ImportError as e:
    REPORTLAB_AVAILABLE = False
    print(f"❌ Failed to import ReportLab: {e}")
    print("ReportLab is not available for PDF generation.")

# Try to import the Rust module, use Python fallbacks if not available
try:
    import market_research_core
    RUST_CORE_AVAILABLE = True
    print("Using high-performance Rust backend")
except ImportError:
    RUST_CORE_AVAILABLE = False
    print("Rust performance core not available, using Python fallback")

class ProgressTracker:
    """Thread-safe progress tracker for report generation"""
    
    def __init__(self):
        """Initialize the progress tracker"""
        if RUST_CORE_AVAILABLE:
            self._tracker = market_research_core.ProgressTracker()
        else:
            self._percentage = 0.0
            self._stage = "Initializing"
            self._agent = "System"
            self._activity = "Starting up"
            self._start_time = time.time()
    
    def update(self, percentage: float, stage: str, agent: str, activity: str) -> None:
        """Update the progress of report generation"""
        if RUST_CORE_AVAILABLE:
            self._tracker.update(percentage, stage, agent, activity)
        else:
            self._percentage = percentage
            self._stage = stage
            self._agent = agent
            self._activity = activity
    
    def get_progress(self) -> Dict[str, Union[float, str]]:
        """Get the current progress data"""
        if RUST_CORE_AVAILABLE:
            return self._tracker.get_progress()
        else:
            return {
                "percentage": self._percentage,
                "stage": self._stage,
                "agent": self._agent,
                "activity": self._activity,
                "elapsed_seconds": time.time() - self._start_time
            }
    
    def get_elapsed_seconds(self) -> float:
        """Get elapsed time in seconds"""
        if RUST_CORE_AVAILABLE:
            return self._tracker.get_elapsed_seconds()
        else:
            return time.time() - self._start_time
    
    def reset(self) -> None:
        """Reset the progress tracker"""
        if RUST_CORE_AVAILABLE:
            self._tracker.reset()
        else:
            self._percentage = 0.0
            self._stage = "Initializing"
            self._agent = "System"
            self._activity = "Starting up"
            self._start_time = time.time()


class ReportManager:
    """Manager for report files"""
    
    def __init__(self, reports_dir: str):
        """Initialize the report manager"""
        self.reports_dir = reports_dir
        
        if RUST_CORE_AVAILABLE:
            self._manager = market_research_core.ReportManager(reports_dir)
        
        # Create directory if it doesn't exist
        os.makedirs(reports_dir, exist_ok=True)
    
    def save_report(self, filename: str, content: str) -> str:
        """Save a report to disk"""
        if RUST_CORE_AVAILABLE:
            return self._manager.save_report(filename, content)
        else:
            path = Path(self.reports_dir) / filename
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
            return str(path)
    
    def get_all_reports(self) -> List[str]:
        """Get a list of all reports"""
        if RUST_CORE_AVAILABLE:
            return self._manager.get_all_reports()
        else:
            reports_path = Path(self.reports_dir)
            if not reports_path.exists():
                return []
            
            return [
                f.name for f in reports_path.iterdir()
                if f.is_file() and f.suffix == '.md'
            ]
    
    def read_report(self, filename: str) -> str:
        """Read a report from disk"""
        if RUST_CORE_AVAILABLE:
            return self._manager.read_report(filename)
        else:
            path = Path(self.reports_dir) / filename
            return path.read_text()
    
    def delete_report(self, filename: str) -> bool:
        """Delete a report"""
        if RUST_CORE_AVAILABLE:
            return self._manager.delete_report(filename)
        else:
            path = Path(self.reports_dir) / filename
            if path.exists():
                path.unlink()
                return True
            return False


def process_markdown(markdown: str) -> str:
    """Process markdown content and convert to HTML"""
    if RUST_CORE_AVAILABLE:
        return market_research_core.process_markdown(markdown)
    else:
        # Simple fallback: markdown to HTML conversion
        try:
            import markdown
            return markdown.markdown(markdown, extensions=['tables', 'fenced_code'])
        except ImportError:
            return f"<pre>{markdown}</pre>"


def format_report(content: str, title: str = None) -> str:
    """Format a report with proper styling"""
    global RUST_CORE_AVAILABLE
    
    # Create default content if empty string is passed
    if not content.strip():
        # Create current timestamp
        current_date = datetime.datetime.now().strftime("%B %d, %Y")
        report_id = datetime.datetime.now().strftime("MR-%Y%m%d-%H%M%S")
        
        # Use the title if provided, otherwise use a default
        title_text = title if title else "Market Analysis"
        
        # Create a basic markdown document with title and metadata
        content = f"""---
id: {report_id}
title: {title_text} Market Analysis
date: {current_date}
---

# {title_text} Market Analysis

Generated on: {current_date}

"""
    
    if RUST_CORE_AVAILABLE:
        try:
            # The Rust version only accepts one parameter (content)
            return market_research_core.format_report(content)
        except TypeError as e:
            # For backwards compatibility, if the Rust function was updated to accept title
            # This is defensive programming to handle future changes
            print(f"Warning: Error calling Rust format_report: {e}. Falling back to Python implementation.")
            # Use a local copy instead of modifying the global
            rust_enabled = RUST_CORE_AVAILABLE
            RUST_CORE_AVAILABLE = False  # Temporarily disable for this call
            result = format_report(content, title)  # Call self with Rust disabled
            RUST_CORE_AVAILABLE = rust_enabled  # Restore original value
            return result
        except ValueError as e:
            # Handle the case where Rust rejects the content
            print(f"Warning: Rust format_report rejected content: {e}. Falling back to Python implementation.")
            rust_enabled = RUST_CORE_AVAILABLE
            RUST_CORE_AVAILABLE = False  # Temporarily disable for this call
            result = format_report(content, title)  # Call self with Rust disabled
            RUST_CORE_AVAILABLE = rust_enabled  # Restore original value
            return result
    else:
        current_date = datetime.datetime.now().strftime("%B %d, %Y")
        report_id = datetime.datetime.now().strftime("MR-%Y%m%d-%H%M%S")
        
        # Use the title if provided, otherwise use a default
        title_text = title if title else "Market Analysis"
        
        return f"""# {title_text} Market Analysis

<div class="report-metadata">
<p class="report-date">Generated on: {current_date}</p>
<p class="report-id">Report ID: {report_id}</p>
<p class="confidentiality">CONFIDENTIAL DOCUMENT</p>
</div>

---

{content}"""


def parse_report_metadata(content: str) -> Dict[str, str]:
    """Parse metadata from a report"""
    if RUST_CORE_AVAILABLE:
        return market_research_core.parse_report_metadata(content)
    else:
        import re
        
        title_match = re.search(r"#\s*(.*?)(?:\n|$)", content)
        date_match = re.search(r"Generated on:\s*(.*?)(?:\n|<)", content)
        id_match = re.search(r"Report ID:\s*(.*?)(?:\n|<)", content)
        
        title = title_match.group(1).strip() if title_match else "Unknown Title"
        date = date_match.group(1).strip() if date_match else "Unknown Date"
        id = id_match.group(1).strip() if id_match else "Unknown ID"
        
        return {
            "title": title,
            "date": date,
            "id": id
        }

def clean_escape_sequences(content: str) -> str:
    """Clean terminal escape sequences from the content"""
    if RUST_CORE_AVAILABLE:
        try:
            # Try to call the Rust function, but fall back to Python if it's not available
            if hasattr(market_research_core, 'clean_escape_sequences'):
                cleaned_content = market_research_core.clean_escape_sequences(content)
                # Double-check if the content was properly cleaned
                if "ESC[" in cleaned_content:
                    # Fall back to Python implementation for additional cleaning
                    return clean_escape_sequences_python(cleaned_content)
                return cleaned_content
            else:
                # Fall back to Python implementation if Rust function doesn't exist
                return clean_escape_sequences_python(content)
        except Exception as e:
            # Fall back to Python implementation if there's any error with the Rust version
            print(f"Warning: Error using Rust clean_escape_sequences: {e}, falling back to Python implementation")
            return clean_escape_sequences_python(content)
    else:
        return clean_escape_sequences_python(content)

def clean_escape_sequences_python(content: str) -> str:
    """Python implementation of escape sequence cleaning with comprehensive patterns"""
    import re
    
    # Try multiple pattern replacements for thoroughness
    
    # Pattern 1: Standard ANSI escape sequences with ESC prefix
    content = re.sub(r'ESC\[(\d+;)*\d*m', '', content)
    
    # Pattern 2: Raw escape character followed by color/formatting codes
    content = re.sub(r'\x1B\[([0-9]{1,2}(;[0-9]{1,2})*)?[m|K|G|A|B|C|D|H|J|s|u|h|l]', '', content)
    
    # Pattern 3: Literal "ESC[" with formatting codes
    content = re.sub(r'ESC\[([0-9]{1,2}(;[0-9]{1,2})*)?[m|K|G|A|B|C|D|H|J|s|u|h|l]', '', content)
    
    # Pattern 4: Additional formats like ESC[1;33m
    content = re.sub(r'ESC\[\d+;\d+m', '', content)
    
    # Pattern 5: Simple ESC[0m pattern (reset)
    content = re.sub(r'ESC\[0m', '', content)
    
    # Pattern 6: Bold and similar formats
    content = re.sub(r'ESC\[1m', '', content)
    
    # Pattern 7: Other common ANSI formats
    content = re.sub(r'ESC\[\d+m', '', content)
    
    # Pattern 8: Catch-all for other escape sequences with bracketed parameters
    content = re.sub(r'(?:\x1B|\bESC)(?:\[|\(|\))[^@-Z\\^_`a-z{|}~]*[@-Z\\^_`a-z{|}~]', '', content)
    
    return content 

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
    
# Add imports needed for PDF conversion Python fallback
import tempfile
import shutil
import platform

def export_to_pdf(content: str, output_path: str) -> str:
    """Export markdown content to a PDF file"""
    if RUST_CORE_AVAILABLE:
        try:
            return market_research_core.export_to_pdf(content, output_path)
        except Exception as e:
            print(f"Warning: Error using Rust export_to_pdf: {e}, falling back to Python implementation")
            return export_to_pdf_python(content, output_path)
    else:
        return export_to_pdf_python(content, output_path)

def export_to_pdf_python(content: str, output_path: str) -> str:
    """Python fallback for PDF export using wkhtmltopdf or reportlab"""
    # Clean any escape sequences
    cleaned_content = clean_escape_sequences_python(content)
    
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
                    extensions=['tables', 'fenced_code', 'codehilite']
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
            font-size: 12pt;
            line-height: 1.5;
            margin: 2cm;
        }}
        h1, h2, h3, h4, h5, h6 {{
            color: #333;
            margin-top: 1.5em;
            margin-bottom: 0.5em;
        }}
        h1 {{ font-size: 24pt; }}
        h2 {{ font-size: 20pt; }}
        h3 {{ font-size: 16pt; }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 1em 0;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }}
        th {{
            background-color: #f2f2f2;
        }}
        .report-metadata {{
            margin-bottom: 2em;
            color: #666;
            font-style: italic;
        }}
        ul, ol {{
            margin: 0.5em 0;
            padding-left: 2em;
        }}
        code {{
            font-family: monospace;
            background-color: #f5f5f5;
            padding: 2px 4px;
            border-radius: 3px;
        }}
        pre {{
            background-color: #f5f5f5;
            padding: 1em;
            border-radius: 5px;
            overflow-x: auto;
        }}
        blockquote {{
            background-color: #f9f9f9;
            border-left: 4px solid #ccc;
            margin: 1em 0;
            padding: 0.5em 1em;
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
                '--page-size', 'A4',
                '--margin-top', '20mm',
                '--margin-bottom', '20mm',
                '--margin-left', '20mm',
                '--margin-right', '20mm',
                '--encoding', 'UTF-8',
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
        
        # First, try to convert any HTML to plain text
        # ReportLab's parser can't handle complex HTML attributes like aria-hidden
        try:
            import re
            
            # Strip HTML tags that cause problems with ReportLab
            # 1. Remove anchor tags with aria-* attributes
            cleaned_content = re.sub(r'<a [^>]*aria-[^>]*>[^<]*</a>', '', cleaned_content)
            
            # 2. Remove other complex HTML tags but preserve their content
            def replace_tag_preserve_content(match):
                # Extract just the content between tags
                content = match.group(2) if match.group(2) else ''
                return content
                
            cleaned_content = re.sub(r'<([a-zA-Z]+)[^>]*>(.*?)</\1>', replace_tag_preserve_content, cleaned_content)
            
            # 3. Remove any remaining HTML tags
            cleaned_content = re.sub(r'<[^>]*>', '', cleaned_content)
            
            print("Content preprocessed for ReportLab")
        except Exception as e:
            print(f"Warning: Error preprocessing content for ReportLab: {e}")
        
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
            name='CustomHeading1',
            parent=styles['Heading1'],
            fontSize=24,
            spaceAfter=20
        ))
        styles.add(ParagraphStyle(
            name='CustomHeading2',
            parent=styles['Heading2'],
            fontSize=18,
            spaceAfter=15,
            spaceBefore=20
        ))
        styles.add(ParagraphStyle(
            name='CustomHeading3',
            parent=styles['Heading3'],
            fontSize=14,
            spaceAfter=10,
            spaceBefore=15
        ))
        styles.add(ParagraphStyle(
            name='CustomNormal',
            parent=styles['Normal'],
            fontSize=11,
            spaceAfter=8
        ))
        styles.add(ParagraphStyle(
            name='ListItem',
            parent=styles['Normal'],
            leftIndent=20,
            fontSize=11
        ))
        styles.add(ParagraphStyle(
            name='CodeBlock',
            parent=styles['Code'],
            fontName='Courier',
            fontSize=9,
            leftIndent=20,
            rightIndent=20,
            spaceAfter=8,
            spaceBefore=8
        ))
        
        # Create elements for the document
        elements = []
        
        # Add title
        elements.append(Paragraph(title, styles['CustomHeading1']))
        
        # Add metadata if available
        if metadata:
            date = metadata.get('date', datetime.datetime.now().strftime("%B %d, %Y"))
            report_id = metadata.get('id', 'N/A')
            
            meta_text = f"Generated on: {date}<br/>Report ID: {report_id}<br/>Confidential Document"
            elements.append(Paragraph(meta_text, styles['CustomNormal']))
            elements.append(Spacer(1, 0.5*inch))
        
        # Process markdown content into reportlab elements
        lines = cleaned_content.split('\n')
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # Skip empty lines
            if not line:
                i += 1
                continue
            
            # Headings
            if line.startswith('# '):
                elements.append(Paragraph(line[2:], styles['CustomHeading1']))
            elif line.startswith('## '):
                elements.append(Paragraph(line[3:], styles['CustomHeading2']))
            elif line.startswith('### '):
                elements.append(Paragraph(line[4:], styles['CustomHeading3']))
            elif line.startswith('#### ') or line.startswith('##### ') or line.startswith('###### '):
                # Count the number of # characters
                level = line.count('#', 0, 7)
                elements.append(Paragraph(line[level+1:], styles['CustomHeading3']))
            
            # Lists
            elif line.startswith('* ') or line.startswith('- '):
                elements.append(Paragraph('• ' + line[2:], styles['ListItem']))
            elif line.startswith('  * ') or line.startswith('  - '):
                elements.append(Paragraph('  ○ ' + line[4:], styles['ListItem']))
            elif line.startswith('    * ') or line.startswith('    - '):
                elements.append(Paragraph('    ▪ ' + line[6:], styles['ListItem']))
            
            # Numbered lists
            elif re.match(r'^\d+\.\s', line):
                text = re.sub(r'^\d+\.\s', '', line)
                elements.append(Paragraph('• ' + text, styles['ListItem']))
            
            # Code blocks
            elif line.startswith('```'):
                code_block = []
                i += 1  # Skip the opening ```
                while i < len(lines) and not lines[i].strip().startswith('```'):
                    code_block.append(lines[i])
                    i += 1
                if code_block:
                    elements.append(Paragraph('<pre>' + '\n'.join(code_block) + '</pre>', styles['CodeBlock']))
            
            # Tables - simplified handling
            elif line.startswith('|') and i + 2 < len(lines) and lines[i+1].startswith('|') and lines[i+1].replace('|', '').strip().replace('-', '') == '':
                headers = [cell.strip() for cell in line.split('|')[1:-1]]
                i += 2  # Skip header and separator rows
                
                data = [headers]
                while i < len(lines) and lines[i].startswith('|'):
                    row_data = [cell.strip() for cell in lines[i].split('|')[1:-1]]
                    data.append(row_data)
                    i += 1
                
                # Create table
                if len(data) > 1:
                    table = Table(data)
                    table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, 0), 10),
                        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                        ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ]))
                    elements.append(table)
                    elements.append(Spacer(1, 0.2*inch))
                continue  # Skip the increment at the end since we've already advanced i
            
            # Normal paragraph
            else:
                # Collect multi-line paragraph
                paragraph_lines = [line]
                j = i + 1
                while j < len(lines) and lines[j].strip() and not lines[j].strip().startswith('#') and not lines[j].strip().startswith('*') and not lines[j].strip().startswith('-') and not lines[j].strip().startswith('|') and not lines[j].strip().startswith('```'):
                    paragraph_lines.append(lines[j].strip())
                    j += 1
                
                paragraph_text = ' '.join(paragraph_lines)
                elements.append(Paragraph(paragraph_text, styles['CustomNormal']))
                i = j - 1  # Adjust i to the last line of the paragraph
            
            i += 1
        
        # Build the PDF
        doc.build(elements)
    
    else:
        # If neither wkhtmltopdf nor reportlab is available, raise an error with installation instructions
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

def open_file(file_path: str) -> bool:
    """Open a file with the default system application"""
    if RUST_CORE_AVAILABLE:
        try:
            return market_research_core.open_file(file_path)
        except Exception as e:
            print(f"Warning: Error using Rust open_file: {e}, falling back to Python implementation")
            return open_file_python(file_path)
    else:
        return open_file_python(file_path)

def open_file_python(file_path: str) -> bool:
    """Python implementation to open a file with the default system application"""
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