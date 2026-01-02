# Minecraft 1.12 to 1.21.10 Command Converter

A modular Python script to convert Minecraft 1.12 commands to 1.21.10 syntax. This tool uses lookup tables to accurately convert entity names, block IDs, and command parameters to their modern equivalents, including 1.21.10-specific format requirements.

## Features

- **Modular Design**: Each parameter type has its own conversion function
- **Entity Name Conversion**: Uses `entity_conversion.csv` to convert old entity names to modern ones
- **Block ID Conversion**: Uses `ID_Lookups.csv` to convert block IDs and data values to modern names
- **Sound Name Conversion**: Uses `sound_conversion.csv` to convert 1.12 sound names to 1.21 equivalents
- **CustomName JSON Format**: Converts CustomName to JSON format (required in 1.21.10 to prevent crashes)
- **Equipment Components**: Converts ArmorItems/HandItems to 1.21.10 equipment structure with components
- **Selector Conversion**: Converts target selectors to modern format (`@e[type=...]` → `@e[type=minecraft:...]`)
- **Command Structure Updates**: Converts deprecated commands to modern equivalents
- **NBT Data Handling**: Separate functions for entity, block, and item NBT data
- **Color Code Preservation**: Maintains Minecraft color codes (§) in CSV files with proper UTF-8 encoding

## Key Conversions

### Entity Names
- `ender_crystal` → `minecraft:end_crystal`
- `boat` → `minecraft:oak_boat`
- `snowman` → `minecraft:snow_golem`
- `zombie_pigman` → `minecraft:zombified_piglin`

### Commands
- `testfor @e[type=...]` → `execute if entity @e[type=minecraft:...]`
- `testforblock ~ ~ ~ block {nbt}` → `execute if block ~ ~ ~ block{nbt}`
- `execute @e[...] ~ ~ ~ command` → `execute as @e[...] at @s positioned ~ ~ ~ run command`
- `entitydata @e[...] {data}` → `data modify entity @e[...] merge value {data}`
- `blockdata ~ ~ ~ block {data}` → `data modify block ~ ~ ~ block merge value {data}`
- `scoreboard players test` → `execute if score ... matches ...`
- `setblock ~ ~ ~ block 0 replace` → `setblock ~ ~ ~ block replace`
- `fill ~ ~ ~ ~ ~ ~ block` → `fill ~ ~ ~ ~ ~ ~ block` (with block conversion)
- `tp @e[type=...] @a[c=1]` → `tp @e[type=minecraft:...] @a[limit=1,sort=nearest]`
- `title @a times 1 3 1` → `title @a times 20 60 20` (seconds to ticks)
- `particle reddust ~ ~ ~ 0.5 0.5 0.5 1 0` → `particle minecraft:dust 0.5 0.5 0.5 1 ~ ~ ~ 0 0 0 1 0` (RGB mode preserved)
- `kill @e[tag=...]` → `kill @e[tag=...]` (with selector conversion)
- `say message` → `say message` (unchanged)
- `clear @a item` → `clear @a item` (with selector conversion)
- `clone x1 y1 z1 x2 y2 z2 x3 y3 z3` → `clone x1 y1 z1 x2 y2 z2 x3 y3 z3`
- `give @a item count` → `give @a item count` (with selector conversion)
- `tellraw @a {"text":"Hello"}` → `tellraw @a {text:Hello}` (JSON formatting)
- `playsound minecraft:block.anvil.break master @a` → `playsound block.anvil.break master @a` (sound name conversion)

### Selectors
- `@e[type=skeleton,r=100]` → `@e[type=minecraft:skeleton,distance=..100]`
- `@e[type=armor_stand,c=1]` → `@e[type=minecraft:armor_stand,limit=1,sort=nearest]`
- `@a[m=2,r=50]` → `@a[m=adventure,distance=..50]`

## Usage

### Single World Conversion

```bash
python convert_single_world.py <world_name>
```

Example:
```bash
python convert_single_world.py my_1.12_world
```

### Batch Conversion (All Worlds)

```bash
python batch_convert_worlds.py
```

This will process all worlds in the `1-12 worlds/` folder.

### Basic Usage (Python API)

```python
from command_converter import LookupTables, CommandConverter

# Initialize the converter
lookups = LookupTables()
converter = CommandConverter(lookups)

# Convert a single command
original = 'summon ender_crystal ~ ~ ~ {NoGravity:1b}'
converted = converter.convert_command(original)
print(converted)
# Output: summon minecraft:end_crystal ~ ~ ~ {NoGravity:1b}
```

