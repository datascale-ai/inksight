# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

InkSight ("inco" / 墨鱼) is a smart e-ink desktop companion: an ESP32-C3 device that displays LLM-generated content on a 4.2" e-ink screen. The system consists of a Python FastAPI backend, a Next.js web app, static web config pages, and ESP32 firmware.

## Commands

### Backend (Python / FastAPI)

```bash
cd backend

# Install dependencies
pip install -r requirements.txt

# Download fonts (~70MB, required before first run)
python scripts/setup_fonts.py

# Copy and configure environment
cp .env.example .env
# Fill in DEEPSEEK_API_KEY, DASHSCOPE_API_KEY, MOONSHOT_API_KEY

# Run the development server
python -m uvicorn api.index:app --host 0.0.0.0 --port 8080

# Run all tests
pytest

# Run a single test file
pytest tests/test_unit_pipeline.py

# Run a specific test function
pytest tests/test_unit_pipeline.py::test_my_function -v
```

### Web App (Next.js)

```bash
cd webapp
npm install
npm run dev      # http://localhost:3000
npm run build
npm run lint
```

### Firmware (PlatformIO)

```bash
cd firmware
pio run --target upload   # Build and flash to ESP32-C3
pio device monitor        # Serial monitor at 115200 baud
```

## Architecture

### Backend (`backend/`)

The backend is a single FastAPI app (`api/index.py`) that serves both API endpoints and static HTML pages from `webconfig/`.

**Core pipeline flow** (for every `/api/render` or `/api/preview` request):
1. `api/index.py` — receives device request (MAC, battery voltage, etc.)
2. `core/cache.py` — checks `ContentCache` (in-memory + SQLite `cache.db`); if hit, returns immediately
3. If miss: `core/pipeline.py:generate_and_render()` — unified dispatcher
4. `core/mode_registry.py:ModeRegistry` — singleton that holds all registered modes; determines if a mode is "builtin Python" or "JSON-defined"
5. **JSON modes**: `core/json_content.py` → `core/json_renderer.py`
6. **Python modes**: `core/patterns/` → `core/renderer.py`
7. Image returned as 1-bit BMP (for device) or PNG (for preview)

**Mode system** — all 22 built-in modes are now JSON-defined (in `core/modes/builtin/`). Custom user modes go in `core/modes/custom/`. The registry loads both at startup. JSON modes can shadow builtin ones only if `mode_id` does not conflict.

**JSON mode definition** structure (required fields):
- `mode_id`, `display_name`, `cacheable`
- `content.type` — one of `llm`, `llm_json`, `static`, `external_data`, `image_gen`, `computed`, `composite`
- `content.prompt_template` + `content.fallback` (required for `llm`/`llm_json` types)
- `layout.body` — list of block renderers (non-empty)

**Data stores** — two SQLite databases:
- `inksight.db` — device configs, config history, device state (managed by `core/config_store.py`)
- `cache.db` — rendered image cache (managed by `core/cache.py`)

**LLM providers** configured in `core/content.py:LLM_CONFIGS`:
- `deepseek` → `DEEPSEEK_API_KEY`
- `aliyun` → `DASHSCOPE_API_KEY`
- `moonshot` → `MOONSHOT_API_KEY`

All LLM calls use the OpenAI-compatible SDK. The `ARTWALL` mode calls Alibaba's image generation API separately via `dashscope`.

**Cache TTL formula**: `refresh_interval × mode_count × 1.1` minutes. The cache pre-generates all enabled cacheable modes at once when any mode is missing.

### Key source files

| File | Purpose |
|------|---------|
| `backend/api/index.py` | All API endpoints + FastAPI app lifecycle |
| `backend/core/pipeline.py` | Unified generate+render dispatcher |
| `backend/core/mode_registry.py` | `ModeRegistry` singleton; `ContentContext` dataclass |
| `backend/core/json_content.py` | JSON mode content generation (LLM calls, static data) |
| `backend/core/json_renderer.py` | JSON mode image rendering engine |
| `backend/core/cache.py` | `ContentCache` (in-memory + SQLite) |
| `backend/core/config.py` | All constants: screen size, fonts, cities, defaults |
| `backend/core/config_store.py` | Device config CRUD + device state (SQLite) |
| `backend/core/stats_store.py` | Render logging + statistics queries |
| `backend/core/context.py` | Weather (Open-Meteo) + date/lunar calendar context |
| `backend/core/content.py` | Low-level LLM call functions; `LLM_CONFIGS` |
| `backend/core/renderer.py` | Builtin Python mode rendering; BMP/PNG conversion |
| `backend/core/patterns/utils.py` | Shared drawing utilities for all renderers |

### Web Config (`webconfig/`)

Static HTML pages served by the FastAPI app:
- `config.html` — device configuration manager
- `preview.html` — render preview console
- `dashboard.html` — statistics dashboard

### Web App (`webapp/`)

Next.js 16 app (App Router) with Tailwind CSS v4. Serves the public website and the Web Flasher for firmware flashing via WebSerial. Environment variables:
- `INKSIGHT_BACKEND_API_BASE` — server-side proxy target (default `http://127.0.0.1:8080`)
- `NEXT_PUBLIC_FIRMWARE_API_BASE` — browser-side API base (optional)

### Firmware (`firmware/`)

PlatformIO / Arduino project for ESP32-C3. Main files:
- `src/main.cpp` — main loop, button handling (short/double/long press), deep sleep + wake logic
- `src/network.cpp` — WiFi connection, HTTP fetch from backend, NTP time sync, RSSI reporting
- `src/display.cpp` — GxEPD2 e-ink display driver
- `src/portal.cpp` — Captive Portal for WiFi provisioning

## Testing

Tests live in `backend/tests/`. `conftest.py` sets dummy API keys (so tests run without real credentials) and adds `backend/` to `sys.path`. The `pytest.ini` sets `asyncio_mode = auto`.

Test files named `test_unit_*.py` test individual modules; others (e.g. `test_briefing_mode.py`) test specific modes end-to-end. Use `pytest -k <pattern>` to filter.

## Creating a Custom JSON Mode

Place a `.json` file in `backend/core/modes/custom/`. Minimum structure:

```json
{
  "mode_id": "MY_MODE",
  "display_name": "My Mode",
  "cacheable": true,
  "content": {
    "type": "llm",
    "prompt_template": "Your prompt with {context} placeholder.",
    "output_format": "text",
    "fallback": { "text": "Fallback content" }
  },
  "layout": {
    "body": [
      { "type": "centered_text", "field": "text", "font": "noto_serif_light", "font_size": 18 }
    ]
  }
}
```

The mode registry reloads on server restart. Mode IDs must not conflict with existing builtin IDs. See `backend/core/modes/custom/my_quote.json` for a working example.
