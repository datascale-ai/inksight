#ifndef INKSIGHT_NETWORK_H
#define INKSIGHT_NETWORK_H

#include <Arduino.h>

// ── Time state (updated by syncNTP / tickTime) ──────────────
extern int curHour, curMin, curSec;

// ── WiFi ────────────────────────────────────────────────────

// Connect to WiFi using stored credentials. Returns true on success.
bool connectWiFi();

// ── HTTP ────────────────────────────────────────────────────

// Fetch BMP image from backend and store in imgBuf. Returns true on success.
// If nextMode is true, appends &next=1 to request the next mode in sequence.
bool fetchBMP(bool nextMode = false);

// POST favorite (triple-click) to backend. Returns true on success.
bool postFavorite();

// POST device config JSON to backend /api/config endpoint.
void postConfigToBackend();

// ── Battery ─────────────────────────────────────────────────

// Read battery voltage via ADC (returns volts)
float readBatteryVoltage();

// ── NTP time ────────────────────────────────────────────────

// Sync time from NTP servers
void syncNTP();

// Advance software clock by one second
void tickTime();

#endif // INKSIGHT_NETWORK_H
