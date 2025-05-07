#!/usr/bin/env python3
"""
Test script to generate a PDF using ReportLab.
"""

import os
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.units import inch, cm

# Path for the output PDF
output_path = "test_report.pdf"

# Sample markdown content
content = """# Test Report

This is a test report to check ReportLab functionality.

## Section 1

This is some content for section 1.

## Section 2

This is some content for section 2.
"""

print(f"Generating PDF at {output_path}...")

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

# Create custom styles
styles.add(ParagraphStyle(
    name='CustomHeading1',
    parent=styles['Heading1'],
    fontSize=24,
    spaceAfter=20
))

styles.add(ParagraphStyle(
    name='CustomNormal',
    parent=styles['Normal'],
    fontSize=11,
    spaceAfter=8
))

# Create elements for the document
elements = []

# Add title
elements.append(Paragraph("Test Report", styles['CustomHeading1']))
elements.append(Spacer(1, 0.5*inch))

# Add some content
elements.append(Paragraph("This is a test report to check ReportLab functionality.", styles['CustomNormal']))
elements.append(Spacer(1, 0.3*inch))

# Add a section heading
elements.append(Paragraph("Section 1", styles['Heading2']))
elements.append(Paragraph("This is some content for section 1.", styles['CustomNormal']))
elements.append(Spacer(1, 0.3*inch))

# Add another section heading
elements.append(Paragraph("Section 2", styles['Heading2']))
elements.append(Paragraph("This is some content for section 2.", styles['CustomNormal']))

# Build the PDF
doc.build(elements)

print(f"✅ PDF generated successfully at {output_path}")

# Try to open the PDF
print("Attempting to open the PDF...")
try:
    import platform
    if platform.system() == 'Windows':
        os.startfile(output_path)
    elif platform.system() == 'Darwin':  # macOS
        import subprocess
        subprocess.run(['open', output_path], check=True)
    else:  # Linux/Unix
        import subprocess
        subprocess.run(['xdg-open', output_path], check=True)
    print("✅ PDF opened successfully")
except Exception as e:
    print(f"❌ Failed to open PDF: {e}")
    print(f"The PDF is still available at: {output_path}") 