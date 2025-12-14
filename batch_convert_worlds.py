import os
import subprocess
import shutil
import glob

print('Batch conversion script started...')

INPUT_DIR = '1-12 worlds'
OUTPUT_DIR = '1-20 worlds'
LOGS_DIR = os.path.join(OUTPUT_DIR, 'logs')
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

for world_name in os.listdir(INPUT_DIR):
    world_path = os.path.join(INPUT_DIR, world_name)
    if not os.path.isdir(world_path):
        continue

    print(f"\n=== Processing world: {world_name} ===")

    # Per-world temp files
    extracted_csv = f"{world_name}_extracted.csv"
    converted_csv = f"{world_name}_converted.csv"
    dx_only_csv = f"{world_name}_dx_only.csv"

    # Step 1: Extract
    print(f"Extracting commands from {world_name}...")
    subprocess.run(["python", "extract_commands.py", world_path, extracted_csv], check=True)

    # Step 2: Convert
    print(f"Converting commands for {world_name}...")
    subprocess.run(["python", "convert_extracted.py", extracted_csv, converted_csv], check=True)

    # Step 3: Reimport
    print(f"Reimporting commands for {world_name}...")
    subprocess.run(["python", "reimport_commands_simple.py", world_name, converted_csv, OUTPUT_DIR], check=True)

    # Step 4: dx-only selector extraction
    print(f"Extracting dx-only selectors for {world_name}...")
    subprocess.run(["python", "extract_dx_only_selectors.py", extracted_csv, dx_only_csv, world_name], check=True)

    # Move only per-world logs to logs directory (after all steps)
    for log_file in glob.glob(f"{world_name}_extracted.csv") + \
                     glob.glob(f"{world_name}_converted.csv") + \
                     glob.glob(f"{world_name}_dx_only.csv"):
        if os.path.exists(log_file):
            shutil.move(log_file, os.path.join(LOGS_DIR, log_file))

print("\nAll worlds processed.") 