# Hardware Guide

This document reflects the **current codebase**. It covers the recommended build, built-in firmware profiles, pin mappings, power options, and common hardware issues.

If this is your first build, start with **ESP32-C3 + 4.2-inch e-paper**.
This guide is mainly for **DIY builders choosing parts, wiring displays, and debugging power or pin issues**.

## 1. Recommended build

The most recommended and best-supported combination today is:

- **MCU**: ESP32-C3
- **Display**: 4.2-inch SPI e-paper
- **Firmware environment**: `epd_42_wsv2_ssd1683_c3_promini`

Why this build is recommended:

- it is the default `platformio` target
- screenshots and product docs are centered on the 4.2-inch version
- it offers the best balance between cost, readability, and ease of assembly

## 2. Recommended BOM

| Part | Recommended choice | Notes |
|------|--------------------|-------|
| MCU | ESP32-C3 Pro mini dev board | best first-build option |
| Display | 4.2-inch SPI e-paper | current default display profile |
| USB | USB data cable | flashing requires data, not charge-only |
| Wiring | Dupont wires or soldered wires | dupont is fine for prototypes |
| Power | USB power during development | most stable for debugging |
| Lithium Battery (optional) | Pouch `505060-2000mAh` | Nominal 3.7V, must connect to 5V pin (uses onboard LDO) |
| Charger (optional) | TP5000 | Default 4.2V charging mode is fine, no modification needed |

A typical DIY BOM can still stay around **CNY 220**, depending on your display source and enclosure choice.

## 3. Built-in firmware hardware profiles

The default environment is `epd_42_wsv2_ssd1683_c3_promini`, and all public-facing docs and setup flow are centered on the **4.2-inch build**.

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

## 5. What to read next

- [Assembly Guide](assembly)
- [Web Flasher Guide](flash)
- [Device Configuration Guide](config)
- [Local Deployment Guide](deploy)
