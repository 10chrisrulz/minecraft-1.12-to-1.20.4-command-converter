"""
Convert a single world from 1.12 to 1.20

Usage: python convert_single_world.py <world_name>
Example: python convert_single_world.py dcs_refresh
"""

import os
import subprocess
import sys
import shutil

if len(sys.argv) < 2:
    print("Usage: python convert_single_world.py <world_name>")
    print("Example: python convert_single_world.py dcs_refresh")
    sys.exit(1)

world_name = sys.argv[1]

INPUT_DIR = '1-12 worlds'
OUTPUT_DIR = '1-20 worlds'
LOGS_DIR = os.path.join(OUTPUT_DIR, 'logs')
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

world_path = os.path.join(INPUT_DIR, world_name)

if not os.path.isdir(world_path):
    print(f"Error: World '{world_name}' not found in '{INPUT_DIR}' directory")
    sys.exit(1)

print(f"\n{'='*80}")
print(f"Converting world: {world_name}")
print(f"{'='*80}\n")

# Per-world temp files
extracted_csv = f"{world_name}_extracted.csv"
converted_csv = f"{world_name}_converted.csv"

# Step 1: Extract
print(f"Step 1: Extracting commands from {world_name}...")
subprocess.run(["python", "extract_commands.py", world_path, extracted_csv], check=True)

# Step 2: Convert
print(f"\nStep 2: Converting commands for {world_name}...")
subprocess.run(["python", "convert_extracted.py", extracted_csv, converted_csv], check=True)

# Step 3: Reimport
print(f"\nStep 3: Reimporting commands to 1.20 world...")
subprocess.run(["python", "reimport_commands_simple.py", world_name, converted_csv, OUTPUT_DIR], check=True)

# Move temporary CSV files to logs folder
for csv_file in [extracted_csv, converted_csv]:
    if os.path.exists(csv_file):
        shutil.move(csv_file, os.path.join(LOGS_DIR, csv_file))
        print(f"Moved {csv_file} to {LOGS_DIR}")

print(f"\n{'='*80}")
print(f"[SUCCESS] Conversion complete!")
print(f"  Source: {INPUT_DIR}/{world_name}")
print(f"  Output: {OUTPUT_DIR}/{world_name}")
print(f"  Logs: {LOGS_DIR}/{extracted_csv}, {LOGS_DIR}/{converted_csv}")
print(f"{'='*80}\n")

print("Sample conversions with NBT selectors:")
print("-" * 80)

# Show some examples from the converted CSV
import csv
converted_csv_path = os.path.join(LOGS_DIR, converted_csv)
try:
    with open(converted_csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        count = 0
        for row in reader:
            if 'nbt=' in row['converted_command'] and count < 3:
                orig = row['command'][:80] + '...' if len(row['command']) > 80 else row['command']
                conv = row['converted_command'][:80] + '...' if len(row['converted_command']) > 80 else row['converted_command']
                print(f"\nOriginal: {orig}")
                print(f"Converted: {conv}")
                count += 1
except Exception as e:
    print(f"Could not display examples: {e}")

print("\n" + "="*80)

