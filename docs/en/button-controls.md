# Button Controls

On the recommended ESP32-C3 development boards (like the Pro mini), there are typically two physical buttons: **RST (Reset)** and **BOOT (Config)**.

The InkSight firmware uses these two buttons to handle device reboots, mode switching, and Wi-Fi provisioning.

## 1. RST Button (Hardware Reset)

- **Function**: Physically cuts and restores power to the chip, executing a hard reboot.
- **Usage**: A single short press at any time will immediately reboot the device.
- **Note**: This is a hardware-level reset that does not save the current state. It is typically used when the device is completely frozen or requires a forced restart.

## 2. BOOT Button (Config Button)

In the InkSight firmware, the BOOT button is defined as the primary interaction button (mapped to `BUTTON_PIN` in code, usually GPIO9).

### Short Press (Single Click)

- **Action**: Press for at least 50ms and less than 2 seconds.
- **Function**: Toggles between **Live (active state)** and **Interval (sleep state)**.
  - **Interval (sleep state)**: The device refreshes based on the schedule configured in the web app, then enters deep sleep. This is the lowest-power mode, ideal for everyday desk use.
  - **Live (active state)**: The device stays online (no deep sleep) and polls the backend frequently for updates. Useful for debugging or when you want to see configuration changes immediately, but consumes significantly more power.

### Long Press (Soft Reboot)

- **Action**: Hold the button for about **2 seconds**.
- **Function**: The screen will display `Restarting`, followed by a graceful soft reboot.

### Hold During Boot (Force Captive Portal)

- **Action**: **Hold the BOOT button down** exactly when the device powers on (or immediately after pressing the RST button).
- **Function**: The device skips the normal connection flow and forces entry into the **Captive Portal (Setup Mode)**.
- **Use Cases**:
  - Changing to a new Wi-Fi network.
  - Updating the backend server URL.
  - Rescuing a device that cannot connect to its saved network.
- **Note**: If the device is freshly flashed and has no saved Wi-Fi credentials, it will enter the captive portal automatically on boot without needing to hold the button.

## 3. Source of truth

- Force-portal check during boot: `firmware/src/main.cpp`
- Short-press / long-press handler: `firmware/src/main.cpp`
- Long-press and debounce thresholds: `firmware/src/config.h`
- Recommended board button pin definitions: `firmware/src/config.h`
