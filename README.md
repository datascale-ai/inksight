English | [中文](README_ZH.md)

# InkSight

> A calm e-ink desk companion with one website for flashing, configuration, preview, and discovering new modes.

Official website: [https://www.inksight.site](https://www.inksight.site)

![InkSight](images/intro_eng.jpg)

## Why It Stands Out

InkSight turns a small e-ink screen into a quiet, always-visible information surface for your desk.
Instead of another glowing notification feed, it gives you useful, beautiful, and customizable content in a paper-like form.

- **Useful at a glance** — weather, countdowns, memos, habits, briefings, and daily prompts
- **Made for desks** — a paper-like e-ink display that stays visible without adding screen fatigue
- **Beautiful and varied** — 24 built-in modes, from practical dashboards to more atmospheric content
- **A one-stop website experience** — beginner-friendly browser flashing, online setup, preview, and mode discovery
- **Open and extensible** — firmware, backend, web configuration, and the JSON mode system are all designed to be expanded over time, including future hardware design files

## One Website, End to End

The website brings the whole user flow together in one place.
Even if you are completely new to e-paper devices, ESP32 boards, or WebSerial, the product is designed so you can get started by following the UI step by step instead of assembling your own toolchain first.

- **Flash firmware in the browser** with the Web Flasher, without starting from a local flashing setup
- **Configure devices online** with modes, preferences, refresh strategy, and per-mode overrides
- **Preview content before saving** so the final e-ink result is visible in advance
- **Try it even without a device** through the no-device demo flow
- **Discover community creations** in the mode plaza, then install and reuse ideas shared by other users

This makes InkSight feel less like a kit with scattered tools and more like a complete product experience.

## Rich Mode Library

InkSight currently ships with **24 built-in modes**, including:

- **Daily Picks** — quotes, books, facts, and seasonal context
- **Weather Dashboard** — live weather with practical advice
- **Poetry / Zen / Stoic** — calm, reflective content for focused desks
- **AI Briefing** — technology highlights and AI insights
- **ArtWall** — black-and-white AI artwork tailored to context
- **Memo / Countdown / Habit / Fitness** — practical everyday desk utilities

You can also:

- **create custom modes**
- **save them to your device**
- **share them to the mode plaza**
- **install community-created modes**

## Recommended Hardware

InkSight is easiest to build with the following setup:

| Part | Recommended choice |
|------|--------------------|
| MCU | ESP32-C3 development board |
| Display | 4.2-inch SPI e-paper display |
| Power | USB for development, optional lithium battery build (recommended `505060-2000mAh` + TP5000) |
| Cost | Typical DIY BOM around **CNY 220** |

> **For detailed purchasing schemes and part links**, please refer to the [**Hardware Purchasing Guide**](docs/en/bom.md) (Note: links are mostly for Taobao, but equivalent parts can be found on AliExpress/Amazon).

The public documentation and setup flow are centered on **ESP32-C3 + 4.2-inch e-paper**.

For a first build, start with **ESP32-C3 + 4.2-inch e-paper**.

## Explore the Official Website

![Official Website](images/official_web_screenshot_eng.png)

If you want to get a feel for the product before buying parts or setting up anything locally, the official website is the best place to start:

- **Homepage** — a quick overview of the product and how the experience fits together
- **Web flasher** — browser-based firmware flashing, with a walkthrough video here: [`Flashing tutorial`](https://www.bilibili.com/video/BV1aWcQzQE3r/?spm_id_from=333.1387.homepage.video_card.click&vd_source=166ea338ef8c38d7904da906b88ef0b7)
- **Device configuration** — once a device is flashed, this is where you configure what it shows
- **Mode plaza** — browse community-made creations, publish your own, or install modes shared by other users
- **No-device demo** — try the experience even if you do not own the hardware yet

## Build the Device

If you enjoy DIY hardware and want to build your own InkSight unit, or if you already have the parts but are not sure how to wire and assemble them, start here:

![Build the Device](images/build-device.png)

You can also follow the step-by-step assembly video here: [`Assembly tutorial`](https://www.bilibili.com/video/BV1spwKzUE6N?spm_id_from=333.788.videopod.sections&vd_source=166ea338ef8c38d7904da906b88ef0b7)

We also provide the matching docs:

- Hardware guide: [`docs/hardware.md`](docs/hardware.md)
- Assembly guide: [`docs/assembly.md`](docs/assembly.md)
- Flashing guide: [`docs/flash.md`](docs/flash.md)
- Configuration guide: [`docs/config.md`](docs/config.md)

## Community Showcase

We are thrilled to see the amazing cases and custom PCBs created by the InkSight community! Here are some excellent community contributions:

### 3D Printable Cases
- **[Orange Desktop Case (MakerWorld)](https://makerworld.com/zh/@CANLAY)**
  
  <img src="images/community/case1.png" width="400">

- **[Pink/Red Minimalist Cases (MakerWorld)](https://makerworld.com/zh/@CANLAY)**
  
  <img src="images/community/case2.png" width="400">
  <img src="images/community/case3.png" width="400">

- **[Huawei Nova 14 Color Display Phone Case 3.98-inch 4-Color E-ink Screen](https://makerworld.com.cn/zh/models/2399226-gu-jian-kai-yuan-diy-hua-wei-nova14cai-xian-shou-j#profileId-2744953)**

  <img src="images/community/case4.png" width="400">

### Custom PCBs
- **[InkSight 4.2" Custom Driver Board (OSHWHUB)](https://oshwhub.com/kidstory/4-2)**
  
  <img src="images/community/pcb1.png" width="400">

- **[Moyu AI E-ink Screen (Verified)](https://oshwhub.com/qq173972819/project_mqihrlpc)**
  
  <img src="images/community/pcb2.png" width="400">

## Self-Host or Develop

If you are a developer, want to run your own local deployment, or want to go beyond the hosted website and build custom integrations or workflows, start here:

- Deployment guide: [`docs/en/deploy.md`](docs/en/deploy.md)
- 中文部署文档：[`docs/deploy.md`](docs/deploy.md)
- Architecture: [`docs/en/architecture.md`](docs/en/architecture.md)
- API: [`docs/en/api.md`](docs/en/api.md)
- Plugin / extension development: [`docs/en/plugin-dev.md`](docs/en/plugin-dev.md)

## Community

- Discord: [https://discord.gg/5Ne6D4YNf](https://discord.gg/5Ne6D4YNf)
- QQ 群: [1026120682](http://qm.qq.com/cgi-bin/qm/qr?_wv=1027&k=kha7gD4FzS3ld_f9bx_TlLIj94Oyoip1&authKey=n4yACMiVaMagSs5HUH5HLw%2BhXdKRFjCDI4rAt7zdVym7yTeXwMxTkWqUjE9jzjXo&noverify=0&group_code=1026120682)
- BiliBili: [https://www.bilibili.com/video/BV1nSNcziE7q/](https://www.bilibili.com/video/BV1nSNcziE7q/)

![QQ Group QR Code](images/QQ_EN.jpg)
