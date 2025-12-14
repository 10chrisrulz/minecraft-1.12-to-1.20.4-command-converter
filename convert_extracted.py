#!/usr/bin/env python3
"""
Convert Extracted Commands - Convert the extracted commands using the command converter
"""

import csv
import sys

def convert_commands(input_file, output_file):
    from command_converter import LookupTables, CommandConverter
    lookups = LookupTables()
    converter = CommandConverter(lookups)

    with open(input_file, 'r', encoding='utf-8', errors='replace') as infile, \
         open(output_file, 'w', encoding='utf-8', newline='', errors='replace') as outfile:
        reader = csv.DictReader(infile)
        fieldnames = reader.fieldnames + ['converted_command'] if 'converted_command' not in reader.fieldnames else reader.fieldnames
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in reader:
            original_command = row['command']
            try:
                converted_command = converter.convert_command(original_command)
            except Exception as e:
                print(f"Error converting command: {original_command} -- {e}")
                converted_command = original_command
            row['converted_command'] = converted_command
            writer.writerow(row)

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python convert_extracted.py <input_extracted_csv> <output_converted_csv>")
        sys.exit(1)
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    convert_commands(input_file, output_file) 