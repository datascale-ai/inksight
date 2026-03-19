# Hardware Guide

This document reflects the **current codebase**. It covers the recommended build, built-in firmware profiles, pin mappings, power options, and common hardware issues.

If this is your first build, start with **ESP32-C3 + 4.2-inch e-paper**.
This guide is mainly for **DIY builders choosing parts, wiring displays, and debugging power or pin issues**.

## 1. Recommended build

The most recommended and best-supported combination today is:

- **MCU**: ESP32-C3
- **Display**: 4.2-inch SPI e-paper
- **Firmware environment**: `epd_42_c3`

Why this build is recommended:

- it is the default `platformio` target
- screenshots and product docs are centered on the 4.2-inch version
- it offers the best balance between cost, readability, and ease of assembly

## 2. Recommended BOM

| Part | Recommended choice | Notes |
|------|--------------------|-------|
| MCU | ESP32-C3 dev board / SuperMini-style board | best first-build option |
| Display | 4.2-inch SPI e-paper | current default display profile |
| USB | USB data cable | flashing requires data, not charge-only |
| Wiring | Dupont wires or soldered wires | dupont is fine for prototypes |
| Power | USB power during development | most stable for debugging |
| Lithium battery (optional) | `505060-2000mAh` | recommended choice for long-running desk builds |
| Charger (optional) | TP5000 | configure for LiFePO4 cutoff |

A typical DIY BOM can still stay around **CNY 220**, depending on your display source and enclosure choice.

## 3. Built-in firmware hardware profiles

The default environment is `epd_42_c3`, and all public-facing docs and setup flow are centered on the **4.2-inch build**.

If you want to inspect other built-in profiles in code, see:

- `firmware/platformio.ini`

For a first build, the default **4.2-inch** setup is still the recommended path.

## 4. Pin mappings

The current pin definitions are implemented in: `firmware/src/config.h`

### ESP32-C3 profile

| Function | Pin |
|----------|-----|
| MOSI | `GPIO6` |
| SCK | `GPIO4` |
| CS | `GPIO7` |
| DC | `GPIO1` |
| RST | `GPIO2` |
| BUSY | `GPIO10` |
| Lithium battery ADC | `GPIO0` |
| Config button | `GPIO9` |
| LED | `GPIO3` |

### ESP32-WROOM32E profile

| Function | Pin |
|----------|-----|
| MOSI | `GPIO14` |
| SCK | `GPIO13` |
| CS | `GPIO15` |
| DC | `GPIO27` |
| RST | `GPIO26` |
| BUSY | `GPIO25` |
| Lithium battery ADC | `GPIO35` |
| Config button | `GPIO0` |
| LED | `GPIO2` |

## 5. Recommended wiring for 4.2-inch + ESP32-C3

If you use the recommended build (`epd_42_c3`), wire it like this:

| ESP32-C3 | E-paper |
|----------|---------|
| `GPIO4` | `CLK / SCK` |
| `GPIO6` | `DIN / MOSI` |
| `GPIO7` | `CS` |
| `GPIO1` | `DC` |
| `GPIO2` | `RST` |
| `GPIO10` | `BUSY` |
| `3V3` | `VCC` |
| `GND` | `GND` |

## 6. Power guidance

### Development and debugging

For the first build, **USB power is strongly recommended**:

- simpler setup
- easier debugging
- stable serial logging

### Lithium battery version

For a long-running desk device, you can use:

- **single-cell LiFePO4**
- **TP5000** charging module

The currently recommended lithium battery model is:

- **`505060-2000mAh`**

Important notes:

- configure TP5000 for **LiFePO4 cutoff voltage**
- verify the board is stable in your chosen voltage range before lithium battery deployment
- real lithium battery life depends on refresh interval, Wi-Fi quality, and runtime mode

The project is often described as “months of lithium battery life in low-refresh scenarios,” but do not treat that as a guaranteed fixed runtime for every usage pattern.

## 7. Assembly recommendation

Suggested build order:

1. start with the minimum system: **USB + MCU + display**
2. confirm flashing, serial logs, and display refresh all work
3. add the lithium battery and charging module only after the core path is stable
4. then move on to enclosure or structural work

If you only want to validate the software flow, skip lithium battery work entirely and stay on USB power first.

## 8. Common hardware issues

### No display output

Check these first:

- `VCC / GND`
- `RST`
- `BUSY`
- SPI pin mapping vs the firmware environment you built
- panel type is actually SPI and matches your target configuration

### Corrupted or partial refresh

Check:

- `CLK / DIN / CS` stability
- wire length
- power stability

### Boot loops / repeated resets

Usually caused by:

- insufficient power
- unstable lithium battery output

For debugging, switch back to USB power first.

### Wi-Fi is fine but refresh still feels slow

E-paper refresh is naturally slower than LCD, and total refresh time also depends on:

- Wi-Fi signal quality
- whether the selected mode needs external data or LLM calls
- whether content was served from cache

This is often a system-timing issue, not a broken display.

## 9. Busy Timeout troubleshooting

If you see `Busy Timeout!` in serial logs, the driver timed out while waiting for the e-paper **BUSY** pin.

Check these first:

1. **BUSY is not connected or has poor contact**
2. **BUSY is wired to the wrong pin**
3. **BUSY is accidentally tied to 3.3V or GND**
4. **the module silk labels do not match your assumed pin order**

For the recommended ESP32-C3 build, the critical path is:

- `GPIO10` ↔ display `BUSY`

If you use another board profile, always follow the mapping in `firmware/src/config.h`.

## 10. What to read next

- Assembly: [`assembly.md`](assembly.md)
- Flashing: [`flash.md`](flash.md)
- Configuration: [`config.md`](config.md)
- Local deployment: [`deploy.md`](deploy.md)
