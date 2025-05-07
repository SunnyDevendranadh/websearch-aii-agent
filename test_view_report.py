#!/usr/bin/env python3
import re
from pathlib import Path
import sys

def clean_escape_sequences(content):
    """Enhanced cleaning of ANSI escape sequences"""
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

def view_report(report_path):
    """View a report with enhanced ANSI escape sequence cleaning"""
    if not Path(report_path).exists():
        print(f"Error: Report file not found at {report_path}")
        return
    
    try:
        content = Path(report_path).read_text(encoding='utf-8')
        
        # Clean all escape sequences
        content = clean_escape_sequences(content)
        
        # Print cleaned content
        print("\n--- CLEANED REPORT ---\n")
        print(content)
        print("\n--- END OF REPORT ---\n")
        
    except Exception as e:
        print(f"Error reading or displaying report: {e}")

# Main execution
if __name__ == "__main__":
    if len(sys.argv) < 2:
        # Default test - list available reports
        reports_dir = Path("reports")
        if reports_dir.exists():
            print("Available reports:")
            for i, report in enumerate(reports_dir.glob("*.md"), 1):
                print(f"{i}. {report.name}")
            
            choice = input("\nEnter report number to view (or press Enter to exit): ")
            if choice.isdigit() and 1 <= int(choice) <= len(list(reports_dir.glob("*.md"))):
                reports = list(reports_dir.glob("*.md"))
                view_report(reports[int(choice)-1])
        else:
            print("Reports directory not found.")
    else:
        # View specific report
        view_report(sys.argv[1]) 