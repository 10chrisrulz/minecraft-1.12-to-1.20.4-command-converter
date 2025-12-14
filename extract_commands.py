#!/usr/bin/env python3
"""
Extract Commands - Extract all command block commands from the original world to CSV
"""

import os
import struct
import zlib
import tempfile
import csv
from pathlib import Path
import nbtlib

def extract_commands(world_name, output_file):
    print("=== Extracting Commands from Original World ===")
    
    world_path = Path(world_name)
    # output_file is now passed as an argument
    
    # CSV headers
    headers = ['region_file', 'chunk_x', 'chunk_z', 'block_x', 'block_y', 'block_z', 'command_index', 'command', 'command_length', 'block_type']
    
    total_commands = 0
    total_chunks = 0
    
    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(headers)
        
        # Process all region files
        region_dir = world_path / "region"
        if not region_dir.exists():
            print("Region directory not found!")
            return
        
        for region_file in region_dir.glob("r.*.mca"):
            print(f"\nProcessing region: {region_file.name}")
            
            with open(region_file, 'rb') as f:
                header = f.read(8192)
                
                # Check each chunk in the region
                for chunk_x in range(32):
                    for chunk_z in range(32):
                        chunk_index = chunk_x + chunk_z * 32
                        offset = chunk_index * 4
                        location = struct.unpack('>I', b'\x00' + header[offset:offset+3])[0]
                        sectors = header[offset+3]
                        
                        if location == 0 or sectors == 0:
                            continue
                        
                        # Read chunk data
                        f.seek(location * 4096)
                        try:
                            length = struct.unpack('>I', f.read(4))[0]
                            compression_type = struct.unpack('B', f.read(1))[0]
                            compressed_data = f.read(length - 1)
                            
                            if compression_type == 2:  # zlib
                                chunk_data = zlib.decompress(compressed_data)
                                
                                # Load as NBT
                                with tempfile.NamedTemporaryFile(delete=False, suffix='.nbt') as temp_file:
                                    temp_file.write(chunk_data)
                                    temp_path = temp_file.name
                                
                                try:
                                    chunk_nbt = nbtlib.load(temp_path)
                                    
                                    # Find tile entities
                                    tile_entities = None
                                    if 'Level' in chunk_nbt and 'TileEntities' in chunk_nbt['Level']:
                                        tile_entities = chunk_nbt['Level']['TileEntities']
                                    elif 'block_entities' in chunk_nbt:
                                        tile_entities = chunk_nbt['block_entities']
                                    
                                    if tile_entities:
                                        chunk_commands = 0
                                        for i, tile_entity in enumerate(tile_entities):
                                            if tile_entity.get('id') in ['minecraft:command_block', 'command_block']:
                                                command = tile_entity.get('Command', '')
                                                if command:
                                                    # Determine block type
                                                    auto = tile_entity.get('auto', 0)
                                                    powered = tile_entity.get('powered', 0)
                                                    
                                                    if auto == 1:
                                                        block_type = "repeating"
                                                    elif powered == 1:
                                                        block_type = "chain"
                                                    else:
                                                        block_type = "impulse"
                                                    # Get world coordinates
                                                    block_x = tile_entity.get('x', '')
                                                    block_y = tile_entity.get('y', '')
                                                    block_z = tile_entity.get('z', '')
                                                    # Write to CSV
                                                    writer.writerow([
                                                        region_file.name,
                                                        chunk_x,
                                                        chunk_z,
                                                        block_x,
                                                        block_y,
                                                        block_z,
                                                        i,
                                                        command,
                                                        len(command),
                                                        block_type
                                                    ])
                                                    
                                                    chunk_commands += 1
                                        
                                        if chunk_commands > 0:
                                            print(f"  Chunk ({chunk_x}, {chunk_z}): {chunk_commands} commands")
                                            total_commands += chunk_commands
                                            total_chunks += 1
                                
                                except Exception as e:
                                    print(f"  Error reading chunk ({chunk_x}, {chunk_z}): {e}")
                                
                                finally:
                                    os.unlink(temp_path)
                            
                            elif compression_type == 0:
                                print(f"  Chunk ({chunk_x}, {chunk_z}) is corrupted (compression type 0)")
                            else:
                                print(f"  Chunk ({chunk_x}, {chunk_z}) has unsupported compression type: {compression_type}")
                                
                        except Exception as e:
                            print(f"  Error reading chunk ({chunk_x}, {chunk_z}): {e}")
    
    print(f"\n=== Extraction Complete ===")
    print(f"Total chunks with commands: {total_chunks}")
    print(f"Total commands extracted: {total_commands}")
    print(f"Commands saved to: {output_file}")
    print(f"\nNext step: Run the command converter on {output_file}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) != 3:
        print("Usage: python extract_commands.py <world_folder> <output_csv>")
        sys.exit(1)
    
    world_name = sys.argv[1]
    output_file = sys.argv[2]
    extract_commands(world_name, output_file) 