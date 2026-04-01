# Local Deployment and Self-Hosting

This document explains how to run InkSight locally and how the current codebase is structured.
If you only want a product overview, start with the repository `README.md`.
This guide is mainly for **developers, self-hosters, and anyone debugging the full backend + webapp + device flow**.

## 1. When to use this document

Use this guide if you want to:

- run the backend and WebApp locally
- self-host your own InkSight instance
- debug flashing, configuration, preview, or API behavior

## 2. Project structure

The repository currently has three main parts:

- `backend/` — FastAPI backend for rendering, configuration, weather, modes, auth, and stats
- `webapp/` — Next.js web app for the website, web flasher, login, device configuration, and preview
- `firmware/` — ESP32 firmware built with PlatformIO / Arduino

## 3. Requirements

### Backend

- Python **3.10+**
- `pip`

### Frontend

- Node.js **20+** recommended
- `npm`

### Firmware (optional)

- PlatformIO

## 4. Start the backend

```bash
cd backend

pip install -r requirements.txt
python scripts/setup_fonts.py

cp .env.example .env
# Fill in the environment variables you need

python -m uvicorn api.index:app --host 0.0.0.0 --port 8080
```

### Backend environment variables

The sample file is located at: `backend/.env.example`

The most important variables currently used by the code are:

- `DEEPSEEK_API_KEY`
- `DASHSCOPE_API_KEY`
- `MOONSHOT_API_KEY`
- `DEBUG_MODE`
- `DEFAULT_CITY`
- `DB_PATH`
- `ADMIN_TOKEN`

Notes:

- If a user does not configure their own model/API key in the profile page, the backend falls back to these environment-level keys.
- `DEFAULT_CITY` is the system fallback weather city and defaults to `杭州`.

## 5. Start the WebApp

```bash
cd webapp

cp .env.example .env
npm install
npm run dev
```

### WebApp environment variables

The sample file is located at: `webapp/.env.example`

Current key variables:

- `INKSIGHT_BACKEND_API_BASE=http://127.0.0.1:8080`
- `NEXT_PUBLIC_FIRMWARE_API_BASE=` (optional)

For local development, the recommended setup is:

- backend: `http://127.0.0.1:8080`
- frontend: `http://127.0.0.1:3000`

## 6. Local entry points

After startup, the usual local entry points are:

| Entry | URL | Purpose |
|------|-----|---------|
| WebApp | `http://127.0.0.1:3000` | Website, local development, web flasher, login, config, preview |
| Backend API | `http://127.0.0.1:8080` | FastAPI API server |
| Preview API | `http://127.0.0.1:8080/api/preview?persona=WEATHER` | Mode-level preview/debug entry |

The backend still exposes some compatibility pages such as the old config page, dashboard, and editor, but the recommended configuration entry is now the WebApp **Device Configuration** flow.

## 7. Accounts, models, and API keys

In the current product structure:

- the **Device Configuration** page manages:
  - modes
  - preferences
  - shared members
  - device status
- the **Profile** page manages:
  - text model provider / model / API key
  - image model provider / model / API key
  - free quota and access mode

So **model and API key settings live in the profile page, not inside the device config tabs**.

## 8. Local firmware build (optional)

If you also want to build or flash firmware locally:

```bash
cd firmware
pio run
pio run --target upload
pio device monitor
```

The default environment is:

- `epd_42_wsv2_ssd1683_c3_promini`

For other supported hardware profiles, see:

- `firmware/platformio.ini`
- `docs/hardware.md`

## 9. Useful verification commands

### Backend

```bash
cd backend
pytest
```

### Frontend

```bash
cd webapp
npm run lint
npx tsc --noEmit
```

## 10. Common issues

### `next build` fails on font download

The current WebApp uses `next/font` with online font fetching.
In restricted or offline environments, `npm run build` may fail if it cannot reach Google Fonts.

This does not usually affect day-to-day `npm run dev`, but it matters for CI and production builds.

### Port conflicts

Default ports are:

- frontend: `3000`
- backend: `8080`

If you change ports, also update `INKSIGHT_BACKEND_API_BASE` accordingly.

### API calls fail

Check the following first:

- backend `.env` contains valid platform-level API keys
- your user profile contains valid personal model/API key settings
- backend logs show no auth, quota, or upstream provider errors
