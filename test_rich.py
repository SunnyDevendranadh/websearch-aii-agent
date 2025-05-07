from rich.console import Console
from rich.table import Table
from rich import print

console = Console()

# Try different ways to create a table
print("Trying different table initializations:")

try:
    # Method 1: From documentation
    table1 = Table(title="Test Table 1")
    table1.add_column("Column 1")
    table1.add_column("Column 2")
    table1.add_row("Value 1", "Value 2")
    console.print(table1)
    print("Method 1 works!")
except Exception as e:
    print(f"Method 1 failed: {e}")

try:
    # Method 2: Using box parameter
    from rich.box import Box, SIMPLE
    table2 = Table(box=SIMPLE)
    table2.add_column("Column 1")
    table2.add_column("Column 2")
    table2.add_row("Value 1", "Value 2")
    console.print(table2)
    print("Method 2 works!")
except Exception as e:
    print(f"Method 2 failed: {e}")

try:
    # Method 3: With data
    data = [["Value 1", "Value 2"], ["Value 3", "Value 4"]]
    table3 = Table(data=data)
    console.print(table3)
    print("Method 3 works!")
except Exception as e:
    print(f"Method 3 failed: {e}") 