# Market Research CLI Troubleshooting Guide

## Escape Sequence Issues in Reports

### Problem

When viewing reports in the CLI application, you may see ANSI escape sequences displayed as text instead of being properly rendered. This can look like:

```
ESC[33m───────────────────────────────────────────────────────────────────────────────────────────────────ESC[0m

                 ESC[1;4mid: REP-3957ESC[0mESC[1;4m ESC[0mESC[1;4mtitle: Ai Market AnalysisESC[0mESESC[1;4m ESC[0mESC[1;4mdate: 2025-04-30 14:48:38ESC[0m
```

These escape sequences are formatting codes that were not properly cleaned when saving the report or displaying it.

### Causes

1. Incompatibility between the version of the `rich` library and how it's used in the code
2. Escape sequences being saved in the report files themselves
3. Incomplete cleaning of escape sequences when displaying reports

### Solutions

#### Solution 1: Use the Fix Script

We've provided a script to clean escape sequences from all your reports. This is the easiest solution:

```bash
python fix_report.py
```

This will process all reports in the `reports/` directory and remove any escape sequences.

#### Solution 2: View Reports with the Test Script

If you're still having issues viewing reports through the main application, you can use our test script:

```bash
python test_view_report.py reports/your_report_file.md
```

This will display a clean version of the report without requiring the main application.

#### Solution 3: Manual Fixes for Developers

If you're developing the application or want to fix the underlying issues:

1. Update the `clean_escape_sequences` function in `market_research_cli/fast_cli.py` to use the enhanced version from `fix_report.py`
2. Update the `view_report` function to use a simpler approach for displaying reports, avoiding compatibility issues with Rich
3. Consider using a different console output library if Rich continues to have compatibility issues

## Rich Library Compatibility Issues

### Problem

The application tries to use features from the Rich library (such as Table with styling) that may not be compatible with the installed version.

### Solution

The application should detect the installed Rich version and adapt accordingly. If you continue experiencing issues with the UI:

1. Check the installed version of Rich: `pip show rich`
2. For development: Update the code to use only basic Rich features or detect and adapt to the installed version
3. For users: Ensure you have the correct version of Rich installed as specified in requirements.txt

## General Troubleshooting

If you continue to experience issues:

1. Run with debug output: `python -m market_research_cli.fast_cli --debug`
2. Make sure all dependencies are installed: `pip install -r requirements.txt`
3. Try creating a fresh virtual environment: `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
4. Check for error messages in the console output that might point to specific issues

## Accessing Your Reports Outside the Application

If the application is not working for you, remember that all reports are stored as Markdown files in the `reports/` directory. You can open these files with any text editor or Markdown viewer.

For best results, process them with the fix script first to remove escape sequences:

```bash
python fix_report.py
```

Then view them with any Markdown viewer of your choice. 