## File Structure

```
worldConverter/
├── command_converter.py          # Main converter script
├── convert_single_world.py        # Single world conversion script
├── batch_convert_worlds.py       # Batch conversion script
├── extract_commands.py           # Extract commands from world files
├── convert_extracted.py           # Convert extracted commands
├── reimport_commands_simple.py   # Reimport converted commands
├── extract_dx_only_selectors.py  # Extract dx-only selectors
├── entity_conversion.csv         # Entity name lookup table
├── ID_Lookups.csv                # Block ID lookup table
├── sound_conversion.csv          # Sound name lookup table
├── particle_conversion.csv        # Particle name lookup table
├── COMMAND_CONVERSION_LOGIC.md   # Detailed conversion logic documentation
├── LATEST_FIXES_SUMMARY.md       # Summary of recent fixes
├── requirements.txt               # Python dependencies
└── README.md                      # This file
```

## Lookup Tables

### entity_conversion.csv
Contains mappings from old entity names to modern names:
```csv
original,converted
ender_crystal,end_crystal
boat,oak_boat
snowman,snow_golem
```

### ID_Lookups.csv
Contains block ID and data value mappings:
```csv
id,data,block,raw_block,conversion name
172,6,stained_hardened_clay,stained_hardened_clay,pink_terracotta
```

### sound_conversion.csv
Contains mappings from 1.12 sound names to 1.21 equivalents:
```csv
1.12_sound,1.20_sound
minecraft:block.anvil.break,block.anvil.break
minecraft:block.enderchest.close,block.ender_chest.close
minecraft:block.note.basedrum,block.note_block.basedrum
minecraft:entity.enderdragon.ambient,entity.ender_dragon.ambient
minecraft:record.11,music_disc.11
```

## Parameter Conversion Functions

The script includes individual functions for converting different parameter types:

- `convert_coordinate()` - Converts coordinates to modern format
- `convert_entity_name()` - Converts entity names using lookup table
- `convert_block_name()` - Converts block names using lookup table
- `convert_selector()` - Converts target selectors to modern format
- `convert_entity_nbt()` - Converts entity NBT data
- `convert_block_nbt()` - Converts block NBT data
- `convert_item_nbt()` - Converts item NBT data
- `convert_sound_name()` - Converts sound names using lookup table

## Command Handlers

The script includes specific handlers for common commands:

- `summon` - Entity summoning with name conversion
- `execute` - Execute command with modern syntax (detect/non-detect)
- `testfor` - Convert to execute if entity
- `testforblock` - Convert to execute if block
- `entitydata` - Convert to data modify entity
- `blockdata` - Convert to data modify block
- `setblock` - Block placement with data value removal
- `fill` - Block filling with block conversion
- `scoreboard` - Scoreboard operations (test → execute if score)
- `effect` - Effect commands with minecraft: prefix
- `playsound` - Sound commands with sound name conversion
- `tp` - Teleport with selector conversion
- `title` - Title commands with tick conversion
- `particle` - Particle commands with special handling for reddust (RGB preservation) and block particles
- `kill` - Kill command with selector conversion
- `say` - Say command (unchanged)
- `clear` - Clear command with selector and NBT conversion
- `clone` - Clone command with coordinate handling
- `give` - Give command with selector and NBT conversion
- `tellraw` - Tellraw command with JSON formatting

## Example Conversions

