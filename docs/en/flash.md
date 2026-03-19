# Web Flasher

InkSight provides browser-based firmware flashing for most users.

![Web flasher screenshot](/images/docs/flash-en.png)

The current flasher page shows the step-by-step guide, firmware source selector, and console logs in one screen.

## Video Tutorial

- Flashing walkthrough: [`Bilibili: InkSight Web Flasher demo`](https://www.bilibili.com/video/BV1aWcQzQE3r/?spm_id_from=333.1387.homepage.video_card.click&vd_source=166ea338ef8c38d7904da906b88ef0b7)

## Requirements

- Chrome or Edge (WebSerial support)
- HTTPS site or `localhost`
- USB data cable (not charge-only)

## Steps

1. Open the **Web Flasher** page
2. Connect device and authorize serial port
3. Select firmware version
4. Click flash and wait for completion

## Troubleshooting

- Serial port not found: check cable and USB driver
- Releases fail to load: check backend availability
- Flash interrupted: reconnect device and retry
