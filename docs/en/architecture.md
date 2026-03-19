# InkSight Architecture

This document reflects the current repository structure and explains the main layers, render pipeline, mode system, and storage model.

## 1. High-level structure

InkSight currently has three major parts:

- **Firmware** — ESP32 firmware for networking, fetching content, driving the e-paper display, and deep sleep behavior
- **Backend** — FastAPI service for configuration, weather context, content generation, rendering, caching, and stats
- **WebApp** — Next.js app for the website, docs, web flasher, login, configuration, and preview

## 2. Core data flow

A typical render flow looks like this:

1. the device requests content from the backend
2. the backend loads device config and environment context
3. the backend chooses static data, computed content, external data, or model-generated content depending on the mode
4. the renderer converts the result into a black-and-white image suitable for e-paper
5. the device receives the image and refreshes the screen

The WebApp also uses backend APIs for:

- saving device configuration
- previewing modes
- listing firmware releases
- showing device state and statistics

## 3. Backend architecture

The backend entry point is:

- `backend/api/index.py`

It serves:

- FastAPI endpoints
- legacy compatibility pages
- application startup and initialization

### Main render pipeline

For `/api/render` and `/api/preview`, the main flow is:

1. `api/index.py` receives the request
2. `core/cache.py` checks the render cache
3. on a miss, `core/pipeline.py:generate_and_render()` runs
4. `core/mode_registry.py` decides whether the mode is built-in or JSON-defined
5. `core/renderer.py` or `core/json_renderer.py` produces the final image

### Mode system

Built-in modes are now defined in:

- `backend/core/modes/builtin/`

Custom JSON modes are loaded from:

- `backend/core/modes/custom/`

The repository currently includes **24 built-in JSON modes**.

### Content sources

Depending on the mode, content may come from:

- static content
- computed rules
- external data
- text models
- image models
- composite pipelines

Weather-related context is mainly handled in:

- `backend/core/context.py`

### Storage and cache

The backend currently uses two SQLite databases:

- `inksight.db` for device config, config history, and device state
- `cache.db` for rendered image caching

Cache lifetime is derived from refresh interval and mode count so repeated renders are cheaper and faster.

## 4. WebApp architecture

The primary frontend lives in:

- `webapp/`

Its responsibilities include:

- website content
- documentation center
- web firmware flashing
- login and profile
- device configuration
- profile management
- preview flows

In the current product structure:

- Device Configuration manages device behavior and mode-related settings
- Profile manages models, API keys, quota, and access mode

That separation is important when reading the rest of the docs.

## 5. Firmware architecture

Firmware lives in:

- `firmware/`

Key modules include:

- `src/main.cpp` for the main loop, buttons, sleep, and wake behavior
- `src/network.cpp` for Wi-Fi, HTTP, and time sync
- `src/display.cpp` for display integration
- `src/portal.cpp` for provisioning
- `src/storage.cpp` for local persisted state

The repository includes multiple board/display profiles, with the default environment set to:

- `epd_42_c3`

## 6. External dependencies

Common external dependencies include:

- weather providers
- text model providers
- image model providers

LLM access is wrapped through OpenAI-compatible client flows, while image-capable modes use the configured image provider path.

## 7. Why caching matters

InkSight content is not always cheap or instant to generate, especially when a mode:

- calls weather APIs
- calls language or image models
- needs multiple previews or pre-generated outputs

The cache and pre-generation strategy reduce:

- device wait time
- repeated provider calls
- rendering cost

## 8. Related docs

- Hardware: [`hardware.md`](hardware.md)
- Flashing: [`flash.md`](flash.md)
- Configuration: [`config.md`](config.md)
- API: [`api.md`](api.md)
