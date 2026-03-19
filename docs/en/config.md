# Device Configuration Guide

The recommended entry point for device setup is now the **WebApp Device Configuration page**.
Legacy backend pages such as the old config page, dashboard, and editor still exist for compatibility, but they are no longer the main product entry.
This guide is mainly for **people who already have a device and want to configure how it behaves day to day**.

![Device configuration entry screenshot](/images/docs/config-en.png)

This screenshot reflects the signed-in state in the current local build. You first see your device list, pairing tools, and device cards, then continue into the full device configuration workflow.

If you want the broader website walkthrough first, start with [`website.md`](website.md).

## 1. Before you start

- log in first
- open your device list
- choose the target device you want to configure

If you do not have a device yet, you can still use the device-free preview flow.

## 2. Current page structure

According to the current code, the device configuration page contains **4 tabs**:

- **Modes**
- **Preferences**
- **Sharing**
- **Status**

> Important: **AI model and API key settings are not managed inside the config tabs**. They are managed in the **Profile** page.

## 3. Modes tab

The Modes tab controls what the device shows and how each mode behaves.

Current capabilities include:

- enable / disable built-in modes
- preview modes and regenerate previews
- apply the current preview to the e-ink display
- open per-mode settings dialogs
- create, edit, preview, and save custom modes

### Per-mode overrides

Some modes support mode-level overrides, for example:

- **Weather**: location
- **Memo**: memo text
- **Countdown**: target date and related parameters
- other schema-based mode parameters

If a mode does not provide its own location, it falls back to the **global default location** from the Preferences tab.

## 4. Preferences tab

The Preferences tab stores the device-wide defaults, including:

- **city / location (global default)**
- **language** (Chinese / English / mixed)
- **content tone**
- **persona style**
- **refresh strategy**
- **refresh interval**

### About the global default location

This location acts as the device-level default:

- Weather uses it when no mode-specific location is set
- In some weather dialogs, “Use default city” fills the input with this location
- If the user has not configured a global location, the system falls back to `杭州`

## 5. Sharing tab

The Sharing tab is for multi-user device collaboration. It is currently used to:

- view current device members
- handle join requests
- manage device sharing relationships

Available actions depend on whether the current user is the owner or a shared member.

## 6. Status tab

The Status tab shows runtime and device information such as:

- online / offline state
- runtime mode
- last seen time
- voltage, lithium battery level, and signal
- render count
- cache hit rate
- mode usage statistics

## 7. Where AI model and API key settings live

In the current product structure:

- **Device Configuration** manages device behavior and content preferences
- **Profile** manages models, API keys, quota, and access mode

So if you want to configure:

- text model provider
- text model name
- image model provider
- image model name
- API keys

go to **Profile**, not the config tabs.

## 8. Save and apply behavior

- Clicking “Save to Device” writes the current config to that device
- If the device is online, changes usually take effect quickly
- If it is offline, the config will apply the next time it comes online

## 9. Recommended real-world flow

1. Configure your models and API keys in **Profile** if needed
2. Choose your display modes in **Device Configuration**
3. Set the global location, language, tone, and refresh strategy
4. Preview individual modes
5. Save the configuration to the device

## 10. Related docs

- Website guide: [`website.md`](website.md)
- Flashing: [`flash.md`](flash.md)
- Hardware: [`hardware.md`](hardware.md)
- Local deployment: [`deploy.md`](deploy.md)
- FAQ: [`faq.md`](faq.md)
