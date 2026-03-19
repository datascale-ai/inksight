# FAQ

If you are already using InkSight and something feels off, missing, or inconsistent, this is the fastest place to check first.

## 1. Where should I start reading?

The recommended doc entry points are:

- `README.md`
- `docs/en/hardware.md`
- `docs/en/assembly.md`
- `docs/en/flash.md`
- `docs/en/config.md`
- `docs/en/deploy.md`
- `docs/en/api-key.md`
- `docs/en/faq.md`

## 2. Why can’t I find AI model settings in the config tabs?

Because the current product structure separates them:

- **Device Configuration** manages device behavior
- **Profile** manages models, API keys, quota, and access mode

So AI model and API key settings now live in the **profile page**, not the device config tabs.

## 3. ARTWALL does not show images

Check these first:

- `DASHSCOPE_API_KEY` is configured
- image model settings are configured in **Profile**
- backend has been restarted after env changes
- backend logs do not show download or timeout failures

## 4. `next build` fails locally

The current WebApp uses `next/font` with online font fetching.
If your local or CI environment cannot reach Google Fonts, `npm run build` may fail.

This is usually an environment/network issue rather than a product logic issue.

## 5. Port conflicts prevent startup

Default ports are:

- WebApp: `3000`
- Backend: `8080`

If needed, change the backend port and update the frontend env config:

```bash
python -m uvicorn api.index:app --host 0.0.0.0 --port 18080
```

## 6. The WebApp opens, but flashing fails

Check:

- `INKSIGHT_BACKEND_API_BASE` is reachable
- backend `/api/firmware/*` endpoints work
- the browser supports WebSerial
- the USB cable is a real data cable

## 7. Preview does not match what the device shows

Check:

- whether preview used mode-level overrides
- whether you clicked “Save to Device”
- whether the device is online and has already pulled the latest config
- whether cached content is being reused

## 8. My PR cannot be merged automatically

If your fork tracks an upstream repo that uses squash or rewritten history, a safer workflow is:

- sync from `upstream/main`
- create a fresh branch from the latest main
- `cherry-pick` only the commits you actually need

That is usually more reliable than repeatedly merging an old branch.
