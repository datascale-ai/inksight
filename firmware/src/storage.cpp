#include "storage.h"
#include "config.h"
#include <Preferences.h>

static Preferences prefs;
static const char *LIVE_BOOT_MARKER = __DATE__ " " __TIME__;
static const char *KEY_LIVE_BOOT_MARKER_NEW = "live_boot_mk";     // <= 15 chars
static const char *KEY_LIVE_BOOT_MARKER_OLD = "live_boot_marker"; // old invalid key, read-compat only

// Config version — bump when NVS schema changes
static const int CONFIG_VERSION = 1;

// ── Runtime config variables ────────────────────────────────
String cfgSSID;
String cfgPass;
String cfgServer;
int    cfgSleepMin;
String cfgConfigJson;
String cfgDeviceToken;
String cfgPendingPairCode;

// ── Load config from NVS ────────────────────────────────────

void loadConfig() {
    prefs.begin("inksight", true);  // read-only

    int version = prefs.getInt("cfg_version", 0);
    if (version != CONFIG_VERSION) {
        Serial.printf("Config version mismatch (%d != %d), using defaults\n",
                      version, CONFIG_VERSION);
        prefs.end();
        cfgSSID = "";
        cfgPass = "";
        cfgServer = DEFAULT_SERVER;
        cfgSleepMin = 60;
        cfgConfigJson = "";
        cfgDeviceToken = "";
        cfgPendingPairCode = "";
        return;
    }

    cfgSSID         = prefs.getString("ssid", "");
    cfgPass         = prefs.getString("pass", "");
    cfgServer       = prefs.getString("server", DEFAULT_SERVER);
    cfgSleepMin     = prefs.getInt("sleep_min", 60);
    cfgConfigJson   = prefs.getString("config_json", "");
    cfgDeviceToken  = prefs.getString("device_token", "");
    cfgPendingPairCode = prefs.getString("pair_code", "");
    prefs.end();

    // Sanity checks
    if (cfgSleepMin < 10 || cfgSleepMin > 1440) {
        cfgSleepMin = 60;
    }
    if (cfgServer.length() > 200) {
        cfgServer = DEFAULT_SERVER;
    }
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

bool isFirstInstallLiveModePending() {
    prefs.begin("inksight", true);
    String marker = prefs.getString(KEY_LIVE_BOOT_MARKER_NEW, "");
    if (marker.length() == 0) {
        marker = prefs.getString(KEY_LIVE_BOOT_MARKER_OLD, "");
    }
    prefs.end();
    return marker != String(LIVE_BOOT_MARKER);
}

void markFirstInstallLiveModeDone() {
    prefs.begin("inksight", false);
    prefs.putString(KEY_LIVE_BOOT_MARKER_NEW, LIVE_BOOT_MARKER);
    prefs.end();
}

// ── Save WiFi credentials ───────────────────────────────────

void saveWiFiConfig(const String &ssid, const String &pass) {
    prefs.begin("inksight", false);  // read-write
    prefs.putInt("cfg_version", CONFIG_VERSION);
    prefs.putString("ssid", ssid);
    prefs.putString("pass", pass);
    prefs.end();
    cfgSSID = ssid;
    cfgPass = pass;
}

// ── Save server URL ─────────────────────────────────────────

void saveServerUrl(const String &url) {
    prefs.begin("inksight", false);
    prefs.putInt("cfg_version", CONFIG_VERSION);
    prefs.putString("server", url);
    prefs.end();
    cfgServer = url;
}

// ── Save user config JSON ───────────────────────────────────

void saveUserConfig(const String &configJson) {
    prefs.begin("inksight", false);
    prefs.putInt("cfg_version", CONFIG_VERSION);
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

void saveSleepMin(int minutes) {
    if (minutes < 10) minutes = 10;
    if (minutes > 1440) minutes = 1440;
    if (cfgSleepMin == minutes) return;
    prefs.begin("inksight", false);
    prefs.putInt("cfg_version", CONFIG_VERSION);
    prefs.putInt("sleep_min", minutes);
    prefs.end();
    cfgSleepMin = minutes;
}

// ── Device token ────────────────────────────────────────────

void saveDeviceToken(const String &token) {
    prefs.begin("inksight", false);
    prefs.putInt("cfg_version", CONFIG_VERSION);
    prefs.putString("device_token", token);
    prefs.end();
    cfgDeviceToken = token;
}

void clearDeviceToken() {
    prefs.begin("inksight", false);
    prefs.putInt("cfg_version", CONFIG_VERSION);
    prefs.remove("device_token");
    prefs.end();
    cfgDeviceToken = "";
}

void savePendingPairCode(const String &code) {
    prefs.begin("inksight", false);
    prefs.putInt("cfg_version", CONFIG_VERSION);
    prefs.putString("pair_code", code);
    prefs.end();
    cfgPendingPairCode = code;
}

void clearPendingPairCode() {
    prefs.begin("inksight", false);
    prefs.putInt("cfg_version", CONFIG_VERSION);
    prefs.remove("pair_code");
    prefs.end();
    cfgPendingPairCode = "";
}
