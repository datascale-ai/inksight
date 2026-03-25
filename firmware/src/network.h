#ifndef INKSIGHT_NETWORK_H
#define INKSIGHT_NETWORK_H

#include <Arduino.h>

extern bool g_userAborted;

// ── Time state (updated by syncNTP / tickTime) ──────────────
extern int curHour, curMin, curSec;

// ── WiFi ────────────────────────────────────────────────────

// Connect to WiFi using stored credentials. Returns true on success.
bool connectWiFi();

// ── HTTP ────────────────────────────────────────────────────

// Fetch BMP image from backend and store in imgBuf. Returns true on success.
// If nextMode is true, appends &next=1 to request the next mode in sequence.
bool fetchBMP(bool nextMode = false, bool *isFallback = nullptr);

// Check whether backend has pending refresh/switch request for this device.
// If shouldExitLive is not null, it is set to true when backend runtime_mode is interval.
bool hasPendingRemoteAction(bool *shouldExitLive = nullptr);

// POST runtime mode (active/interval) to backend.
bool postRuntimeMode(const char *mode);

// POST device config JSON to backend /api/config endpoint.
void postConfigToBackend();

bool ensureDeviceToken();
bool postHeartbeat(bool force = false);

// ── Focus listening helpers ─────────────────────────────────
bool fetchFocusListeningFlag(bool *outEnabled);
bool fetchFocusAlertBMP();

// ── Battery ─────────────────────────────────────────────────

// Read battery voltage via ADC (returns volts)
float readBatteryVoltage();

// ── NTP time ────────────────────────────────────────────────

// Sync time from NTP servers
void syncNTP();

// Advance software clock by one second
void tickTime();

#endif // INKSIGHT_NETWORK_H
