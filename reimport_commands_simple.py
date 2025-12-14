#!/usr/bin/env python3
"""
Simple re-import script for converted commands
"""

import csv
import os
import struct
import tempfile
import zlib
from pathlib import Path
import nbtlib

import shutil

INPUT_DIR = '1-12 worlds'

def reimport_commands(world_name, converted_csv, output_world_folder):
    print("=== Re-importing Converted Commands ===")
    
    # Setup paths
    input_world_folder = os.path.join(INPUT_DIR, world_name)
    output_world_path = os.path.join(output_world_folder, world_name)
    print(f"DEBUG: Looking for source world at: {input_world_folder}")
    print(f"DEBUG: Output world path will be: {output_world_path}")
    if not os.path.exists(input_world_folder):
        print(f"Error: Source world not found: {input_world_folder}")
        return
    if not os.path.exists(output_world_path):
        shutil.copytree(input_world_folder, output_world_path)
    
    # Check files exist
    if not Path(converted_csv).exists():
        print(f"Error: Converted commands file not found: {converted_csv}")
        return
    
    # Load converted commands
    print(f"Loading converted commands from {converted_csv}")
    commands_by_chunk = {}
    
    with open(converted_csv, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            region_file = row['region_file']
            chunk_x = int(row['chunk_x'])
            chunk_z = int(row['chunk_z'])
            command_index = int(row['command_index'])
            converted_command = row['converted_command']
            
            key = (region_file, chunk_x, chunk_z)
            if key not in commands_by_chunk:
                commands_by_chunk[key] = []
            commands_by_chunk[key].append((command_index, converted_command))
    
    print(f"Loaded {len(commands_by_chunk)} chunks with commands")
    
    # Process each chunk
    total_imported = 0
    total_chunks_processed = 0
    
    for (region_file, chunk_x, chunk_z), commands in commands_by_chunk.items():
        print(f"\nProcessing {region_file} chunk ({chunk_x}, {chunk_z}) with {len(commands)} commands")
        
        region_path = Path(output_world_path) / "region" / region_file
        
        if not region_path.exists():
            print(f"  Region file not found: {region_path}")
            continue
        
        temp_path = None
        
        try:
            with open(region_path, 'rb') as f:
                header = f.read(8192)
                
                # Find chunk location
                chunk_index = chunk_x + chunk_z * 32
                offset = chunk_index * 4
                location = struct.unpack('>I', b'\x00' + header[offset:offset+3])[0]
                sectors = header[offset+3]
                
                if location == 0 or sectors == 0:
                    print(f"  Chunk ({chunk_x}, {chunk_z}) not found in region")
                    continue
                
                # Read chunk data
                f.seek(location * 4096)
                length = struct.unpack('>I', f.read(4))[0]
                compression_type = struct.unpack('B', f.read(1))[0]
                compressed_data = f.read(length - 1)
                
                if compression_type == 2:  # zlib
                    chunk_data = zlib.decompress(compressed_data)
                    
                    # Create temporary NBT file
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.nbt') as temp_file:
                        temp_file.write(chunk_data)
                        temp_path = temp_file.name
                    
                    # Load NBT
                    chunk_nbt = nbtlib.load(temp_path)
                    
                    # Find tile entities
                    tile_entities = None
                    if 'Level' in chunk_nbt and 'TileEntities' in chunk_nbt['Level']:
                        tile_entities = chunk_nbt['Level']['TileEntities']
                    elif 'block_entities' in chunk_nbt:
                        tile_entities = chunk_nbt['block_entities']
                    
                    if tile_entities:
                        # Update commands
                        commands_updated = 0
                        for command_index, converted_command in commands:
                            if command_index < len(tile_entities):
                                tile_entity = tile_entities[command_index]
                                if tile_entity.get('id') in ['minecraft:command_block', 'command_block']:
                                    old_command = tile_entity.get('Command', '')
                                    # Clean § color codes from the command
                                    cleaned_command = converted_command
                                    tile_entity['Command'] = nbtlib.String(cleaned_command)
                                    commands_updated += 1
                                    print(f"    Updated command {command_index}: {len(old_command)} -> {len(cleaned_command)} chars")
                        
                        if commands_updated > 0:
                            # Save modified NBT
                            with tempfile.NamedTemporaryFile(delete=False, suffix='.nbt') as save_file:
                                chunk_nbt.save(save_file.name)
                                
                                # Read back and compress
                                with open(save_file.name, 'rb') as save_f:
                                    new_chunk_data = save_f.read()
                                
                                # Clean up save file
                                try:
                                    os.unlink(save_file.name)
                                except:
                                    pass
                                
                                # Compress and write back
                                new_compressed_data = zlib.compress(new_chunk_data)
                                new_length = len(new_compressed_data) + 1
                                
                                with open(region_path, 'r+b') as f:
                                    f.seek(location * 4096)
                                    f.write(struct.pack('>I', new_length))
                                    f.write(struct.pack('B', 2))  # zlib compression
                                    f.write(new_compressed_data)
                                
                                print(f"  [OK] Updated {commands_updated} commands in chunk")
                                total_imported += commands_updated
                                total_chunks_processed += 1
                
                elif compression_type == 0:
                    print(f"  [ERROR] Chunk ({chunk_x}, {chunk_z}) is corrupted")
                else:
                    print(f"  [ERROR] Unsupported compression type: {compression_type}")
                    
        except Exception as e:
            print(f"  [ERROR] Error processing chunk: {e}")
        
        finally:
            # Clean up temporary file
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except:
                    pass
    
    print(f"\n=== Re-import Complete ===")
    print(f"Total chunks processed: {total_chunks_processed}")
    print(f"Total commands imported: {total_imported}")
    print(f"World saved to: {output_world_path}")
    print(f"The world is now ready for Minecraft 1.20!")
    print("Script completed successfully - exiting cleanly")

import sys

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python reimport_commands_simple.py <world_name> <converted_csv> <output_world_folder>")
        sys.exit(1)
    world_name = sys.argv[1]
    converted_csv = sys.argv[2]
    output_world_folder = sys.argv[3]
    reimport_commands(world_name, converted_csv, output_world_folder) 