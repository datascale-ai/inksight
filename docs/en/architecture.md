# InkSight Architecture

## Overview

InkSight is composed of three parts:

- **Firmware (ESP32-C3)**: collects context (time, battery, network), requests rendered content, and drives the E-Ink panel.
- **Backend (FastAPI)**: fetches weather and LLM content, renders bitmap images, and returns binary payloads for devices and web tools.
- **WebApp (Next.js)**: provides docs, web flasher, and device configuration UI.

## Data Flow

1. Device connects to Wi-Fi and calls backend endpoints.
2. Backend gathers external data (weather, LLM outputs).
3. Renderer builds E-Ink-friendly image content.
4. Device receives image bytes and refreshes the screen.

## Frontend Notes

The web frontend supports:

- documentation center
- online firmware flashing
- online configuration and management

## Deployment

- Backend: Python FastAPI service
- Frontend: Next.js app
- Both support same-domain proxy mode for local development
