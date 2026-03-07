English | [中文](README_ZH.md)

# InkSight | inco (墨鱼)

> An LLM-powered smart e-ink desktop companion that delivers calm, meaningful "slow information" on your desk.

Official Website: [https://www.inksight.site](https://www.inksight.site)

![Version](https://img.shields.io/badge/version-v0.1-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Platform](https://img.shields.io/badge/platform-ESP32--C3-orange)
![Python](https://img.shields.io/badge/python-3.10+-blue)

![inco](images/intro.jpg)

---

## Overview

**inco** (墨鱼) is a minimalist smart e-ink desktop companion that generates warm, thoughtful "slow information" through LLM. It uses a backend LLM to generate personalized content based on real-time context — weather, time of day, date, and solar terms — and renders it on a 4.2-inch e-ink screen. With dozens of content modes ranging from daily recommendations to AI briefings, it brings a thoughtful, intelligent companion to your desk.

The backend is built on the OpenAI-compatible SDK, so it works out of the box with **DeepSeek**, **Alibaba Bailian (Qwen)**, and **Moonshot (Kimi)**. Modes are extensible via a JSON config-driven system — create your own content modes without writing Python.

**Key Features:**

- **22 Built-in Modes + Custom Modes** — Core: Daily, Weather, Poetry, ArtWall, Almanac, Briefing; Extended: Stoic, Zen, Recipe, Countdown, Memo, Habit, Letter, ThisDay, Riddle, Question, Bias, Story, LifeBar, Challenge, Roast, Fitness; plus custom JSON modes
- **Extensible Mode System** — Define new modes via JSON config (prompt, layout, style) without writing code
- **AI Mode Generator** — Generate custom modes from natural language descriptions using LLM — "more content, defined by you"
- **Built-in Mode Editor** — Create/edit custom JSON modes with templates and preview in web config
- **4 Refresh Strategies** — Random, Sequential, Time-Bound, Smart
- **Active/Interval Runtime Modes** — Single press BOOT toggles runtime mode; trigger refresh, mode switch, or preview push remotely via web/API
- **User Authentication** — User registration, login, and device binding system
- **Device Token Security** — Token-based authentication for device API access
- **Habit Tracker** — Daily habit tracking with check-in and status monitoring
- **Favorites System** — Save and revisit favorite content and modes
- **Content History** — Browse historical rendered content with pagination
- **Share & QR Codes** — Share device content and generate QR codes for easy access
- **Widget Endpoint** — Embed InkSight content as widgets in external pages
- **Statistics Dashboard** — Device status monitoring, battery voltage trends, mode usage stats, cache hit rate
- **WiFi Provisioning** — Captive Portal auto-popup for zero-friction setup
- **Web Configuration** — Full settings management with import/export, live preview, and config history
- **Smart Caching** — Batch pre-generated content with sub-second response times
- **Multi-LLM Support** — DeepSeek, Alibaba Bailian (Qwen), Moonshot (Kimi)
- **Ultra-Low Power** — Deep Sleep mode, 6 months battery life on a single charge with LiFePO4 battery
- **Affordable Hardware** — Total BOM cost around ¥220, open-source hardware that everyone can build

---

## Content Modes

![Content Modes](images/mode.png)

### Core Modes (6)

| Mode | Description |
|------|-------------|
| **DAILY** — Daily Picks | Rich layout with quotes, book recommendations, fun facts, and seasonal info |
| **WEATHER** — Weather Dashboard | Real-time weather snapshot with practical day planning hints |
| **POETRY** — Daily Poetry | Curated classical Chinese poetry, celebrating the beauty of language |
| **ARTWALL** — AI Gallery | Black-and-white woodcut-style artwork generated from weather and seasonal context |
| **ALMANAC** — Chinese Almanac | Lunar calendar dates, auspicious/inauspicious activities, solar terms, health tips |
| **BRIEFING** — AI Briefing | Hacker News Top 3 + Product Hunt #1, with AI industry insights |

### Custom Modes

Create your own content modes in two ways:
- **Manual Creation**: Define custom modes via JSON config (prompt, layout, style) using the built-in mode editor
- **AI Generation**: Generate mode definitions from natural language descriptions using LLM

---

## Refresh Strategies

| Strategy | Description |
|----------|-------------|
| **Random** | Randomly pick from enabled modes |
| **Sequential** | Cycle through enabled modes in order (progress persists across reboots) |
| **Time-Bound** | Display different modes based on time of day (e.g. Recipe in the morning, Briefing mid-day, Zen at night) |
| **Smart** | Automatically match the best mode to the current time slot |

---

## Architecture

![Architecture Diagram](structure.png)

| Layer | Tech Stack |
|-------|------------|
| Hardware | ESP32-C3 (RISC-V, WiFi, ultra-low power) + 4.2" E-Paper (400x300, 1-bit, paper-like texture, non-glowing) + LiFePO4 battery |
| Firmware | PlatformIO / Arduino, GxEPD2, WiFiManager |
| Backend | Python 3.10+ FastAPI, Pillow, OpenAI SDK, httpx, SQLite, PyJWT, qrcode, dashscope |
| Frontend | Static HTML pages (`webconfig/`) + Next.js 16.1.6 web app (`webapp/`, website + flasher) |
| Authentication | JWT-based user sessions + Device Token authentication |

For detailed architecture design, see the [Architecture Documentation](docs/architecture.md) (Chinese).

---

## What You Need

### Hardware Checklist

- ESP32-C3 dev board (SuperMini recommended)
- 4.2" e-ink display (SPI, 400x300)
- Dupont wires / soldering tools (depending on your assembly method)
- Power option: USB power, or LiFePO4 battery + TP5000 charging module (optional)

### Setup Device Checklist

- A computer (Windows/macOS/Linux, Chrome/Edge recommended)
- A USB cable with data transfer support (for flashing)
- A 2.4GHz WiFi network (for weather + LLM content updates)
- LLM API key(s) when using self-hosted backend
- Optional: a smartphone, only if you want to use captive portal from mobile

---

## Getting Started

### 1. Hardware

- ESP32-C3 dev board (SuperMini recommended) — RISC-V architecture, WiFi connectivity, ultra-low power
- 4.2" e-ink display (SPI, 400x300) — Paper-like texture, non-glowing, eye-friendly
- LiFePO4 battery + TP5000 charge module (optional) — 6 months battery life with Deep Sleep mode

See the [Hardware Guide](docs/hardware.md) (Chinese) for wiring details.

### 2. Backend Deployment

```bash
# Clone the repository
git clone https://github.com/datascale-ai/inksight.git
cd inksight/backend

# Install dependencies
pip install -r requirements.txt

# Download font files (Noto Serif SC, Lora, Inter — ~70MB)
python scripts/setup_fonts.py

# Configure environment variables
cp .env.example .env
# Edit .env and fill in your API key

# Start the server
python -m uvicorn api.index:app --host 0.0.0.0 --port 8080
```

You can use either of the following paths:

- **Public hosted usage (recommended for beginners)**: use the public site directly for flashing and configuration.
- **Local self-hosted usage**: run backend (`http://127.0.0.1:8080`) + webapp (`http://localhost:3000`) locally for configuration and development.

Pick one path for a given runtime setup. In normal usage, you don't need to use both public and local targets at the same time.

Entry points:

| Entry | URL | Description |
|------|-----|-------------|
| Live Demo / Official Website | `https://www.inksight.site` | Public hosted site (easy start for beginners) |

| Local Backend Page | URL | Description |
|------|-----|-------------|
| Preview Console | `http://localhost:8080` | Test rendering for each mode |
| Config Manager | `http://localhost:8080/config` | Manage device configuration |
| Stats Dashboard | `http://localhost:8080/dashboard` | Device status and usage statistics |
| Mode Editor | `http://localhost:8080/editor` | Create and edit custom JSON modes |

### 2.5 Web App (website + flasher)

```bash
cd webapp

# Configure environment variables
cp .env.example .env

npm install

npm run dev
```

Install Node.js in advance

Default URL: `http://localhost:3000`

Environment variables (follow the path you choose):

- `INKSIGHT_BACKEND_API_BASE` (backend target: local self-host usually `http://127.0.0.1:8080`; public deployment uses your backend domain)
- `NEXT_PUBLIC_FIRMWARE_API_BASE` (optional browser-side API base; if set, keep it the same backend target as above)

`/config` in `webapp` includes user login + device binding workflow.

### 3. Firmware Flashing

**Option A: Web Flasher (recommended)**

- Open the InkSight Web Flasher page in Chrome/Edge.
- Select a firmware version from GitHub Releases.
- Connect the ESP32-C3 board over USB and click flash.

Firmware artifacts are published as `inksight-firmware-<semver>.bin` in GitHub Releases.

**Option B: Local flashing with PlatformIO**

```bash
cd firmware

# Build and upload with PlatformIO
pio run --target upload

# Monitor serial output
pio device monitor
```

Alternatively, open `firmware/src/main.cpp` in Arduino IDE to compile and upload.

If `webapp` is deployed separately from backend API, point
`NEXT_PUBLIC_FIRMWARE_API_BASE` to the same backend target you selected. If
not set, `webapp` proxies `/api/firmware/*` to `INKSIGHT_BACKEND_API_BASE`.

### 4. WiFi Provisioning

In most cases, setup can be completed end-to-end in the web frontend. Captive Portal is an optional fallback path.

1. On first boot (or missing WiFi config), the device enters Captive Portal automatically
2. If already configured, long press BOOT (>= 2s) to reboot; keep holding during reboot to force portal mode
3. Connect your computer (or phone) to the `InkSight-XXXX` hotspot
4. A configuration page will pop up automatically — select your WiFi, then choose official server (quick start) or custom backend URL (self-hosted)

### 5. Button Controls

| Action | Effect |
|--------|--------|
| RESET | Hardware reboot |
| Short press BOOT (>= 50ms and < 2s) | Toggle runtime mode: `active` (live polling) / `interval` |
| Long press BOOT (>= 2s) | Restart device |
| Hold BOOT during reboot | Enter Captive Portal provisioning mode |

On first successful setup, firmware enters `active` mode by default once.

---

## Configuration

![Configuration](images/configuration.png)

Visit `http://your-server:8080/config?mac=XX:XX:XX:XX:XX:XX` to configure your device:

| Setting | Description |
|---------|-------------|
| Nickname | Device display name |
| Content Modes | Select which modes to display (multi-select) |
| Refresh Strategy | Random / Sequential / Time-Bound / Smart |
| Time-Bound Rules | Map time slots to specific modes (up to 24 rules) |
| Refresh Interval | 10 minutes to 24 hours |
| Language | Chinese / English / Bilingual |
| Content Tone | Positive / Neutral / Profound / Humorous |
| Character Voice | Presets (Lu Xun, Wang Xiaobo, JARVIS, Socrates, Haruki Murakami) + custom |
| Location | Used for weather data |
| LLM Provider | DeepSeek / Alibaba Bailian / Moonshot |
| LLM Model | Select a specific model based on provider |
| Countdown Events | Date events for COUNTDOWN mode (up to 10) |
| Mode Overrides | Override city/provider/model and mode-specific fields per mode |
| API Keys | Device-level text/image API keys (encrypted at rest) |

### Config Management

- **Import / Export** — Backup and migrate device config in JSON format
- **Live Preview** — Preview rendering for each mode before saving
- **Remote Refresh** — Trigger the device to refresh content on next wake-up
- **Config History** — View and rollback to previous config versions
- **Custom Mode Editor** — Create and edit custom JSON modes with visual editor
- **AI Mode Generator** — Generate mode definitions from natural language descriptions

### Additional Features

- **Habit Tracker** — Track daily habits with check-in functionality (accessible via HABIT mode)
- **Favorites** — Save favorite content and modes for quick access
- **Content History** — Browse historical rendered content with filtering
- **Share & QR Codes** — Share device content and generate QR codes for easy access
- **Widget Embedding** — Embed InkSight content as widgets in external pages
- **Device Authentication** — Secure device API access with token-based authentication
- **User Accounts** — Register, login, and bind multiple devices to your account

See the [API Documentation](docs/api.md) (Chinese) for full endpoint details.

---

## Statistics Dashboard

![Statistics Dashboard](images/dashboard.png)

Visit `http://your-server:8080/dashboard?mac=XX:XX:XX:XX:XX:XX` to view device statistics:

- **Device Status** — Last refresh time, battery voltage, WiFi signal strength (RSSI)
- **Voltage Trend** — Battery voltage history chart (last 30 records)
- **Mode Stats** — Usage frequency distribution per mode
- **Daily Renders** — Daily render count bar chart
- **Cache Hit Rate** — Cache usage efficiency
- **Render Log** — Recent render details (mode, duration, status)

---

## API Endpoints

### Core Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/render` | Generate BMP image (called by device) |
| GET | `/api/preview` | Generate PNG preview |
| GET | `/api/widget/{mac}` | Widget endpoint for embedding content (read-only) |

### Configuration Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/config` | Save device configuration |
| GET | `/api/config/{mac}` | Get current configuration |
| GET | `/api/config/{mac}/history` | Get configuration history |
| PUT | `/api/config/{mac}/activate/{config_id}` | Activate a specific configuration |

### Mode Management Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/modes` | List all available modes (builtin + custom) |
| POST | `/api/modes/custom/preview` | Preview custom mode definition |
| POST | `/api/modes/custom` | Create/update custom JSON mode |
| GET | `/api/modes/custom/{mode_id}` | Get custom mode definition |
| DELETE | `/api/modes/custom/{mode_id}` | Delete custom mode |
| POST | `/api/modes/generate` | Generate mode definition from natural language (AI) |

### Device Control Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/device/{mac}/refresh` | Trigger immediate device refresh |
| GET | `/api/device/{mac}/state` | Get device runtime state |
| POST | `/api/device/{mac}/runtime` | Set device runtime mode (active/interval) |
| POST | `/api/device/{mac}/apply-preview` | Queue preview image to device |
| POST | `/api/device/{mac}/switch` | Switch to a specific mode |
| POST | `/api/device/{mac}/favorite` | Favorite current content or mode |
| GET | `/api/device/{mac}/favorites` | Get favorites list |
| GET | `/api/device/{mac}/history` | Get content history (paginated) |
| POST | `/api/device/{mac}/token` | Generate device authentication token |
| GET | `/api/device/{mac}/qr` | Generate QR code for device access |
| GET | `/api/device/{mac}/share` | Get shareable content |
| GET | `/api/devices/recent` | Get recently used devices |

### Habit Tracker Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/device/{mac}/habit/check` | Record habit check-in |
| GET | `/api/device/{mac}/habit/status` | Get habit status for current week |
| DELETE | `/api/device/{mac}/habit/{habit_name}` | Delete habit and all records |

### Statistics Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/stats/overview` | Global statistics overview (admin) |
| GET | `/api/stats/{mac}` | Device statistics detail |
| GET | `/api/stats/{mac}/renders` | Render history (paginated) |

### Firmware Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/firmware/releases` | Get firmware release list |
| GET | `/api/firmware/releases/latest` | Get latest firmware version |
| GET | `/api/firmware/validate-url` | Validate firmware download URL |

### Authentication Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/register` | User registration |
| POST | `/api/auth/login` | User login |
| POST | `/api/auth/logout` | User logout |
| GET | `/api/auth/me` | Get current user info |

### User Device Management

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/user/devices` | List user's bound devices |
| POST | `/api/user/devices` | Bind device to user |
| DELETE | `/api/user/devices/{mac}` | Unbind device from user |

**Note:** 
- Device endpoints require `X-Device-Token` header for authentication
- Admin endpoints require `Authorization: Bearer <token>` header
- Widget endpoint (`/api/widget/{mac}`) is read-only and does not update device state or trigger refreshes

---

## Project Structure

```
inksight/
├── backend/                # Python backend service
│   ├── api/index.py        # FastAPI entry point + all API endpoints
│   ├── core/               # Core modules
│   │   ├── config.py       # Configuration constants
│   │   ├── config_store.py # Config storage + device state (SQLite)
│   │   ├── stats_store.py  # Statistics collection and queries
│   │   ├── context.py      # Environment context (weather/date)
│   │   ├── content.py      # LLM content generation
│   │   ├── json_content.py # JSON mode content generation
│   │   ├── pipeline.py     # Unified generation pipeline
│   │   ├── renderer.py     # Builtin mode image rendering
│   │   ├── json_renderer.py# JSON mode image rendering
│   │   ├── mode_registry.py# Mode registration (builtin + JSON)
│   │   ├── mode_generator.py # AI mode definition generator
│   │   ├── cache.py        # Caching system
│   │   ├── schemas.py      # Pydantic request validation
│   │   ├── auth.py         # Authentication (JWT + device tokens)
│   │   ├── crypto.py       # Cryptographic utilities
│   │   ├── db.py           # Database connection management
│   │   ├── errors.py       # Error handling
│   │   └── modes/          # JSON mode definitions
│   │       ├── schema/     # JSON Schema for mode validation
│   │       ├── builtin/    # 22 built-in JSON modes
│   │       └── custom/     # User-defined custom JSON modes
│   ├── scripts/            # Utility scripts
│   │   └── setup_fonts.py  # Font download script
│   ├── fonts/              # Font files (downloaded via script)
│   │   └── icons/          # PNG icons
│   ├── tests/              # Test files
│   ├── requirements.txt    # Python dependencies
│   └── vercel.json         # Vercel deployment config
├── firmware/               # ESP32-C3 firmware
│   ├── src/
│   │   ├── main.cpp        # Main firmware (button handling + refresh logic)
│   │   ├── config.h        # Pin definitions + constants
│   │   ├── network.cpp     # WiFi / HTTP / NTP (with RSSI reporting)
│   │   ├── display.cpp     # E-ink display logic
│   │   ├── storage.cpp     # NVS storage
│   │   └── portal.cpp      # Captive Portal provisioning
│   ├── data/portal_html.h  # Provisioning page HTML
│   └── platformio.ini      # PlatformIO configuration
├── webconfig/              # Web config frontend
│   ├── config.html         # Configuration manager
│   ├── preview.html        # Preview console
│   └── dashboard.html      # Statistics dashboard
├── webapp/                 # Next.js 16.1.6 website + Web Flasher frontend
│   ├── app/                # App Router pages and API routes
│   ├── components/         # UI components
│   ├── lib/                # Utility libraries
│   ├── public/             # Static assets
│   └── package.json        # Node.js dependencies and scripts
└── docs/                   # Documentation
    ├── architecture.md     # System architecture
    ├── api.md              # API reference
    └── hardware.md         # Hardware guide
```

---

## Roadmap

- [x] WiFi provisioning (Captive Portal)
- [x] Online config management + config history
- [x] Sequential / Random refresh strategies
- [x] Time-Bound + Smart refresh strategies
- [x] Smart caching (cycle index persists across reboots)
- [x] 22 content modes (including Weather, Memo, Habit, Almanac, Letter, ThisDay, Riddle, Question, Bias, Story, LifeBar, Challenge)
- [x] Multi-LLM provider support
- [x] On-demand refresh, mode switch, and preview push via web/API
- [x] Config import/export + live preview
- [x] Toast notifications replacing confirm/alert dialogs
- [x] Enhanced Preview console (request cancellation, history, rate limiting, resolution simulation)
- [x] Statistics dashboard (device monitoring + usage stats + chart visualization)
- [x] RSSI signal strength reporting
- [x] Extensible mode system (JSON config-driven custom modes)
- [x] User authentication system (registration, login, device binding)
- [x] Device token authentication for secure API access
- [x] Custom mode management (create, preview, delete)
- [x] AI mode generator (natural language to mode definition)
- [x] Habit tracker with check-in and status monitoring
- [x] Favorites system for content and modes
- [x] Content history with pagination
- [x] Share functionality and QR code generation
- [x] Widget endpoint for embedding content
- [x] Mode editor web page
- [x] Multi-resolution rendering support (`w` / `h` request params + firmware build-time screen sizes)
- [x] User-provided API keys (device-level LLM/Image keys with encrypted storage)
- [ ] One-click Vercel deployment
- [ ] Hardware productization (PCB design)

---

## Contributing

Issues and Pull Requests are welcome! See the [Contributing Guide](CONTRIBUTING.md) (Chinese) for details.

---

## License

[MIT License](LICENSE)

---

## Acknowledgments

- [Open-Meteo](https://open-meteo.com/) — Free weather data API
- [Hacker News](https://news.ycombinator.com/) — Tech news
- [Product Hunt](https://www.producthunt.com/) — Product discovery
- [DeepSeek](https://www.deepseek.com/) — LLM provider
- [Alibaba Bailian](https://bailian.console.aliyun.com/) — LLM provider (Qwen)
- [Moonshot](https://www.moonshot.cn/) — LLM provider (Kimi)
- [GxEPD2](https://github.com/ZinggJM/GxEPD2) — E-Paper display driver library
