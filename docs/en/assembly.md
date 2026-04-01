# Assembly Guide

This guide helps you complete basic assembly in 10-20 minutes.

## Video Tutorial

- Assembly walkthrough: [`Bilibili: InkSight assembly demo`](https://www.bilibili.com/video/BV1spwKzUE6N?spm_id_from=333.788.videopod.sections&vd_source=166ea338ef8c38d7904da906b88ef0b7)

## Preparation

- ESP32-C3 Pro mini
- 4.2-inch SPI e-ink panel
- 6+ dupont wires
- USB-C data cable

## 2. Recommended wiring for 4.2-inch + ESP32-C3

If you use the recommended build (`epd_42_wsv2_ssd1683_c3_promini`), wire it like this:

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

## 3. Power guidance

### Development and debugging

For the first build, **USB power is strongly recommended**:

- simpler setup
- easier debugging
- stable serial logging

### Lithium battery version

For a long-running desk device, you can use:

- **Single-cell Lithium Battery (e.g., Li-Po pouch)**
- **TP5000** charging module

The currently recommended lithium battery model is:

- **Pouch cell `505060-2000mAh`** (505060 is the size: 5mm thick, 50x60mm, 2000mAh capacity)

Important notes:

- Standard lithium batteries are nominal 3.7V (4.2V full). **Must be connected to the 5V pin** on the dev board to use the onboard LDO. Do NOT connect directly to the 3.3V pin.
- TP5000 defaults to 4.2V charging mode, so no pad bridging is required.
- real lithium battery life depends on refresh interval, Wi-Fi quality, and runtime mode

The project is often described as “months of lithium battery life in low-refresh scenarios,” but do not treat that as a guaranteed fixed runtime for every usage pattern.

## 4. Assembly recommendation

Suggested build order:

1. start with the minimum system: **USB + MCU + display**
2. confirm flashing, serial logs, and display refresh all work
3. add the lithium battery and charging module only after the core path is stable
4. then move on to enclosure or structural work

If you only want to validate the software flow, skip lithium battery work entirely and stay on USB power first.

## 5. Common hardware issues

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

### Busy Timeout troubleshooting

If you see `Busy Timeout!` in serial logs, the driver timed out while waiting for the e-paper **BUSY** pin.

Check these first:

1. **BUSY is not connected or has poor contact**
2. **BUSY is wired to the wrong pin**
3. **BUSY is accidentally tied to 3.3V or GND**
4. **the module silk labels do not match your assumed pin order**

For the recommended ESP32-C3 build, the critical path is: `GPIO10` ↔ display `BUSY`.

## 6. Next Step

Once your hardware is assembled and verified, your device is ready. Follow these steps to complete the software setup:

1. **Install Firmware**: Read the [Web Flasher Guide](flash) to flash the firmware to your ESP32 directly from your browser.
2. **Configure Device**: Read the [Device Configuration Guide](config) to connect your device to Wi-Fi and choose display modes.
3. **Setup AI Compute**: Read the [Configure API Key](api-key) guide to provide your LLM API keys for AI content generation.
