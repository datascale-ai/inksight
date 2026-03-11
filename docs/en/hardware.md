# Hardware Guide

## BOM

- ESP32-C3 SuperMini
- 4.2" SPI E-Ink display (400x300, SSD1683)
- USB-C data cable
- Dupont wires
- Optional: LiFePO4 battery + TP5000 charging module

## Wiring

Recommended SPI mapping:

- `GPIO4 -> CLK`
- `GPIO6 -> DIN`
- `GPIO7 -> CS`
- `GPIO1 -> DC`
- `GPIO2 -> RST`
- `GPIO10 -> BUSY`

## Power

Use USB power for initial debugging.  
For battery usage, ensure stable output and correct charging cutoff settings.

## Common Issues

- **No display**: check GND, RST, BUSY, and SPI model compatibility.
- **Corrupted refresh**: shorten wires and verify power stability.
- **Boot loop**: usually power related; validate supply voltage first.
