# InkSight Architecture

This document reflects the current repository structure and explains the main layers, render pipeline, mode system, and storage model.

## 1. High-level structure

InkSight currently has three major parts:

- **Firmware** — ESP32 firmware for device provisioning, fetching rendered images on a schedule, driving the e-paper display, button interactions, and low-power deep sleep
- **Backend** — FastAPI service for configuration, weather context, content generation, rendering, caching, and stats
- **WebApp** — Next.js app for the website, docs, web flasher, login, configuration, and preview

## 2. Core data flow

A typical render flow looks like this:

1. the device requests content from the backend
2. the backend loads device config and environment context
3. the backend chooses static data, computed content, external data, or model-generated content depending on the mode
4. the renderer converts the result into a bitmap suitable for e-paper (black-and-white, 3-color, or 4-color, depending on device configuration)
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
4. `core/mode_registry.py` loads the corresponding JSON mode definition
5. `core/json_renderer.py` produces the final image

### Mode system

The system uses a pure JSON-driven mode definition. Built-in modes are defined in:

- `backend/core/modes/builtin/` (includes multi-language support like the `en/` directory)

Custom JSON modes are loaded from:

- `backend/core/modes/custom/`

The repository currently includes **27 built-in JSON modes**.

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

The frontend application lives in:

- `webapp/`

Its responsibilities include:

- website content
- documentation center
- web firmware flashing
- login and profile
- device configuration
- profile management
- preview flows

In the current product structure, the configuration flow is clearly divided into two parts:

- **Device Configuration**: manages device display behavior, refresh strategy, and mode selection.
- **Profile**: manages AI compute resources (including platform free quota and custom LLM API keys).

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

- `epd_42_wsv2_ssd1683_c3_promini` (for 4.2-inch B/W e-paper and ESP32-C3 Pro mini boards)

## 6. External dependencies

Common external dependencies include:

- weather providers
- text model providers
- image model providers

Both LLM text generation and image generation are wrapped through OpenAI-compatible client flows, routing to the corresponding service based on user configuration (preset providers or custom OpenAI format).

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

- [Hardware & Parts Guide](hardware)
- [Assembly Guide](assembly)
- [Web Flasher Guide](flash)
- [Device Configuration Guide](config)
- [API Reference](api)
- [Local Deployment Guide](deploy)
