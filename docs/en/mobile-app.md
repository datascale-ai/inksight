# Mobile App Guide

This document covers how to use the InkSight iOS / Android app, including account management, device pairing, mode browsing, firmware updates, and more.

> **Tip**: If you're new to InkSight, start with the [Website Guide](website) to understand the overall product experience.

---

## 1. Account and Login

### Sign In

If you already have an InkSight website account:

1. Enter your **username** and **password** on the login page
2. Tap **Sign In**
3. On success, you'll be redirected to the **Me** tab

### Register

If you don't have an account yet:

1. Tap "**Create Account**" at the bottom of the login page
2. Fill in your nickname, email, and password
3. You can log in after registration

### Forgot Password

1. Tap "**Forgot Password**" on the login page
2. Enter your username, phone number, or email used during registration
3. Reset your password

### Sign Out

Go to the "**Me**" tab and tap "Sign Out".

---

## 2. Device Pairing

### Prerequisites

- Your device has been flashed with InkSight firmware and connected to Wi-Fi
- Your phone and the device are on the **same Wi-Fi network**

### Adding a Device

1. Go to the "**Device**" tab and tap "**Pair Device**"
2. Choose **Pairing Code** or **Enter MAC Address manually**
   - Pairing Code: The pairing code will appear on the device screen after network setup
   - Manual: Type the device MAC address (e.g., `AABBCCDD0011`)
3. The device appears in your device list once paired

### Device Status

| Status | Meaning |
|--------|---------|
| Online | Device is currently connected to the network |
| Offline | Device is not connected or powered off — check the device power supply |

---

## 3. Mode Browsing and Pushing

### Discover Tab

- **Modes**: Handpicked quality modes, custom modes, and more
- **History**: Modes you've browsed will appear here
- **Favorites**: Modes you've favorited will appear here

### Mode Detail Page

Tap any mode card to see:

- Mode name and description
- AI rewrite mode

---

## 4. Device Configuration

### Accessing Device Settings

Tap any device card in the "**Device**" tab to open its configuration page.

- View current **device status**, including current mode, online status, and refresh interval
- View current **device configuration**, including modes in the rotation, rotation strategy, and city
- View current **modes in rotation**, generate preview images and share them

### Editing Device Configuration

- **City / Location**: Set the city for weather information
- **Refresh Interval**: How often to trigger a refresh (recommended: 15~60 minutes)
- **Modes**: View all modes available for this device's rotation, including built-in and custom modes

### Managing Shared Members

- View the device **owner and shared members**
- Handle **join requests** from other users
- Device owners can **remove** or **invite** members

### Viewing Firmware (OTA)

#### Checking Firmware Version

After entering the **Firmware** page, the latest firmware information is automatically fetched. You can also tap **Refresh Firmware Info** to fetch it again.

#### Performing an OTA Update

When a new firmware version is available:

1. Tap "**Refresh Firmware Info**" on the firmware update page
2. If a new version is found, tap "**Online Flash**" (the device can only be flashed online when in active state)
3. Wait for the firmware to download (1~3 minutes depending on network)
4. The device restarts automatically and applies the new firmware

### Notes

- **Keep the device powered on** during the upgrade — power loss may cause firmware corruption
- It is recommended to perform firmware updates over a stable Wi-Fi connection

---

## Related Documents

- [Device Configuration Guide](config)
- [Website Guide](website)
- [Web Flashing Guide](flash)
- [Hardware Guide](hardware)
- [FAQ](faq)
