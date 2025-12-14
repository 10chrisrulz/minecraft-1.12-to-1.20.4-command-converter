#!/usr/bin/env python3
"""
Extract selectors with dx/dy/dz but without x/y/z from extracted_commands.csv
Output to selector_dx_only.csv as a proper CSV file, including block_x, block_y, block_z from the CSV, and the world name.
"""
import csv
import re
import sys

WORLD_NAME = 'abandoned_mineshaft'

def has_dx_only_selector(command: str) -> bool:
    # Find all selectors in the command (e.g., @e[...])
    selectors = re.findall(r'@[pareas][^\s]*\[[^\]]*\]', command)
    for selector in selectors:
        params = selector[selector.find('[')+1:-1]
        param_dict = {k.strip(): v.strip() for k,v in (p.split('=',1) for p in params.split(',') if '=' in p)}
        has_dx = any(k in param_dict for k in ('dx','dy','dz'))
        has_xyz = any(k in param_dict for k in ('x','y','z'))
        if has_dx and not has_xyz:
            return True
    return False

def extract_dx_only_selectors(input_file: str, output_file: str, world_name: str):
    print('Starting extraction...')
    with open(input_file, 'r', encoding='utf-8', errors='replace') as infile, \
         open(output_file, 'w', encoding='utf-8', newline='', errors='replace') as csvfile:
        print('Files opened successfully.')
        fieldnames = ['world_name','region_file','chunk_x','chunk_z','block_x','block_y','block_z','command_index','block_type','command']
        reader = csv.DictReader(infile)
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for i, row in enumerate(reader):
            if i % 100 == 0:
                print(f'Processing line {i}...')
            command = row['command']
            if has_dx_only_selector(command):
                writer.writerow({
                    'world_name': world_name,
                    'region_file': row['region_file'],
                    'chunk_x': row['chunk_x'],
                    'chunk_z': row['chunk_z'],
                    'block_x': row.get('block_x', ''),
                    'block_y': row.get('block_y', ''),
                    'block_z': row.get('block_z', ''),
                    'command_index': row['command_index'],
                    'block_type': row['block_type'],
                    'command': command
                })
    print(f"Extraction complete. See {output_file} for results.")

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python extract_dx_only_selectors.py <input_extracted_csv> <output_dx_only_csv> <world_name>")
        sys.exit(1)
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    world_name = sys.argv[3]
    extract_dx_only_selectors(input_file, output_file, world_name) 