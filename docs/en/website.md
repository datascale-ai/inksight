# Website Guide

This guide is not about deployment commands. It is a product-facing walkthrough of the main website entry points, so you can tell **where to click next**.

> The screenshots below come from the current local product build. Depending on locale and login state, labels may differ slightly.

![Homepage navigation overview](/images/docs/home-en.png)

The homepage is the easiest place to understand the product map: **Mode Plaza, Web Flasher, Device Config, and the no-device demo** all branch from here.

## 1. Who this is for

- You are visiting the site for the first time and want to understand the experience first
- You do not have a device yet and want to preview the product
- You already bought the hardware and want to flash, connect, and configure it
- You want a clear explanation of what the mode plaza, device config, and profile pages are for

## 2. The five entry points to remember

### Mode Plaza

- This is the best place to browse the content ecosystem and see what the community is making.
- The current page supports **search**, **category filters**, and a **publish mode** entry.
- If you are still deciding whether InkSight fits your workflow, start here.

![Mode Plaza screenshot](/images/docs/discover-en.png)

You can start by browsing cards, then narrow the list with search and category filters.

### No-device Demo

- Use this when you do not have hardware yet, have not flashed it yet, or just want a quick visual preview.
- You can choose a mode and generate an e-ink style preview before touching a device.
- Some modes expose their own preview inputs, such as city, memo text, or custom copy.
- Think of this page as the playground for testing content feel and layout.

![No-device preview screenshot](/images/docs/preview-en.png)

This is the safest place to check whether a mode feels right before saving anything to a real device.

### Web Flasher

- This is the fastest route once the hardware is on your desk.
- Connect over USB, select firmware, authorize the serial port, and flash directly in the browser.
- After flashing, the device typically reboots into the initial network/setup flow.

![Web flasher screenshot](/images/docs/flash-en.png)

The flasher page keeps the steps, firmware source, and runtime logs in one place, which makes the first-time flow easier to follow.

### Device Configuration

- This is the page you will use most after the device is up and running.
- Right now it requires sign-in first, then selecting a device from your device list.
- The main tabs are:
  - **Modes**: choose what the device shows, preview results, and set mode-specific parameters
  - **Preferences**: set the global location, language, tone, refresh strategy, and interval
  - **Sharing**: collaborate on the same device with other users
  - **Status**: check online state, lithium battery level, signal, and rendering stats

![Device configuration entry screenshot](/images/docs/config-en.png)

This screenshot shows the signed-in state with a bound device. From here, you can see your device list, pairing entry, and device cards before entering the full configuration flow.

### Profile

- This page manages **models, API keys, quota, and access mode**.
- If AI-generated modes stop working, check here before changing device config.
- A simple way to think about it:
  - **Device Configuration** decides what the device shows and how often it refreshes
  - **Profile** decides which model and which key the system uses to generate content

## 3. Three common user journeys

### I do not have a device yet

1. Start with **Mode Plaza** to explore the mode ecosystem
2. Go to **No-device Demo** to see how several modes look on e-ink
3. Decide whether you want to build or buy the hardware

### I just got the hardware and want it working fast

1. Review the hardware list and assembly guide
2. Open **Web Flasher** and complete browser-based flashing
3. Finish Wi-Fi setup on the device
4. Sign in and go to **Device Configuration** to choose modes and preferences
5. If you want AI-generated content, configure models and API keys in **Profile**

### My device is already running and I want to keep refining it

1. Browse **Mode Plaza** for ideas or community modes
2. Tune your active device in **Device Configuration**
3. Use **No-device Demo** when you want to test the visual result first
4. Adjust model and key settings in **Profile** when needed

## 4. How to use the Mode Plaza

- Browse cards when you want inspiration
- Use search when you already know the mode name, author, or idea
- Narrow things down with the category filters such as productivity, learning, life, fun, and geek
- Use the publish entry after signing in when you want to share your own creation

If you are unsure how a mode will look on-screen, the safest path is: **preview first, then save it through device config**.

## 5. Two things people often mix up in device configuration

### Global settings vs. mode settings

- **Global settings** live in the Preferences tab, such as default location, language, and refresh strategy
- **Mode settings** live inside the Modes tab and only affect one mode

Using Weather as the example:

- you can set one global default location for the device
- you can also set a dedicated location just for Weather
- if Weather has no dedicated location, it falls back to the global default

### Device Configuration vs. Profile

- **Device Configuration**: device behavior, content preferences, mode selection
- **Profile**: models, API keys, quota, access mode

A practical rule:

- “Why does the content look wrong?” → check **Device Configuration**
- “Why did AI generation fail?” → check **Profile**

## 6. When you want to try things without committing

- Use **No-device Demo** for device-free experiments
- Use per-mode preview inside **Device Configuration**
- Save to the device only after the result looks right

This is the safest way to learn the product without constantly rewriting your live setup.

## 7. Recommended reading order

- Understand the website first: [`website.md`](website.md)
- If you already have hardware: [`hardware.md`](hardware.md) → [`assembly.md`](assembly.md) → [`flash.md`](flash.md)
- Ready to configure the device: [`config.md`](config.md)
- Ready to enable AI features: [`api-key.md`](api-key.md)
