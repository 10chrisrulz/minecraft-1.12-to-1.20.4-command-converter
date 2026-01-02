import csv
import re
import shlex
from typing import Dict, List, Tuple, Optional, Any
from pathlib import Path

class LookupTables:
    """Manages all lookup tables for conversions"""
    
    def __init__(self, entity_csv: str = "entity_conversion.csv", id_csv: str = "ID_Lookups.csv", sound_csv: str = "sound_conversion.csv", particle_csv: str = "particle_conversion.csv", silent: bool = True):
        self.silent = silent
        self.entity_conversions = self._load_entity_conversions(entity_csv)
        self.block_conversions = self._load_block_conversions(id_csv)
        self.sound_conversions = self._load_sound_conversions(sound_csv)
        self.particle_conversions = self._load_particle_conversions(particle_csv)
        
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
            with open(csv_path, 'r', encoding='utf-8', errors='replace') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    try:
                        block_id = row['id']
                        data_value = int(row['data'])
                        conversion_name = row['conversion name']
                        
                        # Store by ID + data
                        conversions[(block_id, data_value)] = conversion_name
                        # Store by raw block name + data
                        conversions[(row['raw_block'], data_value)] = conversion_name
                        # Store by minecraft: prefixed name + data
                        conversions[(f"minecraft:{row['raw_block']}", data_value)] = conversion_name
                        # Store by block column name + data (this is the actual command block name)
                        conversions[(row['block'], data_value)] = conversion_name
                        # Store by minecraft: prefixed block name + data
                        conversions[(f"minecraft:{row['block']}", data_value)] = conversion_name
                    except (ValueError, KeyError) as e:
                        if not self.silent:
                            print(f"Skipping malformed row: {row}. Error: {e}")
            if not self.silent:
                print(f"Loaded {len(conversions)} block conversions")
        except Exception as e:
            if not self.silent:
                print(f"Error loading block conversions: {e}")
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
            data_int = int(data_value) if data_value != '-1' else 0
            converted = self.lookups.block_conversions.get((block_name, data_int), block_name)
            
            # Add minecraft: prefix if not already present and not a coordinate
            if not converted.startswith('minecraft:') and not any(char in converted for char in '~^'):
                converted = f"minecraft:{converted}"
                
            return converted
        except ValueError:
            # Add minecraft: prefix if not already present and not a coordinate
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
        """
        if not isinstance(item_dict, dict) or 'id' not in item_dict:
            return None
        
        result = {}
        
        # Convert id (ensure namespaced)
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
        
        # Convert Count to count
        count = item_dict.get('Count', 1)
        result['count'] = int(count)
        
        # Process tag for components
        components = {}
        tag = item_dict.get('tag', {})
        if isinstance(tag, dict):
            # Convert enchantments
            if 'ench' in tag:
                ench_list = tag['ench']
                if isinstance(ench_list, list):
                    converted_ench = self._convert_enchantments_list(ench_list)
                    if converted_ench:
                        components['minecraft:enchantments'] = converted_ench
            
            # Convert display:{color:...} -> minecraft:dyed_color
            display = tag.get('display', {})
            if isinstance(display, dict):
                if 'color' in display:
                    components['minecraft:dyed_color'] = int(display['color'])
                
                # Convert display:{Name:...} -> minecraft:item_name
                if 'Name' in display:
                    name_value = display['Name']
                    # Remove color codes and extract plain text
                    import re
                    plain_text = re.sub(r'§[0-9a-frlomn]', '', str(name_value))
                    components['minecraft:item_name'] = plain_text
                
                # Convert display:{Lore:[...]} -> minecraft:lore
                if 'Lore' in display:
                    lore_list = display['Lore']
                    if isinstance(lore_list, list):
                        converted_lore = self._convert_lore_list_to_121(lore_list)
                        if converted_lore:
                            components['minecraft:lore'] = converted_lore
            
            # Convert SkullOwner -> minecraft:profile
            if 'SkullOwner' in tag:
                skull_owner = tag['SkullOwner']
                if isinstance(skull_owner, dict):
                    profile = self._convert_skull_owner_to_profile(skull_owner)
                    if profile:
                        components['minecraft:profile'] = profile
        
        # Add components if any
        if components:
            result['components'] = components
        
        return result
    
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
                    # If single component, return as object; if multiple, return as array
                    if len(components) == 1:
                        result.append(components[0])
                    elif len(components) > 1:
                        result.append(components)
                    else:
                        result.append({"text": "", "italic": False})
                elif lore_line.strip():
                    # Plain text - single component object with italic:false
                    result.append({"text": lore_line, "italic": False})
                else:
                    # Empty line - single component object with italic:false
                    result.append({"text": "", "italic": False})
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
        
        # Add remaining text
        if current_text:
            comp = current_formatting.copy()
            comp["text"] = current_text
            # Add italic:false if not explicitly set to true
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

    def convert_entity_nbt(self, nbt: str) -> str:
        """Convert entity NBT data - keep structure intact for selectors"""
        import re
        
        # Try structured NBT parsing first (for equipment, enchantments, CustomName, etc.)
        try:
            # Use the classes defined in this module (they're defined later in the file)
            # Parse SNBT string to structured Python object
            nbt_dict = NBTParser.parse_snbt(nbt)
            
            # Apply registered converters
            converted_dict = self.nbt_registry.convert(nbt_dict, "entity")
            
            # Serialize back to SNBT string
            converted_nbt = NBTSerializer.serialize_snbt(converted_dict)
            
            # If CustomName was converted to JSON, it's done
            # Otherwise, fall through to regex-based conversion for CustomName
            if 'CustomName:{"' in converted_nbt or "CustomName:{" in converted_nbt:
                return converted_nbt
        except Exception as e:
            # Fallback to old regex-based conversion if structured parsing fails
            pass  # Continue to regex-based conversion below
        
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
        
        # Basic entity NBT conversions
        nbt = re.sub(r'MaxHeatlh:', 'MaxHealth:', nbt)  # Fix typo
        nbt = re.sub(r'Fuse:', 'fuse:', nbt)  # Fuse must be lowercase in 1.20+
        
        # Convert ActiveEffects to active_effects with proper attribute names
        # 1.12: ActiveEffects:[{Id:14b,Amplifier:1b,Duration:2147000,ShowParticles:0b}]
        # 1.20: active_effects:[{id:invisibility,amplifier:1b,duration:2147000,show_particles:0b}]
        if 'ActiveEffects:' in nbt:
            # Convert the attribute name
            nbt = re.sub(r'ActiveEffects:', 'active_effects:', nbt)
            
            # Convert effect IDs to names and attribute casing
            def convert_effect_entry(match):
                effect_data = match.group(1)
                
                # Convert Id:<number>b to id:<effect_name>
                def convert_id(id_match):
                    effect_id = id_match.group(1)
                    effect_name = effect_map.get(effect_id, 'speed')  # Default to speed if not found
                    return f'id:{effect_name}'
                
                effect_data = re.sub(r'Id:(\d+)b', convert_id, effect_data)
                
                # Convert CamelCase attributes to snake_case
                effect_data = re.sub(r'Amplifier:', 'amplifier:', effect_data)
                effect_data = re.sub(r'Duration:', 'duration:', effect_data)
                effect_data = re.sub(r'ShowParticles:', 'show_particles:', effect_data)
                
                return f'{{{effect_data}}}'
            
            # Apply conversion to each effect entry
            nbt = re.sub(r'\{([^{}]*Id:\d+b[^{}]*)\}', convert_effect_entry, nbt)
        
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

        # Convert falling_block Block and Data to BlockState
        # 1.12: {Block:double_stone_slab2,Data:9} or {Block:<id>,Data:<data>}
        # 1.20: {BlockState:{Name:"minecraft:block_name"}}
        # The Block: and Data: attributes are specific to falling_block entities
        if 'Block:' in nbt:
            # Match Block:<name>,Data:<value> pattern
            def convert_falling_block_with_data(match):
                block_name = match.group(1)
                data_value = match.group(2)
                
                # Convert using the block lookup table
                converted_block = self.convert_block_name(block_name, data_value)
                
                # Build the BlockState NBT
                return f'BlockState:{{Name:"{converted_block}"}}'
            
            # Replace Block:<name>,Data:<value> with BlockState:{Name:"..."}
            nbt = re.sub(r'Block:([^,}\]]+),Data:(\d+)', convert_falling_block_with_data, nbt)
            
            # Also handle Block without Data (assume Data:0)
            if 'Block:' in nbt and 'BlockState:' not in nbt:
                def convert_falling_block_no_data(match):
                    block_name = match.group(1)
                    converted_block = self.convert_block_name(block_name, '0')
                    return f'BlockState:{{Name:"{converted_block}"}}'
                
                nbt = re.sub(r'Block:([^,}\]]+)', convert_falling_block_no_data, nbt)
        
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
        # We need to convert color codes in nested item display properties
        if '§' in nbt and hasattr(self, '_nbt_color_converter'):
            # Process nested item NBT for color conversion
            nbt = self._nbt_color_converter(nbt, "entity")
        
        return nbt
    
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
    
    def convert_item_nbt(self, nbt: str) -> str:
        """Convert item NBT data"""
        # Check if NBT contains color codes and convert them
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
        
        # Apply converters in order
        # Some converters check for the component themselves (like CustomName)
        # Others only run if the component exists (like ArmorItems)
        for component_name, converter_func in self.converters.items():
            try:
                result = converter_func(result, context)
            except Exception as e:
                # Only log errors for components that should exist
                if component_name in result:
                    print(f"Warning: Error converting {component_name}: {e}")
        
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
        }
        
        # Set up the NBT color converter reference for ParameterConverters
        self.param_converters._nbt_color_converter = lambda nbt, context: self._convert_nbt_colors(nbt, context)
    
    def convert_command(self, command: str) -> str:
        """Convert a single command from 1.12 to 1.20 format"""
        parsed = self.parser.parse_command(command)
        command_name = parsed['command']
        args = parsed['args']
        
        # Handle known commands
        if command_name in self.command_handlers:
            converted_command = self.command_handlers[command_name](args)
        else:
            # For unknown commands, try to convert parameters
            converted_command = self._convert_unknown_command(command_name, args)
        
        # Apply color code conversion if needed
        if '§' in converted_command:
            converted_command = self._convert_color_codes_to_json(converted_command)
        
        return converted_command
    
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
            nested_command = ' '.join(args[10:])
            converted_nested = self.convert_command(nested_command)
            result += f" run {converted_nested}"
        
        return result
    
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
            nbt = self.param_converters.convert_entity_nbt(args[1])
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
        """Convert fill command"""
        if len(args) < 7:
            return "fill"
        
        x1 = self.param_converters.convert_coordinate(args[0])
        y1 = self.param_converters.convert_coordinate(args[1])
        z1 = self.param_converters.convert_coordinate(args[2])
        x2 = self.param_converters.convert_coordinate(args[3])
        y2 = self.param_converters.convert_coordinate(args[4])
        z2 = self.param_converters.convert_coordinate(args[5])
        block = self.param_converters.convert_block_name(args[6], args[7] if len(args) > 7 else '0')
        
        result = f"fill {x1} {y1} {z1} {x2} {y2} {z2} {block}"
        
        # Handle additional parameters
        if len(args) >= 8:
            if args[7] in ['replace', 'destroy', 'keep', 'outline', 'hollow']:
                result += f" {args[7]}"
        
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
        if args[0] in ["blockcrack", "blockdust"] and len(args) >= 8:
            try:
                block_numeric = int(args[-1])
                block_name = self.param_converters._get_block_name_from_numeric(block_numeric)
                result = f"particle block {block_name}"
                for i in range(1, 7):
                    result += f" {args[i]}"
                # Take absolute value of speed (args[6])
                try:
                    speed = str(abs(float(args[6])))
                    result = result.rsplit(' ', 1)[0] + f" {speed}"
                except Exception:
                    pass
                # Add count (args[7])
                result += f" {args[7]}"
                # Add optional mode and target selector (args[8] to len(args)-2)
                if len(args) > 8:
                    # If there are more than one extra argument, the last one before block id might be a selector
                    extras = args[8:-1]
                    if extras:
                        # If the last extra is a selector, convert it
                        if extras[-1].startswith('@'):
                            for extra in extras[:-1]:
                                result += f" {extra}"
                            converted_selector = self.param_converters.convert_selector(extras[-1])
                            result += f" {converted_selector}"
                        else:
                            for extra in extras:
                                result += f" {extra}"
                return result
            except (ValueError, IndexError):
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
                
                nbt = self.param_converters.convert_item_nbt(nbt_data)
                result += f" {item_name}{nbt}"
                
                # Check for count after the item
                if len(args) >= 3 and args[2].isdigit():
                    result += f" {args[2]}"
                
                return result
            
            # No inline NBT, proceed with traditional parsing
            # 1.12 format: clear <player> <item> <data> <maxCount> <nbt>
            # 1.20 format: clear <player> <item>{nbt} <maxCount>
            
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
            
            # Build the result in 1.20 format
            if nbt_data:
                converted_nbt = self.param_converters.convert_item_nbt(nbt_data)
                
                # Add Damage attribute if data_value is present and not 0
                if data_value and data_value != '0':
                    if converted_nbt.endswith('}'):
                        converted_nbt = converted_nbt[:-1] + f',Damage:{data_value}' + '}'
                    else:
                        converted_nbt = f'{converted_nbt},Damage:{data_value}'
                
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
            
            # Add minecraft: namespace prefix if missing
            if ':' not in item_name:
                item_name = f"minecraft:{item_name}"
            
            nbt = self.param_converters.convert_item_nbt(nbt_data)
            
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
        
        # Add minecraft: namespace prefix to item name if missing
        if ':' not in item:
            item = f"minecraft:{item}"
        
        # Handle NBT data and data_value (Damage attribute)
        if nbt_data:
            # Convert the NBT
            nbt = self.param_converters.convert_item_nbt(nbt_data)
            
            # Convert outer braces to brackets for 1.21 item components (do this before adding Damage)
            if nbt.startswith('{') and nbt.endswith('}'):
                nbt = '[' + nbt[1:-1] + ']'
            
            # Add Damage attribute if data_value is present
            # 1.12 data values become Damage NBT in 1.21
            if data_value and data_value != '0':
                # Insert Damage before the closing bracket
                # NBT format: [display:{...},Damage:23]
                if nbt.endswith(']'):
                    nbt = nbt[:-1] + f',Damage:{data_value}' + ']'
                elif nbt.endswith('}'):
                    # Still braces (shouldn't happen after conversion, but handle it)
                    nbt = nbt[:-1] + f',Damage:{data_value}' + '}'
                else:
                    nbt = f'{nbt},Damage:{data_value}'
            
            result += f" {item}{nbt}"
        elif data_value and data_value != '0':
            # No NBT data provided, but we have a data value
            # Create NBT with just Damage (use brackets for 1.21)
            result += f" {item}[Damage:{data_value}]"
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
                name_match = re.search(r'Name:["\']([^"\']*)["\']', display_content)
                if name_match:
                    name_value = name_match.group(1)
                    # Remove any existing JSON escaping
                    name_value = name_value.replace('\\"', '"').replace("\\'", "'")
                    # If it's already JSON, parse it; otherwise convert
                    if name_value.startswith('{') or name_value.startswith('['):
                        # Already JSON, just wrap in array
                        components.append(f"custom_name=[{name_value}]")
                    else:
                        # Convert to 1.21 format: custom_name=[{...}]
                        json_obj = self._convert_plain_text_to_json(name_value)
                        components.append(f"custom_name=[{json_obj}]")
                
                # Extract Lore if present
                lore_match = re.search(r'Lore:\[(.*?)\]', display_content, re.DOTALL)
                if lore_match:
                    lore_content = lore_match.group(1)
                    # Convert lore to 1.21 format: lore=[[...],[...]]
                    converted_lore = self._convert_lore_to_121_format(lore_content)
                    if converted_lore:
                        components.append(f"lore=[{converted_lore}]")
                
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
                        return f"Name:'{json_text}'"
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
                    
                    # Convert colors in lore
                    converted_lore = self._convert_lore_colors(lore_array_content)
                    
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
    
    def _convert_lore_property(self, prop: str, context: str = "item") -> str:
        """Convert lore property to Minecraft 1.20+ format"""
        lore_value = self._convert_lore_value(prop)
        # Item format: display:{Lore:[...]}
        return f"display:{{Lore:{lore_value}}}"
    
    def _convert_lore_to_121_format(self, lore_text: str) -> str:
        """Convert lore text to Minecraft 1.21 component format: [[{...}],[{...}]]"""
        import re
        
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
        
        converted_lines = []
        
        for line in lines:
            # Remove quotes if present
            line = line.strip().strip('"').strip("'")
            
            # Handle empty lines
            if not line:
                converted_lines.append('[{"text":"","italic":false}]')
                continue
            
            # Convert to 1.21 format - each lore line is an array of components
            json_text = self._convert_plain_text_to_json(line)
            
            # If it's already an array (multiple components), use it directly
            # If it's a single object, wrap it in an array
            if json_text.startswith('['):
                converted_lines.append(json_text)
            else:
                converted_lines.append(f'[{json_text}]')
        
        # Return as comma-separated array of arrays
        return ','.join(converted_lines)
    
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