| Original (1.12) | Converted (1.21.10) |
|-----------------|-------------------|
| `summon ender_crystal ~ ~ ~` | `summon minecraft:end_crystal ~ ~ ~` |
| `testfor @e[type=skeleton,r=100]` | `execute if entity @e[type=minecraft:skeleton,distance=..100]` |
| `testforblock ~ ~ ~ chain_command_block -1 {SuccessCount:0}` | `execute if block ~ ~ ~ chain_command_block{SuccessCount:0}` |
| `execute @e[type=skeleton] ~ ~ ~ tp @s ~ ~ ~` | `execute as @e[type=minecraft:skeleton] at @s positioned ~ ~ ~ run tp @s ~ ~ ~` |
| `setblock ~ ~ ~ glass 0 replace` | `setblock ~ ~ ~ glass replace` |
| `blockdata ~ ~ ~ stone {CustomName:"Test"}` | `data modify block ~ ~ ~ stone merge value {CustomName:Test}` |
| `tp @e[type=skeleton] @a[c=1]` | `tp @e[type=minecraft:skeleton] @a[limit=1,sort=nearest]` |
| `title @a times 1 3 1` | `title @a times 20 60 20` |
| `particle reddust ~ ~ ~ 0.5 0.5 0.5 1 0` | `particle minecraft:dust 0.5 0.5 0.5 1 ~ ~ ~ 0 0 0 1 0` |
| `particle reddust ~ ~ ~ 0.1 0.1 0.1 0.5 10` | `particle minecraft:dust 1 0 0 1 ~ ~ ~ 0.1 0.1 0.1 0.5 10` |
| `entitydata @e[type=skeleton] {Health:20}` | `data modify entity @e[type=minecraft:skeleton] merge value {Health:20}` |
| `@e[type=armor_stand,c=1]` | `@e[type=minecraft:armor_stand,limit=1,sort=nearest]` |
| `playsound minecraft:block.anvil.break master @a` | `playsound block.anvil.break master @a` |
| `playsound minecraft:record.11 record @a` | `playsound music_disc.11 record @a` |

## Requirements

- Python 3.6+
- nbtlib (for NBT file parsing)
- CSV files for lookup tables

Install dependencies:
```bash
pip install -r requirements.txt
```

## Color Code Handling

The converter preserves Minecraft color codes (§) in CSV files using UTF-8 encoding.

### Color Code Examples

| Code | Color | Example |
|------|-------|---------|
| `§c` | Red | `§cRed Text` |
| `§e` | Yellow | `§eYellow Text` |
| `§6` | Gold | `§6Golden Sword` |
| `§7` | Gray | `§7Gray Text` |
| `§9` | Blue | `§9Blue Text` |
| `§l` | Bold | `§lBold Text` |
| `§r` | Reset | `§rReset Format` |

## Particle Command Conversion

The `particle` command has special conversion logic, particularly for `reddust` particles which were replaced with `minecraft:dust` in 1.13+.

### Reddust to Dust Conversion

**1.12 Format:**
```
particle reddust <x> <y> <z> <dx> <dy> <dz> <speed> [count] [mode] [targeter]
```

**1.21.10 Format:**
```
particle minecraft:dust <RGB_r> <RGB_g> <RGB_b> 1 <x> <y> <z> <spread_dx> <spread_dy> <spread_dz> <speed> <count> [mode] [targeter]
```

### RGB Functionality Preservation

The converter intelligently preserves RGB color functionality based on the `count` parameter:

- **When `count` is `0` (or omitted, defaults to `0`):**
  - **RGB Mode**: The original `dx`, `dy`, `dz` values are used as RGB color components
  - **Spread**: Set to `0 0 0` (no spread)
  - **Example:**
    - Input: `particle reddust ~ ~ ~ 0.5 0.5 0.5 1 0`
    - Output: `particle minecraft:dust 0.5 0.5 0.5 1 ~ ~ ~ 0 0 0 1 0`
    - The `0.5 0.5 0.5` values are preserved as RGB color (gray particles)

- **When `count` is greater than `0`:**
  - **RGB Mode**: Defaults to red (`1 0 0`)
  - **Spread**: The original `dx`, `dy`, `dz` values become spread values
  - **Example:**
    - Input: `particle reddust ~ ~ ~ 0.1 0.1 0.1 0.5 10`
    - Output: `particle minecraft:dust 1 0 0 1 ~ ~ ~ 0.1 0.1 0.1 0.5 10`
    - The `0.1 0.1 0.1` values become spread, RGB defaults to red

### Other Particle Conversions

- **Block Particles**: `blockcrack` and `blockdust` particles are converted to `particle block <block_name>` with numeric block IDs converted to modern block names
- **Standard Particles**: Other particles use the lookup table from `particle_conversion.csv`
- **Speed Parameter**: Speed values are converted to absolute values (negative speeds become positive)
- **Target Selectors**: Selectors in particle commands are converted to modern format

## Notes

- The script focuses on command syntax conversion, not world file parsing
- NBT data conversion is context-aware (entity vs block vs item)
- Unknown commands are processed by applying parameter conversions
- The script handles malformed commands gracefully
- Some lookup tables may not be 100% complete
