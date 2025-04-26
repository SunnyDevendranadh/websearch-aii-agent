"""
Market Research Core Python Module

A high-performance Python/Rust hybrid package for market research utilities.
This module provides accelerated operations for markdown processing, progress tracking,
and report management.
"""

# Import the implementation components
from .market_research_core_py import (
    ProgressTracker,
    ReportManager,
    process_markdown,
    format_report,
    parse_report_metadata,
    RUST_CORE_AVAILABLE
)

# Define what to export
__all__ = [
    'ProgressTracker',
    'ReportManager',
    'process_markdown',
    'format_report',
    'parse_report_metadata',
    'RUST_CORE_AVAILABLE'
]

# Version
__version__ = '0.1.0'