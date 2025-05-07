#!/usr/bin/env python3
"""
Test ReportLab availability and modules.
"""

import sys
print(f"Python version: {sys.version}")
print(f"Python path: {sys.executable}")

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    from reportlab.lib.units import inch, cm
    print("\n✅ ReportLab is installed and all modules imported successfully.")
    print("ReportLab should be available to the application.")
except ImportError as e:
    print(f"\n❌ ReportLab import error: {e}")
    print("ReportLab is not installed or not properly configured.")

# Try to import the module that uses ReportLab
try:
    from market_research_cli.market_research_core_py.market_research_core_py import REPORTLAB_AVAILABLE
    print(f"\nREPORTLAB_AVAILABLE from module: {REPORTLAB_AVAILABLE}")
except ImportError as e:
    print(f"\nError importing from market_research_core_py: {e}")
    
# Test direct import with fallback
try:
    import market_research_core_py
    print("\nRust module imported successfully.")
    if hasattr(market_research_core_py, 'export_to_pdf'):
        print("export_to_pdf function is available in Rust module.")
    else:
        print("export_to_pdf function is NOT available in Rust module.")
except ImportError:
    print("\nRust module not available.")

print("\nChecking sys.path:")
for p in sys.path:
    print(f"  - {p}") 