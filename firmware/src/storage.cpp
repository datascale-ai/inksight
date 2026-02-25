#include "storage.h"
#include "config.h"
#include <Preferences.h>

static Preferences prefs;

// ── Runtime config variables ────────────────────────────────
String cfgSSID;
String cfgPass;
String cfgServer;
int    cfgSleepMin;
String cfgConfigJson;
String cfgDeviceToken;

// ── Load config from NVS ────────────────────────────────────

void loadConfig() {
    prefs.begin("inksight", true);  // read-only
    cfgSSID         = prefs.getString("ssid", "");
    cfgPass         = prefs.getString("pass", "");
    cfgServer       = prefs.getString("server", DEFAULT_SERVER);
    cfgSleepMin     = prefs.getInt("sleep_min", 60);
    cfgConfigJson   = prefs.getString("config_json", "");
    cfgDeviceToken  = prefs.getString("device_token", "");
    prefs.end();
}

// ── Retry counter ───────────────────────────────────────────

int getRetryCount() {
    prefs.begin("inksight", true);
    int count = prefs.getInt("retry_count", 0);
    prefs.end();
    return count;
}

void setRetryCount(int count) {
    prefs.begin("inksight", false);
    prefs.putInt("retry_count", count);
    prefs.end();
}

void resetRetryCount() {
    setRetryCount(0);
}

// ── Save WiFi credentials ───────────────────────────────────

void saveWiFiConfig(const String &ssid, const String &pass) {
    prefs.begin("inksight", false);  // read-write
    prefs.putString("ssid", ssid);
    prefs.putString("pass", pass);
    prefs.end();
    cfgSSID = ssid;
    cfgPass = pass;
}

// ── Save server URL ─────────────────────────────────────────

void saveServerUrl(const String &url) {
    prefs.begin("inksight", false);
    prefs.putString("server", url);
    prefs.end();
    cfgServer = url;
}

// ── Save user config JSON ───────────────────────────────────

void saveUserConfig(const String &configJson) {
    prefs.begin("inksight", false);
    prefs.putString("config_json", configJson);

    // Extract refreshInterval from JSON and persist as sleep_min
    int idx = configJson.indexOf("\"refreshInterval\"");
    if (idx >= 0) {
        int colon = configJson.indexOf(':', idx);
        if (colon >= 0) {
            int val = configJson.substring(colon + 1).toInt();
            if (val < 10)   val = 10;    // minimum 10 minutes
            if (val > 1440)  val = 1440;  // maximum 24 hours
            prefs.putInt("sleep_min", val);
            cfgSleepMin = val;
            Serial.printf("refreshInterval -> sleep_min = %d min\n", val);
        }
    }

    prefs.end();
    cfgConfigJson = configJson;
}

// ── Device token ────────────────────────────────────────────

void saveDeviceToken(const String &token) {
    prefs.begin("inksight", false);
    prefs.putString("device_token", token);
    prefs.end();
    cfgDeviceToken = token;
}
