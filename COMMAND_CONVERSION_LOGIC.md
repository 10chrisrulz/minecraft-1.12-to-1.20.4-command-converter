# Minecraft 1.12 to 1.20.4 Command Conversion Logic

## Overview
This document details the conversion logic for each Minecraft command type when migrating from 1.12 to 1.20.4. The conversion system handles syntax changes, parameter ordering, NBT structure updates, and namespace requirements.

---

## Table of Contents
1. [Execute Command](#execute-command)
2. [Target Selectors](#target-selectors)
3. [Block Names](#block-names)
4. [Item Names](#item-names)
5. [Entity Names](#entity-names)
6. [NBT Data](#nbt-data)
7. [Specific Commands](#specific-commands)

---

## Execute Command

### Overview
The execute command underwent the most significant changes between 1.12 and 1.20. The syntax completely restructured from a linear format to a modular, chainable format.

### Basic Form (No Detect)
**1.12 Syntax:**
```
execute <selector> <x> <y> <z> <command>
```

**1.20 Syntax:**
```
execute as <selector> at @s positioned <x> <y> <z> run <command>
```

**Logic:**
1. Extract selector, coordinates, and the command to execute
2. Wrap with `execute as <selector> at @s positioned <x> <y> <z> run`
3. Convert the inner command recursively
4. Convert the selector using selector conversion rules

### Detect Form
**1.12 Syntax:**
```
execute <selector> <x1> <y1> <z1> detect <block> <variant> <x2> <y2> <z2> <command>
```

**1.20 Syntax:**
```
execute as <selector> at @s positioned <x2> <y2> <z2> if block <block> <x1> <y1> <z1> run <command>
```

**Logic:**
1. Extract selector, position1 (x1,y1,z1), block, variant, position2 (x2,y2,z2), and command
2. Convert block name using block lookup (block + variant → modern block state)
3. Construct: `execute as <selector> at @s positioned <x2> <y2> <z2> if block <block> <x1> <y1> <z1> run <command>`
4. Note: The coordinate order swaps between detect position and positioned position

**Special Cases:**
- If block variant is not 0, must look up the specific block state variant
- Air blocks don't require variant specification in 1.20

---

## Target Selectors

### Selector Types
- `@p` → `@p` (nearest player, unchanged)
- `@a` → `@a` (all players, unchanged)
- `@e` → `@e` (all entities, unchanged)
- `@r` → `@e[sort=random]` (random entity - changed from random player)
- `@s` → `@s` (self, unchanged)

### Selector Parameters

#### Distance Parameters
**1.12:**
- `r=X` (radius, maximum distance)
- `rm=Y` (minimum radius)

**1.20:**
- `r=X` → `distance=..X`
- `rm=Y` → `distance=Y..`
- `r=X,rm=Y` → `distance=Y..X`

**Logic:**
1. Check for both `r` and `rm` parameters
2. If both exist: combine into `distance=rm..r`
3. If only `r` exists: convert to `distance=..r`
4. If only `rm` exists: convert to `distance=rm..`

#### Game Mode Parameters
**1.12:**
- `m=0` (survival)
- `m=1` (creative)
- `m=2` (adventure)
- `m=3` (spectator)

**1.20:**
- `m=0` → `gamemode=survival`
- `m=1` → `gamemode=creative`
- `m=2` → `gamemode=adventure`
- `m=3` → `gamemode=spectator`

#### Score Parameters
**1.12:**
- `score_objective_min=X`
- `score_objective=Y`

**1.20:**
- `score_objective_min=X` → `scores={objective=X..}`
- `score_objective=Y` → `scores={objective=Y}`
- `score_objective_min=X,score_objective=Y` → `scores={objective=X..Y}`

**Logic:**
1. Extract objective name by removing `score_` prefix and `_min` suffix
2. Group by objective name
3. If both min and max exist for same objective: `scores={objective=min..max}`
4. If multiple objectives: `scores={obj1=X,obj2=Y,obj3=Z..W}`

#### Tag Parameters
**1.12:**
- `tag=foo` (has tag)
- `tag=!foo` (doesn't have tag)

**1.20:**
- `tag=foo` → `tag=foo` (unchanged)
- `tag=!foo` → `tag=!foo` (unchanged)

#### Type Parameters
**1.12:**
- `type=creeper`
- `type=!zombie`

**1.20:**
- `type=creeper` → `type=minecraft:creeper` (add namespace)
- `type=!zombie` → `type=!minecraft:zombie` (add namespace to negation)

**Logic:**
1. Check if type has namespace prefix
2. If not, add `minecraft:` prefix
3. Preserve negation operator `!` before the type

#### Name Parameters
**1.12:**
- `name=PlayerName`
- `name=!PlayerName`

**1.20:**
- Unchanged: `name=PlayerName`, `name=!PlayerName`

#### Level Parameters
**1.12:**
- `l=10` (max level)
- `lm=5` (min level)

**1.20:**
- `l=10` → `level=..10`
- `lm=5` → `level=5..`
- `l=10,lm=5` → `level=5..10`

#### NBT Parameters
**1.12:**
- Selector NBT embedded directly: `@e[type=armor_stand]{Invisible:1b}`

**1.20:**
- `@e[type=minecraft:armor_stand,nbt={Invisible:1b}]`

**Logic:**
1. Extract NBT data outside selector brackets
2. Convert NBT content (see NBT conversion section)
3. Add as `nbt={...}` parameter inside selector

#### Random Selector (@r)
**1.12:**
- `@r` selects random player
- `@r[type=creeper]` selects random creeper

**1.20:**
- `@r` → `@e[sort=random]` (now selects random entity, not just player)
- `@r[type=creeper]` → `@e[type=minecraft:creeper,sort=random]`

**Logic:**
1. If selector is exactly `@r` with no parameters: convert to `@e[sort=random]`
2. If selector is `@r[...]`: change prefix to `@e` and add `sort=random` parameter

---

## Block Names

### Conversion Process
**Logic:**
1. Extract block name and data value from command
2. Look up in `ID_Lookups.csv` using `(block_name, data_value)` tuple
3. Replace with modern block name from lookup table
4. Add `minecraft:` namespace if not present

### Data Value Handling
**1.12:**
- Blocks use numeric data values: `wool 14` (red wool)

**1.20:**
- Block states use descriptive names: `minecraft:red_wool`
- No separate data value parameter

**Example Conversions:**
- `stone 1` → `minecraft:granite`
- `wool 14` → `minecraft:red_wool`
- `log 2` → `minecraft:birch_log`
- `double_stone_slab2 9` → `minecraft:smooth_red_sandstone`
- `stained_hardened_clay 6` → `minecraft:pink_terracotta`

### Lookup Key Strategy
The `_load_block_conversions` function stores multiple lookup keys for each block:
1. `(block_name, data_value)` - primary key using `block` column
2. `(minecraft:block_name, data_value)` - namespaced variant
3. `(raw_block_id, data_value)` - legacy numeric ID support

---

## Item Names

### Conversion Process
Similar to blocks, items use a lookup table for name changes.

**Example Conversions:**
- `golden_sword` → `minecraft:golden_sword` (add namespace)
- `dye 4` (lapis) → `minecraft:lapis_lazuli`
- `skull 3` (player head) → `minecraft:player_head`

### Damage/Durability
**1.12:**
- Item damage as separate parameter: `golden_sword 1 23` (count=1, damage=23)

**1.20:**
- Damage as NBT tag: `minecraft:golden_sword{Damage:23} 1`

**Logic:**
1. Extract item name, count, and damage value
2. If damage value exists and is not 0: add `{Damage:value}` to NBT
3. Format as: `give <player> <item>{nbt} <count>`

---

## Entity Names

### Namespace Requirement
**1.12:**
- `zombie`, `creeper`, `armor_stand`

**1.20:**
- `minecraft:zombie`, `minecraft:creeper`, `minecraft:armor_stand`

**Logic:**
1. Check if entity name contains `:` (namespace separator)
2. If not, prepend `minecraft:`
3. Look up in entity conversion table for renamed entities

### Special Entity Conversions
- `xp_orb` → `minecraft:experience_orb`
- `xp_bottle` → `minecraft:experience_bottle`
- `eye_of_ender_signal` → `minecraft:eye_of_ender`
- `evocation_illager` → `minecraft:evoker`
- `vindication_illager` → `minecraft:vindicator`
- `illusion_illager` → `minecraft:illusioner`

---

## NBT Data

### Color Code Conversion
**1.12:**
- Uses section symbol color codes: `§e` (yellow), `§7` (gray), `§r` (reset)

**1.20:**
- Uses JSON text components: `{"text": "...", "color": "yellow"}`

**Color Code Mapping:**
- `§0` → `black`
- `§1` → `dark_blue`
- `§2` → `dark_green`
- `§3` → `dark_aqua`
- `§4` → `dark_red`
- `§5` → `dark_purple`
- `§6` → `gold`
- `§7` → `gray`
- `§8` → `dark_gray`
- `§9` → `blue`
- `§a` → `green`
- `§b` → `aqua`
- `§c` → `red`
- `§d` → `light_purple`
- `§e` → `yellow`
- `§f` → `white`
- `§r` → `white` (reset to default)

### Name and Lore Conversion
**1.12:**
```json
{display:{Name:"§eGolden Sword",Lore:["§7A legendary weapon","§9Rare"]}}
```

**1.20:**
```json
{display:{Name:"{\"text\": \"Golden Sword\", \"color\": \"yellow\"}",Lore:["{\"text\": \"A legendary weapon\", \"color\": \"gray\"}","{\"text\": \"Rare\", \"color\": \"blue\"}"]}}
```

**Logic:**
1. Find `Name:` or `Lore:` properties in NBT
2. Extract text between quotes
3. Split on color codes (§ followed by character)
4. For each segment:
   - Extract color code and following text
   - Convert to JSON: `{"text": "...", "color": "color_name"}`
5. For lore arrays: convert each element separately
6. Handle empty lore lines: `""` → `"{\"text\": \"\"}"`

### ActiveEffects (Potion Effects)
**1.12:**
```json
ActiveEffects:[{Id:14b,Amplifier:1b,Duration:2147000,ShowParticles:0b}]
```

**1.20:**
```json
active_effects:[{id:invisibility,amplifier:1b,duration:2147000,show_particles:0b}]
```

**Logic:**
1. Detect `ActiveEffects:` in NBT
2. Convert to lowercase: `active_effects:`
3. For each effect entry:
   - Convert `Id:<number>b` to `id:<effect_name>` using effect ID lookup
   - Convert `Amplifier:` → `amplifier:`
   - Convert `Duration:` → `duration:`
   - Convert `ShowParticles:` → `show_particles:`

**Effect ID Mapping:**
- `1` → `speed`
- `2` → `slowness`
- `3` → `haste`
- `4` → `mining_fatigue`
- `5` → `strength`
- `6` → `instant_health`
- `7` → `instant_damage`
- `8` → `jump_boost`
- `9` → `nausea`
- `10` → `regeneration`
- `11` → `resistance`
- `12` → `fire_resistance`
- `13` → `water_breathing`
- `14` → `invisibility`
- `15` → `blindness`
- `16` → `night_vision`
- `17` → `hunger`
- `18` → `weakness`
- `19` → `poison`
- `20` → `wither`
- `21` → `health_boost`
- `22` → `absorption`
- `23` → `saturation`
- `24` → `glowing`
- `25` → `levitation`
- `26` → `luck`
- `27` → `unluck`
- `28` → `slow_falling`
- `29` → `conduit_power`
- `30` → `dolphins_grace`
- `31` → `bad_omen`
- `32` → `hero_of_the_village`

### Enchantments
**1.12:**
```json
tag:{ench:[{id:35,lvl:1}]}
HandItems:[{id:"golden_axe",tag:{ench:[{id:35,lvl:1}]}}]
```

**1.20:**
```json
tag:{Enchantments:[{id:"fortune",lvl:1}]}
HandItems:[{id:"minecraft:golden_axe",tag:{Enchantments:[{id:"fortune",lvl:1}]}}]
```

**Logic:**
1. Detect `ench:` in NBT (item enchantments)
2. Convert tag name: `ench:` → `Enchantments:`
3. For each enchantment entry:
   - Convert `id:<number>` to `id:"<enchantment_name>"` using enchantment ID lookup
   - Preserve `lvl:` values
4. All other NBT fields remain unchanged

**Enchantment ID Mapping (27 total):**

**Armor Enchantments:**
- `0` → `protection`
- `1` → `fire_protection`
- `2` → `feather_falling`
- `3` → `blast_protection`
- `4` → `projectile_protection`
- `5` → `respiration`
- `6` → `aqua_affinity`
- `7` → `thorns`
- `8` → `depth_strider`
- `9` → `frost_walker`
- `10` → `binding_curse` (Curse of Binding)

**Weapon Enchantments:**
- `16` → `sharpness`
- `17` → `smite`
- `18` → `bane_of_arthropods`
- `19` → `knockback`
- `20` → `fire_aspect`
- `21` → `looting`
- `22` → `sweeping` (Sweeping Edge)

**Tool Enchantments:**
- `32` → `efficiency`
- `33` → `silk_touch`
- `34` → `unbreaking`
- `35` → `fortune`

**Bow Enchantments:**
- `48` → `power`
- `49` → `punch`
- `50` → `flame`
- `51` → `infinity`

**Fishing Rod Enchantments:**
- `61` → `luck_of_the_sea`
- `62` → `lure`

**Universal Enchantments:**
- `70` → `mending`
- `71` → `vanishing_curse` (Curse of Vanishing)

**Examples:**

Multiple enchantments on a bow:
```
1.12: ench:[{id:48,lvl:5},{id:50,lvl:1},{id:51,lvl:1},{id:34,lvl:3}]
1.20: Enchantments:[{id:"power",lvl:5},{id:"flame",lvl:1},{id:"infinity",lvl:1},{id:"unbreaking",lvl:3}]
```

Diamond sword with Sharpness V:
```
1.12: {id:"diamond_sword",tag:{ench:[{id:16,lvl:5}]}}
1.20: {id:"minecraft:diamond_sword",tag:{Enchantments:[{id:"sharpness",lvl:5}]}}
```

### Falling Block NBT
**1.12:**
```json
{id:"minecraft:falling_block",Block:double_stone_slab2,Data:9}
```

**1.20:**
```json
{id:"minecraft:falling_block",BlockState:{Name:"minecraft:smooth_red_sandstone"}}
```

**Logic:**
1. Detect `Block:` attribute in NBT
2. Extract block name and check for `Data:` attribute
3. Look up converted block using `(block_name, data_value)` tuple
4. Replace `Block:<name>,Data:<value>` with `BlockState:{Name:"<converted_block>"}`
5. If no `Data:` attribute: use data value 0 for lookup

### Fuse Tag (TNT)
**1.12:**
```json
{Fuse:1s}
```

**1.20:**
```json
{fuse:1s}
```

**Logic:**
- Simple case conversion: `Fuse:` → `fuse:`

### NBT Structure Preservation
**Critical Rule:**
- When converting NBT, preserve ALL existing fields
- Only modify specific fields that require conversion
- Use in-place regex replacement, not reconstruction
- This prevents data loss from unknown or custom NBT fields

---

## Specific Commands

### Scoreboard

#### players tag
**1.12:**
```
scoreboard players tag <selector> add <tag>
scoreboard players tag <selector> remove <tag>
scoreboard players tag <selector> list
```

**1.20:**
```
tag <selector> add <tag>
tag <selector> remove <tag>
tag <selector> list
```

**Logic:**
1. Detect `scoreboard players tag` at start
2. Extract selector, operation (add/remove/list), and tag name
3. Reformat as `tag <selector> <operation> [tag]`
4. Convert selector using standard selector rules

#### players set/add/remove/operation
**1.12:**
```
scoreboard players set <selector> <objective> <value>
scoreboard players add <selector> <objective> <value>
```

**1.20:**
```
scoreboard players set <selector> <objective> <value>
scoreboard players add <selector> <objective> <value>
```

**Logic:**
- These remain largely unchanged
- Convert selector in the command

### Testfor
**1.12:**
```
testfor <selector>
testfor <selector> {NBT}
```

**1.20:**
```
execute if entity <selector> run <command>
```

**Logic:**
1. Wrap with `execute if entity <selector>`
2. Convert selector and any attached NBT
3. Usually needs a `run` clause - if used standalone, typically replaced with `/execute if entity <selector>`

### Give
**1.12:**
```
give <player> <item> [count] [data] [nbt]
```

**1.20:**
```
give <player> <item>{nbt} [count]
```

**Logic:**
1. Extract player, item name, count, data value, and NBT
2. Convert item name using item lookup table
3. If data value exists and not 0: add `{Damage:<value>}` to NBT
4. Merge damage NBT with any existing NBT
5. Format as: `give <player> <item>{nbt} <count>`
6. Default count to 1 if not specified

**Example:**
- Input: `give @p golden_sword 1 23 {display:{Name:"§eKing's Blade"}}`
- Output: `give @p minecraft:golden_sword{Damage:23,display:{Name:"{\"text\": \"King's Blade\", \"color\": \"yellow\"}"}} 1`

### Clear
**1.12:**
```
clear <player> [item] [data] [maxCount] [nbt]
```

**1.20:**
```
clear <player> [item]{nbt} [maxCount]
```

**Logic:**
1. Similar to give command
2. Extract player, item, data, max count, and NBT
3. Convert item name and add data as Damage NBT
4. Format as: `clear <player> [item]{nbt} [maxCount]`

### Effect
**1.12:**
```
effect <entity> <effect> [duration] [amplifier] [hideParticles]
effect <entity> clear
```

**1.20:**
```
effect give <entity> <effect> [duration] [amplifier] [hideParticles]
effect clear <entity> [effect]
```

**Logic:**
1. Check if second argument is "clear" - if so, format as `effect clear <entity>`
2. Otherwise, check if duration is 0:
   - If duration = 0: convert to `effect clear <entity> <effect>`
   - If duration > 0: convert to `effect give <entity> <effect> [duration] [amplifier] [hideParticles]`
3. Convert effect name using effect name lookup
4. Add `minecraft:` namespace to effect name

### Particle
**1.12:**
```
particle <name> <x> <y> <z> <dx> <dy> <dz> <speed> [count] [mode] [selector]
```

**1.20:**
```
particle <name> <x> <y> <z> <dx> <dy> <dz> <speed> [count] [mode] [selector]
```

**General Logic:**
- Most particles: add `minecraft:` namespace
- Convert particle names using particle lookup table
- Convert any selector parameter

#### Special Case: reddust → dust
**1.12:**
```
particle reddust <x> <y> <z> <red> <green> <blue> <speed> [count] [mode] [selector]
```

**1.20 Syntax:**
```
particle dust <red> <green> <blue> <size> <x> <y> <z> <dx> <dy> <dz> <speed> [count] [mode] [selector]
```

**Conversion Logic:**

The `reddust` particle changes meaning based on the `count` parameter:

**Case 1: count = 0 or missing (RGB mode)**
- 1.12 dx/dy/dz values represent RGB color (0-1 range)
- Spread cannot be used when specifying RGB
- Size defaults to 1

```
# 1.12
particle reddust ~ ~1 ~ 1 0.5 0 1 0 force @a[r=50]

# 1.20
particle dust 1 0.5 0 1 ~ ~1 ~ 0 0 0 1 0 force @a[distance=..50]
```

**Logic:**
1. RGB values come from original dx/dy/dz positions
2. Size = 1 (default)
3. Spread (new dx/dy/dz) = 0 0 0
4. Speed = abs(original speed)
5. Count defaults to 0 if missing

**Case 2: count > 0 (Spread mode)**
- 1.12 dx/dy/dz values represent particle spread
- RGB cannot be customized, defaults to red
- Size defaults to 1

```
# 1.12
particle reddust ~ ~1 ~ 0.5 0.5 0.5 0.1 10 force @a[r=50]

# 1.20
particle dust 1 0 0 1 ~ ~1 ~ 0.5 0.5 0.5 0.1 10 force @a[distance=..50]
```

**Logic:**
1. RGB = 1 0 0 (red, default)
2. Size = 1 (default)
3. Spread (new dx/dy/dz) = original dx/dy/dz values
4. Speed = abs(original speed)
5. Count = original count value

**Additional Particle Conversions:**
- `explode` → `minecraft:explosion`
- `largeexplode` → `minecraft:explosion_emitter`
- `hugeexplosion` → `minecraft:explosion_emitter`
- `fireworksSpark` → `minecraft:firework`
- `wake` → `minecraft:fishing`
- `splash` → `minecraft:splash`
- `suspended` → `minecraft:underwater`

### Summon
**1.12:**
```
summon <entity> [x] [y] [z] [nbt]
```

**1.20:**
```
summon <entity> [x] [y] [z] [nbt]
```

**Logic:**
1. Convert entity name (add namespace, check entity lookup)
2. Convert NBT data:
   - ActiveEffects → active_effects
   - Fuse → fuse
   - Block/Data → BlockState:{Name:"..."}
   - Color codes in CustomName
   - All other NBT conversions
3. Handle Passengers array recursively (convert nested entity NBT)

### Setblock
**1.12:**
```
setblock <x> <y> <z> <block> [data] [mode] [nbt]
```

**1.20:**
```
setblock <x> <y> <z> <block>[blockstate] [mode] {nbt}
```

**Logic:**
1. Extract coordinates, block name, data value, mode, and NBT
2. Convert block using `(block_name, data_value)` lookup
3. If block state properties exist, append as `[property=value,...]`
4. Convert any NBT data (for containers, command blocks, etc.)

### Fill
**1.12:**
```
fill <x1> <y1> <z1> <x2> <y2> <z2> <block> [data] [mode] [nbt]
```

**1.20:**
```
fill <x1> <y1> <z1> <x2> <y2> <z2> <block> [mode] [nbt]
```

**Logic:**
- Same as setblock but with two coordinate sets
- Convert block name/data to modern format

### Replaceitem
**1.12:**
```
replaceitem entity <selector> <slot> <item> [count] [data] [nbt]
replaceitem block <x> <y> <z> <slot> <item> [count] [data] [nbt]
```

**1.20:**
```
item replace entity <selector> <slot> with <item>{nbt} [count]
item replace block <x> <y> <z> <slot> with <item>{nbt} [count]
```

**Logic:**
1. Change command from `replaceitem` to `item replace`
2. Add `with` keyword before item
3. Convert item name and handle data→Damage conversion
4. Convert NBT data

### Entitydata
**1.12:**
```
entitydata <selector> <nbt>
```

**1.20:**
```
data merge entity <selector> <nbt>
```

**Logic:**
1. Change to `data merge entity`
2. Convert selector
3. Convert NBT data

### Blockdata
**1.12:**
```
blockdata <x> <y> <z> <nbt>
```

**1.20:**
```
data merge block <x> <y> <z> <nbt>
```

**Logic:**
1. Change to `data merge block`
2. Convert NBT data

### Stats
**1.12:**
```
stats entity <selector> set <stat> <objective>
stats block <x> <y> <z> set <stat> <objective>
```

**1.20:**
- No direct equivalent
- Must be replaced with execute store commands

**Note:** Stats command is complex and requires context-specific conversion. Generally:
```
execute store result score <target> <objective> run <command>
execute store success score <target> <objective> run <command>
```

---

## Skipped Commands

The following commands are skipped during conversion (as per project requirements):
- `clock`
- `project`
- `button`
- `velocity`
- `script`
- `run` (when standalone)

These are likely custom commands from command block frameworks or plugins.

---

## Conversion Order

The conversion process follows this order to prevent conflicts:

1. **Execute commands** (outermost first, recursive for nested execute)
2. **Selectors** (in all commands)
3. **Block names** (in setblock, fill, detect, etc.)
4. **Item names** (in give, clear, replaceitem, etc.)
5. **Entity names** (in summon, type selectors, etc.)
6. **NBT data** (last, to handle all nested conversions)
   - Color codes → JSON text
   - ActiveEffects conversion
   - Falling block conversion
   - Fuse tag conversion
   - Custom NBT preservation

---

## Error Handling

### Common Issues
1. **Missing namespace:** Add `minecraft:` prefix to blocks, items, entities
2. **Invalid selectors:** Validate selector syntax before conversion
3. **Malformed NBT:** Preserve original if parsing fails
4. **Unknown blocks/items:** Log warning but attempt conversion
5. **Nested execute:** Handle recursively with proper depth tracking

### Validation
- Check that all selector brackets are balanced
- Verify NBT has matching braces
- Ensure coordinate patterns match expected format (numbers or relative ~)
- Validate that block/item lookups succeed

---

## Testing Recommendations

For developers reviewing this conversion:

1. **Test each command type individually** with representative examples
2. **Test nested execute commands** (execute within execute)
3. **Test complex NBT** with multiple levels of nesting
4. **Test edge cases:**
   - Empty parameters
   - Missing optional parameters
   - Selectors with multiple conditions
   - NBT with special characters
   - Color codes at boundaries (start/end of strings)
5. **Verify block conversions** for all data value variants
6. **Test particle commands** with both count=0 and count>0
7. **Validate effect conversion** with duration=0

---

## Future Considerations

### Potential Issues
1. **Custom enchantments:** May need special handling
2. **Modded blocks/items:** Won't be in lookup tables
3. **Custom NBT tags:** Should be preserved but not converted
4. **Command block chains:** Timing may differ between versions
5. **Selector limits:** 1.20 has different performance characteristics

### Version-Specific Features
Some 1.20 features have no 1.12 equivalent:
- Predicates
- Item modifiers
- Advancements (different format)
- Loot tables (different format)

These cannot be generated from 1.12 commands and must be manually created if needed.

---

## Conclusion

This conversion system handles the majority of command syntax changes between 1.12 and 1.20.4. The most complex conversions involve:
1. Execute command restructuring
2. Selector parameter translation
3. NBT data format updates
4. Block/item/entity name modernization

The system prioritizes data preservation - when uncertain about a conversion, it attempts to maintain the original structure while updating the syntax to be as compatible as possible with 1.20.4.

