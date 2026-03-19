# Button Controls

The current firmware uses a single config button for two jobs: switching runtime behavior and re-entering the setup flow.

## 1. Supported button actions

### Single press

- A short press toggles between **Live mode** and the normal **interval refresh mode**.
- In firmware, a short press means **at least 50ms and less than 2 seconds**.

### Long press

- Hold the button for about **2 seconds** and the device shows `Restarting`, then reboots.
- To enter Wi-Fi/setup mode, keep holding the button briefly during reboot so the device boots into the captive portal.

## 2. What the two runtime modes mean

### Interval refresh mode

- The device refreshes on the schedule configured in the web app.
- This is the lower-power mode and is the right default for everyday desk use.

### Live mode

- The device stays online and polls more frequently for pending updates.
- It is useful while tuning layouts, testing modes, or checking changes quickly.
- Power usage is noticeably higher than interval refresh mode.

## 3. Forcing the setup portal at boot

- If the device has no Wi-Fi config yet, it enters the captive portal automatically.
- If Wi-Fi is already configured, you can still hold the config button during boot to force the captive portal.
- This is the recovery path for changing Wi-Fi, updating the backend URL, or fixing a device that cannot reconnect normally.

## 4. What is not implemented right now

- The current firmware **does not define a dedicated double-click action**.
- It also **does not use short press to jump to the next content mode**; short press only toggles Live / interval behavior.

## 5. Source of truth

- Force-portal check during boot: `firmware/src/main.cpp:124`
- Short-press / long-press handler: `firmware/src/main.cpp:497`
- Long-press and debounce thresholds: `firmware/src/config.h:61`
- Recommended board button pin definitions: `firmware/src/config.h:14`
