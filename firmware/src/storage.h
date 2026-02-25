#ifndef INKSIGHT_STORAGE_H
#define INKSIGHT_STORAGE_H

#include <Arduino.h>

// ── Runtime config variables (populated from NVS) ───────────
extern String cfgSSID;
extern String cfgPass;
extern String cfgServer;
extern int    cfgSleepMin;
extern String cfgConfigJson;
extern String cfgDeviceToken;

// ── NVS operations ──────────────────────────────────────────

// Load all config from NVS into runtime variables
void loadConfig();

// Save WiFi credentials to NVS
void saveWiFiConfig(const String &ssid, const String &pass);

// Save server URL to NVS
void saveServerUrl(const String &url);

// Save user config JSON to NVS (also extracts refreshInterval)
void saveUserConfig(const String &configJson);

// Retry counter management
int  getRetryCount();
void setRetryCount(int count);
void resetRetryCount();

// Device token for backend auth
void saveDeviceToken(const String &token);

#endif // INKSIGHT_STORAGE_H
