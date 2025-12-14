# Minecraft 1.12 to 1.20 Command Converter

A modular Python script to convert Minecraft 1.12 commands to 1.20 syntax. This tool uses lookup tables to accurately convert entity names, block IDs, and command parameters to their modern equivalents.

## Features

- **Modular Design**: Each parameter type has its own conversion function
- **Entity Name Conversion**: Uses `entity_conversion.csv` to convert old entity names to modern ones
- **Block ID Conversion**: Uses `ID_Lookups.csv` to convert block IDs and data values to modern names
- **Sound Name Conversion**: Uses `sound_conversion.csv` to convert 1.12 sound names to 1.20 equivalents
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
- `particle reddust ~ ~ ~` → `particle reddust ~ ~ ~` (custom particles preserved)
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

### Basic Usage

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

### Process Test Commands

```python
from command_converter import process_test_commands

# Process all commands from test_commands.csv
process_test_commands(
    input_file="test_commands.csv",
    output_file="converted_commands.csv"
)
```

### Run Converter

```bash
python command_converter.py
```

## File Structure

```
worldConverter/
├── command_converter.py      # Main converter script
├── entity_conversion.csv     # Entity name lookup table
├── ID_Lookups.csv           # Block ID lookup table
├── sound_conversion.csv     # Sound name lookup table
├── test_commands.csv        # Input test commands
├── converted_commands.csv   # Output converted commands
├── verify_csv_encoding.py   # CSV encoding verification utility
├── 1.12 sounds.txt          # 1.12 sound list (reference)
├── 1.20 sounds.txt          # 1.20 sound list (reference)
└── README.md                # Documentation
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
Contains mappings from 1.12 sound names to 1.20 equivalents:
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
- `particle` - Particle commands with custom particle preservation
- `kill` - Kill command with selector conversion
- `say` - Say command (unchanged)
- `clear` - Clear command with selector and NBT conversion
- `clone` - Clone command with coordinate handling
- `give` - Give command with selector and NBT conversion
- `tellraw` - Tellraw command with JSON formatting

## Example Conversions

| Original (1.12) | Converted (1.20) |
|-----------------|------------------|
| `summon ender_crystal ~ ~ ~` | `summon minecraft:end_crystal ~ ~ ~` |
| `testfor @e[type=skeleton,r=100]` | `execute if entity @e[type=minecraft:skeleton,distance=..100]` |
| `testforblock ~ ~ ~ chain_command_block -1 {SuccessCount:0}` | `execute if block ~ ~ ~ chain_command_block{SuccessCount:0}` |
| `execute @e[type=skeleton] ~ ~ ~ tp @s ~ ~ ~` | `execute as @e[type=minecraft:skeleton] at @s positioned ~ ~ ~ run tp @s ~ ~ ~` |
| `setblock ~ ~ ~ glass 0 replace` | `setblock ~ ~ ~ glass replace` |
| `blockdata ~ ~ ~ stone {CustomName:"Test"}` | `data modify block ~ ~ ~ stone merge value {CustomName:Test}` |
| `tp @e[type=skeleton] @a[c=1]` | `tp @e[type=minecraft:skeleton] @a[limit=1,sort=nearest]` |
| `title @a times 1 3 1` | `title @a times 20 60 20` |
| `particle reddust ~ ~ ~` | `particle reddust ~ ~ ~` |
| `entitydata @e[type=skeleton] {Health:20}` | `data modify entity @e[type=minecraft:skeleton] merge value {Health:20}` |
| `@e[type=armor_stand,c=1]` | `@e[type=minecraft:armor_stand,limit=1,sort=nearest]` |
| `playsound minecraft:block.anvil.break master @a` | `playsound block.anvil.break master @a` |
| `playsound minecraft:record.11 record @a` | `playsound music_disc.11 record @a` |

## Requirements

- Python 3.6+
- CSV files for lookup tables
- No external dependencies

## Color Code Handling

The converter preserves Minecraft color codes (§) in CSV files using UTF-8 encoding. To verify your CSV files are properly encoded:

```bash
python verify_csv_encoding.py your_file.csv
```

This utility will:
- Test multiple encodings (UTF-8, CP1252, Latin-1, ISO-8859-1)
- Show examples of color codes found in the file
- Provide recommendations if encoding issues are detected

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

## Notes

- The script focuses on command syntax conversion, not world file parsing
- NBT data conversion is context-aware (entity vs block vs item)
- Unknown commands are processed by applying parameter conversions
- The script handles malformed commands gracefully 