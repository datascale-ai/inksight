# Hardware Guide

This document reflects the **current codebase**. It covers the recommended build, built-in firmware profiles, pin mappings, power options, and common hardware issues.

If this is your first build, start with **ESP32-C3 + 4.2-inch e-paper**.
This guide is mainly for **DIY builders choosing parts, wiring displays, and debugging power or pin issues**.

## 1. Recommended build & Multi-hardware Support

The most recommended and best-supported combination today is:

- **MCU**: ESP32-C3 Pro mini dev board
- **Display**: 4.2-inch SPI e-paper (e.g., Waveshare V2 or Zhongjingyuan SSD1683)
- **Firmware environment**: `epd_42_wsv2_ssd1683_c3_promini`

**Multi-hardware Support**:
To accommodate different developers, we provide pre-compiled firmware in our Releases for various boards and screens. The main supported MCUs include:
1. **ESP32-C3 Pro mini**: Compact size, native USB CDC (firmware suffix typically contains `c3_promini`).
2. **ESP32-C3 Standard Board**: Features a dedicated serial chip (like CH340) for more stable serial debugging (firmware suffix typically contains `c3_std`).
3. **ESP32-WROOM-32E**: The classic standard ESP32 development board (firmware suffix typically contains `wroom32e`).

Why the **4.2-inch screen** paired with the **ESP32-C3 series** is recommended as the first choice:
- screenshots and product docs are centered on the 4.2-inch version
- the ESP32-C3 chip offers low power consumption and a small footprint (whether using Pro mini or Standard board)
- it offers the best balance between overall cost, readability, and ease of assembly

## 2. Recommended Purchasing Schemes & BOM

To make sourcing parts easier, we've organized three mainstream hardware purchasing schemes (matching our video guides). All schemes are based on the **ESP32-C3** or **ESP32** chip paired with a **4.2-inch e-paper display**.

### Scheme 1: Component Assembly (Best for Beginners, Clear Wiring)
The classic DIY approach: buy a standard ESP32-C3 dev board, a display driver board, and a bare e-paper screen, then connect them with Dupont wires.
- **ESP32-C3 Dev Board**: Standard board (pre-soldered pins) with a dedicated serial chip for stable debugging.
- **Display Driver Board**: Used to connect the bare screen to the ESP32.
- **4.2-inch E-paper (Bare Screen)**: Zhongjingyuan / Waveshare (B/W), or Dalian Good Display (B/W/R/Y 4-color).
- **Dupont Wires**: Female-to-Female.

### Scheme 2: Integrated Driver Board (Cleanest Wiring)
Buy a display driver board that has the ESP32 chip built-in. This eliminates the need for Dupont wires between the MCU and driver board—just plug in the screen's ribbon cable.
- **Integrated ESP32 Driver Board**: Highly integrated board with onboard ESP32.
- **4.2-inch E-paper (Bare Screen)**: Same as Scheme 1.

### Scheme 3: Screen Module (Most Compact)
Buy a "screen module" (where the driver circuit is integrated onto the back of the screen) and pair it with a tiny ESP32-C3 Pro mini. Perfect for building ultra-thin cases.
- **ESP32-C3 Dev Board**: Pro mini (extremely small) or the standard board from Scheme 1.
- **4.2-inch Screen Module**: Waveshare 4.2-inch module (screen and driver board integrated).
- **Dupont Wires**: Female-to-Female.

> **Note for international builders**: The specific Taobao links are available in the [**Hardware BOM**](bom) page for reference. For builders outside of China, you can easily find equivalent ESP32-C3 boards and 4.2-inch SPI e-paper displays (like Waveshare or generic SSD1683 panels) on AliExpress or Amazon.

### Optional Power Accessories
| Part | Recommended choice | Notes |
|------|--------------------|-------|
| Power | USB power during development | most stable for debugging |
| Lithium Battery (optional) | Pouch `505060-2000mAh` | Nominal 3.7V, must connect to 5V pin (uses onboard LDO) |
| Charger (optional) | TP5000 | Default 4.2V charging mode is fine, no modification needed |

A typical DIY BOM can still stay around **CNY 220**, depending on your specific scheme and display source.

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
