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
extern String cfgPendingPairCode;

// ── NVS operations ──────────────────────────────────────────

// Load all config from NVS into runtime variables
void loadConfig();

// Save WiFi credentials to NVS
void saveWiFiConfig(const String &ssid, const String &pass);

// ── Multi-WiFi credential list (up to MAX_WIFI_NETWORKS) ────
// Networks are tried in index order (0 first) on boot.

// Number of saved WiFi networks.
int  getWiFiCount();

// Read credentials at index. Returns false if idx out of range.
bool getWiFiAt(int idx, String &ssid, String &pass);

// Add or update a network. If the SSID already exists, its password is
// updated and it is moved to the front (slot 0). Otherwise it is appended.
// Returns false if the list is full and the SSID is new.
bool addWiFiConfig(const String &ssid, const String &pass);

// Delete a network by SSID and compact the list. Returns true if removed.
bool deleteWiFiBySSID(const String &ssid);

// Fill out[] (length >= MAX_WIFI_NETWORKS) with saved SSID names (no passwords).
// count is set to the number written.
void getWiFiSSIDList(String out[], int &count);

// Save server URL to NVS
void saveServerUrl(const String &url);

// Save user config JSON to NVS (also extracts refreshInterval)
void saveUserConfig(const String &configJson);
void saveSleepMin(int minutes);

// Retry counter management
int  getRetryCount();
void setRetryCount(int count);
void resetRetryCount();

// One-time boot flag for first-install live mode
bool isFirstInstallLiveModePending();
void markFirstInstallLiveModeDone();

// Device token for backend auth
void saveDeviceToken(const String &token);
void clearDeviceToken();
void savePendingPairCode(const String &code);
void clearPendingPairCode();

#endif // INKSIGHT_STORAGE_H
