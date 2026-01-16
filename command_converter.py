import csv
import re
import shlex
import logging
import functools
from typing import Dict, List, Tuple, Optional, Any
from pathlib import Path

# Set up method call logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('method_calls.log', mode='w', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
method_logger = logging.getLogger('method_calls')

def log_method_call(func):
    """Decorator to log method calls"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        class_name = args[0].__class__.__name__ if args else 'Unknown'
        method_logger.info(f"CALLED: {class_name}.{func.__name__}")
        try:
            result = func(*args, **kwargs)
            return result
        except Exception as e:
            method_logger.error(f"ERROR in {class_name}.{func.__name__}: {e}")
            raise
    return wrapper

class LookupTables:
    """Manages all lookup tables for conversions"""
    
    def __init__(self, entity_csv: str = "entity_conversion.csv", id_csv: str = "ID_Lookups.csv", sound_csv: str = "sound_conversion.csv", particle_csv: str = "particle_conversion.csv", legacy_json: str = "legacy.json", silent: bool = True):
        self.silent = silent
        self.entity_conversions = self._load_entity_conversions(entity_csv)
        self.block_conversions = self._load_block_conversions(id_csv)
        self.sound_conversions = self._load_sound_conversions(sound_csv)
        self.particle_conversions = self._load_particle_conversions(particle_csv)
        self.legacy_blocks = self._load_legacy_json(legacy_json)
        self.block_name_to_id = self._build_block_name_to_id_map(id_csv)
        
    def _load_entity_conversions(self, csv_path: str) -> Dict[str, str]:
        """Load entity name conversions from CSV"""
        conversions = {}
        try:
            with open(csv_path, 'r', encoding='utf-8', errors='replace') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    original = row['original'].strip()
                    converted = row['converted'].strip()
                    conversions[original] = converted
            if not self.silent:
                print(f"Loaded {len(conversions)} entity conversions")
        except Exception as e:
            if not self.silent:
                print(f"Error loading entity conversions: {e}")
        return conversions
    
    def _load_block_conversions(self, csv_path: str) -> Dict[Tuple[str, int], str]:
        """Load block ID/name conversions from CSV"""
        conversions = {}
        try:
            import os
            # Get the directory of this script
            script_dir = os.path.dirname(os.path.abspath(__file__))
            csv_full_path = os.path.join(script_dir, csv_path)
            
            with open(csv_full_path, 'r', encoding='utf-8', errors='replace') as file:
                reader = csv.DictReader(file)
                row_count = 0
                for row in reader:
                    row_count += 1
                    try:
                        block_id = row['id'].strip()
                        data_value = int(row['data'].strip())
                        conversion_name = row['conversion name'].strip()
                        block_name = row['block'].strip()
                        raw_block_name = row['raw_block'].strip()
                        
                        # Store by ID + data
                        conversions[(block_id, data_value)] = conversion_name
                        # Store by raw block name + data
                        conversions[(raw_block_name, data_value)] = conversion_name
                        # Store by minecraft: prefixed name + data
                        conversions[(f"minecraft:{raw_block_name}", data_value)] = conversion_name
                        # Store by block column name + data (this is the actual command block name)
                        conversions[(block_name, data_value)] = conversion_name
                        # Store by minecraft: prefixed block name + data
                        conversions[(f"minecraft:{block_name}", data_value)] = conversion_name
                    except (ValueError, KeyError) as e:
                        if not self.silent:
                            print(f"Skipping malformed row {row_count}: {row}. Error: {e}", file=sys.stderr)
            if not self.silent:
                print(f"Loaded {len(conversions)} block conversions from {row_count} rows", file=sys.stderr)
        except Exception as e:
            import sys
            import traceback
            if not self.silent:
                print(f"Error loading block conversions from {csv_path}: {e}", file=sys.stderr)
                traceback.print_exc(file=sys.stderr)
        return conversions
    
    def _load_sound_conversions(self, csv_path: str) -> Dict[str, str]:
        """Load sound name conversions from CSV"""
        conversions = {}
        try:
            with open(csv_path, 'r', encoding='utf-8', errors='replace') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    original = row['1.12_sound'].strip()
                    converted = row['1.20_sound'].strip()
                    conversions[original] = converted
            if not self.silent:
                print(f"Loaded {len(conversions)} sound conversions")
        except Exception as e:
            if not self.silent:
                print(f"Error loading sound conversions: {e}")
        return conversions
    
    def _load_particle_conversions(self, csv_path: str) -> Dict[str, str]:
        """Load particle name conversions from CSV"""
        conversions = {}
        try:
            with open(csv_path, 'r', encoding='utf-8', errors='replace') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    original = row['1.12_particle'].strip()
                    converted = row['1.20_particle'].strip()
                    conversions[original] = converted
            if not self.silent:
                print(f"Loaded {len(conversions)} particle conversions")
        except Exception as e:
            if not self.silent:
                print(f"Error loading particle conversions: {e}")
        return conversions
    
    def _load_legacy_json(self, json_path: str) -> Dict[str, str]:
        """Load legacy block ID:data to new block name mappings from JSON"""
        import json
        import os
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            json_full_path = os.path.join(script_dir, json_path)
            
            with open(json_full_path, 'r', encoding='utf-8', errors='replace') as file:
                data = json.load(file)
                blocks = data.get('blocks', {})
            if not self.silent:
                print(f"Loaded {len(blocks)} legacy block mappings")
            return blocks
        except Exception as e:
            if not self.silent:
                print(f"Error loading legacy JSON: {e}")
            return {}
    
    def _build_block_name_to_id_map(self, csv_path: str) -> Dict[str, str]:
        """Build a reverse lookup map from block name to block ID"""
        name_to_id = {}
        try:
            import os
            script_dir = os.path.dirname(os.path.abspath(__file__))
            csv_full_path = os.path.join(script_dir, csv_path)
            
            with open(csv_full_path, 'r', encoding='utf-8', errors='replace') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    try:
                        block_id = row['id'].strip()
                        block_name = row['block'].strip()
                        raw_block_name = row['raw_block'].strip()
                        
                        # Map block name to ID (use first occurrence, but prefer block column over raw_block)
                        if block_name:
                            block_name_lower = block_name.lower()
                            if block_name_lower not in name_to_id:
                                name_to_id[block_name_lower] = block_id
                            # Also store without minecraft: prefix if present
                            if block_name_lower.startswith('minecraft:'):
                                name_to_id[block_name_lower[10:]] = block_id
                        
                        if raw_block_name:
                            raw_block_name_lower = raw_block_name.lower()
                            if raw_block_name_lower not in name_to_id:
                                name_to_id[raw_block_name_lower] = block_id
                            # Also store without minecraft: prefix if present
                            if raw_block_name_lower.startswith('minecraft:'):
                                name_to_id[raw_block_name_lower[10:]] = block_id
                    except (ValueError, KeyError):
                        continue
        except Exception as e:
            if not self.silent:
                print(f"Error building block name to ID map: {e}")
        return name_to_id

class ParameterConverters:
    """Individual parameter conversion functions"""
    
    def __init__(self, lookups: LookupTables):
        self.lookups = lookups
        # Initialize NBT converter registry
        self.nbt_registry = NBTConverterRegistry()
        self._register_nbt_converters()
    
    def _register_nbt_converters(self):
        """Register all NBT component converters - extensible system"""
        # Equipment converter (ArmorItems/HandItems -> equipment)
        self.nbt_registry.register('ArmorItems', self._convert_armor_items_component)
        self.nbt_registry.register('HandItems', self._convert_hand_items_component)
        # Drop chances converter
        self.nbt_registry.register('ArmorDropChances', self._convert_armor_drop_chances_component)
        self.nbt_registry.register('HandDropChances', self._convert_hand_drop_chances_component)
        # CustomName converter (must be JSON format in 1.21.10)
        self.nbt_registry.register('CustomName', self._convert_custom_name_nbt)
        # Inventory converter (processes items in Inventory arrays)
        try:
            self.nbt_registry.register('Inventory', self._convert_inventory_array)
            import sys
            print(f"DEBUG: Successfully registered Inventory converter", file=sys.stderr)
        except Exception as e:
            import sys
            print(f"DEBUG: ERROR registering Inventory converter: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
        
        # SelectedItem converter (processes single item, similar to Inventory)
        try:
            self.nbt_registry.register('SelectedItem', self._convert_selected_item)
            import sys
            print(f"DEBUG: Successfully registered SelectedItem converter", file=sys.stderr)
        except Exception as e:
            import sys
            print(f"DEBUG: ERROR registering SelectedItem converter: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
        
        # Debug: Verify registration
        import sys
        print(f"DEBUG ParameterConverters._register_nbt_converters: Registered = {list(self.nbt_registry.converters.keys())}", file=sys.stderr)
        
    def _convert_inventory_array(self, nbt_dict: Dict[str, Any], context: str = "entity") -> Dict[str, Any]:
        """Convert Inventory array - processes each item in the array to component format"""
        # Debug: Check if Inventory exists
        if 'Inventory' not in nbt_dict:
            return nbt_dict
        
        inventory = nbt_dict.get('Inventory')
        if isinstance(inventory, list):
            converted_inventory = []
            for item in inventory:
                if isinstance(item, dict):
                    # Debug: Print item structure
                    import sys
                    print(f"DEBUG _convert_inventory_array: item keys = {list(item.keys())}", file=sys.stderr)
                    if 'tag' in item:
                        print(f"DEBUG: item['tag'] type = {type(item['tag'])}, value = {item.get('tag')}", file=sys.stderr)
                    
                    # Convert item using the same logic as equipment items
                    # This should convert display:{Name:...,Lore:...} to components:{minecraft:custom_name:...,minecraft:lore:...}
                    # IMPORTANT: The item dict should have 'id' and 'tag' keys from the parsed NBT
                    # If it doesn't, something went wrong with parsing
                    print(f"DEBUG _convert_inventory_array: Processing item = {item}", file=sys.stderr)
                    converted_item = self._convert_item_dict_to_121_format(item)
                    if converted_item:
                        print(f"DEBUG: converted_item = {converted_item}", file=sys.stderr)
                        # Ensure components are present and tag is removed
                        if 'components' in converted_item and converted_item['components']:
                            # Flatten lore arrays for entity NBT (Inventory/SelectedItem always use flat arrays)
                            if 'minecraft:lore' in converted_item['components']:
                                lore = converted_item['components']['minecraft:lore']
                                if isinstance(lore, list):
                                    # Flatten nested arrays: [[{...}],[{...}]] -> [{...},{...}]
                                    flattened_lore = []
                                    for lore_entry in lore:
                                        if isinstance(lore_entry, list):
                                            # If it's a nested array, extract the components
                                            flattened_lore.extend(lore_entry)
                                        else:
                                            # If it's already a single object, add it
                                            flattened_lore.append(lore_entry)
                                    converted_item['components']['minecraft:lore'] = flattened_lore
                            
                            # Remove tag field if present (components replace tag)
                            if 'tag' in converted_item:
                                del converted_item['tag']
                            # Also remove any remaining display or other old fields
                            if 'display' in converted_item:
                                del converted_item['display']
                            # Preserve other fields like id, count, Slot from the ORIGINAL item
                            # This is critical - the converted_item might not have id if it wasn't in the item_dict
                            for key in ['id', 'count', 'Slot']:
                                if key in item and key not in converted_item:
                                    converted_item[key] = item[key]
                            print(f"DEBUG: Final converted_item after preserving keys = {converted_item}", file=sys.stderr)
                        else:
                            # No components were created - this shouldn't happen if display was found
                            print(f"DEBUG WARNING: No components in converted_item! item = {item}", file=sys.stderr)
                        converted_inventory.append(converted_item)
                    else:
                        print(f"DEBUG: _convert_item_dict_to_121_format returned None", file=sys.stderr)
                        # Conversion failed - this shouldn't happen, but keep original
                        converted_inventory.append(item)
                else:
                    converted_inventory.append(item)  # Keep non-dict items as-is
            nbt_dict['Inventory'] = converted_inventory
        
        return nbt_dict
    
    def _convert_selected_item(self, nbt_dict: Dict[str, Any], context: str = "entity") -> Dict[str, Any]:
        """Convert SelectedItem - processes single item to component format (similar to Inventory but no array)"""
        if 'SelectedItem' not in nbt_dict:
            return nbt_dict
        
        selected_item = nbt_dict.get('SelectedItem')
        if isinstance(selected_item, dict):
            # Convert item using the same logic as Inventory items
            converted_item = self._convert_item_dict_to_121_format(selected_item)
            if converted_item:
                # Ensure components are present and tag is removed
                if 'components' in converted_item and converted_item['components']:
                    # Flatten lore arrays for entity NBT (Inventory/SelectedItem always use flat arrays)
                    if 'minecraft:lore' in converted_item['components']:
                        lore = converted_item['components']['minecraft:lore']
                        if isinstance(lore, list):
                            # Flatten nested arrays: [[{...}],[{...}]] -> [{...},{...}]
                            flattened_lore = []
                            for lore_entry in lore:
                                if isinstance(lore_entry, list):
                                    # If it's a nested array, extract the components
                                    flattened_lore.extend(lore_entry)
                                else:
                                    # If it's already a single object, add it
                                    flattened_lore.append(lore_entry)
                            # Remove empty lore entries (text is empty string)
                            flattened_lore = [entry for entry in flattened_lore if not (isinstance(entry, dict) and entry.get('text') == '' and not any(k != 'text' and k != 'italic' for k in entry.keys()))]
                            # Reorder keys in each lore entry: color, italic, text
                            def reorder_lore_keys(entry):
                                if isinstance(entry, dict):
                                    ordered = {}
                                    key_order = ["color", "italic", "text"]
                                    for key in key_order:
                                        if key in entry:
                                            ordered[key] = entry[key]
                                    for key, value in entry.items():
                                        if key not in key_order:
                                            ordered[key] = value
                                    return ordered
                                return entry
                            flattened_lore = [reorder_lore_keys(entry) for entry in flattened_lore]
                            converted_item['components']['minecraft:lore'] = flattened_lore
                    
                    # Remove tag field if present (components replace tag)
                    if 'tag' in converted_item:
                        del converted_item['tag']
                    # Also remove any remaining display or other old fields
                    if 'display' in converted_item:
                        del converted_item['display']
                    # Ensure count is present (default to 1 if not specified)
                    if 'count' not in converted_item:
                        converted_item['count'] = 1
                nbt_dict['SelectedItem'] = converted_item
        
        return nbt_dict
    
    def convert_coordinate(self, coord: str) -> str:
        """Convert coordinates to modern format (~1 → ~1.0)"""
        if not coord.startswith('~'):
            return coord
        num = coord[1:] or '0'
        try:
            if '.' in num:
                return f'~{float(num)}'
            return f'~{int(num)}' if num != '0' else '~'
        except ValueError:
            return coord
    
    def convert_entity_name(self, entity_name: str) -> str:
        """Convert entity names using lookup table"""
        # Remove minecraft: prefix if present for lookup
        clean_name = entity_name.replace('minecraft:', '')
        converted = self.lookups.entity_conversions.get(clean_name, entity_name)
        
        # Add minecraft: prefix if not present
        if not converted.startswith('minecraft:') and ':' not in converted:
            converted = f'minecraft:{converted}'
            
        return converted
    
    def convert_block_name(self, block_name: str, data_value: str = '0') -> str:
        """Convert block names using lookup table"""
        try:
            # Strip quotes if present
            block_name = block_name.strip('"').strip("'")
            data_int = int(data_value) if data_value != '-1' else 0
            
            # Try lookup with original block name
            lookup_key = (block_name, data_int)
            converted = self.lookups.block_conversions.get(lookup_key)
            if converted:
                # Add minecraft: prefix if not already present and not a coordinate
                if not converted.startswith('minecraft:') and not any(char in converted for char in '~^'):
                    converted = f"minecraft:{converted}"
                return converted
            
            # Try with minecraft: prefix if not already present
            if not block_name.startswith('minecraft:'):
                lookup_key = (f"minecraft:{block_name}", data_int)
                converted = self.lookups.block_conversions.get(lookup_key)
                if converted:
                    if not converted.startswith('minecraft:') and not any(char in converted for char in '~^'):
                        converted = f"minecraft:{converted}"
                    return converted
            
            # If not found, return original with minecraft: prefix
            if not block_name.startswith('minecraft:') and not any(char in block_name for char in '~^'):
                return f"minecraft:{block_name}"
            return block_name
        except ValueError:
            # Add minecraft: prefix if not already present and not a coordinate
            block_name = block_name.strip('"').strip("'")
            if not block_name.startswith('minecraft:') and not any(char in block_name for char in '~^'):
                return f"minecraft:{block_name}"
            return block_name
    
    def convert_block_name_legacy(self, block_name: str, data_value: str = '0') -> str:
        """Convert block names using legacy.json (for project/clock/script commands)
        
        Flow:
        1. Look up block name -> ID in ID_Lookups.csv (via block_name_to_id map)
        2. Use legacy.json with "id:data" format to get new block name
        """
        try:
            # Strip quotes if present
            block_name = block_name.strip('"').strip("'")
            data_int = int(data_value) if data_value != '-1' else 0
            
            # Step 1: Look up block name -> ID
            block_name_lower = block_name.lower()
            block_id = self.lookups.block_name_to_id.get(block_name_lower)
            
            if not block_id:
                # Try with minecraft: prefix removed
                if block_name_lower.startswith('minecraft:'):
                    block_name_lower = block_name_lower[10:]
                    block_id = self.lookups.block_name_to_id.get(block_name_lower)
            
            if not block_id:
                # Fallback: try direct lookup in block_conversions to find ID
                # This is a reverse lookup - find any entry with this block name
                for (key, data), converted in self.lookups.block_conversions.items():
                    if isinstance(key, str) and key.lower() == block_name_lower and data == data_int:
                        # Found a match, but we need the ID
                        # Try to find the ID by looking at the CSV structure
                        # For now, return the converted name directly
                        return converted
                
                # If still not found, return original with minecraft: prefix
                if not block_name.startswith('minecraft:') and not any(char in block_name for char in '~^'):
                    return f"minecraft:{block_name}"
                return block_name
            
            # Step 2: Use legacy.json with "id:data" format
            legacy_key = f"{block_id}:{data_int}"
            converted = self.lookups.legacy_blocks.get(legacy_key)
            
            if converted:
                return converted
            
            # Fallback: if not in legacy.json, try regular conversion
            return self.convert_block_name(block_name, data_value)
            
        except ValueError:
            # Add minecraft: prefix if not already present and not a coordinate
            block_name = block_name.strip('"').strip("'")
            if not block_name.startswith('minecraft:') and not any(char in block_name for char in '~^'):
                return f"minecraft:{block_name}"
            return block_name
    
    def convert_selector(self, selector: str) -> str:
        """Convert target selectors to modern format"""
        if not selector.startswith('@'):
            return selector
            
        # Handle @[type=...] format (1.12 style)
        if selector.startswith('@['):
            return self._convert_old_selector(selector)
        
        # Handle @r without parameters - convert to @e[sort=random]
        if selector == '@r':
            return '@e[sort=random]'
            
        # Handle @e[type=...] format
        if '[' not in selector:
            return selector
            
        prefix, params = selector[1:].split('[', 1)
        params = params.rstrip(']')
        
        converted_params = []
        scores_dict = {}  # Collect all score parameters
        distance_min = None
        distance_max = None
        x_rotation_min = None
        x_rotation_max = None
        y_rotation_min = None
        y_rotation_max = None
        
        for param in params.split(','):
            param = param.strip()
            if '=' not in param:
                continue
                
            key, value = param.split('=', 1)
            key = key.strip()
            value = value.strip()

            # Add .5 to integer x/y/z values (not floats, not ~)
            if key in ['x', 'y', 'z']:
                if value.lstrip('-').isdigit():
                    value = str(float(value) + 0.5)
            
            # Convert specific parameters
            if key == 'type':
                value = self.convert_entity_name(value)
                converted_params.append(f"{key}={value}")
            elif key == 'r':
                # Maximum distance
                distance_max = value
            elif key == 'rm':
                # Minimum distance
                distance_min = value
            elif key == 'distance':
                # Handle existing distance parameter
                if value.startswith('..'):
                    # Maximum distance only
                    distance_max = value[2:]
                elif value.endswith('..'):
                    # Minimum distance only
                    distance_min = value[:-2]
                elif '..' in value:
                    # Range already specified
                    converted_params.append(f"{key}={value}")
                else:
                    # Exact distance
                    converted_params.append(f"{key}={value}")
            elif key == 'c':
                limit = abs(int(value))
                # Determine sort based on selector type and value
                if prefix == 'r':
                    # @r selector should use random sort
                    sort = 'random'
                else:
                    # Other selectors use nearest/furthest based on value
                    sort = 'furthest' if value.startswith('-') else 'nearest'
                converted_params.extend([f"limit={limit}", f"sort={sort}"])
            elif key == 'm':
                # Convert m= to gamemode=
                gamemode_map = {
                    '0': 'survival', '1': 'creative', 
                    '2': 'adventure', '3': 'spectator',
                    's': 'survival', 'c': 'creative', 
                    'a': 'adventure', 'sp': 'spectator'
                }
                value = gamemode_map.get(value.lower(), value)
                converted_params.append(f"gamemode={value}")
            elif key == 'nbt':
                # Convert NBT parameter to modern format
                value = self.convert_entity_nbt(value)
                converted_params.append(f"{key}={value}")
            elif key.startswith('score_'):
                # Collect score parameters to combine later
                objective = key[6:]  # Remove 'score_' prefix
                scores_dict[objective] = value
            elif key in ['rx', 'rxm', 'ry', 'rym']:
                # Handle rotation parameters - collect them to combine later
                if key == 'rx':
                    x_rotation_max = value
                elif key == 'rxm':
                    x_rotation_min = value
                elif key == 'ry':
                    y_rotation_max = value
                elif key == 'rym':
                    y_rotation_min = value
            else:
                # Handle other parameters
                converted_params.append(f"{key}={value}")
        
        # Combine distance parameters
        if distance_min is not None and distance_max is not None:
            # Check if rm (minimum) is actually greater than r (maximum)
            # This handles cases where people accidentally used rm as radius maximum
            try:
                min_val = float(distance_min)
                max_val = float(distance_max)
                if min_val > max_val:
                    # Swap them so smaller number comes first
                    distance_min, distance_max = distance_max, distance_min
            except ValueError:
                # If we can't parse as numbers, keep original order
                pass
            converted_params.append(f"distance={distance_min}..{distance_max}")
        elif distance_min is not None:
            converted_params.append(f"distance={distance_min}..")
        elif distance_max is not None:
            converted_params.append(f"distance=..{distance_max}")
        
        # Add combined scores parameter if we have any
        if scores_dict:
            scores_str = ','.join([f"{obj}={val}" for obj, val in scores_dict.items()])
            converted_params.append(f"scores={{{scores_str}}}")
        
        # Combine rotation parameters
        if x_rotation_min is not None or x_rotation_max is not None:
            if x_rotation_min is not None and x_rotation_max is not None:
                converted_params.append(f"x_rotation={x_rotation_min}..{x_rotation_max}")
            elif x_rotation_min is not None:
                converted_params.append(f"x_rotation={x_rotation_min}..")
            elif x_rotation_max is not None:
                converted_params.append(f"x_rotation=..{x_rotation_max}")
        
        if y_rotation_min is not None or y_rotation_max is not None:
            if y_rotation_min is not None and y_rotation_max is not None:
                converted_params.append(f"y_rotation={y_rotation_min}..{y_rotation_max}")
            elif y_rotation_min is not None:
                converted_params.append(f"y_rotation={y_rotation_min}..")
            elif y_rotation_max is not None:
                converted_params.append(f"y_rotation=..{y_rotation_max}")
        
        # Handle @r selector change (now only selects players, not all entities)
        # Convert @r to @e[sort=random] to maintain entity selection behavior
        if prefix == 'r':
            # @r now only selects random players, not all entities
            # Convert to @e with sort=random to select random entities (1.12 behavior)
            prefix = 'e'
            # Always add sort=random for @r conversion
            if 'sort=random' not in converted_params:
                converted_params.append('sort=random')
        
        if not converted_params:
            return f'@{prefix}'
            
        return f'@{prefix}[{",".join(converted_params)}]'
    
    def _convert_old_selector(self, selector: str) -> str:
        """Convert @[type=...] format to @e[type=...]"""
        if not selector.startswith('@['):
            return selector
            
        params = selector[2:-1]  # Remove @[ and ]
        
        # Find type parameter
        type_match = re.search(r'type=([^,\]]+)', params)
        if type_match:
            entity_type = type_match.group(1)
            converted_type = self.convert_entity_name(entity_type)
            
            # Replace type parameter
            params = re.sub(r'type=[^,\]]+', f'type={converted_type}', params)
            
            return f'@e[{params}]'
        
        return f'@e[{params}]'
    
    @log_method_call
    def _convert_armor_items_component(self, nbt_dict: Dict[str, Any], context: str) -> Dict[str, Any]:
        """Convert ArmorItems array to equipment structure"""
        if 'ArmorItems' not in nbt_dict:
            return nbt_dict
        
        armor_items = nbt_dict['ArmorItems']
        if not isinstance(armor_items, list):
            return nbt_dict
        
        # Initialize equipment if not present
        if 'equipment' not in nbt_dict:
            nbt_dict['equipment'] = {}
        
        # Map armor slots: [feet, legs, chest, head]
        slot_names = ['feet', 'legs', 'chest', 'head']
        for i, item in enumerate(armor_items):
            if i < len(slot_names) and item and isinstance(item, dict):
                slot = slot_names[i]
                converted_item = self._convert_item_dict_to_121_format(item)
                if converted_item:
                    nbt_dict['equipment'][slot] = converted_item
        
        # Remove old ArmorItems
        del nbt_dict['ArmorItems']
        return nbt_dict
    
    @log_method_call
    def _convert_hand_items_component(self, nbt_dict: Dict[str, Any], context: str) -> Dict[str, Any]:
        """Convert HandItems array to equipment structure"""
        if 'HandItems' not in nbt_dict:
            return nbt_dict
        
        hand_items = nbt_dict['HandItems']
        if not isinstance(hand_items, list):
            return nbt_dict
        
        # Initialize equipment if not present
        if 'equipment' not in nbt_dict:
            nbt_dict['equipment'] = {}
        
        # Map hand slots: [mainhand, offhand]
        slot_names = ['mainhand', 'offhand']
        
        # Special case: if HandItems[0] is empty and HandItems[1] has an item,
        # put HandItems[1] in mainhand
        if len(hand_items) >= 2:
            if (not hand_items[0] or (isinstance(hand_items[0], dict) and not hand_items[0])) and \
               hand_items[1] and isinstance(hand_items[1], dict):
                converted_item = self._convert_item_dict_to_121_format(hand_items[1])
                if converted_item:
                    nbt_dict['equipment']['mainhand'] = converted_item
            else:
                # Normal case: map items to their slots
                for i, item in enumerate(hand_items):
                    if i < len(slot_names) and item and isinstance(item, dict):
                        slot = slot_names[i]
                        converted_item = self._convert_item_dict_to_121_format(item)
                        if converted_item:
                            nbt_dict['equipment'][slot] = converted_item
        else:
            # Single item or empty
            for i, item in enumerate(hand_items):
                if i < len(slot_names) and item and isinstance(item, dict):
                    slot = slot_names[i]
                    converted_item = self._convert_item_dict_to_121_format(item)
                    if converted_item:
                        nbt_dict['equipment'][slot] = converted_item
        
        # Remove old HandItems
        del nbt_dict['HandItems']
        return nbt_dict
    
    def _convert_armor_drop_chances_component(self, nbt_dict: Dict[str, Any], context: str) -> Dict[str, Any]:
        """Convert ArmorDropChances to drop_chances structure"""
        if 'ArmorDropChances' not in nbt_dict:
            return nbt_dict
        
        armor_drops = nbt_dict['ArmorDropChances']
        if not isinstance(armor_drops, list):
            return nbt_dict
        
        # Initialize drop_chances if not present
        if 'drop_chances' not in nbt_dict:
            nbt_dict['drop_chances'] = {}
        
        # Map armor slots: [feet, legs, chest, head]
        slot_names = ['feet', 'legs', 'chest', 'head']
        for i, chance in enumerate(armor_drops):
            if i < len(slot_names):
                slot = slot_names[i]
                nbt_dict['drop_chances'][slot] = float(chance) if chance is not None else 0.0
        
        # Ensure all armor slots are present (fill missing with 0.000)
        for slot in slot_names:
            if slot not in nbt_dict['drop_chances']:
                nbt_dict['drop_chances'][slot] = 0.0
        
        # Ensure all equipment slots are present in drop_chances (fill missing with 0.000)
        all_slots = ['feet', 'legs', 'chest', 'head', 'mainhand', 'offhand']
        for slot in all_slots:
            if slot not in nbt_dict.get('drop_chances', {}):
                if 'drop_chances' not in nbt_dict:
                    nbt_dict['drop_chances'] = {}
                nbt_dict['drop_chances'][slot] = 0.0
        
        # Remove old ArmorDropChances
        del nbt_dict['ArmorDropChances']
        return nbt_dict
    
    def _convert_hand_drop_chances_component(self, nbt_dict: Dict[str, Any], context: str) -> Dict[str, Any]:
        """Convert HandDropChances to drop_chances structure"""
        if 'HandDropChances' not in nbt_dict:
            return nbt_dict
        
        hand_drops = nbt_dict['HandDropChances']
        if not isinstance(hand_drops, list):
            return nbt_dict
        
        # Initialize drop_chances if not present
        if 'drop_chances' not in nbt_dict:
            nbt_dict['drop_chances'] = {}
        
        # Map hand slots: [mainhand, offhand]
        slot_names = ['mainhand', 'offhand']
        for i, chance in enumerate(hand_drops):
            if i < len(slot_names):
                slot = slot_names[i]
                nbt_dict['drop_chances'][slot] = float(chance) if chance is not None else 0.0
        
        # Ensure all hand slots are present (fill missing with 0.000)
        for slot in slot_names:
            if slot not in nbt_dict['drop_chances']:
                nbt_dict['drop_chances'][slot] = 0.0
        
        # Ensure all equipment slots are present in drop_chances (fill missing with 0.000)
        all_slots = ['feet', 'legs', 'chest', 'head', 'mainhand', 'offhand']
        for slot in all_slots:
            if slot not in nbt_dict.get('drop_chances', {}):
                if 'drop_chances' not in nbt_dict:
                    nbt_dict['drop_chances'] = {}
                nbt_dict['drop_chances'][slot] = 0.0
        
        # Remove old HandDropChances
        del nbt_dict['HandDropChances']
        return nbt_dict
    
    def _convert_item_dict_to_121_format(self, item_dict: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Convert item dict from 1.12 format to 1.21.10 equipment format
        
        Input: {id:"minecraft:golden_axe",Count:1,tag:{ench:[{id:35,lvl:1}]}}
        Output: {id:"minecraft:golden_axe",count:1,components:{"minecraft:enchantments":[...]}}
        
        For give commands, the NBT might not have an 'id' field (item ID is separate),
        so we allow conversion without 'id' field.
        """
        if not isinstance(item_dict, dict):
            return None
        
        # Debug
        import sys
        print(f"DEBUG _convert_item_dict_to_121_format: item_dict = {item_dict}", file=sys.stderr)
        
        # For give commands, NBT might not have 'id' field - create a minimal result dict
        result = {}
        
        # Convert id (ensure namespaced) - only if present
        if 'id' in item_dict:
            item_id = item_dict.get('id', '')
            if ':' not in item_id:
                item_id = f'minecraft:{item_id}'
            result['id'] = item_id
            
            # Handle skull items with Damage -> convert to specific head type
            damage = item_dict.get('Damage')
            if damage is not None and (item_id == 'skull' or item_id == 'minecraft:skull'):
                skull_map = {
                    0: 'minecraft:skeleton_skull',
                    1: 'minecraft:wither_skeleton_skull',
                    2: 'minecraft:zombie_head',
                    3: 'minecraft:player_head',
                    4: 'minecraft:creeper_head',
                    5: 'minecraft:dragon_head'
                }
                new_id = skull_map.get(int(damage))
                if new_id:
                    result['id'] = new_id
        
        # Convert Count to count - only if present
        if 'Count' in item_dict:
            count = item_dict.get('Count', 1)
            result['count'] = int(count)
        
        # Process tag for components
        components = {}
        tag = item_dict.get('tag', {})
        other_tag_data = {}  # Store non-convertible tag data
        
        # Check for Damage at top level (not in tag) - convert to minecraft:damage component
        if 'Damage' in item_dict:
            damage_value = item_dict['Damage']
            # Convert to integer if it's a string with suffix (e.g., "32s" -> 32)
            if isinstance(damage_value, str):
                damage_value = int(damage_value.rstrip('sSbBlLfFdD'))
            components['minecraft:damage'] = int(damage_value)
        
        # Handle display - it can be at top level OR inside tag
        # For entity NBT (Inventory/SelectedItem), display is usually in tag:{display:{...}}
        # For give commands, display might be at top level
        display = item_dict.get('display', {})
        if not display and isinstance(tag, dict):
            display = tag.get('display', {})
        
        # Debug: Check what we found
        import sys
        if display:
            print(f"DEBUG: Found display = {display}", file=sys.stderr)
            print(f"DEBUG: display type = {type(display)}", file=sys.stderr)
            if isinstance(display, dict) and 'Name' in display:
                print(f"DEBUG: display['Name'] = {display.get('Name')}", file=sys.stderr)
        
        if isinstance(display, dict):
            # Convert display:{color:...} -> minecraft:dyed_color
            if 'color' in display:
                components['minecraft:dyed_color'] = int(display['color'])
            
            # Convert display:{Name:...} -> minecraft:custom_name (for entity NBT) or minecraft:item_name (for give commands)
            # Note: For give commands, the prefix is stripped in convert_item_nbt, so we use minecraft:custom_name here
            if 'Name' in display:
                name_value = display['Name']
                # Convert to JSON text component (preserve color codes)
                import re
                if '§' in str(name_value):
                    # Has color codes, convert to JSON
                    name_json = self._convert_plain_text_to_json(str(name_value))
                    import json
                    parsed_name = json.loads(name_json)
                    # For single-component names, use the object directly; for multi-component, use array
                    if isinstance(parsed_name, list) and len(parsed_name) == 1:
                        components['minecraft:custom_name'] = parsed_name[0]
                    else:
                        components['minecraft:custom_name'] = parsed_name
                else:
                    # Plain text, use as string
                    components['minecraft:custom_name'] = str(name_value)
            
            # Convert display:{Lore:[...]} -> minecraft:lore
            # For entity NBT, lore should be a flat array of objects, not nested arrays
            # For give commands with namespaced items, lore should be nested arrays [[{...}],[{...}]]
            # Note: We don't know the context here, so we keep nested arrays and let convert_item_nbt decide
            if 'Lore' in display:
                lore_list = display['Lore']
                if isinstance(lore_list, list):
                    converted_lore = self._convert_lore_list_to_121(lore_list)
                    if converted_lore:
                        # Keep nested arrays as-is - convert_item_nbt will flatten if needed for non-namespaced items
                        components['minecraft:lore'] = converted_lore
        
        if isinstance(tag, dict):
            # Convert enchantments
            if 'ench' in tag:
                ench_list = tag['ench']
                if isinstance(ench_list, list):
                    converted_ench = self._convert_enchantments_list(ench_list)
                    if converted_ench:
                        components['minecraft:enchantments'] = converted_ench
            
            # Convert SkullOwner -> minecraft:profile
            if 'SkullOwner' in tag:
                skull_owner = tag['SkullOwner']
                if isinstance(skull_owner, dict):
                    profile = self._convert_skull_owner_to_profile(skull_owner)
                    if profile:
                        components['minecraft:profile'] = profile
            
            # Convert Damage to minecraft:damage component
            if 'Damage' in tag:
                damage_value = tag['Damage']
                # Convert to integer if it's a string with suffix (e.g., "32s" -> 32)
                if isinstance(damage_value, str):
                    damage_value = int(damage_value.rstrip('sSbBlLfFdD'))
                components['minecraft:damage'] = int(damage_value)
            
            # Check for other tag data that should be preserved
            # In 1.21.9+, Damage is deprecated but might still be present
            # Other custom data should go to minecraft:custom_data component
            for key, value in tag.items():
                if key not in ['display', 'ench', 'SkullOwner', 'Damage']:
                    # Preserve other tag data (like custom plugin data, etc.)
                    # These should go to custom_data component if components are used
                    if key not in other_tag_data:
                        other_tag_data[key] = value
        
        # Add components if any
        if components:
            result['components'] = components
            # In 1.21.9+, when components are present, tag should be removed
            # Remove tag field from result since all data is now in components
            if 'tag' in result:
                del result['tag']
            # Also remove display if it's at top level (should be in components now)
            if 'display' in result:
                del result['display']
        
        # Debug: Check what we're returning
        import sys
        print(f"DEBUG _convert_item_dict_to_121_format: result keys = {list(result.keys())}", file=sys.stderr)
        if 'components' in result:
            print(f"DEBUG: result['components'] = {result['components']}", file=sys.stderr)
        
        # If no components were added but we have other data, still return the result
        # This ensures items without display data are still preserved
        if result:
            return result
        
        # If result is empty, return None to indicate conversion failed
        return None
    
    def _convert_enchantments_list(self, ench_list: List[Dict[str, Any]]) -> Optional[List[Dict[str, Any]]]:
        """Convert enchantment list from 1.12 format to 1.21 format"""
        enchantment_map = {
            0: 'protection', 1: 'fire_protection', 2: 'feather_falling',
            3: 'blast_protection', 4: 'projectile_protection', 5: 'respiration',
            6: 'aqua_affinity', 7: 'thorns', 8: 'depth_strider',
            9: 'frost_walker', 10: 'binding_curse',
            16: 'sharpness', 17: 'smite', 18: 'bane_of_arthropods',
            19: 'knockback', 20: 'fire_aspect', 21: 'looting',
            22: 'sweeping', 32: 'efficiency', 33: 'silk_touch',
            34: 'unbreaking', 35: 'fortune', 48: 'power',
            49: 'punch', 50: 'flame', 51: 'infinity',
            61: 'luck_of_the_sea', 62: 'lure',
            70: 'mending', 71: 'vanishing_curse'
        }
        
        result = []
        for ench in ench_list:
            if isinstance(ench, dict):
                ench_id = ench.get('id')
                if isinstance(ench_id, int):
                    ench_name = enchantment_map.get(ench_id, 'protection')
                    level = ench.get('lvl', 1)
                    result.append({
                        'id': f'minecraft:{ench_name}',
                        'lvl': int(level)
                    })
        
        return result if result else None
    
    def _convert_lore_list_to_121(self, lore_list: List[str]) -> Optional[List[Any]]:
        """Convert lore list to 1.21 format: [{...},[{...}],{...}]
        
        Format: Flat array where:
        - Single-component lines are objects: {"color":"gold","text":"Right Click","italic":false}
        - Multi-component lines are arrays: [{"color":"gray","text":"Open the "},{"color":"white","text":"Portsmouth"}]
        - Empty lines are objects: {"text":"","italic":false}
        
        Note: In 1.21.10, lore is italicized by default, so we must add "italic":false
        unless the text has §o (italic formatting code).
        """
        import re
        import json
        
        result = []
        for lore_line in lore_list:
            if isinstance(lore_line, str):
                # Check if text has italic formatting code (§o)
                has_italic_code = '§o' in lore_line or '§O' in lore_line
                
                # Convert color codes to JSON components
                if '§' in lore_line:
                    components = self._parse_color_codes_to_components(lore_line)
                    # Add italic:false to components that don't have italic formatting
                    # Only remove italic:false if the component explicitly has italic:true
                    for comp in components:
                        # If component doesn't have italic property and text doesn't have §o, add italic:false
                        if 'italic' not in comp and not has_italic_code:
                            comp['italic'] = False
                        # If component has italic:false and text has §o, it should be italic:true (handled by parser)
                        # If component has italic:false and text doesn't have §o, keep it
                    # All lore lines should be wrapped in arrays (even single components)
                    if len(components) == 1:
                        result.append(components)  # Wrap single component in array
                    elif len(components) > 1:
                        result.append(components)
                    else:
                        result.append([{"text": "", "italic": False}])  # Wrap empty in array
                elif lore_line.strip():
                    # Plain text - single component wrapped in array
                    result.append([{"text": lore_line, "italic": False}])
                else:
                    # Empty line - single component wrapped in array
                    result.append([{"text": "", "italic": False}])
            else:
                result.append({"text": "", "italic": False})
        
        return result if result else None
    
    def _parse_color_codes_to_components(self, text: str) -> List[Dict[str, Any]]:
        """Parse text with color codes into JSON text components
        
        Returns list of components. Adds italic:false by default unless §o is present.
        In 1.21.10, lore is italicized by default, so we must explicitly set italic:false.
        """
        import re
        
        color_map = {
            '0': 'black', '1': 'dark_blue', '2': 'dark_green', '3': 'dark_aqua',
            '4': 'dark_red', '5': 'dark_purple', '6': 'gold', '7': 'gray',
            '8': 'dark_gray', '9': 'blue', 'a': 'green', 'b': 'aqua',
            'c': 'red', 'd': 'light_purple', 'e': 'yellow', 'f': 'white'
        }
        
        # Track if any part of the text has italic formatting
        has_italic_in_text = '§o' in text or '§O' in text
        
        parts = re.split(r'(§[0-9a-frlomn])', text)
        components = []
        current_text = ""
        current_formatting = {}
        has_italic_formatting = False  # Track if current formatting has italic
        
        for part in parts:
            if part.startswith('§'):
                # Color code - save current text if any
                if current_text:
                    comp = current_formatting.copy()
                    comp["text"] = current_text
                    # Add italic:false if not explicitly set to true
                    if 'italic' not in comp:
                        comp['italic'] = False
                    components.append(comp)
                    current_text = ""
                
                code = part[1].lower()
                if code in color_map:
                    # Color code resets formatting, start fresh
                    current_formatting = {"color": color_map[code], "italic": False}
                    has_italic_formatting = False
                elif code == 'r':
                    # Reset - clear all formatting
                    current_formatting = {"italic": False}
                    has_italic_formatting = False
                elif code == 'o':
                    # Italic formatting - set italic to true
                    current_formatting["italic"] = True
                    has_italic_formatting = True
            else:
                current_text += part
        
        # Add remaining text (or empty component if formatting was set but no text)
        if current_text:
            comp = current_formatting.copy()
            comp["text"] = current_text
            # Add italic:false if not explicitly set to true
            if 'italic' not in comp:
                comp['italic'] = False
            components.append(comp)
        elif components and current_formatting:
            # No remaining text but we have formatting - add empty component
            # This handles cases where the string ends with a color code (e.g., "§eGate Stone§7")
            comp = current_formatting.copy()
            comp["text"] = ""
            if 'italic' not in comp:
                comp['italic'] = False
            components.append(comp)
        
        # If no components, return empty text with italic:false
        if not components:
            return [{"text": "", "italic": False}]
        
        return components
    
    def _convert_skull_owner_to_profile(self, skull_owner: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Convert SkullOwner to minecraft:profile component"""
        properties = skull_owner.get('Properties', {})
        if isinstance(properties, dict):
            textures = properties.get('textures', [])
            if isinstance(textures, list) and textures:
                texture_obj = textures[0] if isinstance(textures[0], dict) else {}
                value = texture_obj.get('Value', '')
                if value:
                    return {
                        "properties": [{
                            "name": "textures",
                            "value": value
                        }]
                    }
        return None
    
    @log_method_call
    def _convert_custom_name_nbt(self, nbt_dict: Dict[str, Any], context: str) -> Dict[str, Any]:
        """Convert CustomName to JSON format (required in 1.21.10 to avoid crashes)
        
        Converts CustomName from plain string (possibly with § color codes) to JSON format.
        Example: CustomName:"§cGuardian" -> CustomName:{"color":"red","text":"Guardian"}
        """
        if 'CustomName' not in nbt_dict:
            return nbt_dict
        
        custom_name = nbt_dict['CustomName']
        
        # If it's already a dict (JSON format), keep it
        if isinstance(custom_name, dict):
            return nbt_dict
        
        # Convert string to JSON format
        if isinstance(custom_name, str):
            # Remove quotes if present
            name_value = custom_name.strip('"').strip("'")
            
            # Convert color codes to JSON components
            if '§' in name_value:
                components = self._parse_color_codes_to_components(name_value)
                # If single component, use it directly; if multiple, use array format
                if len(components) == 1:
                    nbt_dict['CustomName'] = components[0]
                else:
                    nbt_dict['CustomName'] = components
            else:
                # Plain text without color codes - wrap in JSON
                nbt_dict['CustomName'] = {"text": name_value}
        
        return nbt_dict
    
    def _convert_active_effects_regex(self, nbt: str) -> str:
        """Convert ActiveEffects to active_effects with proper attribute names (regex-based fallback)
        
        1.12: ActiveEffects:[{Id:14b,Amplifier:1b,Duration:2147000,ShowParticles:0b}]
        1.20: active_effects:[{id:invisibility,amplifier:1b,duration:2147000,show_particles:0b}]
        """
        import re
        
        if 'ActiveEffects:' not in nbt:
            return nbt
        
        # Effect ID to name mapping (1.12 numeric IDs to 1.20 names)
        effect_map = {
            '1': 'speed', '2': 'slowness', '3': 'haste', '4': 'mining_fatigue',
            '5': 'strength', '6': 'instant_health', '7': 'instant_damage', '8': 'jump_boost',
            '9': 'nausea', '10': 'regeneration', '11': 'resistance', '12': 'fire_resistance',
            '13': 'water_breathing', '14': 'invisibility', '15': 'blindness', '16': 'night_vision',
            '17': 'hunger', '18': 'weakness', '19': 'poison', '20': 'wither',
            '21': 'health_boost', '22': 'absorption', '23': 'saturation', '24': 'glowing',
            '25': 'levitation', '26': 'luck', '27': 'unluck', '28': 'slow_falling',
            '29': 'conduit_power', '30': 'dolphins_grace', '31': 'bad_omen', '32': 'hero_of_the_village'
        }
        
        # Convert the attribute name
        nbt = re.sub(r'ActiveEffects:', 'active_effects:', nbt)
        
        # Convert effect IDs to names and attribute casing
        def convert_effect_entry(match):
            effect_data = match.group(1)
            
            # Convert Id:<number> or Id:<number>b to id:"minecraft:<effect_name>"
            def convert_id(id_match):
                effect_id = id_match.group(1)
                effect_name = effect_map.get(effect_id, 'speed')  # Default to speed if not found
                return f'id:"minecraft:{effect_name}"'
            
            # Match Id: followed by number with optional 'b' suffix
            effect_data = re.sub(r'Id:(\d+)(?:b)?', convert_id, effect_data)
            
            # Convert CamelCase attributes to snake_case
            # Note: amplifier and show_particles should have 'b' suffix (byte), duration is regular int
            effect_data = re.sub(r'Amplifier:', 'amplifier:', effect_data)
            effect_data = re.sub(r'Duration:', 'duration:', effect_data)
            effect_data = re.sub(r'ShowParticles:', 'show_particles:', effect_data)
            
            # Ensure amplifier and show_particles have 'b' suffix if they're 0 or 1 (byte values)
            # Only add suffix if not already present
            effect_data = re.sub(r'\bamplifier:([01])(?![bBsSlLfFdD])', r'amplifier:\1b', effect_data)
            effect_data = re.sub(r'\bshow_particles:([01])(?![bBsSlLfFdD])', r'show_particles:\1b', effect_data)
            
            return f'{{{effect_data}}}'
        
        # Apply conversion to each effect entry - match Id: followed by number (with or without 'b' suffix)
        nbt = re.sub(r'\{([^{}]*Id:\d+(?:b)?[^{}]*)\}', convert_effect_entry, nbt)
        
        return nbt
    
    def _convert_falling_block_recursive(self, nbt: str) -> str:
        """Recursively convert Block: to BlockState: in NBT (handles Passengers arrays)"""
        import re
        
        # Find all Block: occurrences (including in nested structures like Passengers)
        # Continue until no more Block: entries exist (that aren't already part of BlockState)
        max_iterations = 100  # Safety limit
        iteration = 0
        while 'Block:' in nbt and iteration < max_iterations:
            iteration += 1
            # Find the first occurrence
            block_start = nbt.find('Block:')
            if block_start == -1:
                break
            
            # Check if this Block: is already part of a BlockState (skip if so)
            # Look backwards to see if BlockState: appears before this Block:
            before_block = nbt[:block_start]
            # Check if there's a BlockState:{Name:" pattern that this Block: might be part of
            # We need to check if this Block: is inside a BlockState:{Name:"..."} structure
            if 'BlockState:' in before_block:
                last_blockstate = before_block.rfind('BlockState:')
                # Check the text between BlockState: and Block:
                between = nbt[last_blockstate:block_start]
                # If BlockState:{Name:" appears and there's no closing } before Block:, skip it
                # This Block: is likely part of the BlockState structure
                if 'BlockState:{Name:"' in between or 'BlockState:{Name:\'' in between:
                    # Check if there's a closing brace between BlockState: and Block:
                    # Count braces to see if BlockState is closed
                    brace_count = 0
                    in_quotes = False
                    quote_char = None
                    for i, char in enumerate(between):
                        if char in ['"', "'"] and (i == 0 or between[i-1] != '\\'):
                            if not in_quotes:
                                in_quotes = True
                                quote_char = char
                            elif char == quote_char:
                                in_quotes = False
                                quote_char = None
                        elif not in_quotes:
                            if char == '{':
                                brace_count += 1
                            elif char == '}':
                                brace_count -= 1
                                if brace_count < 0:
                                    # Found closing brace, BlockState is closed
                                    break
                    # If brace_count > 0, BlockState is still open, skip this Block:
                    if brace_count > 0:
                        # Skip this Block: occurrence by replacing it temporarily
                        nbt = nbt[:block_start] + '___SKIP_BLOCK___' + nbt[block_start + 6:]
                        continue
            
            # Find the start of the block name (after 'Block:')
            name_start = block_start + len('Block:')
            
            # Find where the block name ends (comma, closing brace, or end of string)
            # Handle quoted and unquoted block names
            block_name = ''
            name_end = name_start
            
            # Check if it starts with a quote
            if name_start < len(nbt) and nbt[name_start] in ['"', "'"]:
                quote_char = nbt[name_start]
                # Find the matching closing quote
                name_end = name_start + 1
                while name_end < len(nbt):
                    if nbt[name_end] == quote_char and (name_end == name_start + 1 or nbt[name_end - 1] != '\\'):
                        name_end += 1
                        break
                    name_end += 1
                block_name = nbt[name_start:name_end]
            else:
                # Unquoted block name - find the end (comma, closing brace, or whitespace before comma/brace)
                name_end = name_start
                while name_end < len(nbt):
                    char = nbt[name_end]
                    if char in [',', '}', ']']:
                        break
                    name_end += 1
                block_name = nbt[name_start:name_end]
            
            # Extract the actual block name (remove quotes if present)
            block_name_clean = block_name.strip('"').strip("'").strip()
            # Remove minecraft: prefix if present (will be added by convert_block_name if needed)
            if block_name_clean.startswith('minecraft:'):
                block_name_clean = block_name_clean[10:]
            
            # Check if there's a Data: value following this Block:
            # Look for "Data:" after the block name, before the next comma or closing brace
            remaining = nbt[name_end:]
            data_match = re.search(r'^\s*,\s*Data:(\d+)', remaining)
            
            if data_match:
                # Has Data: value
                data_value = data_match.group(1)
                # Convert using the block lookup table
                converted_block = self.convert_block_name(block_name_clean, data_value)
                # Replace Block:<name>,Data:<value> with BlockState:{Name:"..."}
                replacement = f'BlockState:{{Name:"{converted_block}"}}'
                # Calculate the end position including the Data: part
                data_end = name_end + data_match.end()
                nbt = nbt[:block_start] + replacement + nbt[data_end:]
            else:
                # No Data: value, assume Data:0
                # Convert using the block lookup table
                converted_block = self.convert_block_name(block_name_clean, '0')
                # Replace Block:<name> with BlockState:{Name:"..."}
                replacement = f'BlockState:{{Name:"{converted_block}"}}'
                nbt = nbt[:block_start] + replacement + nbt[name_end:]
        
        # Restore any skipped Block: occurrences
        nbt = nbt.replace('___SKIP_BLOCK___', 'Block:')
        
        return nbt
    
    def _convert_active_effects_recursive(self, nbt: str) -> str:
        """Recursively convert ActiveEffects to active_effects in NBT (handles Passengers arrays)"""
        import re
        
        # Find all ActiveEffects: occurrences (including in nested structures like Passengers)
        while 'ActiveEffects:' in nbt:
            # Find the first occurrence
            active_effects_start = nbt.find('ActiveEffects:')
            if active_effects_start == -1:
                break
            
            # Find the start of the array (after 'ActiveEffects:')
            array_start = active_effects_start + len('ActiveEffects:')
            
            # Find the matching bracket for the array
            bracket_start = array_start
            if bracket_start < len(nbt) and nbt[bracket_start] == '[':
                # Find matching closing bracket
                depth = 1
                bracket_end = bracket_start + 1
                in_quotes = False
                quote_char = None
                
                for i in range(bracket_start + 1, len(nbt)):
                    char = nbt[i]
                    if char in ['"', "'"] and (i == 0 or nbt[i-1] != '\\'):
                        if not in_quotes:
                            in_quotes = True
                            quote_char = char
                        elif char == quote_char:
                            in_quotes = False
                            quote_char = None
                    elif not in_quotes:
                        if char == '[':
                            depth += 1
                        elif char == ']':
                            depth -= 1
                            if depth == 0:
                                bracket_end = i
                                break
                
                if bracket_end > bracket_start:
                    # Extract the array content
                    array_content = nbt[bracket_start + 1:bracket_end]
                    
                    # Convert ActiveEffects: to active_effects:
                    nbt = nbt[:active_effects_start] + 'active_effects:' + nbt[array_start:]
                    
                    # Convert effect entries within this array
                    effect_map = {
                        '1': 'speed', '2': 'slowness', '3': 'haste', '4': 'mining_fatigue',
                        '5': 'strength', '6': 'instant_health', '7': 'instant_damage', '8': 'jump_boost',
                        '9': 'nausea', '10': 'regeneration', '11': 'resistance', '12': 'fire_resistance',
                        '13': 'water_breathing', '14': 'invisibility', '15': 'blindness', '16': 'night_vision',
                        '17': 'hunger', '18': 'weakness', '19': 'poison', '20': 'wither',
                        '21': 'health_boost', '22': 'absorption', '23': 'saturation', '24': 'glowing',
                        '25': 'levitation', '26': 'luck', '27': 'unluck', '28': 'slow_falling',
                        '29': 'conduit_power', '30': 'dolphins_grace', '31': 'bad_omen', '32': 'hero_of_the_village'
                    }
                    
                    def convert_effect_entry(match):
                        effect_data = match.group(1)
                        def convert_id(id_match):
                            effect_id = id_match.group(1)
                            effect_name = effect_map.get(effect_id, 'speed')
                            return f'id:"minecraft:{effect_name}"'
                        # Match Id: followed by number with optional 'b' suffix
                        # Match Id: followed by number with optional 'b' suffix
                        effect_data = re.sub(r'Id:(\d+)(?:b)?', convert_id, effect_data)
                        effect_data = re.sub(r'Amplifier:', 'amplifier:', effect_data)
                        effect_data = re.sub(r'Duration:', 'duration:', effect_data)
                        effect_data = re.sub(r'ShowParticles:', 'show_particles:', effect_data)
                        
                        # Ensure amplifier and show_particles have 'b' suffix if they're 0 or 1 (byte values)
                        # Only add suffix if not already present
                        effect_data = re.sub(r'\bamplifier:([01])(?![bBsSlLfFdD])', r'amplifier:\1b', effect_data)
                        effect_data = re.sub(r'\bshow_particles:([01])(?![bBsSlLfFdD])', r'show_particles:\1b', effect_data)
                        
                        return f'{{{effect_data}}}'
                    
                    # Convert effects in the array content - match Id: followed by number (with or without 'b' suffix)
                    converted_array = re.sub(r'\{([^{}]*Id:\d+(?:b)?[^{}]*)\}', convert_effect_entry, array_content)
                    
                    # Replace the array content
                    active_effects_start_new = nbt.find('active_effects:', active_effects_start)
                    if active_effects_start_new != -1:
                        array_start_new = active_effects_start_new + len('active_effects:')
                        bracket_start_new = array_start_new
                        if bracket_start_new < len(nbt) and nbt[bracket_start_new] == '[':
                            depth = 1
                            bracket_end_new = bracket_start_new + 1
                            in_quotes = False
                            quote_char = None
                            for i in range(bracket_start_new + 1, len(nbt)):
                                char = nbt[i]
                                if char in ['"', "'"] and (i == 0 or nbt[i-1] != '\\'):
                                    if not in_quotes:
                                        in_quotes = True
                                        quote_char = char
                                    elif char == quote_char:
                                        in_quotes = False
                                        quote_char = None
                                elif not in_quotes:
                                    if char == '[':
                                        depth += 1
                                    elif char == ']':
                                        depth -= 1
                                        if depth == 0:
                                            bracket_end_new = i
                                            break
                            if bracket_end_new > bracket_start_new:
                                nbt = nbt[:bracket_start_new + 1] + converted_array + nbt[bracket_end_new:]
            else:
                # No array found, just convert the name
                nbt = nbt[:active_effects_start] + 'active_effects:' + nbt[array_start:]
        
        return nbt
    
    def _convert_inventory_items_recursive(self, nbt: str) -> str:
        """Recursively convert item NBT in Inventory arrays (for execute if entity selectors)
        
        Converts items in Inventory arrays from 1.12 format (display:{Name:...,Lore:...})
        to 1.21 format (custom_name=...,lore=...) using brackets [] for components.
        """
        import re
        
        # Find all Inventory: occurrences
        max_iterations = 100  # Safety limit to prevent infinite loops
        iteration = 0
        while ('Inventory:' in nbt or 'inventory:' in nbt) and iteration < max_iterations:
            iteration += 1
            # Find the first occurrence (case-insensitive)
            inventory_start = nbt.find('Inventory:')
            if inventory_start == -1:
                inventory_start = nbt.find('inventory:')
            if inventory_start == -1:
                break
            
            # Find the start of the array (after 'Inventory:' or 'inventory:')
            array_start = inventory_start + len('Inventory:') if 'Inventory:' in nbt[inventory_start:inventory_start+10] else inventory_start + len('inventory:')
            
            # Find the matching bracket for the array
            bracket_start = array_start
            if bracket_start < len(nbt) and nbt[bracket_start] == '[':
                # Find matching closing bracket
                depth = 1
                bracket_end = bracket_start + 1
                in_quotes = False
                quote_char = None
                
                for i in range(bracket_start + 1, len(nbt)):
                    char = nbt[i]
                    if char in ['"', "'"] and (i == 0 or nbt[i-1] != '\\'):
                        if not in_quotes:
                            in_quotes = True
                            quote_char = char
                        elif char == quote_char:
                            in_quotes = False
                            quote_char = None
                    elif not in_quotes:
                        if char == '[':
                            depth += 1
                        elif char == ']':
                            depth -= 1
                            if depth == 0:
                                bracket_end = i
                                break
                
                if bracket_end > bracket_start:
                    # Extract the array content
                    array_content = nbt[bracket_start + 1:bracket_end]
                    
                    # Convert each item in the array
                    # Items are separated by commas at the top level
                    items = []
                    current_item = ""
                    brace_depth = 0
                    bracket_depth = 0
                    in_quotes = False
                    quote_char = None
                    
                    for char in array_content:
                        if char in ['"', "'"] and (not current_item or current_item[-1] != '\\'):
                            if not in_quotes:
                                in_quotes = True
                                quote_char = char
                            elif char == quote_char:
                                in_quotes = False
                                quote_char = None
                            current_item += char
                        elif not in_quotes:
                            if char == '{':
                                brace_depth += 1
                                current_item += char
                            elif char == '}':
                                brace_depth -= 1
                                current_item += char
                            elif char == '[':
                                bracket_depth += 1
                                current_item += char
                            elif char == ']':
                                bracket_depth -= 1
                                current_item += char
                            elif char == ',' and brace_depth == 0 and bracket_depth == 0:
                                if current_item.strip():
                                    # Convert this item's NBT
                                    converted_item = self._convert_item_nbt_in_entity_context(current_item.strip())
                                    items.append(converted_item)
                                current_item = ""
                            else:
                                current_item += char
                        else:
                            current_item += char
                    
                    # Add the last item
                    if current_item.strip():
                        converted_item = self._convert_item_nbt_in_entity_context(current_item.strip())
                        items.append(converted_item)
                    
                    # Replace the array content with converted items
                    converted_array = ','.join(items)
                    new_nbt = nbt[:bracket_start + 1] + converted_array + nbt[bracket_end:]
                    # Only update if something changed (prevents infinite loops)
                    if new_nbt != nbt:
                        nbt = new_nbt
                    else:
                        # No change made, skip this Inventory: to prevent infinite loop
                        # Replace "Inventory:" temporarily to skip it
                        nbt = nbt[:inventory_start] + '___PROCESSED_INVENTORY___' + nbt[inventory_start + 10:]
            else:
                # No array found, skip this Inventory: to prevent infinite loop
                nbt = nbt[:inventory_start] + '___PROCESSED_INVENTORY___' + nbt[inventory_start + 10:]
        
        # Restore any skipped Inventory: markers
        nbt = nbt.replace('___PROCESSED_INVENTORY___', 'Inventory:')
        
        return nbt
    
    def _fix_display_quotes(self, nbt: str) -> str:
        """Ensure display.Name and display.Lore have properly escaped JSON strings
        Ensures double quotes are properly escaped for compatibility in selector parameters.
        This handles cases where structured parser or other conversion steps output unescaped JSON.
        NOTE: This should NOT be called on NBT that has already been processed by
        _convert_inventory_items_recursive, as that function already outputs escaped JSON.
        """
        import re
        
        # Fix Name:"{...}" -> Name:'{...}' 
        # Find Name:" then find the matching closing quote after the JSON object
        while 'Name:"{' in nbt:
            name_start = nbt.find('Name:"{')
            if name_start == -1:
                break
            
            # Find the opening brace (after Name:")
            brace_start = name_start + 6  # After 'Name:"{'
            
            # Find the matching closing brace
            brace_count = 1
            brace_end = brace_start
            in_quotes = False
            quote_char = None
            
            while brace_end < len(nbt) and brace_count > 0:
                char = nbt[brace_end]
                if char in ['"', "'"] and (brace_end == 0 or nbt[brace_end - 1] != '\\'):
                    if not in_quotes:
                        in_quotes = True
                        quote_char = char
                    elif char == quote_char:
                        in_quotes = False
                        quote_char = None
                elif not in_quotes:
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                brace_end += 1
            
            if brace_count == 0:
                # Found the matching closing brace, now find the closing quote
                quote_end = brace_end
                while quote_end < len(nbt) and nbt[quote_end] != '"' and nbt[quote_end] not in [',', '}']:
                    quote_end += 1
                
                if quote_end < len(nbt) and nbt[quote_end] == '"':
                    # Extract the JSON content (between the braces)
                    json_content = nbt[brace_start-1:brace_end]  # Include the braces
                    # Ensure proper escaping for double quotes (required for selector parameters)
                    json_content_escaped = json_content.replace('\\', r'\\').replace('"', r'\"')
                    replacement = f'Name:"{json_content_escaped}"'
                    nbt = nbt[:name_start] + replacement + nbt[quote_end + 1:]
                else:
                    break
            else:
                break
        
        # Fix Lore array elements: "{"text":...}" -> '{"text":...}'
        # Find each quoted JSON string in Lore arrays and convert quotes
        while 'Lore:[' in nbt and '"{"text"' in nbt:
            lore_start = nbt.find('Lore:[')
            if lore_start == -1:
                break
            
            # Find the matching closing bracket
            bracket_count = 1
            bracket_end = lore_start + 6
            in_quotes = False
            quote_char = None
            
            while bracket_end < len(nbt) and bracket_count > 0:
                char = nbt[bracket_end]
                if char in ['"', "'"] and (bracket_end == 0 or nbt[bracket_end - 1] != '\\'):
                    if not in_quotes:
                        in_quotes = True
                        quote_char = char
                    elif char == quote_char:
                        in_quotes = False
                        quote_char = None
                elif not in_quotes:
                    if char == '[':
                        bracket_count += 1
                    elif char == ']':
                        bracket_count -= 1
                bracket_end += 1
            
            if bracket_count == 0:
                # Found the Lore array, now fix quotes inside it
                lore_content = nbt[lore_start + 6:bracket_end - 1]
                original_lore = lore_content
                
                # Ensure all JSON strings are properly escaped with double quotes
                # First, handle unquoted JSON strings: {"text":...} -> "{\"text\":...}"
                def quote_and_escape_json(match):
                    json_content = match.group(2)  # The JSON object part
                    # Escape quotes and backslashes for double-quoted string
                    json_content_escaped = json_content.replace('\\', r'\\').replace('"', r'\"')
                    return f'{match.group(1)}"{json_content_escaped}"{match.group(3)}'
                
                # Match unquoted JSON objects in the array and quote/escape them
                fixed_lore = re.sub(r'([,\[])(\{[^}]*"text"[^}]*\})([,\]])', quote_and_escape_json, lore_content)
                
                # Then, fix already-quoted JSON strings that might not be properly escaped
                # Pattern: "{"text":...}" - ensure inner quotes are escaped (but don't double-escape)
                def ensure_escaped_quotes(match):
                    full_match = match.group(0)  # The whole "..." string
                    json_content = match.group(1)  # The JSON object inside quotes
                    # Check if quotes are already escaped - if they are, don't re-escape
                    # Look for patterns like \" which indicate already escaped
                    if '\\"' in json_content or json_content.count('\\') > json_content.count('"'):
                        # Already escaped, return as-is
                        return full_match
                    # Not escaped, escape it
                    json_content_escaped = json_content.replace('\\', r'\\').replace('"', r'\"')
                    return f'"{json_content_escaped}"'
                
                fixed_lore = re.sub(r'"(\{[^}]*"text"[^}]*\})"', ensure_escaped_quotes, fixed_lore)
                
                if fixed_lore != original_lore:
                    nbt = nbt[:lore_start + 6] + fixed_lore + nbt[bracket_end - 1:]
                    continue
            
            break
        
        return nbt
    
    def _convert_plain_text_to_json(self, text: str) -> str:
        """Convert plain text with § codes to JSON - handles sequential codes properly"""
        import re
        import json
        
        if '§' not in text:
            # For 1.21, always include italic:false
            return json.dumps({"text": text, "italic": False})
        
        # Split text by § codes, keeping the codes as separate parts
        parts = re.split(r'(§[0-9a-frlomn])', text)
        
        components = []
        current_text = ""
        current_formatting = {}
        
        for part in parts:
            if part.startswith('§'):
                # This is a color code
                if current_text:
                    # Save previous component
                    comp = {"text": current_text}
                    comp.update(current_formatting)
                    components.append(comp)
                    current_text = ""
                    current_formatting = {}
                
                # Process the color code
                code = part[1].lower()
                if code in ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'a', 'b', 'c', 'd', 'e', 'f']:
                    # Color code - reset formatting and set color
                    current_formatting = {"color": self._get_color_name(code)}
                elif code == 'r':
                    # Reset - clear all formatting
                    current_formatting = {}
                elif code == 'l':
                    current_formatting["bold"] = True
                elif code == 'm':
                    current_formatting["strikethrough"] = True
                elif code == 'n':
                    current_formatting["underline"] = True
                elif code == 'o':
                    current_formatting["italic"] = True
            else:
                current_text += part
        
        # Add any remaining text (or empty component if formatting was set but no text)
        if current_text:
            component = {"text": current_text}
            component.update(current_formatting)
            components.append(component)
        elif components and current_formatting:
            # No remaining text but we have formatting - add empty component
            # This handles cases where the string ends with a color code (e.g., "§eGate Stone§7")
            component = current_formatting.copy()
            component["text"] = ""
            components.append(component)
        
        # Don't filter out empty components - keep them for proper multi-component names
        # Empty components are needed when color codes change (e.g., "§eGate Stone§7" -> [yellow "Gate Stone", gray ""])
        
        # Always add italic:false to each component (required in 1.21)
        for comp in components:
            if "italic" not in comp:
                comp["italic"] = False
        
        # Reorder keys to put "color", "italic", "text" in that order (for entity NBT components)
        def reorder_keys(comp):
            if isinstance(comp, dict):
                ordered = {}
                # Order: color, italic, text (for entity NBT)
                key_order = ["color", "italic", "text"]
                for key in key_order:
                    if key in comp:
                        ordered[key] = comp[key]
                # Add any other keys that weren't in the order list
                for key, value in comp.items():
                    if key not in key_order:
                        ordered[key] = value
                return ordered
            return comp
        
        components = [reorder_keys(comp) for comp in components]
        
        # Always return array format for consistency (even for single component)
        # This ensures multi-component names are properly handled
        return json.dumps(components)
    
    def _get_color_name(self, code: str) -> str:
        """Convert § color code to color name"""
        color_map = {
            '0': 'black', '1': 'dark_blue', '2': 'dark_green', '3': 'dark_aqua',
            '4': 'dark_red', '5': 'dark_purple', '6': 'gold', '7': 'gray',
            '8': 'dark_gray', '9': 'blue', 'a': 'green', 'b': 'aqua',
            'c': 'red', 'd': 'light_purple', 'e': 'yellow', 'f': 'white'
        }
        return color_map.get(code.lower(), 'white')
    
    def _convert_item_nbt_in_entity_context(self, item_str: str) -> str:
        """Convert item NBT from 1.12 format to 1.21 format when found in entity NBT (Inventory arrays)
        
        IMPORTANT: In Minecraft 1.21.9+, items in entity NBT (like Inventory arrays) should use
        components:{"minecraft:custom_name":...,"minecraft:lore":...} format, NOT display format.
        Components use raw JSON (no escaping) since they are COMPOUND/LIST tags.
        """
        import re
        
        # Check if item has display tag or tag with display
        has_display = 'display:{' in item_str or (',tag:{' in item_str and 'display:{' in item_str)
        if not has_display:
            return item_str
        
        import json
        
        # Parse the item NBT to extract display data
        # We need to find tag:{display:{...}} or just display:{...}
        result = item_str
        
        # Try to parse as structured NBT first (more reliable)
        try:
            # Find the item NBT structure
            # Look for tag:{display:{...}} pattern
            tag_pattern = re.compile(r'tag:\{([^}]*display:\{[^}]*\}[^}]*)\}')
            tag_match = tag_pattern.search(result)
            
            if tag_match:
                # Has tag structure, need to convert display to components
                tag_content = tag_match.group(1)
                display_match = re.search(r'display:\{([^}]*)\}', tag_content)
                
                if display_match:
                    display_content = display_match.group(1)
                    components = {}
                    
                    # Extract Name if present
                    name_match = re.search(r'Name:["\']([^"\']*)["\']', display_content)
                    if name_match:
                        name_value = name_match.group(1)
                        # Remove color codes and convert to JSON text component
                        name_value_clean = re.sub(r'§[0-9a-frlomn]', '', name_value)
                        if '§' in name_value:
                            # Has color codes, convert to JSON
                            name_json = self._convert_plain_text_to_json(name_value)
                            components['minecraft:item_name'] = json.loads(name_json)
                        else:
                            # Plain text, use as string (components accept strings or objects)
                            components['minecraft:item_name'] = name_value_clean
                    
                    # Extract Lore if present
                    lore_match = re.search(r'Lore:\[(.*?)\]', display_content, re.DOTALL)
                    if lore_match:
                        lore_content = lore_match.group(1)
                        # Parse lore entries (they're quoted strings)
                        lore_entries = []
                        # Split by commas, handling quoted strings
                        current_entry = ""
                        in_quotes = False
                        quote_char = None
                        for char in lore_content:
                            if char in ['"', "'"] and (not current_entry or current_entry[-1] != '\\'):
                                if not in_quotes:
                                    in_quotes = True
                                    quote_char = char
                                elif char == quote_char:
                                    in_quotes = False
                                    quote_char = None
                                current_entry += char
                            elif char == ',' and not in_quotes:
                                if current_entry.strip():
                                    # Remove quotes and process
                                    entry = current_entry.strip().strip('"').strip("'")
                                    if '§' in entry:
                                        # Has color codes, convert to JSON components
                                        lore_comp = self._parse_color_codes_to_components(entry)
                                        if len(lore_comp) == 1:
                                            lore_entries.append(lore_comp[0])
                                        elif len(lore_comp) > 1:
                                            lore_entries.append(lore_comp)
                                        else:
                                            lore_entries.append({"text": "", "italic": False})
                                    elif entry.strip():
                                        lore_entries.append({"text": entry, "italic": False})
                                    else:
                                        lore_entries.append({"text": "", "italic": False})
                                current_entry = ""
                            else:
                                current_entry += char
                        
                        # Add last entry
                        if current_entry.strip():
                            entry = current_entry.strip().strip('"').strip("'")
                            if '§' in entry:
                                lore_comp = self._parse_color_codes_to_components(entry)
                                if len(lore_comp) == 1:
                                    lore_entries.append(lore_comp[0])
                                elif len(lore_comp) > 1:
                                    lore_entries.append(lore_comp)
                                else:
                                    lore_entries.append({"text": "", "italic": False})
                            elif entry.strip():
                                lore_entries.append({"text": entry, "italic": False})
                            else:
                                lore_entries.append({"text": "", "italic": False})
                        
                        if lore_entries:
                            components['minecraft:lore'] = lore_entries
                    
                    # Replace tag:{display:{...}} with components:{...}
                    if components:
                        # Serialize components to SNBT format (raw JSON, no escaping)
                        components_str = ','.join([f'"{k}":{json.dumps(v)}' for k, v in components.items()])
                        replacement = f'components:{{{components_str}}}'
                        
                        # Find the full tag:{} block and replace display part with components
                        # For now, replace the entire tag block
                        tag_start = result.find('tag:{')
                        if tag_start != -1:
                            # Find matching closing brace for tag
                            tag_brace_start = tag_start + 4
                            tag_brace_count = 1
                            tag_brace_end = tag_brace_start
                            while tag_brace_end < len(result) and tag_brace_count > 0:
                                if result[tag_brace_end] == '{':
                                    tag_brace_count += 1
                                elif result[tag_brace_end] == '}':
                                    tag_brace_count -= 1
                                tag_brace_end += 1
                            
                            # Replace tag:{...} with components:{...}
                            # But preserve other tag content if any
                            tag_content_full = result[tag_brace_start:tag_brace_end-1]
                            # Check if there's other content besides display
                            other_content = tag_content_full.replace(display_match.group(0), '').strip(',').strip()
                            
                            if other_content:
                                # Has other tag content, keep tag and add components
                                result = result[:tag_start] + f'tag:{{{other_content}}},{replacement}' + result[tag_brace_end-1:]
                            else:
                                # Only display, replace tag with components
                                result = result[:tag_start] + replacement + result[tag_brace_end-1:]
        except Exception:
            # If parsing fails, fall back to regex-based conversion
            pass
        
        return result
    
    def _convert_lore_array_to_json_strings(self, lore_content: str) -> str:
        """Convert lore array content to array of JSON strings for display:Lore in entity NBT
        
        Input: "text1","text2" (comma-separated quoted strings)
        Output: '{"text":"text1","italic":false}','{"text":"text2","italic":false}' (JSON strings)
        """
        import re
        import json
        
        # Split by commas, but be careful about nested structures and quoted strings
        lines = []
        current_line = ""
        bracket_count = 0
        in_quotes = False
        quote_char = None
        
        for char in lore_content:
            if char in ['"', "'"] and (not current_line or current_line[-1] != '\\'):
                if not in_quotes:
                    in_quotes = True
                    quote_char = char
                elif char == quote_char:
                    in_quotes = False
                    quote_char = None
                current_line += char
            elif char == '{' and not in_quotes:
                bracket_count += 1
                current_line += char
            elif char == '}' and not in_quotes:
                bracket_count -= 1
                current_line += char
            elif char == ',' and bracket_count == 0 and not in_quotes:
                if current_line.strip():
                    lines.append(current_line.strip())
                current_line = ""
                continue
            else:
                current_line += char
        
        if current_line.strip():
            lines.append(current_line.strip())
        
        converted_lines = []
        for line in lines:
            # Remove quotes if present, but preserve escaped content
            # Check if line is already a JSON string (starts with { and contains "text")
            if line.strip().startswith('{') and '"text"' in line:
                # Already JSON, check if it's escaped
                if '\\"' in line or line.count('\\') > line.count('"'):
                    # Already escaped, just wrap in double quotes
                    converted_lines.append(f'"{line}"')
                else:
                    # JSON but not escaped, escape it
                    json_text_escaped = line.replace('\\', r'\\').replace('"', r'\"')
                    converted_lines.append(f'"{json_text_escaped}"')
                continue
            
            # Remove quotes if present
            line = line.strip().strip('"').strip("'")
            
            # Handle empty lines
            if not line:
                # Escape quotes for double-quoted string (required for compatibility in selector parameters)
                converted_lines.append('"{\\"text\\":\\"\\",\\"italic\\":false}"')
                continue
            
            # Convert to JSON format
            if '§' in line:
                json_text = self._convert_plain_text_to_json(line)
            else:
                json_text = json.dumps({"text": line, "italic": False})
            
            # Escape quotes for double-quoted string (required for compatibility in selector parameters)
            # This ensures proper escaping when NBT is used in selector parameters like nbt={...}
            # First escape backslashes, then escape quotes (order matters!)
            json_text_escaped = json_text.replace('\\', r'\\').replace('"', r'\"')
            converted_lines.append(f'"{json_text_escaped}"')
        
        return ','.join(converted_lines)
    
    def _find_matching_bracket_for_item(self, start_pos: int, text: str) -> int:
        """Find matching closing bracket starting from start_pos (for item NBT parsing)"""
        if start_pos >= len(text) or text[start_pos] != '[':
            return -1
        
        depth = 1
        in_quotes = False
        quote_char = None
        
        for i in range(start_pos + 1, len(text)):
            char = text[i]
            if char in ['"', "'"] and (i == 0 or text[i-1] != '\\'):
                if not in_quotes:
                    in_quotes = True
                    quote_char = char
                elif char == quote_char:
                    in_quotes = False
                    quote_char = None
            elif not in_quotes:
                if char == '[':
                    depth += 1
                elif char == ']':
                    depth -= 1
                    if depth == 0:
                        return i
        
        return -1
    
    @log_method_call
    def convert_entity_nbt(self, nbt: str) -> str:
        """Convert entity NBT data - keep structure intact for selectors
        
        Uses structured NBT parsing (NBTParser/NBTSerializer/NBTConverterRegistry) for all entity NBT.
        This ensures consistent conversion of equipment, drop_chances, CustomName, enchantments, etc.
        Falls back to regex-based conversion only if structured parsing fails.
        """
        import re
        
        # ALWAYS try structured NBT parsing first (for equipment, enchantments, CustomName, etc.)
        # This is the same logic used for Cryptkeeper and should be applied to all entity NBT
        try:
            # Parse SNBT string to structured Python object
            nbt_dict = NBTParser.parse_snbt(nbt)
            
            # Debug: Check what was parsed
            import sys
            if 'Inventory' in nbt_dict:
                print(f"DEBUG convert_entity_nbt: Found Inventory, type = {type(nbt_dict['Inventory'])}, value = {nbt_dict['Inventory']}", file=sys.stderr)
            if 'SelectedItem' in nbt_dict:
                print(f"DEBUG convert_entity_nbt: Found SelectedItem, type = {type(nbt_dict['SelectedItem'])}, value = {nbt_dict['SelectedItem']}", file=sys.stderr)
            
            # Apply registered converters (equipment, drop_chances, CustomName, etc.)
            # Use self.nbt_registry (this is ParameterConverters' registry which has Inventory and SelectedItem)
            import sys
            print(f"DEBUG convert_entity_nbt: About to call convert, registry has = {list(self.nbt_registry.converters.keys())}", file=sys.stderr)
            converted_dict = self.nbt_registry.convert(nbt_dict, "entity")
            
            # Debug: Check what was converted
            if 'Inventory' in converted_dict:
                print(f"DEBUG convert_entity_nbt: After conversion, Inventory = {converted_dict['Inventory']}", file=sys.stderr)
            if 'SelectedItem' in converted_dict:
                print(f"DEBUG convert_entity_nbt: After conversion, SelectedItem = {converted_dict['SelectedItem']}", file=sys.stderr)
            
            # Serialize back to SNBT string
            converted_nbt = NBTSerializer.serialize_snbt(converted_dict)
            
            # Apply additional regex-based conversions that aren't handled by structured parsing
            # (These are basic fixes that don't require structured parsing)
            converted_nbt = re.sub(r'MaxHeatlh:', 'MaxHealth:', converted_nbt)  # Fix typo
            converted_nbt = re.sub(r'Fuse:', 'fuse:', converted_nbt)  # Fuse must be lowercase in 1.20+
            
            # Convert ActiveEffects to active_effects (recursively handles Passengers arrays)
            if 'ActiveEffects:' in converted_nbt:
                converted_nbt = self._convert_active_effects_recursive(converted_nbt)
            
            # Convert falling_block Block and Data to BlockState (recursively handles Passengers arrays)
            # This must happen after structured parsing to ensure nested structures are processed
            converted_nbt = self._convert_falling_block_recursive(converted_nbt)
            
            # Structured parser should have already converted Inventory items to components format
            # No need to call _convert_inventory_items_recursive here since structured parser handles it
            # Fix any display.Name or display.Lore that might still need escaping (for non-Inventory contexts)
            converted_nbt = self._fix_display_quotes(converted_nbt)
            
            # Return the structured conversion result
            return converted_nbt
        except Exception as e:
            # Fallback to old regex-based conversion if structured parsing fails
            # Log the error for debugging but continue with regex fallback
            import traceback
            print(f"Warning: Structured NBT parsing failed ({e}). Falling back to regex-based conversion.")
            traceback.print_exc()
            pass  # Continue to regex-based conversion below
        
        # Basic entity NBT conversions (regex-based fallback only)
        nbt = re.sub(r'MaxHeatlh:', 'MaxHealth:', nbt)  # Fix typo
        nbt = re.sub(r'Fuse:', 'fuse:', nbt)  # Fuse must be lowercase in 1.20+
        
        # Convert ActiveEffects to active_effects (recursively handles Passengers arrays)
        nbt = self._convert_active_effects_recursive(nbt)
        
        # Convert enchantments from numeric IDs to string names
        # 1.12: ench:[{id:35,lvl:1}] or tag:{ench:[...]}
        # 1.20: Enchantments:[{id:"fortune",lvl:1}] or tag:{Enchantments:[...]}
        if 'ench:' in nbt:
            # Enchantment ID to name mapping (1.12 numeric IDs to 1.20 names)
            enchantment_map = {
                '0': 'protection', '1': 'fire_protection', '2': 'feather_falling',
                '3': 'blast_protection', '4': 'projectile_protection', '5': 'respiration',
                '6': 'aqua_affinity', '7': 'thorns', '8': 'depth_strider',
                '9': 'frost_walker', '10': 'binding_curse',
                '16': 'sharpness', '17': 'smite', '18': 'bane_of_arthropods',
                '19': 'knockback', '20': 'fire_aspect', '21': 'looting',
                '22': 'sweeping', '32': 'efficiency', '33': 'silk_touch',
                '34': 'unbreaking', '35': 'fortune', '48': 'power',
                '49': 'punch', '50': 'flame', '51': 'infinity',
                '61': 'luck_of_the_sea', '62': 'lure',
                '70': 'mending', '71': 'vanishing_curse'
            }
            
            # Convert the tag name from ench to Enchantments
            nbt = re.sub(r'\bench:', 'Enchantments:', nbt)
            
            # Convert enchantment IDs to names
            def convert_enchantment_entry(match):
                ench_data = match.group(1)
                
                # Convert id:<number> to id:"<enchantment_name>"
                def convert_ench_id(id_match):
                    ench_id = id_match.group(1)
                    ench_name = enchantment_map.get(ench_id, 'protection')  # Default to protection if not found
                    return f'id:"{ench_name}"'
                
                ench_data = re.sub(r'id:(\d+)', convert_ench_id, ench_data)
                
                return f'{{{ench_data}}}'
            
            # Apply conversion to each enchantment entry
            # Match patterns like {id:35,lvl:1} or {id:34,lvl:3}
            nbt = re.sub(r'\{([^{}]*id:\d+[^{}]*)\}', convert_enchantment_entry, nbt)
        
        # Convert skull items that rely on Damage metadata for differentiation
        # Handle both quoted (id:"skull") and unquoted (id:skull) formats
        if ('skull' in nbt or 'minecraft:skull' in nbt) and 'Damage:' in nbt:
            skull_map = {
                '0': 'minecraft:skeleton_skull',
                '1': 'minecraft:wither_skeleton_skull',
                '2': 'minecraft:zombie_head',
                '3': 'minecraft:player_head',
                '4': 'minecraft:creeper_head',
                '5': 'minecraft:dragon_head'
            }

            # Match both quoted (id:"skull") and unquoted (id:skull) skull IDs
            # Pattern: id:"skull" or id:skull (with optional minecraft: prefix)
            pattern = re.compile(r'id:(?:"(?:minecraft:)?skull"|(?:minecraft:)?skull(?=[,}]))')
            result_segments = []
            last_index = 0
            updated = False

            for match in pattern.finditer(nbt):
                bounds = self._find_enclosing_braces(nbt, match.start())
                if not bounds:
                    continue

                item_start, item_end = bounds
                item_str = nbt[item_start:item_end]

                damage_match = re.search(r'Damage:(\d+)(?:[bBsSlLfFdD])?', item_str)
                if not damage_match:
                    continue

                damage_value = str(int(damage_match.group(1)))
                new_id = skull_map.get(damage_value)
                if not new_id:
                    continue

                # Replace both quoted and unquoted formats
                # Match: id:"skull", id:"minecraft:skull", id:skull, or id:minecraft:skull
                converted_item = re.sub(r'id:(?:"(?:minecraft:)?skull"|(?:minecraft:)?skull(?=[,}]))', f'id:"{new_id}"', item_str, count=1)
                converted_item = self._remove_damage_attribute(converted_item)

                if converted_item != item_str:
                    result_segments.append(nbt[last_index:item_start])
                    result_segments.append(converted_item)
                    last_index = item_end
                    updated = True

            if updated:
                result_segments.append(nbt[last_index:])
                nbt = ''.join(result_segments)
        
        # Convert item IDs to namespaced format (add minecraft: prefix if missing)
        # This handles items in HandItems, ArmorItems, Inventory, etc.
        # Pattern: id:"item_name" -> id:"minecraft:item_name" (if not already namespaced)
        def convert_quoted_item_id(match):
            item_name = match.group(1)
            # Skip if already namespaced
            if ':' in item_name:
                return match.group(0)
            return f'id:"minecraft:{item_name}"'
        
        # Match quoted item IDs: id:"item_name"
        nbt = re.sub(r'\bid:"([^"]+)"', convert_quoted_item_id, nbt)
        
        # Pattern: id:item_name -> id:"minecraft:item_name" (if not already namespaced)
        # Match unquoted item IDs - only match valid item names (lowercase, underscores)
        # Look for id: followed by item name, followed by comma or } (item context)
        def convert_unquoted_item_id(match):
            item_name = match.group(1)
            # Skip if already namespaced or if it looks like a number
            if ':' in item_name or (item_name and item_name[0].isdigit()):
                return match.group(0)
            return f'id:"minecraft:{item_name}"'
        
        # Match unquoted item IDs: id:item_name (only in item contexts - followed by comma or })
        nbt = re.sub(r'\bid:([a-z_][a-z0-9_]*)(?=[,}])', convert_unquoted_item_id, nbt)

        # Convert falling_block Block and Data to BlockState (recursively handles Passengers arrays)
        nbt = self._convert_falling_block_recursive(nbt)
        
        # Use structured NBT parsing for equipment conversion (1.21.10 format)
        # This uses the new extensible converter system
        try:
            # Parse NBT string to structured format
            nbt_dict = NBTParser.parse_snbt(nbt)
            
            # Apply registered converters
            nbt_dict = self.nbt_registry.convert(nbt_dict, "entity")
            
            # Serialize back to SNBT string
            nbt = NBTSerializer.serialize_snbt(nbt_dict)
        except Exception as e:
            # Fallback to old method if parsing fails
            # Convert ArmorItems/HandItems to equipment structure (1.21.10 format)
            nbt = self._convert_equipment_to_121_format(nbt)
            # Convert HandDropChances/ArmorDropChances to drop_chances (1.21.10 format)
            nbt = self._convert_drop_chances_to_121_format(nbt)
        
        # Entity NBT may contain nested item NBT (e.g., in Inventory arrays)
        # Convert items in Inventory arrays from old format to new format
        # Items in entity NBT should use display:{Name:...,Lore:[...]} format (not component format)
        if 'Inventory:' in nbt or 'inventory:' in nbt:
            nbt = self._convert_inventory_items_recursive(nbt)
        
        # Convert color codes in nested item display properties
        if '§' in nbt and hasattr(self, '_nbt_color_converter'):
            # Process nested item NBT for color conversion
            nbt = self._nbt_color_converter(nbt, "entity")
        
        return nbt
    
    @log_method_call
    def _convert_equipment_to_121_format(self, nbt: str) -> str:
        """Convert ArmorItems/HandItems to equipment structure for 1.21.10"""
        import re
        import json
        
        # Slot mapping: ArmorItems [feet, legs, chest, head], HandItems [mainhand, offhand]
        # Note: HandItems[0] = mainhand, HandItems[1] = offhand
        armor_slots = ['feet', 'legs', 'chest', 'head']
        hand_slots = ['mainhand', 'offhand']  # Index 0 = mainhand, index 1 = offhand
        
        equipment_items = {}
        has_armor = False
        has_hands = False
        
        # Process ArmorItems - use bracket matching to find the full array
        armor_start = nbt.find('ArmorItems:[')
        if armor_start != -1:
            bracket_start = armor_start + 11  # Position of '[' in 'ArmorItems:['
            # Find matching bracket (start AFTER the opening bracket)
            depth = 1
            bracket_end = bracket_start
            in_quotes = False
            quote_char = None
            for i in range(bracket_start + 1, len(nbt)):
                char = nbt[i]
                if char in ['"', "'"] and (i == 0 or nbt[i-1] != '\\'):
                    if not in_quotes:
                        in_quotes = True
                        quote_char = char
                    elif char == quote_char:
                        in_quotes = False
                        quote_char = None
                elif not in_quotes:
                    if char == '[':
                        depth += 1
                    elif char == ']':
                        depth -= 1
                        if depth == 0:
                            bracket_end = i
                            break
            if bracket_end > bracket_start:
                has_armor = True
                # Extract content inside brackets (starting after '[' which is at bracket_start)
                # bracket_start points to '[', so bracket_start+1 is the first character of the first item '{'
                armor_content = nbt[bracket_start + 1:bracket_end]
                # Parse armor items (they're comma-separated, but may contain nested structures)
                armor_items = self._parse_item_array(armor_content)
                # Process each armor item - all 4 slots should be processed
                for i, item_str in enumerate(armor_items):
                    # Map to slot based on index: [0]=feet, [1]=legs, [2]=chest, [3]=head
                    if i < len(armor_slots):
                        if item_str.strip() and item_str.strip() != '{}':
                            slot = armor_slots[i]
                            converted_item = self._convert_item_to_121_equipment_format(item_str)
                            if converted_item:
                                equipment_items[slot] = converted_item
        
        # Process HandItems - use bracket matching to find the full array
        hand_start = nbt.find('HandItems:[')
        if hand_start != -1:
            bracket_start = hand_start + 10  # Position of '[' in 'HandItems:['
            # Find matching bracket
            depth = 1
            bracket_end = bracket_start
            in_quotes = False
            quote_char = None
            for i in range(bracket_start + 1, len(nbt)):
                char = nbt[i]
                if char in ['"', "'"] and (i == 0 or nbt[i-1] != '\\'):
                    if not in_quotes:
                        in_quotes = True
                        quote_char = char
                    elif char == quote_char:
                        in_quotes = False
                        quote_char = None
                elif not in_quotes:
                    if char == '[':
                        depth += 1
                    elif char == ']':
                        depth -= 1
                        if depth == 0:
                            bracket_end = i
                            break
            if bracket_end > bracket_start:
                has_hands = True
                hand_content = nbt[bracket_start + 1:bracket_end]
                # Parse hand items
                hand_items = self._parse_item_array(hand_content)
                # Special case: if HandItems[0] is empty and HandItems[1] has an item,
                # put HandItems[1] in mainhand (shift the item to fill the empty mainhand slot)
                if len(hand_items) >= 2 and (not hand_items[0].strip() or hand_items[0].strip() == '{}'):
                    # HandItems[0] is empty, check if HandItems[1] has an item
                    if hand_items[1].strip() and hand_items[1].strip() != '{}':
                        # Put HandItems[1] in mainhand instead of offhand
                        converted_item = self._convert_item_to_121_equipment_format(hand_items[1])
                        if converted_item:
                            equipment_items['mainhand'] = converted_item
                else:
                    # Normal case: map items to their slots
                    for i, item_str in enumerate(hand_items):
                        if i < len(hand_slots) and item_str.strip() and item_str.strip() != '{}':
                            slot = hand_slots[i]
                            converted_item = self._convert_item_to_121_equipment_format(item_str)
                            if converted_item:
                                equipment_items[slot] = converted_item
        
        # Replace ArmorItems/HandItems with equipment structure
        if has_armor or has_hands:
            # Build equipment structure
            if equipment_items:
                equipment_parts = []
                for slot in ['feet', 'legs', 'chest', 'head', 'mainhand', 'offhand']:
                    if slot in equipment_items:
                        equipment_parts.append(f'{slot}:{{{equipment_items[slot]}}}')
                
                equipment_str = '{' + ','.join(equipment_parts) + '}'
                
                # Remove ArmorItems and HandItems
                if armor_start != -1:
                    # Find the end of ArmorItems array
                    armor_end = nbt.find(']', armor_start + 12)
                    if armor_end != -1:
                        # Find the start of the next token (comma or end)
                        next_char_pos = armor_end + 1
                        while next_char_pos < len(nbt) and nbt[next_char_pos] in [' ', '\n', '\t']:
                            next_char_pos += 1
                        if next_char_pos < len(nbt) and nbt[next_char_pos] == ',':
                            next_char_pos += 1
                        nbt = nbt[:armor_start] + nbt[next_char_pos:]
                if hand_start != -1:
                    # Adjust position if armor was already removed
                    hand_pos = nbt.find('HandItems:[')
                    if hand_pos != -1:
                        # Find matching bracket
                        h_bracket_start = hand_pos + 10
                        h_depth = 1
                        h_bracket_end = h_bracket_start
                        h_in_quotes = False
                        h_quote_char = None
                        for i in range(h_bracket_start + 1, len(nbt)):
                            char = nbt[i]
                            if char in ['"', "'"] and (i == 0 or nbt[i-1] != '\\'):
                                if not h_in_quotes:
                                    h_in_quotes = True
                                    h_quote_char = char
                                elif char == h_quote_char:
                                    h_in_quotes = False
                                    h_quote_char = None
                            elif not h_in_quotes:
                                if char == '[':
                                    h_depth += 1
                                elif char == ']':
                                    h_depth -= 1
                                    if h_depth == 0:
                                        h_bracket_end = i
                                        break
                        if h_bracket_end > h_bracket_start:
                            next_char_pos = h_bracket_end + 1
                            while next_char_pos < len(nbt) and nbt[next_char_pos] in [' ', '\n', '\t']:
                                next_char_pos += 1
                            if next_char_pos < len(nbt) and nbt[next_char_pos] == ',':
                                next_char_pos += 1
                            nbt = nbt[:hand_pos] + nbt[next_char_pos:]
                
                # Insert equipment at the beginning (after opening brace)
                if nbt.startswith('{'):
                    nbt = '{equipment:' + equipment_str + (',' if nbt[1:].strip() else '') + nbt[1:]
                else:
                    nbt = 'equipment:' + equipment_str + ',' + nbt
        
        return nbt
    
    def _find_matching_brace_for_item(self, start_pos: int, text: str) -> int:
        """Find matching closing brace starting from start_pos (position of opening brace)"""
        if start_pos >= len(text) or text[start_pos] != '{':
            # Find the opening brace if start_pos points to a different position
            for i in range(start_pos, len(text)):
                if text[i] == '{':
                    start_pos = i
                    break
            else:
                return -1
        
        # Start with depth = 1 because start_pos points to the opening '{'
        depth = 1
        in_quotes = False
        quote_char = None
        
        # Start from the character AFTER the opening brace
        for i in range(start_pos + 1, len(text)):
            char = text[i]
            
            if char in ['"', "'"] and (i == 0 or text[i-1] != '\\'):
                if not in_quotes:
                    in_quotes = True
                    quote_char = char
                elif char == quote_char:
                    in_quotes = False
                    quote_char = None
            elif not in_quotes:
                if char == '{':
                    depth += 1
                elif char == '}':
                    depth -= 1
                    if depth == 0:
                        return i
        
        return -1
    
    def _convert_item_to_121_equipment_format(self, item_str: str) -> str:
        """Convert item NBT to 1.21.10 equipment format"""
        import re
        import json
        
        # Extract id, Count, Damage, and tag
        id_match = re.search(r'id:"?([^",\s]+)"?', item_str)
        count_match = re.search(r'Count:(\d+)([bBsSlLfFdD])?', item_str)
        damage_match = re.search(r'Damage:(\d+)([bBsSlLfFdD])?', item_str)
        
        if not id_match:
            return None
        
        item_id = id_match.group(1)
        
        # Handle skull items with Damage:3 -> player_head (and other skull types)
        skull_map = {
            '0': 'minecraft:skeleton_skull',
            '1': 'minecraft:wither_skeleton_skull',
            '2': 'minecraft:zombie_head',
            '3': 'minecraft:player_head',
            '4': 'minecraft:creeper_head',
            '5': 'minecraft:dragon_head'
        }
        if damage_match and (item_id == 'skull' or item_id == 'minecraft:skull'):
            damage_value = str(int(damage_match.group(1)))
            new_id = skull_map.get(damage_value)
            if new_id:
                item_id = new_id
        
        if ':' not in item_id:
            item_id = f'minecraft:{item_id}'
        
        count = 1
        if count_match:
            count = int(count_match.group(1))
        
        components = {}
        
        # Extract tag content - find matching brace manually for robustness
        tag_start = item_str.find('tag:{')
        if tag_start != -1:
            tag_brace_start = tag_start + 4  # Position of '{' in 'tag:{'
            tag_brace_end = self._find_matching_brace_for_item(tag_brace_start, item_str)
            if tag_brace_end != -1:
                tag_content = item_str[tag_brace_start + 1:tag_brace_end]  # Content inside tag:{...}
                
                # Check for display:{color:...} -> minecraft:dyed_color
                # Match color value even if there are other properties
                color_match = re.search(r'display:\{[^}]*color:(\d+)[^}]*\}', tag_content)
                if color_match:
                    color_value = color_match.group(1)
                    components['minecraft:dyed_color'] = color_value
                
                # Check for display:{Name:...,Lore:...}
                # Use brace matching to find the display block
                display_start = tag_content.find('display:{')
                if display_start != -1:
                    display_brace_start = display_start + 8  # Position of '{' in 'display:{'
                    display_brace_end = self._find_matching_brace_for_item(display_brace_start, tag_content)
                    if display_brace_end != -1:
                        display_content = tag_content[display_brace_start + 1:display_brace_end]  # Content inside display:{...}
                    
                    # Extract Name - handle both quoted formats and JSON
                    name_match = re.search(r'Name:["\']([^"\']*)["\']', display_content)
                    if name_match:
                        name_value = name_match.group(1)
                        # Remove JSON escaping
                        name_value = name_value.replace('\\"', '"').replace("\\'", "'")
                        # If it's JSON, extract text; otherwise use as-is
                        if name_value.startswith('{'):
                            try:
                                json_obj = json.loads(name_value)
                                name_value = json_obj.get('text', name_value)
                            except:
                                pass
                        # Remove color codes from item_name (1.21.10 uses plain text for item_name)
                        # Remove § codes to get plain text
                        name_value = re.sub(r'§[0-9a-frlomn]', '', name_value)
                        # For item_name component, it's just the plain string value (no color codes)
                        components['minecraft:item_name'] = json.dumps(name_value)
                    
                    # Extract Lore - need to parse array and convert each line
                    lore_start = display_content.find('Lore:[')
                    if lore_start != -1:
                        # Find the opening bracket position in display_content
                        bracket_start_pos = lore_start + 5  # Position of '[' in "Lore:["
                        # Find matching bracket - start AFTER the opening bracket
                        depth = 1  # Start at 1 because we're already inside the opening bracket
                        lore_end_pos = bracket_start_pos
                        in_quotes = False
                        quote_char = None
                        # Start loop AFTER the opening bracket (bracket_start_pos + 1)
                        for i in range(bracket_start_pos + 1, len(display_content)):
                            char = display_content[i]
                            # Handle quotes
                            if char in ['"', "'"] and (i == 0 or display_content[i-1] != '\\'):
                                if not in_quotes:
                                    in_quotes = True
                                    quote_char = char
                                elif char == quote_char:
                                    in_quotes = False
                                    quote_char = None
                            elif not in_quotes:
                                if char == '[':
                                    depth += 1
                                elif char == ']':
                                    depth -= 1
                                    if depth == 0:
                                        lore_end_pos = i
                                        break
                        
                        if lore_end_pos > bracket_start_pos:
                            # Extract content between brackets (exclude the brackets themselves)
                            lore_content = display_content[bracket_start_pos + 1:lore_end_pos]
                            # Parse lore entries
                            lore_entries = self._parse_item_array(lore_content)
                            converted_lore_entries = []
                            for lore_entry in lore_entries:
                                # Remove quotes
                                lore_text = lore_entry.strip().strip('"').strip("'")
                                # Convert color codes to JSON components
                                if '§' in lore_text:
                                    # Convert using color code parser
                                    converted = self._convert_lore_line_to_121_component(lore_text)
                                    converted_lore_entries.append(converted)
                                elif lore_text:
                                    # Plain text
                                    converted_lore_entries.append(json.dumps([{"text": lore_text, "italic": False}]))
                                else:
                                    # Empty line
                                    converted_lore_entries.append(json.dumps([{"text": "", "italic": False}]))
                            
                            # Join lore entries: [[{...}],[{...}]]
                            if converted_lore_entries:
                                components['minecraft:lore'] = '[' + ','.join(converted_lore_entries) + ']'
                
                # Check for SkullOwner - convert to minecraft:profile
                # Use brace matching to find the full SkullOwner block
                skull_start = tag_content.find('SkullOwner:{')
                if skull_start != -1:
                    skull_brace_start = skull_start + 11  # Position of '{' in 'SkullOwner:{' (11 chars: "SkullOwner:")
                    skull_brace_end = self._find_matching_brace_for_item(skull_brace_start, tag_content)
                    if skull_brace_end != -1:
                        skull_content = tag_content[skull_brace_start + 1:skull_brace_end]
                        # Extract texture value - Properties:{textures:[{Value:"..."}]}
                        props_match = re.search(r'Properties:\{textures:\[\{Value:"([^"]+)"\}\]\}', skull_content, re.DOTALL)
                        if props_match:
                            texture_value = props_match.group(1)
                            # Format as minecraft:profile component: {"properties":[{"name":"textures","value":"..."}]}
                            profile_json = json.dumps({"properties": [{"name": "textures", "value": texture_value}]})
                            components['minecraft:profile'] = profile_json
        
        # Build the item structure
        parts = [f'id:"{item_id}"', f'count:{count}']
        if components:
            comp_parts = []
            for key, value in components.items():
                comp_parts.append(f'"{key}":{value}')
            parts.append(f'components:{{{",".join(comp_parts)}}}')
        
        return ','.join(parts)
    
    def _convert_lore_line_to_121_component(self, lore_text: str) -> str:
        """Convert a single lore line with color codes to 1.21 component format array"""
        import re
        import json
        
        if '§' not in lore_text:
            return json.dumps([{"text": lore_text, "italic": False}])
        
        # Color code mapping
        color_map = {
            '0': 'black', '1': 'dark_blue', '2': 'dark_green', '3': 'dark_aqua',
            '4': 'dark_red', '5': 'dark_purple', '6': 'gold', '7': 'gray',
            '8': 'dark_gray', '9': 'blue', 'a': 'green', 'b': 'aqua',
            'c': 'red', 'd': 'light_purple', 'e': 'yellow', 'f': 'white'
        }
        
        # Split by color codes
        parts = re.split(r'(§[0-9a-frlomn])', lore_text)
        components = []
        current_text = ""
        current_formatting = {"italic": False}
        
        for part in parts:
            if part.startswith('§'):
                # Color code - save current text if any
                if current_text:
                    comp = current_formatting.copy()
                    comp["text"] = current_text
                    components.append(comp)
                    current_text = ""
                
                code = part[1].lower()
                if code in color_map:
                    # Color code - reset formatting and set color
                    current_formatting = {"color": color_map[code], "italic": False}
                elif code == 'r':
                    # Reset - clear formatting
                    current_formatting = {"italic": False}
                elif code == 'l':
                    current_formatting["bold"] = True
                elif code == 'm':
                    current_formatting["strikethrough"] = True
                elif code == 'n':
                    current_formatting["underline"] = True
                elif code == 'o':
                    current_formatting["italic"] = True
            else:
                current_text += part
        
        # Add remaining text
        if current_text:
            comp = current_formatting.copy()
            comp["text"] = current_text
            components.append(comp)
        
        # Ensure italic:false on all components
        for comp in components:
            if "italic" not in comp:
                comp["italic"] = False
        
        return json.dumps(components)
    
    def _parse_item_array(self, array_content: str) -> list:
        """Parse comma-separated item array, handling nested structures (braces and brackets)
        
        Each item in the array is a complete object like {id:"...",Count:1b,...}
        Items are separated by commas, but only when we're at the top level (brace_depth == 0, bracket_depth == 0)
        """
        items = []
        current_item = ""
        brace_depth = 0
        bracket_depth = 0
        in_quotes = False
        quote_char = None
        i = 0
        
        while i < len(array_content):
            char = array_content[i]
            
            # Handle quotes (ignore braces/brackets/commas inside quotes)
            if char in ['"', "'"] and (i == 0 or array_content[i-1] != '\\'):
                if not in_quotes:
                    in_quotes = True
                    quote_char = char
                elif char == quote_char:
                    in_quotes = False
                    quote_char = None
                current_item += char
                i += 1
            elif not in_quotes:
                if char == '{':
                    brace_depth += 1
                    current_item += char
                    i += 1
                elif char == '}':
                    brace_depth -= 1
                    current_item += char
                    i += 1
                    # When we close a brace and return to depth 0, we've completed an item
                    # But wait for the comma separator before adding it
                elif char == '[':
                    bracket_depth += 1
                    current_item += char
                    i += 1
                elif char == ']':
                    bracket_depth -= 1
                    current_item += char
                    i += 1
                elif char == ',' and brace_depth == 0 and bracket_depth == 0:
                    # We're at top level, this comma separates items
                    if current_item.strip():
                        items.append(current_item.strip())
                    current_item = ""
                    i += 1
                    # Skip any whitespace after the comma
                    while i < len(array_content) and array_content[i] in [' ', '\n', '\t']:
                        i += 1
                else:
                    current_item += char
                    i += 1
            else:
                current_item += char
                i += 1
        
        # Add the last item (if any)
        if current_item.strip():
            items.append(current_item.strip())
        
        return items
    
    @log_method_call
    def _convert_drop_chances_to_121_format(self, nbt: str) -> str:
        """Convert HandDropChances/ArmorDropChances to drop_chances structure for 1.21.10"""
        import re
        
        drop_chances = {}
        has_armor_drops = False
        has_hand_drops = False
        
        # Process ArmorDropChances
        armor_drop_match = re.search(r'ArmorDropChances:\[([^\]]+)\]', nbt)
        if armor_drop_match:
            has_armor_drops = True
            armor_drops_str = armor_drop_match.group(1)
            armor_drops = [float(x.strip().rstrip('Ff')) for x in armor_drops_str.split(',') if x.strip()]
            slots = ['feet', 'legs', 'chest', 'head']
            for i, drop in enumerate(armor_drops):
                if i < len(slots):
                    drop_chances[slots[i]] = f'{drop:.3f}'
        
        # Process HandDropChances
        hand_drop_match = re.search(r'HandDropChances:\[([^\]]+)\]', nbt)
        if hand_drop_match:
            has_hand_drops = True
            hand_drops_str = hand_drop_match.group(1)
            hand_drops = [float(x.strip().rstrip('Ff')) for x in hand_drops_str.split(',') if x.strip()]
            slots = ['mainhand', 'offhand']
            for i, drop in enumerate(hand_drops):
                if i < len(slots):
                    drop_chances[slots[i]] = f'{drop:.3f}'
        
        # Replace with drop_chances structure
        if has_armor_drops or has_hand_drops:
            # Fill in missing slots with 0.000
            all_slots = ['feet', 'legs', 'chest', 'head', 'mainhand', 'offhand']
            for slot in all_slots:
                if slot not in drop_chances:
                    drop_chances[slot] = '0.000'
            
            # Build drop_chances structure
            drop_parts = [f'{slot}:{drop_chances[slot]}' for slot in all_slots]
            drop_chances_str = '{' + ','.join(drop_parts) + '}'
            
            # Remove old drop chance arrays
            if armor_drop_match:
                nbt = nbt[:armor_drop_match.start()] + nbt[armor_drop_match.end():]
            if hand_drop_match:
                hand_pos = nbt.find('HandDropChances:[')
                if hand_pos != -1:
                    hand_drop_match2 = re.search(r'HandDropChances:\[([^\]]+)\]', nbt)
                    if hand_drop_match2:
                        nbt = nbt[:hand_drop_match2.start()] + nbt[hand_drop_match2.end():]
            
            # Insert drop_chances
            if nbt.startswith('{'):
                nbt = '{drop_chances:' + drop_chances_str + (',' if nbt[1:].strip() else '') + nbt[1:]
            else:
                nbt = 'drop_chances:' + drop_chances_str + ',' + nbt
        
        return nbt
    
    def convert_block_nbt(self, nbt: str) -> str:
        """Convert block NBT data"""
        # Block-specific NBT conversions
        return nbt
    
    @log_method_call
    def convert_item_nbt(self, nbt: str, item_id: Optional[str] = None) -> str:
        """Convert item NBT data using structured parser for proper component format
        
        Args:
            nbt: NBT data string
            item_id: Optional item ID (e.g., 'minecraft:player_head' or 'golden_sword') to determine component naming
        """
        # Try structured parsing first (more reliable for components)
        try:
            # Parse SNBT string to structured Python object
            nbt_dict = NBTParser.parse_snbt(nbt)
            
            # Convert item using structured parser
            if isinstance(nbt_dict, dict):
                # Handle top-level SkullOwner (not in tag) - move it into tag for processing
                if 'SkullOwner' in nbt_dict:
                    if 'tag' not in nbt_dict:
                        nbt_dict['tag'] = {}
                    if 'SkullOwner' not in nbt_dict['tag']:
                        nbt_dict['tag']['SkullOwner'] = nbt_dict.pop('SkullOwner')
                
                converted_item = self._convert_item_dict_to_121_format(nbt_dict)
                if converted_item and 'components' in converted_item and converted_item['components']:
                    # Extract components and format for give command bracket notation
                    # Format depends on item type:
                    # - Namespaced items (minecraft:player_head) use minecraft:item_name and minecraft:lore
                    # - Non-namespaced items (golden_sword) use custom_name and lore
                    components = converted_item['components']
                    component_parts = []
                    
                    # Check if item ID is namespaced to determine component naming
                    # Use provided item_id or check converted_item
                    check_id = item_id or converted_item.get('id', '')
                    is_namespaced = ':' in check_id if check_id else False
                    
                    for key, value in components.items():
                        # Serialize the component value
                        import json
                        # For give commands:
                        # - Namespaced items: keep minecraft: prefix (minecraft:item_name, minecraft:lore)
                        # - Non-namespaced items: strip prefix (custom_name, lore)
                        # - minecraft:profile: always keep prefix
                        display_key = key
                        if key == 'minecraft:profile':
                            display_key = 'minecraft:profile'  # Always keep prefix for profile
                        elif is_namespaced:
                            # Namespaced items: use minecraft:item_name and minecraft:lore
                            if key == 'minecraft:item_name':
                                display_key = 'minecraft:item_name'
                            elif key == 'minecraft:lore':
                                display_key = 'minecraft:lore'
                            elif key == 'minecraft:custom_name':
                                display_key = 'minecraft:item_name'  # Convert custom_name to item_name for namespaced
                        else:
                            # Non-namespaced items: strip prefix
                            if key == 'minecraft:item_name':
                                display_key = 'custom_name'
                            elif key == 'minecraft:lore':
                                display_key = 'lore'
                            elif key == 'minecraft:custom_name':
                                display_key = 'custom_name'
                        
                        # For minecraft:profile, use SNBT format (no quotes)
                        # For other components, use JSON format (with quotes)
                        if key == 'minecraft:profile':
                            value_str = NBTSerializer.serialize_snbt(value)
                        else:
                            # For namespaced items (minecraft:item_name, minecraft:lore):
                            # - item_name: keep as array (even if single element) for multi-component names
                            # - lore: keep nested arrays [[{...}],[{...}]] (don't flatten)
                            # For non-namespaced items (custom_name, lore):
                            # - custom_name: if single element array, use the element directly
                            # - lore: flatten nested arrays to flat array
                            if is_namespaced:
                                # Namespaced items: keep structure as-is (arrays stay arrays, nested arrays stay nested)
                                # Don't modify value structure - keep nested arrays for lore
                                pass
                            else:
                                # Non-namespaced items: flatten/convert structure
                                if display_key == 'custom_name' and isinstance(value, list) and len(value) == 1:
                                    value = value[0]  # Use single object instead of array
                                elif display_key == 'lore' and isinstance(value, list):
                                    # Flatten nested arrays: [[{...}],[{...}]] -> [{...},{...}]
                                    flattened = []
                                    for item in value:
                                        if isinstance(item, list):
                                            flattened.extend(item)
                                        else:
                                            flattened.append(item)
                                    value = flattened
                            
                            # Use JSON format with proper key ordering (text first)
                            def reorder_obj(obj):
                                """Reorder object keys to put 'text' first"""
                                if isinstance(obj, dict) and "text" in obj:
                                    ordered = {"text": obj["text"]}
                                    for k, v in obj.items():
                                        if k != "text":
                                            ordered[k] = v
                                    return ordered
                                return obj
                            
                            def deep_reorder(value):
                                """Recursively reorder keys in nested structures"""
                                if isinstance(value, list):
                                    return [deep_reorder(item) for item in value]
                                elif isinstance(value, dict):
                                    return reorder_obj(value)
                                return value
                            
                            value = deep_reorder(value)
                            
                            # For non-namespaced items, add spaces after colons/commas for readability
                            # For namespaced items, keep compact format
                            if is_namespaced:
                                value_str = json.dumps(value, separators=(',', ':'))
                            else:
                                value_str = json.dumps(value, separators=(', ', ': '))
                        # Format as key=value (using display_key without minecraft: prefix)
                        component_parts.append(f'{display_key}={value_str}')
                    
                    if component_parts:
                        return '[' + ','.join(component_parts) + ']'
                    return ''
            
            # If not a dict or conversion failed, fall back to regex
        except Exception as e:
            # Fall back to regex-based conversion if structured parsing fails
            import traceback
            print(f"Warning: Structured item NBT parsing failed: {e}")
            traceback.print_exc()
            pass
        
        # Fallback: Check if NBT contains color codes and convert them
        if '§' in nbt and hasattr(self, '_nbt_color_converter'):
            nbt = self._nbt_color_converter(nbt, "item")
        return nbt
    
    def convert_sound_name(self, sound_name: str) -> str:
        """Convert sound names using lookup table"""
        # Remove minecraft: prefix if present for lookup
        clean_name = sound_name.replace('minecraft:', '')
        full_name = f"minecraft:{clean_name}"
        
        # Look up the conversion
        converted = self.lookups.sound_conversions.get(full_name, sound_name)
        
        # If no conversion found, try without minecraft: prefix
        if converted == sound_name:
            converted = self.lookups.sound_conversions.get(clean_name, sound_name)
        
        return converted
    
    def convert_particle_name(self, particle_name: str) -> str:
        """Convert particle names using lookup table"""
        # Remove minecraft: prefix if present for lookup
        clean_name = particle_name.replace('minecraft:', '')
        
        # Look up the conversion
        converted = self.lookups.particle_conversions.get(clean_name, particle_name)
        
        # Add minecraft: prefix if not present and not a custom particle
        if not converted.startswith('minecraft:') and ':' not in converted:
            converted = f'minecraft:{converted}'
        
        return converted
    
    def _reverse_block_id_formula(self, numeric_value: int) -> tuple[int, int]:
        """
        Reverse the block ID formula: numeric_value = block_id + (block_data * 4096)
        Returns (block_id, block_data)
        """
        # For now, let's try the formula: numeric_value = block_id + (block_data * 4096)
        # This is a common pattern in Minecraft
        block_data = numeric_value // 4096
        block_id = numeric_value % 4096
        return block_id, block_data
    
    def _get_block_name_from_numeric(self, numeric_value: int) -> str:
        """
        Convert a numeric block value to a block name using the lookup table
        """
        try:
            block_id, block_data = self._reverse_block_id_formula(numeric_value)
            
            # Look up the block name in our conversion table
            converted = self.lookups.block_conversions.get((str(block_id), block_data), None)
            
            if converted:
                # Add minecraft: prefix if not present
                if not converted.startswith('minecraft:') and ':' not in converted:
                    converted = f'minecraft:{converted}'
                return converted
            
            # If not found, return a fallback
            return f"minecraft:stone"  # Default fallback
            
        except (ValueError, TypeError):
            return "minecraft:stone"  # Default fallback

    def _find_enclosing_braces(self, text: str, index: int) -> Optional[Tuple[int, int]]:
        start = self._find_brace_start(text, index)
        if start is None:
            return None
        end = self._find_brace_end(text, start)
        if end is None:
            return None
        return start, end

    def _find_brace_start(self, text: str, index: int) -> Optional[int]:
        in_quotes = False
        quote_char = ''
        escape = False
        brace_depth = 0

        for i in range(index, -1, -1):
            char = text[i]

            if escape:
                escape = False
                continue

            if char == '\\':
                escape = True
                continue

            if char in ('"', "'"):
                if in_quotes and char == quote_char:
                    in_quotes = False
                elif not in_quotes:
                    in_quotes = True
                    quote_char = char
                continue

            if in_quotes:
                continue

            if char == '}':
                brace_depth += 1
            elif char == '{':
                if brace_depth == 0:
                    return i
                brace_depth -= 1

        return None

    def _find_brace_end(self, text: str, start_index: int) -> Optional[int]:
        in_quotes = False
        quote_char = ''
        escape = False
        brace_depth = 0

        for i in range(start_index, len(text)):
            char = text[i]

            if escape:
                escape = False
                continue

            if char == '\\':
                escape = True
                continue

            if char in ('"', "'"):
                if in_quotes and char == quote_char:
                    in_quotes = False
                elif not in_quotes:
                    in_quotes = True
                    quote_char = char
                continue

            if in_quotes:
                continue

            if char == '{':
                brace_depth += 1
            elif char == '}':
                brace_depth -= 1
                if brace_depth == 0:
                    return i + 1

        return None

    def _remove_damage_attribute(self, item_str: str) -> str:
        item_str = re.sub(r',\s*Damage:-?\d+(?:[bBsSlLfFdD])?', '', item_str, count=1)
        item_str = re.sub(r'Damage:-?\d+(?:[bBsSlLfFdD])?,\s*', '', item_str, count=1)
        item_str = re.sub(r'Damage:-?\d+(?:[bBsSlLfFdD])?', '', item_str, count=1)
        return item_str

class NBTParser:
    """Parse SNBT (String NBT) into structured Python objects"""
    
    @staticmethod
    def parse_snbt(snbt_str: str) -> Any:
        """Parse SNBT string into Python dict/list/primitives
        
        Returns:
            - dict for compounds: {key:value,...}
            - list for arrays: [value,...]
            - str, int, float, bool for primitives
        """
        snbt_str = snbt_str.strip()
        if not snbt_str:
            return {}
        
        method_logger.info("CALLED: NBTParser.parse_snbt")
        parser = NBTParser()
        
        # If it starts with {, parse as compound
        if snbt_str.startswith('{'):
            result, _ = parser._parse_compound(snbt_str, 0)
            return result if result is not None else {}
        # If it starts with [, parse as array
        elif snbt_str.startswith('['):
            result, _ = parser._parse_array(snbt_str, 0)
            return result if result is not None else []
        # Otherwise parse as value
        else:
            result, _ = parser._parse_value(snbt_str, 0)
            return result if result is not None else {}
    
    def _parse_value(self, text: str, start_pos: int) -> Tuple[Any, int]:
        """Parse a value starting at start_pos, return (value, next_position)"""
        # Skip whitespace
        pos = start_pos
        while pos < len(text) and text[pos] in ' \n\t':
            pos += 1
        
        if pos >= len(text):
            return None, pos
        
        # Compound (starts with {)
        if text[pos] == '{':
            result, offset = self._parse_compound(text, pos)
            return result, offset
        
        # Array (starts with [)
        if text[pos] == '[':
            result, offset = self._parse_array(text, pos)
            return result, offset
        
        # String (starts with " or ')
        if text[pos] in ['"', "'"]:
            result, offset = self._parse_string(text, pos)
            return result, offset
        
        # Number or boolean
        result, offset = self._parse_primitive(text, pos)
        return result, offset
    
    def _parse_compound(self, text: str, start_pos: int) -> Tuple[Dict[str, Any], int]:
        """Parse compound tag: {key:value,key:value,...}"""
        result = {}
        pos = start_pos + 1  # Skip opening {
        text_len = len(text)
        
        while pos < text_len:
            # Skip whitespace
            while pos < text_len and text[pos] in ' \n\t':
                pos += 1
            
            if pos >= text_len:
                break
            
            # Check for closing brace
            if text[pos] == '}':
                return result, pos + 1
            
            # Parse key
            key, pos = self._parse_key(text, pos)
            if key is None:
                break
            
            # Skip whitespace and colon
            while pos < text_len and text[pos] in ' \n\t:':
                pos += 1
            
            # Parse value
            value, new_pos = self._parse_value(text, pos)
            if value is not None:
                result[key] = value
                pos = new_pos
            else:
                # If parsing failed, advance position by 1 to avoid infinite loop
                pos += 1
            
            # Skip whitespace and comma
            while pos < text_len and text[pos] in ' \n\t,':
                pos += 1
        
        return result, pos
    
    def _parse_array(self, text: str, start_pos: int) -> Tuple[List[Any], int]:
        """Parse array tag: [value,value,...]"""
        result = []
        pos = start_pos + 1  # Skip opening [
        text_len = len(text)
        brace_depth = 0
        bracket_depth = 1  # Already inside opening bracket
        in_quotes = False
        quote_char = None
        
        current_item_start = pos
        
        while pos < text_len:
            char = text[pos]
            
            # Handle quotes
            if char in ['"', "'"] and (pos == 0 or text[pos-1] != '\\'):
                if not in_quotes:
                    in_quotes = True
                    quote_char = char
                elif char == quote_char:
                    in_quotes = False
                    quote_char = None
            
            elif not in_quotes:
                if char == '{':
                    brace_depth += 1
                elif char == '}':
                    brace_depth -= 1
                elif char == '[':
                    bracket_depth += 1
                elif char == ']':
                    bracket_depth -= 1
                    if bracket_depth == 0:
                        # End of array
                        if current_item_start < pos:
                            item_text = text[current_item_start:pos].strip()
                            if item_text:
                                value, _ = self._parse_value(text, current_item_start)
                                if value is not None:
                                    result.append(value)
                        return result, pos + 1
                elif char == ',' and brace_depth == 0 and bracket_depth == 1:
                    # Item separator at top level
                    if current_item_start < pos:
                        item_text = text[current_item_start:pos].strip()
                        if item_text:
                            value, _ = self._parse_value(text, current_item_start)
                            if value is not None:
                                result.append(value)
                    current_item_start = pos + 1
            
            pos += 1
        
        return result, pos
    
    def _parse_key(self, text: str, start_pos: int) -> Tuple[Optional[str], int]:
        """Parse a key (identifier or quoted string)"""
        text = text[start_pos:].lstrip()
        if not text:
            return None, start_pos
        
        # Quoted key
        if text[0] in ['"', "'"]:
            key, pos = self._parse_string(text, 0)
            return key, start_pos + pos
        
        # Unquoted key (identifier)
        key_end = 0
        while key_end < len(text) and (text[key_end].isalnum() or text[key_end] in '_.-'):
            key_end += 1
        
        if key_end > 0:
            return text[:key_end], start_pos + key_end
        
        return None, start_pos
    
    def _parse_string(self, text: str, start_pos: int) -> Tuple[str, int]:
        """Parse a string value (handles both " and ' quotes)"""
        if start_pos >= len(text):
            return "", start_pos
        
        quote_char = text[start_pos]
        pos = start_pos + 1
        result = []
        text_len = len(text)
        
        while pos < text_len:
            char = text[pos]
            
            # Handle escape sequences
            if char == '\\' and pos + 1 < text_len:
                next_char = text[pos + 1]
                if next_char in ['\\', quote_char]:
                    result.append(next_char)
                    pos += 2
                    continue
            
            # Handle closing quote
            if char == quote_char:
                return ''.join(result), pos + 1
            
            result.append(char)
            pos += 1
        
        # Unclosed string
        return ''.join(result), pos
    
    def _parse_primitive(self, text: str, start_pos: int) -> Tuple[Any, int]:
        """Parse primitive value (number, boolean, or identifier)"""
        if start_pos >= len(text):
            return None, start_pos
        
        # Boolean
        if start_pos + 4 <= len(text) and text[start_pos:start_pos+4] == 'true':
            return True, start_pos + 4
        if start_pos + 5 <= len(text) and text[start_pos:start_pos+5] == 'false':
            return False, start_pos + 5
        
        # Number (int or float)
        pos = start_pos
        has_dot = False
        has_sign = False
        
        # Optional sign
        if pos < len(text) and text[pos] in '+-':
            has_sign = True
            pos += 1
        
        num_start = pos
        
        # Digits and optional decimal point
        while pos < len(text):
            char = text[pos]
            if char.isdigit():
                pos += 1
            elif char == '.' and not has_dot:
                has_dot = True
                pos += 1
            elif char.lower() in 'bbslfd':  # Type suffix (1b, 2s, 3.0f, etc.)
                break
            else:
                break
        
        if pos > num_start:
            num_str = text[num_start:pos]
            try:
                if has_dot:
                    return float(num_str), pos
                else:
                    return int(num_str), pos
            except ValueError:
                pass
        
        # Identifier (unquoted string, like minecraft:stone)
        pos = start_pos
        while pos < len(text) and (text[pos].isalnum() or text[pos] in '_:.-'):
            pos += 1
        
        if pos > start_pos:
            return text[start_pos:pos], pos
        
        return None, start_pos


class NBTSerializer:
    """Serialize Python objects back to SNBT format"""
    
    @staticmethod
    def serialize_snbt(obj: Any, indent: int = 0) -> str:
        """Convert Python dict/list/primitives to SNBT string"""
        method_logger.info("CALLED: NBTSerializer.serialize_snbt")
        serializer = NBTSerializer()
        result = serializer._serialize_value(obj, 0)
        return result
    
    def _serialize_value(self, value: Any, indent: int, key: str = None, parent_key: str = None) -> str:
        """Serialize a value to SNBT format
        
        Args:
            value: Value to serialize
            indent: Current indentation level
            key: Optional key name (for boolean detection)
            parent_key: Optional parent key name (for drop_chances formatting)
        """
        if isinstance(value, dict):
            return self._serialize_compound(value, indent, parent_key=key or parent_key)
        elif isinstance(value, list):
            return self._serialize_array(value, indent, parent_key=parent_key)
        elif isinstance(value, str):
            return self._serialize_string(value)
        elif isinstance(value, bool):
            return 'true' if value else 'false'
        elif isinstance(value, (int, float)):
            # Check if this is a boolean field that should have 'b' suffix
            if key and value in (0, 1):
                # Common boolean fields in Minecraft NBT
                boolean_fields = ['CustomNameVisible', 'NoAI', 'PersistenceRequired', 'CanPickUpLoot', 
                                 'Invulnerable', 'Silent', 'Glowing', 'OnGround', 'Invisible']
                if any(key.startswith(field) for field in boolean_fields):
                    return f'{int(value)}b'
            # Format floats with 3 decimal places for drop_chances
            if isinstance(value, float) and (key == 'drop_chances' or parent_key == 'drop_chances'):
                return f'{value:.3f}'
            return str(value)
        else:
            return str(value)
    
    def _serialize_compound(self, compound: Dict[str, Any], indent: int, parent_key: str = None) -> str:
        """Serialize compound tag"""
        if not compound:
            return '{}'
        
        parts = []
        for key, value in compound.items():
            # Quote key if needed (contains special chars, starts with number, or contains colon)
            if ':' in key or not key.replace('_', '').replace('-', '').replace('.', '').isalnum() or (key and key[0].isdigit()):
                key_str = self._serialize_string(key)
            else:
                key_str = key
            
            # For components in entity NBT, serialize component values as JSON (quoted keys)
            # This applies to minecraft:custom_name, minecraft:lore, etc.
            if parent_key == 'components' or (parent_key and 'components' in parent_key):
                # Serialize component values as JSON
                import json
                value_str = json.dumps(value, separators=(',', ':'))
            else:
                # Pass parent key context for drop_chances formatting
                if parent_key == 'drop_chances' or key == 'drop_chances':
                    value_str = self._serialize_value(value, indent + 1, key=key, parent_key='drop_chances')
                else:
                    value_str = self._serialize_value(value, indent + 1, key=key, parent_key=parent_key)
            parts.append(f'{key_str}:{value_str}')
        
        return '{' + ','.join(parts) + '}'
    
    def _serialize_array(self, array: List[Any], indent: int, parent_key: str = None) -> str:
        """Serialize array tag"""
        if not array:
            return '[]'
        
        parts = [self._serialize_value(item, indent + 1, parent_key=parent_key) for item in array]
        return '[' + ','.join(parts) + ']'
    
    def _serialize_string(self, value: str) -> str:
        """Serialize string (use double quotes, escape as needed)"""
        # Escape backslashes and quotes
        escaped = value.replace('\\', '\\\\').replace('"', '\\"')
        return f'"{escaped}"'


class NBTConverterRegistry:
    """Registry for NBT component converters - extensible system"""
    
    def __init__(self):
        self.converters = {}
    
    def register(self, component_name: str, converter_func):
        """Register a converter function for a specific NBT component
        
        Args:
            component_name: Name of the NBT component (e.g., 'ArmorItems', 'HandItems')
            converter_func: Function that takes (nbt_dict, context) and returns modified nbt_dict
        """
        self.converters[component_name] = converter_func
    
    def convert(self, nbt_dict: Dict[str, Any], context: str = "entity") -> Dict[str, Any]:
        """Apply all registered converters to the NBT structure
        
        Args:
            nbt_dict: Parsed NBT structure (dict)
            context: Conversion context ('entity', 'item', etc.)
        
        Returns:
            Modified NBT structure
        """
        result = nbt_dict.copy()
        
        # Debug: Show registered converters
        import sys
        print(f"DEBUG NBTConverterRegistry: Registered converters = {list(self.converters.keys())}", file=sys.stderr)
        
        # Apply converters in order
        # Some converters check for the component themselves (like CustomName, Inventory)
        # Others only run if the component exists (like ArmorItems)
        for component_name, converter_func in self.converters.items():
            try:
                # Always call converters that handle their own checking (CustomName, Inventory, SelectedItem)
                # For others, only call if the component exists
                if component_name in ['CustomName', 'Inventory', 'SelectedItem']:
                    print(f"DEBUG NBTConverterRegistry: Calling converter for {component_name}", file=sys.stderr)
                    result = converter_func(result, context)
                    if component_name == 'Inventory' and 'Inventory' in result:
                        print(f"DEBUG NBTConverterRegistry: After {component_name} conversion, Inventory = {result['Inventory']}", file=sys.stderr)
                    if component_name == 'SelectedItem' and 'SelectedItem' in result:
                        print(f"DEBUG NBTConverterRegistry: After {component_name} conversion, SelectedItem = {result['SelectedItem']}", file=sys.stderr)
                elif component_name in result:
                    result = converter_func(result, context)
            except Exception as e:
                # Log errors for debugging
                if component_name in result or component_name in ['CustomName', 'Inventory']:
                    print(f"Warning: Error converting {component_name}: {e}")
                    import traceback
                    traceback.print_exc()
        
        return result


class CommandParser:
    """Parse and split commands into components"""
    
    @staticmethod
    def parse_command(command: str) -> Dict[str, Any]:
        """Parse a command string into its components"""
        command = command.strip()
        if command.startswith('/'):
            command = command[1:]
        
        # Use a more robust parsing method for Minecraft commands
        parts = CommandParser._parse_minecraft_command(command)
        
        if not parts:
            return {'command': '', 'args': []}
        
        return {
            'command': parts[0].lower(),
            'args': parts[1:] if len(parts) > 1 else []
        }
    
    @staticmethod
    def _parse_minecraft_command(command: str) -> List[str]:
        """Parse Minecraft command with proper handling of NBT data"""
        parts = []
        current_part = ""
        in_quotes = False
        quote_char = None
        brace_level = 0
        bracket_level = 0
        i = 0
        
        while i < len(command):
            char = command[i]
            
            # Handle quotes
            if char in ['"', "'"] and (i == 0 or command[i-1] != '\\'):
                if not in_quotes:
                    in_quotes = True
                    quote_char = char
                elif char == quote_char:
                    in_quotes = False
                    quote_char = None
                current_part += char
            
            # Handle braces and brackets (for NBT data)
            elif char == '{' and not in_quotes:
                brace_level += 1
                current_part += char
            elif char == '}' and not in_quotes:
                brace_level -= 1
                current_part += char
            elif char == '[' and not in_quotes:
                bracket_level += 1
                current_part += char
            elif char == ']' and not in_quotes:
                bracket_level -= 1
                current_part += char
            
            # Handle spaces (only split if not in quotes and not in braces/brackets)
            elif char == ' ' and not in_quotes and brace_level == 0 and bracket_level == 0:
                if current_part.strip():
                    parts.append(current_part.strip())
                current_part = ""
            
            else:
                current_part += char
            
            i += 1
        
        # Add the last part
        if current_part.strip():
            parts.append(current_part.strip())
        
        return parts

class CommandConverter:
    """Main command conversion class"""
    
    def __init__(self, lookups: LookupTables):
        self.lookups = lookups
        self.param_converters = ParameterConverters(lookups)
        self.parser = CommandParser()
        
        # Register command conversion methods
        self.command_handlers = {
            'summon': self._convert_summon,
            'execute': self._convert_execute,
            'testfor': self._convert_testfor,
            'testforblock': self._convert_testforblock,
            'entitydata': self._convert_entitydata,
            'blockdata': self._convert_blockdata,
            'setblock': self._convert_setblock,
            'fill': self._convert_fill,
            'scoreboard': self._convert_scoreboard,
            'effect': self._convert_effect,
            'playsound': self._convert_playsound,
            'title': self._convert_title,
            'tellraw': self._convert_tellraw,
            'kill': self._convert_kill,
            'tp': self._convert_tp,
            'teleport': self._convert_tp,
            'particle': self._convert_particle,
            'say': self._convert_say,
            'clear': self._convert_clear,
            'clone': self._convert_clone,
            'give': self._convert_give,
            'tag': self._convert_tag,
            'project': lambda args: self._convert_project_clock_script('project', args),
            'clock': lambda args: self._convert_project_clock_script('clock', args),
            'script': lambda args: self._convert_project_clock_script('script', args),
        }
        
        # Set up the NBT color converter reference for ParameterConverters
        self.param_converters._nbt_color_converter = lambda nbt, context: self._convert_nbt_colors(nbt, context)
    
    @log_method_call
    def convert_command(self, command: str) -> str:
        """Convert a single command from 1.12 to 1.20 format"""
        parsed = self.parser.parse_command(command)
        command_name = parsed['command']
        args = parsed['args']
        
        # Handle known commands
        if command_name in self.command_handlers:
            handler = self.command_handlers[command_name]
            converted_command = handler(args)
        else:
            # For unknown commands, try to convert parameters
            converted_command = self._convert_unknown_command(command_name, args)
        
        # Apply color code conversion if needed
        if '§' in converted_command:
            converted_command = self._convert_color_codes_to_json(converted_command)
        
        return converted_command
    
    @log_method_call
    def _convert_summon(self, args: List[str]) -> str:
        """Convert summon command"""
        if len(args) < 1:
            return "summon"
        
        entity_type = self.param_converters.convert_entity_name(args[0])
        result = f"summon {entity_type}"
        
        # Handle coordinates
        if len(args) >= 4:
            x = self.param_converters.convert_coordinate(args[1])
            y = self.param_converters.convert_coordinate(args[2])
            z = self.param_converters.convert_coordinate(args[3])
            result += f" {x} {y} {z}"
        
        # Handle NBT data
        if len(args) >= 5:
            nbt = self.param_converters.convert_entity_nbt(args[4])
            result += f" {nbt}"
        
        return result
    
    @log_method_call
    def _convert_execute(self, args: List[str]) -> str:
        """Convert execute command from 1.12 to 1.20 format with proper nested chain handling"""
        if len(args) < 4:
            return "execute"
        
        # For now, use the simple approach for basic execute commands
        # Check if this is a detect command
        if len(args) >= 5 and args[4] == "detect":
            return self._convert_execute_detect_simple(args)
        
        # Regular execute command
        target = self.param_converters.convert_selector(args[0])
        x = self.param_converters.convert_coordinate(args[1])
        y = self.param_converters.convert_coordinate(args[2])
        z = self.param_converters.convert_coordinate(args[3])

        def is_zero_offset(coord):
            # Accepts ~, ~0, ~0.0, or 0 as zero offset
            return coord in ('~', '~0', '~0.0', '0', '0.0')

        result = f"execute as {target} at @s"
        if not (is_zero_offset(x) and is_zero_offset(y) and is_zero_offset(z)):
            result += f" positioned {x} {y} {z}"
        
        # Handle the nested command
        if len(args) >= 5:
            nested_command = ' '.join(args[4:])
            converted_nested = self.convert_command(nested_command)
            result += f" run {converted_nested}"
        
        return result
    
    def _convert_execute_detect_simple(self, args: List[str]) -> str:
        """Convert execute detect subcommand (simple version)"""
        if len(args) < 10:
            return "execute"
        
        # Old 1.12 format: execute <target> <x1> <y1> <z1> detect <x2> <y2> <z2> <block> <variant> <command>
        # New 1.20 format: execute as <target> at @s positioned <x1> <y1> <z1> if block <x2> <y2> <z2> <block> run <command>
        
        target = self.param_converters.convert_selector(args[0])
        x1 = self.param_converters.convert_coordinate(args[1])
        y1 = self.param_converters.convert_coordinate(args[2])
        z1 = self.param_converters.convert_coordinate(args[3])
        # args[4] is "detect"
        x2 = self.param_converters.convert_coordinate(args[5])
        y2 = self.param_converters.convert_coordinate(args[6])
        z2 = self.param_converters.convert_coordinate(args[7])
        block = self.param_converters.convert_block_name(args[8], args[9] if len(args) > 9 else '0')
        
        result = f"execute as {target} at @s positioned {x1} {y1} {z1} if block {x2} {y2} {z2} {block}"
        
        # Handle the command that comes after detect
        if len(args) >= 11:
            # Convert the nested command
            # Join all remaining args, preserving NBT data as a single argument
            nested_command = ' '.join(args[10:])
            converted_nested = self.convert_command(nested_command)
            result += f" run {converted_nested}"
        elif len(args) == 10:
            # No nested command provided, just return the execute if block part
            pass
        
        return result
    
    @log_method_call
    def _convert_execute_chain(self, args: List[str]) -> str:
        """Convert a complete execute chain with proper offset stacking"""
        if len(args) < 4:
            return "execute"
        
        # Parse the execute chain into components
        chain_components = self._parse_execute_chain(args)
        
        # Build the converted command with cumulative offsets
        return self._build_execute_chain(chain_components)
    
    def _parse_execute_chain(self, args: List[str]) -> List[Dict[str, Any]]:
        """Parse an execute chain into its components"""
        components = []
        i = 0
        
        # Check if this is a detect command first
        if len(args) >= 5 and args[4] == "detect":
            return [self._parse_execute_detect_component(args, 0)]
        
        # Check if this is a regular execute command
        if len(args) >= 4:
            return [self._parse_execute_position_component(args, 0)]
        
        # If we can't parse it, treat as unknown command
        return [{
            'type': 'command',
            'command': ' '.join(args)
        }]
    
    def _parse_execute_component(self, args: List[str], start_index: int) -> Dict[str, Any]:
        """Parse a single execute component"""
        if start_index >= len(args):
            return None
        
        # Check if this is a detect command
        if start_index + 4 < len(args) and args[start_index + 4] == "detect":
            return self._parse_execute_detect_component(args, start_index)
        else:
            return self._parse_execute_position_component(args, start_index)
    
    def _parse_execute_position_component(self, args: List[str], start_index: int) -> Dict[str, Any]:
        """Parse execute <target> <x> <y> <z> <command>"""
        if start_index + 4 >= len(args):
            return None
        
        target = self.param_converters.convert_selector(args[start_index])
        x = self.param_converters.convert_coordinate(args[start_index + 1])
        y = self.param_converters.convert_coordinate(args[start_index + 2])
        z = self.param_converters.convert_coordinate(args[start_index + 3])
        
        # Check if the next argument is another execute command
        next_index = start_index + 4
        if next_index < len(args) and args[next_index] == "execute":
            return {
                'type': 'position',
                'target': target,
                'x': x,
                'y': y,
                'z': z,
                'next_index': next_index
            }
        else:
            # This is the final command
            command = ' '.join(args[next_index:])
            return {
                'type': 'position',
                'target': target,
                'x': x,
                'y': y,
                'z': z,
                'command': command,
                'next_index': len(args)
            }
    
    def _parse_execute_detect_component(self, args: List[str], start_index: int) -> Dict[str, Any]:
        """Parse execute <target> <x1> <y1> <z1> detect <x2> <y2> <z2> <block> <variant> <command>"""
        if start_index + 10 >= len(args):
            return None
        
        target = self.param_converters.convert_selector(args[start_index])
        x1 = self.param_converters.convert_coordinate(args[start_index + 1])
        y1 = self.param_converters.convert_coordinate(args[start_index + 2])
        z1 = self.param_converters.convert_coordinate(args[start_index + 3])
        # args[start_index + 4] is "detect"
        x2 = self.param_converters.convert_coordinate(args[start_index + 5])
        y2 = self.param_converters.convert_coordinate(args[start_index + 6])
        z2 = self.param_converters.convert_coordinate(args[start_index + 7])
        block = self.param_converters.convert_block_name(args[start_index + 8], args[start_index + 9])
        
        # Check if the next argument is another execute command
        next_index = start_index + 10
        if next_index < len(args) and args[next_index] == "execute":
            return {
                'type': 'detect',
                'target': target,
                'x1': x1,
                'y1': y1,
                'z1': z1,
                'x2': x2,
                'y2': y2,
                'z2': z2,
                'block': block,
                'next_index': next_index
            }
        else:
            # This is the final command
            command = ' '.join(args[next_index:])
            return {
                'type': 'detect',
                'target': target,
                'x1': x1,
                'y1': y1,
                'z1': z1,
                'x2': x2,
                'y2': y2,
                'z2': z2,
                'block': block,
                'command': command,
                'next_index': len(args)
            }
    
    def _build_execute_chain(self, components: List[Dict[str, Any]]) -> str:
        """Build the converted execute chain with cumulative offsets"""
        if not components:
            return "execute"
        
        # Start with the first component
        first_component = components[0]
        result = "execute"
        
        # Track cumulative offsets
        cumulative_x = 0
        cumulative_y = 0
        cumulative_z = 0
        
        # Process each component
        for i, component in enumerate(components):
            if component['type'] == 'position':
                # Handle position component
                if i == 0:
                    # First component: set target and initial position
                    result += f" as {component['target']} at @s"
                    
                    # Add initial positioning
                    x, y, z = self._parse_coordinate(component['x']), self._parse_coordinate(component['y']), self._parse_coordinate(component['z'])
                    cumulative_x += x
                    cumulative_y += y
                    cumulative_z += z
                    result += f" positioned {component['x']} {component['y']} {component['z']}"
                else:
                    # Subsequent component: add to cumulative offset
                    x, y, z = self._parse_coordinate(component['x']), self._parse_coordinate(component['y']), self._parse_coordinate(component['z'])
                    cumulative_x += x
                    cumulative_y += y
                    cumulative_z += z
                    result += f" positioned {component['x']} {component['y']} {component['z']}"
                
                # If this has a command, it's the final component
                if 'command' in component:
                    converted_command = self.convert_command(component['command'])
                    result += f" run {converted_command}"
                    break
                    
            elif component['type'] == 'detect':
                # Handle detect component
                if i == 0:
                    # First component: set target and initial position
                    result += f" as {component['target']} at @s"
                    
                    # Add initial positioning
                    x, y, z = self._parse_coordinate(component['x1']), self._parse_coordinate(component['y1']), self._parse_coordinate(component['z1'])
                    cumulative_x += x
                    cumulative_y += y
                    cumulative_z += z
                    result += f" positioned {component['x1']} {component['y1']} {component['z1']}"
                else:
                    # Subsequent component: add to cumulative offset
                    x, y, z = self._parse_coordinate(component['x1']), self._parse_coordinate(component['y1']), self._parse_coordinate(component['z1'])
                    cumulative_x += x
                    cumulative_y += y
                    cumulative_z += z
                    result += f" positioned {component['x1']} {component['y1']} {component['z1']}"
                
                # Add block detection
                result += f" if block {component['x2']} {component['y2']} {component['z2']} {component['block']}"
                
                # If this has a command, it's the final component
                if 'command' in component:
                    converted_command = self.convert_command(component['command'])
                    result += f" run {converted_command}"
                    break
                    
            elif component['type'] == 'command':
                # Final command component
                converted_command = self.convert_command(component['command'])
                result += f" run {converted_command}"
                break
        
        return result
    
    def _parse_coordinate(self, coord: str) -> float:
        """Parse a coordinate string to get its numeric value for offset calculation"""
        if coord == '~':
            return 0.0
        elif coord.startswith('~'):
            try:
                return float(coord[1:])
            except ValueError:
                return 0.0
        else:
            try:
                return float(coord)
            except ValueError:
                return 0.0
    
    def _add_nbt_to_selector(self, selector: str, nbt: str) -> str:
        """Add NBT data as a selector parameter: @s[...] becomes @s[...,nbt={...}]"""
        # selector is like "@e[type=skeleton,tag=test]" or "@s"
        # nbt is like "{Health:500.0f}"
        
        if '[' in selector and ']' in selector:
            # Selector has parameters, insert nbt before the closing bracket
            closing_bracket = selector.rfind(']')
            return f"{selector[:closing_bracket]},nbt={nbt}]"
        else:
            # Selector has no parameters, add them
            return f"{selector}[nbt={nbt}]"
    
    def _convert_testfor(self, args: List[str]) -> str:
        """Convert testfor command to execute if entity"""
        if len(args) < 1:
            return "execute if entity @s"
        
        selector = self.param_converters.convert_selector(args[0])
        
        # Handle NBT data parameter (args[1] if present)
        # NBT should be added as a selector parameter: @s[nbt={...}]
        if len(args) >= 2:
            nbt = args[1]
            # Convert Inventory to SelectedItem for testfor commands
            # Inventory is an array: Inventory:[{...}] -> SelectedItem:{...} (remove array, use first item)
            import re
            if 'Inventory:' in nbt or 'inventory:' in nbt:
                # Find Inventory: pattern and convert to SelectedItem
                # Pattern: Inventory:[{...}] -> SelectedItem:{...}
                inventory_pattern = re.compile(r'Inventory:\s*\[(\{[^\]]+\})\]', re.IGNORECASE)
                match = inventory_pattern.search(nbt)
                if match:
                    # Extract the first item from the array
                    first_item = match.group(1)
                    # Replace Inventory:[{...}] with SelectedItem:{...}
                    nbt = inventory_pattern.sub(f'SelectedItem:{first_item}', nbt)
                    # Also handle case where Inventory: might be lowercase
                    nbt = re.sub(r'inventory:\s*\[(\{[^\]]+\})\]', f'SelectedItem:{first_item}', nbt, flags=re.IGNORECASE)
            
            nbt = self.param_converters.convert_entity_nbt(nbt)
            # Insert nbt parameter into the selector
            selector = self._add_nbt_to_selector(selector, nbt)
        
        return f"execute if entity {selector}"
    
    def _convert_testforblock(self, args: List[str]) -> str:
        """Convert testforblock command to execute if block"""
        if len(args) < 3:
            return "execute if block ~ ~ ~ air"
        
        x = self.param_converters.convert_coordinate(args[0])
        y = self.param_converters.convert_coordinate(args[1])
        z = self.param_converters.convert_coordinate(args[2])
        block = self.param_converters.convert_block_name(args[3], args[4] if len(args) > 4 else '0')
        
        result = f"execute if block {x} {y} {z} {block}"
        
        # Handle NBT data - append directly after block name
        if len(args) >= 6:
            nbt = self.param_converters.convert_block_nbt(args[5])
            result += nbt
        
        return result
    
    @log_method_call
    def _convert_entitydata(self, args: List[str]) -> str:
        """Convert entitydata command to execute as for multiple targets"""
        if len(args) < 2:
            return "execute as"
        
        selector = self.param_converters.convert_selector(args[0])
        nbt = self.param_converters.convert_entity_nbt(args[1])
        
        # Check if selector targets multiple entities
        # If it's a single entity selector (@p, @r, @s) or specific player name, use data merge
        if selector in ['@p', '@r', '@s'] or (not selector.startswith('@') and '[' not in selector):
            return f"data merge entity {selector} {nbt}"
        else:
            # For multiple entity selectors (@e, @a), use execute as
            return f"execute as {selector} run data merge entity @s {nbt}"
    
    def _convert_setblock(self, args: List[str]) -> str:
        """Convert setblock command"""
        if len(args) < 4:
            return "setblock"
        
        x = self.param_converters.convert_coordinate(args[0])
        y = self.param_converters.convert_coordinate(args[1])
        z = self.param_converters.convert_coordinate(args[2])
        block = self.param_converters.convert_block_name(args[3], args[4] if len(args) > 4 else '0')
        
        result = f"setblock {x} {y} {z} {block}"
        
        # Handle additional parameters (like replace, destroy, keep)
        if len(args) >= 6:
            if args[5] in ['replace', 'destroy', 'keep']:
                result += f" {args[5]}"
            else:
                # Handle NBT data
                nbt = self.param_converters.convert_block_nbt(args[5])
                result += nbt
        
        return result
    
    def _convert_fill(self, args: List[str]) -> str:
        """Convert fill command
        
        1.12 Format:
        - fill x1 y1 z1 x2 y2 z2 ID1 data1 [action] ID2 data2
        - fill x1 y1 z1 x2 y2 z2 ID1 data1
        
        1.21 Format:
        - fill x1 y1 z1 x2 y2 z2 block_name1 [action] block_name2
        - fill x1 y1 z1 x2 y2 z2 block_name1
        """
        if len(args) < 7:
            return "fill"
        
        x1 = self.param_converters.convert_coordinate(args[0])
        y1 = self.param_converters.convert_coordinate(args[1])
        z1 = self.param_converters.convert_coordinate(args[2])
        x2 = self.param_converters.convert_coordinate(args[3])
        y2 = self.param_converters.convert_coordinate(args[4])
        z2 = self.param_converters.convert_coordinate(args[5])
        
        # First block: ID1 (args[6]) and data1 (args[7])
        block1_id = args[6]
        block1_data = args[7] if len(args) > 7 else '0'
        block1 = self.param_converters.convert_block_name(block1_id, block1_data)
        
        result = f"fill {x1} {y1} {z1} {x2} {y2} {z2} {block1}"
        
        # Check if there's an action and second block
        # Format: ID1 data1 [action] ID2 data2
        # So if args[8] is an action keyword, then args[9] and args[10] are ID2 and data2
        if len(args) >= 9:
            if args[8] in ['replace', 'destroy', 'keep', 'outline', 'hollow']:
                # args[8] is the action, args[9] and args[10] are the second block
                action = args[8]
                result += f" {action}"
                
                if len(args) >= 11:
                    # Second block: ID2 (args[9]) and data2 (args[10])
                    block2_id = args[9]
                    block2_data = args[10] if len(args) > 10 else '0'
                    block2 = self.param_converters.convert_block_name(block2_id, block2_data)
                    result += f" {block2}"
        
        return result
    
    def _convert_project_clock_script(self, command_name: str, args: List[str]) -> str:
        """Convert project, clock, or script commands
        
        Format: {x},{y},{z},[block],[data],{delay};
        - Multiple entries separated by semicolons (;)
        - x, y, z, block are required
        - data is optional (defaults to 0)
        - delay is optional
        - Trailing text after last semicolon is preserved
        
        Example:
        Input:  project 0,1,0,stained_glass,15,10;
        Output: project 0,1,0,red_stained_glass,10;
        """
        if not args:
            return command_name
        
        # Join all args back together to get the full parameter string
        param_string = ' '.join(args)
        
        # Split by semicolons to get individual entries
        parts = param_string.split(';')
        
        converted_parts = []
        trailing_text = ""
        
        for i, part in enumerate(parts):
            part = part.strip()
            if not part:
                continue
            
            # Check if this is the last part and doesn't look like coordinates,block,data,delay
            # If it doesn't have commas or has text that doesn't match the pattern, it's trailing text
            if i == len(parts) - 1 and (',' not in part or not any(char.isdigit() or char == '-' for char in part.split(',')[0] if part.split(','))):
                # This might be trailing text - check if previous parts were valid
                if converted_parts:
                    trailing_text = part
                    break
            
            # Parse: x,y,z,block,data,delay
            # x, y, z, block are required; data and delay are optional
            components = [c.strip() for c in part.split(',')]
            
            if len(components) < 4:
                # Not enough components, might be trailing text
                if i == len(parts) - 1 and converted_parts:
                    trailing_text = part
                    break
                # Otherwise, skip invalid entries
                continue
            
            x = components[0]
            y = components[1]
            z = components[2]
            block = components[3].lower()  # Convert to lowercase for lookup
            
            # Determine data and delay
            # Format: x,y,z,block,data,delay
            # - 4 components: x, y, z, block (data=0, no delay)
            # - 5 components: x, y, z, block, delay (data=0)
            # - 6 components: x, y, z, block, data, delay
            data = '0'  # Default data
            delay = None
            
            if len(components) == 4:
                # x, y, z, block only (data=0, no delay)
                data = '0'
                delay = None
            elif len(components) == 5:
                # x, y, z, block, delay (data=0)
                data = '0'
                delay = components[4]
            elif len(components) >= 6:
                # x, y, z, block, data, delay
                data = components[4]
                delay = components[5]
                # Check if there's extra content after delay (trailing text)
                if len(components) > 6 and i == len(parts) - 1:
                    trailing_text = ','.join(components[6:])
                    break
            
            # Convert block name using legacy.json
            # First, look up block name -> ID in ID_Lookups.csv
            # Then use legacy.json with id:data format
            converted_block = self.param_converters.convert_block_name_legacy(block, data)
            # Remove minecraft: prefix if present (these commands might not use it)
            if converted_block.startswith('minecraft:'):
                converted_block = converted_block[10:]
            
            # Reconstruct: x,y,z,converted_block,delay (if delay exists)
            if delay is not None:
                converted_parts.append(f"{x},{y},{z},{converted_block},{delay}")
            else:
                converted_parts.append(f"{x},{y},{z},{converted_block}")
        
        # Reconstruct the command
        result = f"{command_name} {';'.join(converted_parts)}"
        if trailing_text:
            # Check if there was a space after the last semicolon in the original
            last_semicolon_idx = param_string.rfind(';')
            if last_semicolon_idx >= 0 and last_semicolon_idx + 1 < len(param_string):
                char_after_semicolon = param_string[last_semicolon_idx + 1]
                if char_after_semicolon == ' ':
                    result += f"; {trailing_text}"
                else:
                    result += f";{trailing_text}"
            else:
                result += f";{trailing_text}"
        elif converted_parts:
            result += ";"  # Add semicolon if there are parts but no trailing text
        
        return result
    
    def _convert_scoreboard(self, args: List[str]) -> str:
        """Convert scoreboard command"""
        if len(args) < 2:
            return "scoreboard"
        
        subcommand = args[0]
        if subcommand == "players":
            return self._convert_scoreboard_players(args[1:])
        
        return f"scoreboard {' '.join(args)}"
    
    def _convert_scoreboard_players(self, args: List[str]) -> str:
        """Convert scoreboard players subcommand"""
        if len(args) < 3:
            return "scoreboard players"
        
        action = args[0]
        target = self.param_converters.convert_selector(args[1])
        
        # Handle scoreboard players tag -> tag conversion
        if action == "tag":
            if len(args) >= 4:
                tag_action = args[2]  # add, remove, or list (not objective)
                if len(args) >= 4:
                    tag_name = args[3]
                    result_target = target
                    # Handle NBT data parameter (args[4] if present)
                    # NBT should be added as a selector parameter: @s[nbt={...}]
                    if len(args) >= 5:
                        nbt = self.param_converters.convert_entity_nbt(args[4])
                        result_target = self._add_nbt_to_selector(target, nbt)
                    result = f"tag {result_target} {tag_action} {tag_name}"
                    return result
                else:
                    return f"tag {target} {tag_action}"
            else:
                return f"tag {target} list"
        
        # For non-tag actions, use the normal parsing
        objective = args[2]
        
        if action == "test":
            if len(args) >= 4:
                min_val = args[3]
                # Check if max value is provided
                if len(args) >= 5:
                    max_val = args[4]
                    return f"execute if score {target} {objective} matches {min_val}..{max_val}"
                else:
                    # Only min provided, max is infinite
                    return f"execute if score {target} {objective} matches {min_val}.."
            return f"scoreboard players test {target} {objective}"
        
        # Handle add, remove, set actions that require a value
        if action in ['add', 'remove', 'set'] and len(args) >= 4:
            value = args[3]
            return f"scoreboard players {action} {target} {objective} {value}"
        
        return f"scoreboard players {action} {target} {objective}"
    
    def _convert_effect(self, args: List[str]) -> str:
        """Convert effect command"""
        if len(args) < 2:
            return "effect"
        
        target = self.param_converters.convert_selector(args[0])
        effect = args[1]
        
        # Add minecraft: prefix if not present
        if not effect.startswith('minecraft:') and ':' not in effect:
            effect = f'minecraft:{effect}'
        
        # Check if duration is 0 (effect clear in 1.12)
        # 1.12: effect [target] [effect] 0
        # 1.20: effect clear [target] [effect]
        if len(args) >= 3 and args[2] == '0':
            return f"effect clear {target} {effect}"
        
        result = f"effect give {target} {effect}"
        
        if len(args) >= 3:
            result += f" {args[2]}"  # duration
        if len(args) >= 4:
            result += f" {args[3]}"  # amplifier
        
        return result
    
    def _convert_playsound(self, args: List[str]) -> str:
        """Convert playsound command"""
        if len(args) < 3:
            return "playsound"
        
        sound = args[0]
        source = args[1]
        target = self.param_converters.convert_selector(args[2])
        
        # Convert sound name using lookup table
        sound = self.param_converters.convert_sound_name(sound)
        
        result = f"playsound {sound} {source} {target}"
        
        # Handle coordinates
        if len(args) >= 6:
            x = self.param_converters.convert_coordinate(args[3])
            y = self.param_converters.convert_coordinate(args[4])
            z = self.param_converters.convert_coordinate(args[5])
            result += f" {x} {y} {z}"
        
        # Handle optional volume, pitch, and minVolume parameters
        if len(args) >= 7:
            result += f" {args[6]}"  # volume
        if len(args) >= 8:
            result += f" {args[7]}"  # pitch
        if len(args) >= 9:
            result += f" {args[8]}"  # minVolume
        
        return result
    

    
    def _convert_particle(self, args: List[str]) -> str:
        """Convert particle command to 1.20 syntax"""
        if len(args) < 1:
            return "particle"
        
        # Special handling for reddust particles
        # 1.12: particle reddust <x> <y> <z> <dx> <dy> <dz> <speed> [count] [mode] [targeter]
        # 1.20.4: particle minecraft:dust <RGB_dx> <RGB_dy> <RGB_dz> 1 <x> <y> <z> <spread_dx> <spread_dy> <spread_dz> <speed> <count> [mode]
        if args[0] == "reddust" and len(args) >= 7:
            try:
                x, y, z = args[1], args[2], args[3]
                dx, dy, dz = args[4], args[5], args[6]
                speed = args[7] if len(args) > 7 else "0"
                count = args[8] if len(args) > 8 else "0"  # Count defaults to 0 if not specified (RGB mode)
                mode = args[9] if len(args) > 9 else None
                targeter = args[10] if len(args) > 10 else None
                # NBT data for targeter (args[11]) will be handled by convert_selector if present
                
                # Determine RGB and spread based on count
                if count == '0':
                    # When count=0, RGB comes from dx/dy/dz, spread defaults to 0 0 0
                    rgb_dx, rgb_dy, rgb_dz = dx, dy, dz
                    spread_dx, spread_dy, spread_dz = "0", "0", "0"
                else:
                    # When count>0, RGB is default red (1 0 0), spread from original dx/dy/dz
                    rgb_dx, rgb_dy, rgb_dz = "1", "0", "0"
                    spread_dx, spread_dy, spread_dz = dx, dy, dz
                
                # Take absolute value of speed
                try:
                    speed_val = abs(float(speed))
                    # Format as integer if it's a whole number
                    if speed_val == int(speed_val):
                        speed = str(int(speed_val))
                    else:
                        speed = str(speed_val)
                except Exception:
                    pass
                
                # Build 1.20.4 command
                # Format: particle minecraft:dust <RGB> 1 <x> <y> <z> <spread> <speed> <count> [mode] [targeter]
                result = f"particle minecraft:dust {rgb_dx} {rgb_dy} {rgb_dz} 1 {x} {y} {z} {spread_dx} {spread_dy} {spread_dz} {speed} {count}"
                
                # Add mode if present
                if mode and not mode.startswith('@'):
                    result += f" {mode}"
                
                # Add converted targeter if present
                if targeter and targeter.startswith('@'):
                    converted_targeter = self.param_converters.convert_selector(targeter)
                    result += f" {converted_targeter}"
                
                return result
            except (ValueError, IndexError):
                pass
        
        # Special handling for blockcrack and blockdust particles
        # 1.12: particle blockcrack <x> <y> <z> <dx> <dy> <dz> <speed> [count] [mode] [targeter] [encoded_block_id]
        # 1.21: particle block{block_state:"[block name]"} <x> <y> <z> <dx> <dy> <dz> <speed> [count] [mode] [targeter]
        # Formula: encoded_block_id = block_id + (block_data * 4096)
        if args[0] in ["blockcrack", "blockdust"] and len(args) >= 8:
            try:
                # The last argument is the encoded block ID
                block_numeric = int(args[-1])
                
                # Reverse engineer: id = encoded % 4096, data = encoded // 4096
                block_id = block_numeric % 4096
                block_data = block_numeric // 4096
                
                # Look up block name using ID_Lookups.csv (normal conversion)
                block_name = self.param_converters.convert_block_name(str(block_id), str(block_data))
                
                # Remove minecraft: prefix if present (block_state should be just the block name)
                if block_name.startswith('minecraft:'):
                    block_name = block_name[10:]
                
                # Format: particle block{block_state:"[block name]"} ...
                result = f'particle block{{block_state:"{block_name}"}}'
                
                # Add coordinates (args[1] through args[3])
                result += f" {args[1]} {args[2]} {args[3]}"
                
                # Add spread (args[4] through args[6])
                result += f" {args[4]} {args[5]} {args[6]}"
                
                # Take absolute value of speed (args[6] is dz, args[7] should be speed)
                # Actually, looking at the format: particle blockcrack <x> <y> <z> <dx> <dy> <dz> <speed> [count] [mode] [targeter] [encoded_block_id]
                # So args[7] is speed, args[8] is count, etc.
                if len(args) >= 8:
                    try:
                        speed = str(abs(float(args[7])))
                        result += f" {speed}"
                    except (ValueError, IndexError):
                        result += f" {args[7]}" if len(args) > 7 else ""
                
                # Add count if present (args[8])
                if len(args) >= 9:
                    result += f" {args[8]}"
                
                # Add optional mode and target selector (args[9] to len(args)-2, excluding the last encoded_block_id)
                if len(args) > 9:
                    # Skip the last argument (encoded_block_id) and process the rest
                    extras = args[9:-1]
                    for extra in extras:
                        # Convert selector if it's a selector
                        if extra.startswith('@'):
                            converted_selector = self.param_converters.convert_selector(extra)
                            result += f" {converted_selector}"
                        else:
                            result += f" {extra}"
                
                return result
            except (ValueError, IndexError) as e:
                # If conversion fails, fall through to standard particle conversion
                pass
        
        # Standard particle conversion (for particles with same parameter structure)
        particle_name = self.param_converters.convert_particle_name(args[0])
        result = f"particle {particle_name}"
        
        if len(args) > 1:
            # Copy arguments, but take abs of speed if present (7th argument, index 7 or 6)
            std_args = args[1:]
            # Try to find the speed parameter (by convention, it's the 7th argument, index 6)
            if len(std_args) >= 7:
                try:
                    speed_idx = 6
                    speed_val = std_args[speed_idx]
                    std_args[speed_idx] = str(abs(float(speed_val)))
                except Exception:
                    pass
            # Add all arguments except the last one
            for i in range(len(std_args) - 1):
                result += f" {std_args[i]}"
            # Handle the last argument - if it's a target selector, convert it
            last_arg = std_args[-1]
            if last_arg.startswith('@'):
                converted_selector = self.param_converters.convert_selector(last_arg)
                result += f" {converted_selector}"
            else:
                result += f" {last_arg}"
        return result
    
    def _convert_blockdata(self, args: List[str]) -> str:
        """Convert blockdata command to data modify block"""
        if len(args) < 4:
            return "data modify block"
        
        x = self.param_converters.convert_coordinate(args[0])
        y = self.param_converters.convert_coordinate(args[1])
        z = self.param_converters.convert_coordinate(args[2])
        
        # Convert block name using lookup table
        block = self.param_converters.convert_block_name(args[3], '0')
        
        result = f"data modify block {x} {y} {z} {block}"
        
        # Handle NBT data
        if len(args) >= 5:
            nbt = self.param_converters.convert_block_nbt(args[4])
            result += f" merge value {nbt}"
        
        return result
    
    def _convert_tp(self, args: List[str]) -> str:
        """Convert tp/teleport command"""
        if len(args) < 1:
            return "tp"
        
        # Convert target selector
        target = self.param_converters.convert_selector(args[0])
        result = f"tp {target}"
        
        # Handle destination (can be coordinates or another target)
        if len(args) >= 4:
            # Coordinates
            x = self.param_converters.convert_coordinate(args[1])
            y = self.param_converters.convert_coordinate(args[2])
            z = self.param_converters.convert_coordinate(args[3])
            result += f" {x} {y} {z}"
            
            # Handle rotation (optional)
            if len(args) >= 6:
                yaw = args[4]
                pitch = args[5]
                result += f" {yaw} {pitch}"
        elif len(args) >= 2:
            # Another target
            dest = self.param_converters.convert_selector(args[1])
            result += f" {dest}"
        
        return result
    
    def _convert_title(self, args: List[str]) -> str:
        """Convert title command (duration in ticks)"""
        if len(args) < 2:
            return "title"
        
        target = self.param_converters.convert_selector(args[0])
        action = args[1]
        result = f"title {target} {action}"
        
        # Handle different title actions
        if action in ['title', 'subtitle', 'actionbar'] and len(args) >= 3:
            # Text content
            text = args[2]
            result += f" {text}"
        elif action in ['times'] and len(args) >= 5:
            # Convert seconds to ticks (1 second = 20 ticks)
            fade_in = str(int(float(args[2]) * 20))
            stay = str(int(float(args[3]) * 20))
            fade_out = str(int(float(args[4]) * 20))
            result += f" {fade_in} {stay} {fade_out}"
        
        return result
    
    def _convert_say(self, args: List[str]) -> str:
        """Convert say command"""
        if len(args) < 1:
            return "say"
        
        # Join all arguments as the message
        message = ' '.join(args)
        return f"say {message}"
    
    def _convert_clear(self, args: List[str]) -> str:
        """Convert clear command to 1.20 syntax"""
        if len(args) < 1:
            return "clear"
        
        target = self.param_converters.convert_selector(args[0])
        result = f"clear {target}"
        
        # Handle item specification
        if len(args) >= 2:
            item = args[1]
            
            # Check if the item itself contains NBT data (inline with item name)
            if '[' in item or '{' in item:
                # Extract the item name and NBT data
                bracket_pos = item.find('[') if '[' in item else len(item)
                brace_pos = item.find('{') if '{' in item else len(item)
                
                # Use whichever comes first
                if bracket_pos < brace_pos:
                    item_name = item[:bracket_pos]
                    nbt_data = item[bracket_pos:]
                else:
                    item_name = item[:brace_pos]
                    nbt_data = item[brace_pos:]
                
                # Convert NBT - ensure it uses bracket notation for component format
                nbt = self.param_converters.convert_item_nbt(nbt_data)
                
                # If converted NBT has component format but is wrapped in braces, convert to brackets
                if nbt.startswith('{') and nbt.endswith('}') and ('custom_name=' in nbt or 'lore=' in nbt):
                    # Extract content and wrap in brackets
                    content = nbt[1:-1]
                    # Only convert if it's component-style (not traditional NBT like id, Count, etc.)
                    if not any(key + ':' in content for key in ['id', 'Count', 'Damage', 'tag', 'Slot']):
                        nbt = '[' + content + ']'
                
                result += f" {item_name}{nbt}"
                
                # Check for count after the item
                if len(args) >= 3 and args[2].isdigit():
                    result += f" {args[2]}"
                
                return result
            
            # No inline NBT, proceed with traditional parsing
            # 1.12 format: clear <player> <item> <data> <maxCount> <nbt>
            # 1.21 format: clear <player> <item>[nbt] <maxCount> (component format uses brackets)
            
            data_value = '0'
            max_count = None
            nbt_data = None
            
            # Parse arguments to identify data, maxCount, and NBT
            for i in range(2, len(args)):
                arg = args[i]
                if arg.startswith('{') or arg.startswith('['):
                    # This is NBT data
                    nbt_data = arg
                    break  # NBT is always last
                elif arg.isdigit():
                    # Numeric value - could be data value or maxCount
                    if i == 2:
                        # First numeric after item is data value
                        data_value = arg
                    else:
                        # Second numeric is maxCount
                        max_count = arg
            
            # Convert item name using lookup table (e.g., skull 3 -> player_head)
            converted_item = self.param_converters.convert_block_name(item, data_value)
            
            # Add minecraft: prefix if not present
            if not converted_item.startswith('minecraft:') and ':' not in converted_item:
                converted_item = f"minecraft:{converted_item}"
            
            # Build the result in 1.21 format
            # NOTE: For clear command, items use bracket notation [custom_name=...,lore=[...]] for component format
            # Same as give command - both use brackets for component format
            if nbt_data:
                # Normal NBT conversion (handles display:{Name:...,Lore:[...]} format)
                converted_nbt = self.param_converters.convert_item_nbt(nbt_data)
                
                # If converted NBT has component format but is wrapped in braces, convert to brackets
                if converted_nbt.startswith('{') and converted_nbt.endswith('}') and ('custom_name=' in converted_nbt or 'lore=' in converted_nbt):
                    # Extract content and wrap in brackets
                    content = converted_nbt[1:-1]
                    # Only convert if it's component-style (not traditional NBT like id, Count, etc.)
                    if not any(key + ':' in content for key in ['id', 'Count', 'Damage', 'tag', 'Slot']):
                        converted_nbt = '[' + content + ']'
                
                # Add damage attribute if data_value is present and not 0
                if data_value and data_value != '0':
                    if converted_nbt.endswith(']'):
                        # Insert damage before closing bracket
                        converted_nbt = converted_nbt[:-1] + f',damage={data_value}' + ']'
                    elif converted_nbt.endswith('}'):
                        # Insert damage before closing brace
                        converted_nbt = converted_nbt[:-1] + f',Damage:{data_value}' + '}'
                    else:
                        converted_nbt = f'{converted_nbt},damage={data_value}'
                
                result += f" {converted_item}{converted_nbt}"
            elif data_value and data_value != '0':
                # No NBT data provided, but we have a data value
                result += f" {converted_item}{{Damage:{data_value}}}"
            else:
                result += f" {converted_item}"
            
            # Add maxCount if present
            if max_count:
                result += f" {max_count}"
        
        return result
    
    def _convert_clone(self, args: List[str]) -> str:
        """Convert clone command"""
        if len(args) < 7:
            return "clone"
        
        # Source coordinates
        x1 = self.param_converters.convert_coordinate(args[0])
        y1 = self.param_converters.convert_coordinate(args[1])
        z1 = self.param_converters.convert_coordinate(args[2])
        x2 = self.param_converters.convert_coordinate(args[3])
        y2 = self.param_converters.convert_coordinate(args[4])
        z2 = self.param_converters.convert_coordinate(args[5])
        
        # Destination coordinates
        x3 = self.param_converters.convert_coordinate(args[6])
        y3 = self.param_converters.convert_coordinate(args[7])
        z3 = self.param_converters.convert_coordinate(args[8])
        
        result = f"clone {x1} {y1} {z1} {x2} {y2} {z2} {x3} {y3} {z3}"
        
        # Handle mode parameter
        if len(args) >= 10:
            mode = args[9]
            result += f" {mode}"
        
        return result
    
    @log_method_call
    def _convert_give(self, args: List[str]) -> str:
        """Convert give command"""
        if len(args) < 2:
            return "give"
        
        target = self.param_converters.convert_selector(args[0])
        
        # Handle the case where args might be split incorrectly due to spaces in NBT
        # Reconstruct the full arguments string and parse it properly
        full_args = ' '.join(args[1:])
        
        # Parse the item and any additional arguments
        parts = []
        current_part = ""
        bracket_count = 0
        in_quotes = False
        quote_char = None
        
        for char in full_args:
            if char in ['"', "'"] and (not current_part or current_part[-1] != '\\'):
                if not in_quotes:
                    in_quotes = True
                    quote_char = char
                elif char == quote_char:
                    in_quotes = False
                    quote_char = None
                current_part += char
            elif char == '[' and not in_quotes:
                bracket_count += 1
                current_part += char
            elif char == ']' and not in_quotes:
                bracket_count -= 1
                current_part += char
            elif char == '{' and not in_quotes:
                bracket_count += 1
                current_part += char
            elif char == '}' and not in_quotes:
                bracket_count -= 1
                current_part += char
            elif char == ' ' and bracket_count == 0 and not in_quotes:
                if current_part.strip():
                    parts.append(current_part.strip())
                current_part = ""
                continue
            else:
                current_part += char
        
        if current_part.strip():
            parts.append(current_part.strip())
        
        if not parts:
            return f"give {target}"
        
        item = parts[0]
        
        # Check if the item itself contains NBT data (inline with item name)
        if '[' in item or '{' in item:
            # Extract the item name and NBT data
            # Find which bracket/brace comes first (NBT starts with [ or { immediately after item name)
            bracket_pos = item.find('[') if '[' in item else len(item)
            brace_pos = item.find('{') if '{' in item else len(item)
            
            # Use whichever comes first
            if bracket_pos < brace_pos:
                item_name = item[:bracket_pos]
                nbt_data = item[bracket_pos:]
            else:
                item_name = item[:brace_pos]
                nbt_data = item[brace_pos:]
            
            # Don't add minecraft: prefix for give commands (1.21 format doesn't require it)
            # Item names are used as-is
            
            nbt = self.param_converters.convert_item_nbt(nbt_data, item_id=item_name)
            
            # In Minecraft 1.21, item data components use brackets [] instead of braces {}
            # Convert outer braces to brackets if present
            if nbt.startswith('{') and nbt.endswith('}'):
                nbt = '[' + nbt[1:-1] + ']'
            
            result = f"give {target} {item_name}{nbt}"
            
            # Check for count after the item
            if len(parts) >= 2 and parts[1].isdigit():
                result += f" {parts[1]}"
            
            return result
        
        # No inline NBT, check for separate arguments
        # 1.12 format: give <player> <item> <count> <data> <nbt>
        # 1.21 format: give <player> <item>[nbt] <count>
        
        count = None
        data_value = None
        nbt_data = None
        
        # Parse the parts to identify count, data value, and NBT
        for i, part in enumerate(parts[1:], start=1):
            if part.isdigit():
                # This is a numeric value - could be count or data value
                if count is None:
                    count = part
                elif data_value is None:
                    data_value = part  # This is the old data/damage value (deprecated in 1.13+)
            elif part.startswith('{') or part.startswith('['):
                # This is NBT data
                nbt_data = part
                break  # NBT is always last
        
        # Build the result in 1.21 format: give <player> <item>[nbt] <count>
        # In Minecraft 1.21, item data components use brackets [] instead of braces {}
        result = f"give {target}"
        
        # Handle skull conversion: skull with data_value -> specific head type
        # 1.12: give <player> skull 1 3 -> 1.21: give <player> player_head 1
        skull_map = {
            '0': 'minecraft:skeleton_skull',
            '1': 'minecraft:wither_skeleton_skull',
            '2': 'minecraft:zombie_head',
            '3': 'minecraft:player_head',
            '4': 'minecraft:creeper_head',
            '5': 'minecraft:dragon_head'
        }
        
        # Check if item is skull and data_value is present
        if (item == 'skull' or item == 'minecraft:skull') and data_value:
            new_item = skull_map.get(data_value)
            if new_item:
                item = new_item
                data_value = None  # Don't add damage for skulls (data_value was used for head type)
        
        # Don't add minecraft: prefix for give commands (1.21 format doesn't require it)
        # Item names are used as-is
        
        # Handle NBT data and data_value (Damage attribute)
        if nbt_data:
            # Convert the NBT - pass item name to determine component naming
            nbt = self.param_converters.convert_item_nbt(nbt_data, item_id=item)
            
            # Convert outer braces to brackets for 1.21 item components (do this before adding Damage)
            if nbt.startswith('{') and nbt.endswith('}'):
                nbt = '[' + nbt[1:-1] + ']'
            
            # Add damage attribute if data_value is present
            # 1.12 data values become damage NBT in 1.21 (lowercase, equals sign)
            if data_value and data_value != '0':
                # Insert damage before the closing bracket
                # NBT format: [display:{...},damage=23]
                if nbt.endswith(']'):
                    nbt = nbt[:-1] + f',damage={data_value}' + ']'
                elif nbt.endswith('}'):
                    # Still braces (shouldn't happen after conversion, but handle it)
                    nbt = nbt[:-1] + f',damage={data_value}' + '}'
                else:
                    nbt = f'{nbt},damage={data_value}'
            
            result += f" {item}{nbt}"
        elif data_value and data_value != '0':
            # No NBT data provided, but we have a data value
            # Create NBT with just damage (use brackets for 1.21)
            result += f" {item}[damage={data_value}]"
        else:
            result += f" {item}"
        
        # Add count (if present)
        if count:
            result += f" {count}"
        
        return result
    
    def _convert_tellraw(self, args: List[str]) -> str:
        """Convert tellraw command - syntax unchanged, pass through as-is"""
        if len(args) < 2:
            return "tellraw"
        
        target = self.param_converters.convert_selector(args[0])
        result = f"tellraw {target}"
        
        # Handle JSON text component - combine all remaining args as the text component
        if len(args) >= 2:
            # Join all remaining arguments as the text component
            text_component = ' '.join(args[1:])
            # Don't convert color codes - leave message content unchanged
            result += f" {text_component}"
        
        return result
    
    def _convert_color_codes(self, text: str) -> str:
        """Convert Minecraft §-color codes to color names (or strip them for plain text)."""
        # Hardcoded mapping for Minecraft color codes
        color_map = {
            '0': 'black',
            '1': 'dark_blue',
            '2': 'dark_green',
            '3': 'dark_aqua',
            '4': 'dark_red',
            '5': 'dark_purple',
            '6': 'gold',
            '7': 'gray',
            '8': 'dark_gray',
            '9': 'blue',
            'a': 'green',
            'b': 'aqua',
            'c': 'red',
            'd': 'light_purple',
            'e': 'yellow',
            'f': 'white',
            'l': 'bold',
            'm': 'strikethrough',
            'n': 'underline',
            'o': 'italic',
            'r': 'reset',
        }
        import re
        # Replace §-codes with [color] or strip for plain text
        def replacer(match):
            code = match.group(1).lower()
            return f'<{color_map.get(code, "")}>' if code in color_map else ''
        # Example: convert §cHello§fWorld to <red>Hello<white>World
        return re.sub(r'§([0-9a-frlomn])', replacer, text)
    
    def _convert_color_codes_to_json(self, command: str) -> str:
        """Convert § color codes to vanilla JSON formatting"""
        import re
        import json
        
        # Color code mapping
        color_map = {
            '0': 'black', '1': 'dark_blue', '2': 'dark_green', '3': 'dark_aqua',
            '4': 'dark_red', '5': 'dark_purple', '6': 'gold', '7': 'gray',
            '8': 'dark_gray', '9': 'blue', 'a': 'green', 'b': 'aqua',
            'c': 'red', 'd': 'light_purple', 'e': 'yellow', 'f': 'white',
            'l': 'bold', 'm': 'strikethrough', 'n': 'underline', 'o': 'italic', 'r': 'reset'
        }
        
        if '§' not in command:
            return command
        
        parts = command.split(' ', 1)
        if len(parts) < 2:
            return command
        
        cmd_name = parts[0].lower()
        args = parts[1]
        
        # Commands with NBT data have already been converted by their respective NBT converters
        # Skip double-conversion for these commands
        if cmd_name in ['give', 'summon', 'clear', 'entitydata', 'replaceitem', 'setblock', 'fill']:
            return command
        
        if cmd_name == 'tellraw':
            return self._convert_tellraw_colors(args)
        elif cmd_name == 'title':
            return self._convert_title_colors(args)
        else:
            return self._convert_generic_colors(command)
    
    def _convert_summon_colors(self, args: str) -> str:
        """Convert colors in summon command (CustomName, etc.)"""
        import re
        
        # Don't apply color conversion here - it's already done in convert_entity_nbt
        # This function is called from _convert_color_codes_to_json which runs AFTER
        # the initial conversion, and we don't want to double-convert
        return f"summon {args}"
    
    def _convert_tellraw_colors(self, args: str) -> str:
        """Convert colors in tellraw command"""
        import re
        
        # Split into selector and text component
        parts = args.split(' ', 1)
        if len(parts) < 2:
            return f"tellraw {args}"
        
        selector = parts[0]
        text_component = parts[1]
        
        # Check if text component already has JSON structure
        if text_component.startswith('{') and text_component.endswith('}'):
            # Already JSON, convert § codes within it
            converted_text = self._convert_text_with_colors(text_component)
            return f"tellraw {selector} {converted_text}"
        else:
            # Plain text, convert to JSON
            converted_text = self._convert_plain_text_to_json(text_component)
            return f"tellraw {selector} {converted_text}"
    
    def _convert_give_colors(self, args: str) -> str:
        """Convert colors in give command (custom_name, lore, etc.)"""
        import re
        
        # Don't apply color conversion here - it's already done in convert_item_nbt
        # This function is called from _convert_color_codes_to_json which runs AFTER
        # the initial conversion, and we don't want to double-convert
        return f"give {args}"
    
    def _convert_title_colors(self, args: str) -> str:
        """Convert colors in title command"""
        import re
        
        # Split into target, action, and text
        parts = args.split(' ', 2)
        if len(parts) < 3:
            return f"title {args}"
        
        target = parts[0]
        action = parts[1]
        text_component = parts[2]
        
        # Convert text component
        converted_text = self._convert_text_with_colors(text_component)
        return f"title {target} {action} {converted_text}"
    
    def _convert_generic_colors(self, command: str) -> str:
        """Convert colors in generic commands"""
        # Look for quoted strings and convert them
        import re
        
        def convert_quoted_text(match):
            quoted_text = match.group(1)
            if '§' in quoted_text:
                return f'"{self._convert_plain_text_to_json(quoted_text)}"'
            return match.group(0)
        
        return re.sub(r'"([^"]*)"', convert_quoted_text, command)
    
    def _convert_text_with_colors(self, text: str) -> str:
        """Convert § codes in text to JSON formatting"""
        import re
        import json
        
        # If it's already JSON, parse and convert
        if text.startswith('{') and text.endswith('}'):
            try:
                data = json.loads(text)
                if 'text' in data:
                    # Convert the text content and return the result directly
                    return self._convert_plain_text_to_json(data['text'])
                return json.dumps(data)
            except:
                pass
        
        # Convert plain text to JSON
        return self._convert_plain_text_to_json(text)
    
    def _convert_plain_text_to_json(self, text: str) -> str:
        """Convert plain text with § codes to JSON - handles sequential codes properly"""
        import re
        import json
        
        if '§' not in text:
            # For 1.21, always include italic:false
            return json.dumps({"text": text, "italic": False})
        
        # Split text by § codes, keeping the codes as separate parts
        parts = re.split(r'(§[0-9a-frlomn])', text)
        
        components = []
        current_text = ""
        current_formatting = {}
        
        for part in parts:
            if part.startswith('§'):
                # This is a color code
                if current_text:
                    # Add the accumulated text as a component
                    component = {"text": current_text}
                    component.update(current_formatting)
                    components.append(component)
                    current_text = ""
                
                # Process the color code
                code = part[1].lower()
                if code in ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'a', 'b', 'c', 'd', 'e', 'f']:
                    # Color code - reset formatting and set color
                    current_formatting = {"color": self._get_color_name(code)}
                elif code == 'r':
                    # Reset - clear all formatting
                    current_formatting = {}
                elif code == 'l':
                    current_formatting["bold"] = True
                elif code == 'm':
                    current_formatting["strikethrough"] = True
                elif code == 'n':
                    current_formatting["underline"] = True
                elif code == 'o':
                    current_formatting["italic"] = True
            else:
                # This is text
                current_text += part
        
        # Add any remaining text
        if current_text:
            component = {"text": current_text}
            component.update(current_formatting)
            components.append(component)
        
        # Filter out empty components (but keep spaces)
        components = [comp for comp in components if comp.get("text", "") != ""]
        
        # Always add italic:false to each component (required in 1.21)
        for comp in components:
            if "italic" not in comp:
                comp["italic"] = False
        
        # If we have multiple components, return an array
        if len(components) > 1:
            return json.dumps(components)
        elif len(components) == 1:
            return json.dumps(components[0])
        else:
            return json.dumps({"text": ""})
    
    def _find_matching_brace(self, text: str, start_pos: int) -> int:
        """Find the matching closing brace for an opening brace at start_pos"""
        if start_pos >= len(text) or text[start_pos] != '{':
            return -1
        
        depth = 0
        in_quotes = False
        quote_char = None
        i = start_pos
        
        while i < len(text):
            char = text[i]
            
            # Handle quotes
            if char in ['"', "'"] and (i == 0 or text[i-1] != '\\'):
                if not in_quotes:
                    in_quotes = True
                    quote_char = char
                elif char == quote_char:
                    in_quotes = False
                    quote_char = None
            
            # Count braces (only when not in quotes)
            elif not in_quotes:
                if char == '{':
                    depth += 1
                elif char == '}':
                    depth -= 1
                    if depth == 0:
                        return i
            
            i += 1
        
        return -1  # No matching brace found
    
    def _find_matching_bracket(self, text: str, start_pos: int) -> int:
        """Find the matching closing bracket for an opening bracket at start_pos"""
        if start_pos >= len(text) or text[start_pos] != '[':
            return -1
        
        depth = 0
        in_quotes = False
        quote_char = None
        i = start_pos
        
        while i < len(text):
            char = text[i]
            
            # Handle quotes
            if char in ['"', "'"] and (i == 0 or text[i-1] != '\\'):
                if not in_quotes:
                    in_quotes = True
                    quote_char = char
                elif char == quote_char:
                    in_quotes = False
                    quote_char = None
            
            # Count brackets (only when not in quotes)
            elif not in_quotes:
                if char == '[':
                    depth += 1
                elif char == ']':
                    depth -= 1
                    if depth == 0:
                        return i
            
            i += 1
        
        return -1  # No matching bracket found
    
    def _convert_nbt_colors(self, nbt_data: str, context: str = "item") -> str:
        """Convert colors in NBT data to Minecraft 1.20+ format - preserves all structure"""
        import re
        
        # For entity context, always process CustomName even without color codes
        # (CustomName must be JSON format in 1.21.10 to avoid crashes)
        if context == "entity" and 'CustomName:' in nbt_data:
            # Process CustomName conversion even if no color codes
            pass
        elif '§' not in nbt_data:
            # If no color codes and not entity CustomName, return as-is
            return nbt_data
        
        # Protect minez.customName| patterns from conversion (custom plugin format)
        # These should preserve their color codes as-is
        protected_patterns = []
        def protect_minez_names(match):
            protected_patterns.append(match.group(0))
            return f"__PROTECTED_{len(protected_patterns)-1}__"
        
        # Temporarily replace minez.customName| entries with placeholders
        nbt_data = re.sub(r'minez\.customName\|[^"]*', protect_minez_names, nbt_data)
        
        # Strategy: Find and replace display properties in-place to preserve all other NBT
        # This handles: display:{Name:"...",Lore:[...]} or tag:{display:{...}}
        
        result = nbt_data
        
        # Pattern 1: Convert display:{...} blocks to 1.21 component format for items
        # In 1.21, items use: [custom_name=[{...}],lore=[[...],[...]]]
        # Instead of: {display:{Name:'...',Lore:[...]}}
        # Only convert for item context (not entity context)
        if context == "item":
            # Find all occurrences of "display:{"
            display_pattern = re.compile(r'display:\{')
            matches = list(display_pattern.finditer(result))
            
            # Process from end to start to preserve positions
            for match in reversed(matches):
                display_start = match.end() - 1  # Position of the opening brace
                display_content_start = match.end()  # Position after "display:{"
                
                # Find the matching closing brace
                closing_brace_pos = self._find_matching_brace(result, display_start)
                if closing_brace_pos == -1:
                    continue  # Invalid structure, skip
                
                # Extract the display content
                display_content = result[display_content_start:closing_brace_pos]
                
                # Convert to 1.21 component format
                components = []
                
                # Extract Name if present (handle both quoted formats)
                # Use brace matching to find the full quoted string (handles apostrophes)
                name_pattern = re.compile(r'Name:["\']')
                name_matches = list(name_pattern.finditer(display_content))
                if name_matches:
                    name_match = name_matches[0]
                    quote_start = name_match.end() - 1  # Position of opening quote
                    quote_char = display_content[quote_start]
                    
                    # Find the closing quote (handle escaped quotes)
                    quote_end = quote_start + 1
                    while quote_end < len(display_content):
                        if display_content[quote_end] == '\\':
                            quote_end += 2  # Skip escaped character
                            continue
                        if display_content[quote_end] == quote_char:
                            break
                        quote_end += 1
                    
                    if quote_end < len(display_content):
                        name_value = display_content[name_match.end():quote_end]
                        # Remove any existing JSON escaping
                        name_value = name_value.replace('\\"', '"').replace("\\'", "'")
                        # If it's already JSON, parse it; otherwise convert
                        if name_value.startswith('{') or name_value.startswith('['):
                            # Already JSON, use as single object (not array)
                            components.append(f"custom_name={name_value}")
                        else:
                            # Convert to 1.21 format: custom_name={...} (single object, not array)
                            json_obj = self._convert_plain_text_to_json(name_value)
                            # json_obj is already a valid JSON string, use it directly
                            components.append(f"custom_name={json_obj}")
                
                # Extract Lore if present - use bracket matching for robustness
                lore_pattern = re.compile(r'Lore:\[')
                lore_matches = list(lore_pattern.finditer(display_content))
                if lore_matches:
                    lore_match = lore_matches[0]
                    lore_start = lore_match.end() - 1  # Position of opening bracket
                    lore_content_start = lore_match.end()  # Position after "Lore:["
                    
                    # Find matching closing bracket (handles nested arrays)
                    closing_bracket_pos = self._find_matching_bracket(display_content, lore_start)
                    if closing_bracket_pos != -1:
                        lore_content = display_content[lore_content_start:closing_bracket_pos]
                        # Convert lore to 1.21 format: lore=[{...},{...}] (flat array)
                        converted_lore = self._convert_lore_to_121_format(lore_content)
                        if converted_lore:
                            # converted_lore is already a JSON array string, so use it directly
                            components.append(f"lore={converted_lore}")
                
                # Replace display:{...} with component format (remove "display:" prefix)
                if components:
                    replacement = ','.join(components)
                    # Find where "display:" starts (before the opening brace)
                    display_prefix_start = result.rfind('display:', 0, display_start)
                    if display_prefix_start != -1:
                        result = result[:display_prefix_start] + replacement + result[closing_brace_pos+1:]
                    else:
                        result = result[:display_start] + replacement + result[closing_brace_pos+1:]
                else:
                    # No Name or Lore found, remove the display block
                    result = result[:display_start] + result[closing_brace_pos+1:]
        else:
            # For entity context, keep the old format (display:{Name:...,Lore:...})
            # Find all occurrences of "display:{"
            display_pattern = re.compile(r'display:\{')
            matches = list(display_pattern.finditer(result))
            
            # Process from end to start to preserve positions
            for match in reversed(matches):
                display_start = match.end() - 1  # Position of the opening brace
                display_content_start = match.end()  # Position after "display:{"
                
                # Find the matching closing brace
                closing_brace_pos = self._find_matching_brace(result, display_start)
                if closing_brace_pos == -1:
                    continue  # Invalid structure, skip
                
                # Extract the display content
                display_content = result[display_content_start:closing_brace_pos]
                
                # Convert Name if present
                def convert_name(name_match):
                    name_value = name_match.group(1)
                    if '§' in name_value or True:  # Always convert to JSON format in 1.21
                        json_text = self._convert_plain_text_to_json(name_value)
                        # Use single quotes for outer string to avoid escaping inner quotes (SNBT format)
                        # Escape quotes for double-quoted string (required for compatibility in selector parameters)
                        json_text_escaped = json_text.replace('\\', r'\\').replace('"', r'\"')
                        return f'Name:"{json_text_escaped}"'
                    return name_match.group(0)
                
                converted_content = re.sub(r'Name:"([^"]*)"', convert_name, display_content)
                
                # Convert Lore if present - find using bracket matching for robustness
                lore_pattern = re.compile(r'Lore:\[')
                lore_matches = list(lore_pattern.finditer(converted_content))
                
                # Process from end to start to preserve positions
                for lore_match in reversed(lore_matches):
                    lore_start = lore_match.end() - 1  # Position of opening bracket
                    lore_content_start = lore_match.end()  # Position after "Lore:["
                    
                    # Find matching closing bracket (handles nested arrays)
                    closing_bracket_pos = self._find_matching_bracket(converted_content, lore_start)
                    if closing_bracket_pos == -1:
                        continue  # Invalid structure, skip
                    
                    # Extract lore array content
                    lore_array_content = converted_content[lore_content_start:closing_bracket_pos]
                    
                    # Convert colors in lore - for entity context, use escaped JSON strings
                    # display.Lore is a STRING array, so each element must be an escaped JSON string
                    converted_lore = self._convert_lore_array_to_json_strings(lore_array_content)
                    
                    # Replace the lore array
                    converted_content = converted_content[:lore_content_start] + converted_lore + converted_content[closing_bracket_pos:]
                
                # Replace the display block with converted content
                result = result[:display_content_start] + converted_content + result[closing_brace_pos:]
        
        # Pattern 2: For top-level CustomName in entities (not in display or tag)
        # In 1.21.10, CustomName must be JSON format to avoid crashes from special characters
        if context == "entity":
            def convert_entity_name(match):
                name_value = match.group(1)
                # Remove JSON escaping first
                name_value = name_value.replace('\\"', '"').replace("\\'", "'")
                
                # If it's already JSON format, keep it but ensure it's valid
                if name_value.startswith('{') and '"text"' in name_value:
                    import json
                    try:
                        json_obj = json.loads(name_value)
                        # Already valid JSON, return as-is
                        return f'CustomName:{json.dumps(json_obj)}'
                    except:
                        # Invalid JSON, treat as plain text and convert
                        pass
                
                # Convert color codes to JSON format
                if '§' in name_value:
                    # Use the color code parser to convert to JSON components
                    components = self._parse_color_codes_to_components(name_value)
                    # If single component, use it directly; if multiple, use array format
                    if len(components) == 1:
                        json_obj = components[0]
                    else:
                        json_obj = components  # Array of components
                    return f'CustomName:{json.dumps(json_obj)}'
                else:
                    # Plain text without color codes - wrap in JSON
                    json_obj = {"text": name_value}
                    return f'CustomName:{json.dumps(json_obj)}'
            
            # Convert any remaining CustomName (these are top-level entity properties)
            # CustomName is always a top-level entity property, not nested in display/tag
            if 'CustomName:"' in result or "CustomName:'" in result:
                result = re.sub(r"CustomName:[\"']([^\"']*)[\"']", convert_entity_name, result)
        
        # Pattern 3: Handle bare Name/Lore properties (no display wrapper) - wrap them in display:{}
        # This handles the case where Name/Lore appear without display in item NBT
        # But we need to be careful not to double-wrap or mess with already-wrapped properties
        
        # Check if we have Name or Lore outside of display:{}
        if 'Name:"' in result and 'display:{' not in result and context == "item":
            # Extract and convert Name
            def convert_bare_name(match):
                full_nbt = match.group(1)
                name_match = re.search(r'Name:"([^"]*)"', full_nbt)
                if name_match:
                    name_value = name_match.group(1)
                    if '§' in name_value:
                        json_text = self._convert_plain_text_to_json(name_value)
                        json_text_escaped = json_text.replace('"', r'\"')
                        # Replace the Name property with display:{Name:...}
                        new_nbt = full_nbt.replace(name_match.group(0), f'tag:{{display:{{Name:"{json_text_escaped}"}}}}')
                        return f'{{{new_nbt}}}'
                return match.group(0)
            
            # This is tricky - might need more context
        
        # Restore protected minez.customName| patterns
        for i, pattern in enumerate(protected_patterns):
            result = result.replace(f"__PROTECTED_{i}__", pattern)
        
        return result
    
    @log_method_call
    def _convert_custom_name_value(self, prop: str) -> str:
        """Extract and convert just the name value (for use in display:{})"""
        import re
        import json
        
        # Extract the text value - handle both custom_name, CustomName, and Name
        match = re.search(r'(?:custom_name|CustomName|Name):"([^"]*)"', prop, re.IGNORECASE)
        if not match:
            return "''"
        
        text_value = match.group(1)
        
        # Convert to JSON format
        if '§' in text_value:
            json_text = self._convert_plain_text_to_json(text_value)
        else:
            # No color codes, just wrap in JSON
            json_text = json.dumps({'text': text_value})
        
        # Escape double quotes inside the JSON (Minecraft NBT requires escaped quotes)
        # Example: {"text":"Relic"} becomes "{\"text\":\"Relic\"}"
        json_text_escaped = json_text.replace('"', r'\"')
        
        return f'"{json_text_escaped}"'
    
    @log_method_call
    def _convert_custom_name_property(self, prop: str, context: str = "item") -> str:
        """Convert custom_name property to Minecraft 1.20+ format with apostrophe wrapping"""
        import re
        import json
        
        # Extract the text value - handle both custom_name, CustomName, and Name
        match = re.search(r'(?:custom_name|CustomName|Name):"([^"]*)"', prop, re.IGNORECASE)
        if not match:
            return prop
        
        text_value = match.group(1)
        
        # Convert to JSON format
        if '§' in text_value:
            json_text = self._convert_plain_text_to_json(text_value)
        else:
            # No color codes, just wrap in JSON
            json_text = json.dumps({'text': text_value})
        
        # Escape double quotes inside the JSON (Minecraft NBT requires escaped quotes)
        # Example: {"text":"Relic"} becomes "{\"text\":\"Relic\"}"
        json_text_escaped = json_text.replace('"', r'\"')
        
        # For entities, CustomName is a top-level property
        # Entity format: CustomName:"{...}"
        return f'CustomName:"{json_text_escaped}"'
    
    @log_method_call
    def _convert_lore_value(self, prop: str) -> str:
        """Extract and convert just the lore value (for use in display:{})"""
        import re
        
        # Extract the lore array content - handle both [content] and ["content","content"] formats
        # Use a more robust regex that handles nested brackets and quotes
        match = re.search(r'lore:\[(.*)\]', prop, re.IGNORECASE)
        if not match:
            return "[]"
        
        lore_content = match.group(1)
        converted_lore = self._convert_lore_colors(lore_content)
        
        return f"[{converted_lore}]"
    
    @log_method_call
    def _convert_lore_property(self, prop: str, context: str = "item") -> str:
        """Convert lore property to Minecraft 1.20+ format"""
        lore_value = self._convert_lore_value(prop)
        # Item format: display:{Lore:[...]}
        return f"display:{{Lore:{lore_value}}}"
    
    def _convert_lore_to_121_format(self, lore_text: str) -> str:
        """Convert lore text to Minecraft 1.21 component format: [{...},{...}] (flat array)"""
        import re
        import json
        
        # Split by commas, but be careful about nested structures and quoted strings
        lines = []
        current_line = ""
        bracket_count = 0
        in_quotes = False
        quote_char = None
        
        for char in lore_text:
            if char in ['"', "'"] and (not current_line or current_line[-1] != '\\'):
                if not in_quotes:
                    in_quotes = True
                    quote_char = char
                elif char == quote_char:
                    in_quotes = False
                    quote_char = None
                current_line += char
            elif char == '{' and not in_quotes:
                bracket_count += 1
                current_line += char
            elif char == '}' and not in_quotes:
                bracket_count -= 1
                current_line += char
            elif char == ',' and bracket_count == 0 and not in_quotes:
                if current_line.strip():
                    lines.append(current_line.strip())
                current_line = ""
                continue
            else:
                current_line += char
        
        if current_line.strip():
            lines.append(current_line.strip())
        
        converted_components = []
        
        for line in lines:
            # Remove quotes if present
            line = line.strip().strip('"').strip("'")
            
            # Handle empty lines
            if not line:
                converted_components.append({"text": "", "italic": False})
                continue
            
            # Convert to 1.21 format - parse the JSON to get components
            json_text = self._convert_plain_text_to_json(line)
            
            # Parse the JSON to get the component(s)
            try:
                parsed = json.loads(json_text)
                if isinstance(parsed, list):
                    # Multiple components - add each one to the flat array
                    converted_components.extend(parsed)
                else:
                    # Single component - add it to the flat array
                    converted_components.append(parsed)
            except:
                # Fallback if JSON parsing fails
                converted_components.append({"text": line, "italic": False})
        
        # Return as a flat array of components (not nested arrays)
        return json.dumps(converted_components)
    
    def _convert_lore_colors(self, lore_text: str) -> str:
        """Convert colors in lore text to Minecraft 1.20+ format (legacy - kept for compatibility)"""
        # This is now handled by _convert_lore_to_121_format for items
        return self._convert_lore_to_121_format(lore_text)
    
    def _get_color_name(self, code: str) -> str:
        """Get color name from code"""
        color_map = {
            '0': 'black', '1': 'dark_blue', '2': 'dark_green', '3': 'dark_aqua',
            '4': 'dark_red', '5': 'dark_purple', '6': 'gold', '7': 'gray',
            '8': 'dark_gray', '9': 'blue', 'a': 'green', 'b': 'aqua',
            'c': 'red', 'd': 'light_purple', 'e': 'yellow', 'f': 'white'
        }
        return color_map.get(code, 'white')
    
    def _convert_tag(self, args: List[str]) -> str:
        """Convert tag command"""
        if len(args) < 2:
            return "tag"
        
        target = self.param_converters.convert_selector(args[0])
        action = args[1]
        
        # Check if the second argument is an action
        if action in ['add', 'remove', 'list']:
            if action == 'list':
                return f"tag {target} list"
            elif len(args) >= 3:
                tag_name = args[2]
                # Check if there's NBT data after the tag name
                if len(args) >= 4 and args[3].startswith('{'):
                    nbt_data = args[3]
                    # Move NBT into the selector
                    if '[' in target and target.endswith(']'):
                        # Insert nbt= before the closing bracket
                        target = target[:-1] + f",nbt={nbt_data}]"
                    else:
                        target = f"{target}[nbt={nbt_data}]"
                return f"tag {target} {action} {tag_name}"
            else:
                return f"tag {target} {action}"
        else:
            # If no action specified, assume it's a tag name (add action)
            tag_name = action
            # Check if there's NBT data after the tag name
            if len(args) >= 3 and args[2].startswith('{'):
                nbt_data = args[2]
                # Move NBT into the selector
                if '[' in target and target.endswith(']'):
                    # Insert nbt= before the closing bracket
                    target = target[:-1] + f",nbt={nbt_data}]"
                else:
                    target = f"{target}[nbt={nbt_data}]"
            return f"tag {target} add {tag_name}"
    
    def _convert_kill(self, args: List[str]) -> str:
        """Convert kill command"""
        if len(args) < 1:
            return "kill"
        
        target = self.param_converters.convert_selector(args[0])
        return f"kill {target}"
    
    def _convert_unknown_command(self, command_name: str, args: List[str]) -> str:
        """Convert unknown commands by applying parameter conversions"""
        result = command_name
        
        for arg in args:
            # Try to convert as selector
            if arg.startswith('@'):
                result += f" {self.param_converters.convert_selector(arg)}"
            # Try to convert as coordinate
            elif arg.startswith('~') or arg.replace('-', '').replace('.', '').isdigit():
                result += f" {self.param_converters.convert_coordinate(arg)}"
            # Try to convert as entity name
            elif command_name in ['summon', 'spawn']:
                result += f" {self.param_converters.convert_entity_name(arg)}"
            else:
                result += f" {arg}"
        
        return result


def run_test_commands():
    """Run hardcoded test commands and compare with expected results"""
    import sys
    import io
    
    # Fix Unicode output for Windows
    if sys.platform == 'win32':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    
    # Hardcoded test cases: (original, expected)
    # Note: Fixed encoding issue - replaced Â§ with §
    test_cases = [
        (
            'give @p[m=2,r=150,tag=waygate.activate8] minecraft:skull 1 3 {display:{Name:"§eGate Stone§7",Lore:["§7Charges: §e7§7/§e8","","§6Swap Item","§7Use near a §eWaygate §7to begin","§7a teleportation sequence.","","§7§oA smooth gem with magic sigils","§7§oetched into it. Used to travel","§7§obetween §e§oWaygates§7§o.","","§9Legendary Item"]},SkullOwner:{Id:"18d47163-dfe8-4159-95a3-d396c5022840",Properties:{textures:[{Value:"eyJ0ZXh0dXJlcyI6eyJTS0lOIjp7InVybCI6Imh0dHA6Ly90ZXh0dXJlcy5taW5lY3JhZnQubmV0L3RleHR1cmUvYjliMWZiYjY4NTdkYWYyMWMxMjljYmExMzQ4ZWNjNWQ0ZWJhYzBjYjc4YThiMTMyYTkxODE2YWM0MzgwODhmMiJ9fX0="}]}}}',
            'give @p[gamemode=adventure,tag=waygate.activate8,distance=..150] minecraft:player_head[minecraft:item_name=[{"text":"Gate Stone","color":"yellow","italic":false},{"text":"","color":"gray","italic":false}],minecraft:lore=[[{"text":"Charges: ","color":"gray","italic":false},{"text":"7","color":"yellow","italic":false},{"text":"/","color":"gray","italic":false},{"text":"8","color":"yellow","italic":false}],[{"text":"","italic":false}],[{"text":"Swap Item","color":"gold","italic":false}],[{"text":"Use near a ","color":"gray","italic":false},{"text":"Waygate ","color":"yellow","italic":false},{"text":"to begin","color":"gray","italic":false}],[{"text":"a teleportation sequence.","color":"gray","italic":false}],[{"text":"","italic":false}],[{"text":"A smooth gem with magic sigils","color":"gray","italic":true}],[{"text":"etched into it. Used to travel","color":"gray","italic":true}],[{"text":"between ","color":"gray","italic":true},{"text":"Waygates","color":"yellow","italic":true},{"text":".","color":"gray","italic":true}],[{"text":"","italic":false}],[{"text":"Legendary Item","color":"blue","italic":false}]],minecraft:profile={properties:[{name:"textures",value:"eyJ0ZXh0dXJlcyI6eyJTS0lOIjp7InVybCI6Imh0dHA6Ly90ZXh0dXJlcy5taW5lY3JhZnQubmV0L3RleHR1cmUvYjliMWZiYjY4NTdkYWYyMWMxMjljYmExMzQ4ZWNjNWQ0ZWJhYzBjYjc4YThiMTMyYTkxODE2YWM0MzgwODhmMiJ9fX0="}]}] 1'
        ),
        (
            'give @p golden_sword 1 23 {display:{Name:"§eUsurper\'s Scepter",Lore:["§7Radiates a strange aura that grants","§7access to unauthorized domains.","","§9Dungeon Item","§r§6Soulbound"]}}',
            'give @p golden_sword[custom_name={"text": "Usurper\'s Scepter", "color": "yellow", "italic": false},lore=[{"text": "Radiates a strange aura that grants", "color": "gray", "italic": false}, {"text": "access to unauthorized domains.", "color": "gray", "italic": false}, {"text": "", "italic": false}, {"text": "Dungeon Item", "color": "blue", "italic": false}, {"text": "Soulbound", "color": "gold", "italic": false}],damage=23] 1'
        ),
        (
            'scoreboard players tag @a[m=2,tag=!dcsHasSword,r=300] add dcsHasSword {Inventory:[{id:"minecraft:golden_sword",tag:{display:{Name:"§eUsurper\'s Scepter",Lore:["§7Radiates a strange aura that grants","§7access to unauthorized domains.","","§9Dungeon Item","§r§6Soulbound"]}}}]}',
            'tag @a[gamemode=adventure,tag=!dcsHasSword,distance=..300,nbt={Inventory:[{id:"minecraft:golden_sword",components:{"minecraft:custom_name":{"color":"yellow","italic":false,"text":"Usurper\'s Scepter"},"minecraft:lore":[{"color":"gray","italic":false,"text":"Radiates a strange aura that grants"},{"color":"gray","italic":false,"text":"access to unauthorized domains."},{"text":"","italic":false},{"color":"blue","italic":false,"text":"Dungeon Item"},{"color":"gold","italic":false,"text":"Soulbound"}]}}]}] add dcsHasSword'
        ),
        (
            'execute @a[m=2,r=100] ~ ~ ~ detect ~ 173 ~ stained_hardened_clay 13 testfor @s {SelectedItem:{id:"minecraft:golden_sword",tag:{display:{Name:"§eUsurper\'s Scepter",Lore:["§7Radiates a strange aura that grants","§7access to unauthorized domains.","","§9Dungeon Item","§r§6Soulbound"]}}}}',
            'execute as @a[gamemode=adventure,distance=..100] at @s positioned ~ ~ ~ if block ~ 173 ~ minecraft:green_terracotta run execute if entity @s[nbt={SelectedItem:{id:"minecraft:golden_sword",components:{"minecraft:custom_name":{"color":"yellow","italic":false,"text":"Usurper\'s Scepter"},"minecraft:lore":[{"color":"gray","italic":false,"text":"Radiates a strange aura that grants"},{"color":"gray","italic":false,"text":"access to unauthorized domains."},{"color":"blue","italic":false,"text":"Dungeon Item"},{"color":"gold","italic":false,"text":"Soulbound"}]},count:1}}]'
        ),
    ]
    
    lookups = LookupTables(silent=True)
    converter = CommandConverter(lookups)
    
    passed = 0
    failed = 0
    
    for i, (original, expected) in enumerate(test_cases, 1):
        print("=" * 80)
        print(f"TEST CASE {i}")
        print("=" * 80)
        print()
        print("ORIGINAL (1.12):")
        print(original)
        print()
        
        try:
            converted = converter.convert_command(original)
            print("CONVERTED (1.21.10):")
            print(converted)
            print()
            print("EXPECTED (1.21.10):")
            print(expected)
            print()
            
            # Compare
            if converted == expected:
                print("[PASS] Output matches expected")
                passed += 1
            else:
                print("[FAIL] Output does not match expected")
                failed += 1
                print()
                print("DIFFERENCES:")
                # Find differences
                if len(converted) != len(expected):
                    print(f"  - Length: converted={len(converted)}, expected={len(expected)}")
                
                # Compare character by character to find first difference
                min_len = min(len(converted), len(expected))
                for j in range(min_len):
                    if converted[j] != expected[j]:
                        start = max(0, j - 50)
                        end = min(len(converted), j + 50)
                        print(f"  - First difference at position {j}:")
                        print(f"    Converted: ...{converted[start:end]}...")
                        print(f"    Expected:  ...{expected[start:end]}...")
                        break
                else:
                    if len(converted) > len(expected):
                        print(f"  - Converted is longer by {len(converted) - len(expected)} characters")
                        print(f"    Extra: {converted[len(expected):]}")
                    else:
                        print(f"  - Expected is longer by {len(expected) - len(converted)} characters")
                        print(f"    Missing: {expected[len(converted):]}")
            
        except Exception as e:
            print(f"[ERROR] {e}")
            import traceback
            traceback.print_exc()
            failed += 1
        
        print()
        print()
    
    print("=" * 80)
    print(f"SUMMARY: {passed} passed, {failed} failed out of {len(test_cases)} tests")
    print("=" * 80)


if __name__ == "__main__":
    # Run tests if script is executed directly
    run_test_commands()