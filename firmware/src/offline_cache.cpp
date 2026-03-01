#include "offline_cache.h"
#include <LittleFS.h>

static const char *CACHE_FILE = "/cache.bmp";
static bool fsReady = false;

bool cacheInit() {
    if (!LittleFS.begin(true)) {  // true = format on failure
        Serial.println("LittleFS mount failed");
        return false;
    }
    fsReady = true;
    Serial.println("LittleFS ready");
    return true;
}

bool cacheSave(const uint8_t *buf, int len) {
    if (!fsReady) return false;
    File f = LittleFS.open(CACHE_FILE, "w");
    if (!f) {
        Serial.println("Cache write failed: cannot open file");
        return false;
    }
    size_t written = f.write(buf, len);
    f.close();
    Serial.printf("Cache saved: %d bytes\n", written);
    return (int)written == len;
}

bool cacheLoad(uint8_t *buf, int len) {
    if (!fsReady) return false;
    File f = LittleFS.open(CACHE_FILE, "r");
    if (!f) {
        Serial.println("No cache file found");
        return false;
    }
    size_t read = f.readBytes((char *)buf, len);
    f.close();
    Serial.printf("Cache loaded: %d bytes\n", read);
    return (int)read == len;
}

bool cacheExists() {
    if (!fsReady) return false;
    return LittleFS.exists(CACHE_FILE);
}
