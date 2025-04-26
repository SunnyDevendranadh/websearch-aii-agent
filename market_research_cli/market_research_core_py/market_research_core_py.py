"""
Market Research Core Python Module

This module provides a wrapper around the Rust-based market_research_core module,
with Python fallbacks if the Rust implementation is not available.
"""

import os
import json
import time
import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Union

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


def format_report(content: str, title: str) -> str:
    """Format a report with proper styling"""
    if RUST_CORE_AVAILABLE:
        return market_research_core.format_report(content, title)
    else:
        current_date = datetime.datetime.now().strftime("%B %d, %Y")
        report_id = datetime.datetime.now().strftime("MR-%Y%m%d-%H%M%S")
        
        return f"""# {title} Market Analysis

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