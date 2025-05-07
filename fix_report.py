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

def fix_report_file(report_path):
    """Clean a report file and save it back with escape sequences removed"""
    path = Path(report_path)
    if not path.exists():
        print(f"Error: Report file not found at {report_path}")
        return False
    
    try:
        # Read the file
        content = path.read_text(encoding='utf-8')
        
        # Clean the content
        cleaned_content = clean_escape_sequences(content)
        
        # Save the cleaned content back to the file
        path.write_text(cleaned_content, encoding='utf-8')
        
        print(f"Successfully cleaned escape sequences in: {report_path}")
        return True
        
    except Exception as e:
        print(f"Error processing file {report_path}: {e}")
        return False

def process_all_reports():
    """Process all .md files in the reports directory"""
    reports_dir = Path("reports")
    if not reports_dir.exists():
        print("Error: Reports directory not found.")
        return
    
    success_count = 0
    fail_count = 0
    
    for report_file in reports_dir.glob("*.md"):
        print(f"Processing: {report_file.name}")
        if fix_report_file(report_file):
            success_count += 1
        else:
            fail_count += 1
    
    print(f"\nProcessing complete. Successfully processed {success_count} files. Failed: {fail_count}")

# Main execution
if __name__ == "__main__":
    if len(sys.argv) < 2:
        # No arguments - process all reports
        print("No specific file provided. Processing all reports in the 'reports' directory...")
        process_all_reports()
    else:
        # Process specific file
        fix_report_file(sys.argv[1]) 