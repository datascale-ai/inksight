#include "network.h"
#include "config.h"
#include "storage.h"
#include "certs.h"

#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <time.h>

// ── Time state ──────────────────────────────────────────────
int curHour, curMin, curSec;
static unsigned long lastHeartbeatAt = 0;
bool g_userAborted = false;

static bool checkAbort() {
    if (digitalRead(PIN_CFG_BTN) == LOW) {
        delay(50);
        if (digitalRead(PIN_CFG_BTN) == LOW) {
            g_userAborted = true;
            return true;
        }
    }
    return false;
}

static bool beginHttpForUrl(HTTPClient &http, WiFiClient &plainClient, WiFiClientSecure &secClient, const String &url);
static bool recoverDeviceTokenIfUnauthorized(int code);
static String extractJsonStringField(const String &body, const char *key);

// ── WiFi connection ─────────────────────────────────────────

bool connectWiFi() {
    g_userAborted = false;
    Serial.printf("WiFi: %s ", cfgSSID.c_str());
    WiFi.mode(WIFI_STA);
    WiFi.begin(cfgSSID.c_str(), cfgPass.c_str());

    unsigned long t0 = millis();
    while (WiFi.status() != WL_CONNECTED) {
        if (checkAbort()) return false;
        if (millis() - t0 > (unsigned long)WIFI_TIMEOUT) {
            Serial.println("TIMEOUT");
            return false;
        }
        delay(300);
        Serial.print(".");
    }
    Serial.printf(" OK  IP=%s\n", WiFi.localIP().toString().c_str());
    if (!ensureDeviceToken()) return false;
    if (cfgPendingPairCode.length() > 0) {
        String mac = WiFi.macAddress();
        String url = cfgServer + "/api/device/" + mac + "/claim-token";
        String body = String("{\"pair_code\":\"") + cfgPendingPairCode + "\"}";
        for (int attempt = 0; attempt < 3; attempt++) {
            if (checkAbort()) return false;
            Serial.printf("[PAIR] POST %s (attempt %d/3)\n", url.c_str(), attempt + 1);
            WiFiClient plainClient;
            WiFiClientSecure secClient;
            HTTPClient http;
            if (!beginHttpForUrl(http, plainClient, secClient, url)) {
                Serial.println("[PAIR] begin failed");
                delay(800);
                continue;
            }
            http.addHeader("Content-Type", "application/json");
            if (cfgDeviceToken.length() > 0) {
                http.addHeader("X-Device-Token", cfgDeviceToken);
            }
            http.setTimeout(HTTP_TIMEOUT);

            int code = http.POST(body);
            Serial.printf("[PAIR] HTTP code: %d\n", code);
            if (code >= 200 && code < 300) {
                String resp = http.getString();
                String savedPairCode = extractJsonStringField(resp, "pair_code");
                http.end();
                if (savedPairCode == cfgPendingPairCode) {
                    clearPendingPairCode();
                    Serial.println("[PAIR] pair code registered");
                    break;
                }
                Serial.printf(
                    "[PAIR] pair code mismatch: local=%s remote=%s\n",
                    cfgPendingPairCode.c_str(),
                    savedPairCode.length() > 0 ? savedPairCode.c_str() : "empty"
                );
                delay(800);
                continue;
            }
            if (code < 0) {
                Serial.printf("[PAIR] error: %s\n", http.errorToString(code).c_str());
            } else {
                String resp = http.getString();
                Serial.printf("[PAIR] response: %s\n", resp.substring(0, 300).c_str());
            }
            http.end();
            if (!recoverDeviceTokenIfUnauthorized(code)) {
                delay(800);
            }
        }
    }
    postHeartbeat(true);
    return true;
}

// ── Battery voltage ─────────────────────────────────────────

float readBatteryVoltage() {
    const int SAMPLES = 16;
    const int DISCARD = 2;  // Discard highest and lowest outliers
    int readings[SAMPLES];

    for (int i = 0; i < SAMPLES; i++) {
        readings[i] = analogRead(PIN_BAT_ADC);
        delayMicroseconds(100);
    }

    // Sort for outlier removal
    for (int i = 0; i < SAMPLES - 1; i++)
        for (int j = i + 1; j < SAMPLES; j++)
            if (readings[i] > readings[j]) {
                int tmp = readings[i];
                readings[i] = readings[j];
                readings[j] = tmp;
            }

    // Average middle readings (discard DISCARD highest and lowest)
    long sum = 0;
    for (int i = DISCARD; i < SAMPLES - DISCARD; i++)
        sum += readings[i];

    float avgRaw = (float)sum / (SAMPLES - 2 * DISCARD);
    return avgRaw * (3.3f / 4095.0f) * 2.0f;
}

// ── Stream helper ───────────────────────────────────────────

static bool readExact(WiFiClient *s, uint8_t *buf, int len) {
    int got = 0;
    unsigned long t0 = millis();
    while (got < len) {
        if (!s->connected() && !s->available()) {
            Serial.printf("readExact: disconnected %d/%d\n", got, len);
            return false;
        }
        if (millis() - t0 > 10000) {
            Serial.printf("readExact: timeout %d/%d\n", got, len);
            return false;
        }
        int avail = s->available();
        if (avail > 0) {
            int r = s->readBytes(buf + got, min(avail, len - got));
            got += r;
            t0 = millis();  // Reset timeout on progress
        }
    }
    return true;
}

static bool beginHttpForUrl(HTTPClient &http, WiFiClient &plainClient, WiFiClientSecure &secClient, const String &url) {
    if (url.startsWith("https://")) {
        secClient.setCACert(ROOT_CA);
        return http.begin(secClient, url);
    }
    return http.begin(plainClient, url);
}

static String extractJsonStringField(const String &body, const char *key) {
    String needle = String("\"") + key + "\":\"";
    int start = body.indexOf(needle);
    if (start < 0) return "";
    start += needle.length();
    int end = body.indexOf('"', start);
    if (end < 0) return "";
    return body.substring(start, end);
}

static bool recoverDeviceTokenIfUnauthorized(int code) {
    if (code != 401 || cfgDeviceToken.length() == 0) return false;
    Serial.println("[AUTH] 401 unauthorized, resetting cached device token");
    clearDeviceToken();
    return ensureDeviceToken();
}

bool postHeartbeat(bool force) {
    if (WiFi.status() != WL_CONNECTED) return false;
    unsigned long now = millis();
    if (!force && lastHeartbeatAt != 0 && now - lastHeartbeatAt < HEARTBEAT_INTERVAL_MS) {
        return true;
    }
    if (!ensureDeviceToken()) return false;

    float v = readBatteryVoltage();
    int rssi = WiFi.RSSI();
    String mac = WiFi.macAddress();
    String url = cfgServer + "/api/device/" + mac + "/heartbeat";
    String body = String("{\"battery_voltage\":") + String(v, 2) + ",\"wifi_rssi\":" + String(rssi) + "}";
    for (int attempt = 0; attempt < 2; attempt++) {
        WiFiClient plainClient;
        WiFiClientSecure secClient;
        HTTPClient http;
        if (!beginHttpForUrl(http, plainClient, secClient, url)) return false;
        http.addHeader("Content-Type", "application/json");
        if (cfgDeviceToken.length() > 0) {
            http.addHeader("X-Device-Token", cfgDeviceToken);
        }
        http.setTimeout(HTTP_TIMEOUT);

        int code = http.POST(body);
        if (code >= 200 && code < 300) {
            Serial.printf("[HEARTBEAT] POST -> %d\n", code);
            http.end();
            lastHeartbeatAt = now;
            return true;
        }
        if (code < 0) {
            Serial.printf("[HEARTBEAT] error: %s\n", http.errorToString(code).c_str());
        } else {
            Serial.printf("[HEARTBEAT] POST -> %d\n", code);
        }
        http.end();
        if (!recoverDeviceTokenIfUnauthorized(code)) {
            return false;
        }
    }
    return false;
}

bool ensureDeviceToken() {
    if (cfgDeviceToken.length() > 0) return true;
    if (WiFi.status() != WL_CONNECTED) return false;

    String mac = WiFi.macAddress();
    String url = cfgServer + "/api/device/" + mac + "/token";
    delay(1200);
    for (int attempt = 0; attempt < 3; attempt++) {
        if (checkAbort()) return false;
        Serial.printf("[TOKEN] POST %s (attempt %d/3)\n", url.c_str(), attempt + 1);
        WiFiClient plainClient;
        WiFiClientSecure secClient;
        HTTPClient http;
        if (!beginHttpForUrl(http, plainClient, secClient, url)) {
            Serial.println("[TOKEN] begin failed");
            delay(800);
            continue;
        }
        http.addHeader("Content-Type", "application/json");
        http.setTimeout(HTTP_TIMEOUT);

        int code = http.POST("{}");
        Serial.printf("[TOKEN] HTTP code: %d\n", code);
        if (code >= 200 && code < 300) {
            String body = http.getString();
            http.end();
            String token = extractJsonStringField(body, "token");
            if (token.length() == 0) {
                Serial.println("[TOKEN] token field empty");
                delay(800);
                continue;
            }
            saveDeviceToken(token);
            Serial.println("[TOKEN] token saved");
            return true;
        }
        if (code < 0) {
            Serial.printf("[TOKEN] error: %s\n", http.errorToString(code).c_str());
        } else {
            String body = http.getString();
            Serial.printf("[TOKEN] response: %s\n", body.substring(0, 300).c_str());
        }
        http.end();
        delay(800);
    }
    Serial.println("[TOKEN] failed to obtain device token");
    return false;
}

bool fetchFocusListeningFlag(bool *outEnabled) {
    if (!outEnabled) return false;
    *outEnabled = false;
    if (WiFi.status() != WL_CONNECTED) return false;
    if (!ensureDeviceToken()) return false;

    String mac = WiFi.macAddress();
    String url = cfgServer + "/api/config/" + mac;
    bool useSSL = cfgServer.startsWith("https://");

    for (int attempt = 0; attempt < 2; attempt++) {
        WiFiClient plainClient;
        WiFiClientSecure secClient;
        HTTPClient http;
        if (useSSL) {
            secClient.setCACert(ROOT_CA);
            http.begin(secClient, url);
        } else {
            http.begin(plainClient, url);
        }
        http.setTimeout(HTTP_TIMEOUT);
        if (cfgDeviceToken.length() > 0) {
            http.addHeader("X-Device-Token", cfgDeviceToken);
        }

        int code = http.GET();
        if (code != 200) {
            http.end();
            if (!recoverDeviceTokenIfUnauthorized(code)) return false;
            continue;
        }

        String body = http.getString();
        http.end();
        bool enabled =
            body.indexOf("\"is_focus_listening\":true") >= 0 ||
            body.indexOf("\"is_focus_listening\": true") >= 0 ||
            body.indexOf("\"focus_listening\":1") >= 0 ||
            body.indexOf("\"focus_listening\": 1") >= 0;
        *outEnabled = enabled;
        Serial.printf("[FOCUS] is_focus_listening=%s\n", enabled ? "true" : "false");
        return true;
    }
    return false;
}

bool fetchFocusAlertBMP() {
    if (WiFi.status() != WL_CONNECTED) return false;
    if (!ensureDeviceToken()) return false;
    String mac = WiFi.macAddress();
    String url = cfgServer + "/api/device/" + mac + "/alert-bmp"
               + "?w=" + String(W) + "&h=" + String(H);
    bool useSSL = cfgServer.startsWith("https://");

    for (int attempt = 0; attempt < 2; attempt++) {
        WiFiClient plainClient;
        WiFiClientSecure secClient;
        HTTPClient http;
        if (useSSL) {
            secClient.setCACert(ROOT_CA);
            http.begin(secClient, url);
        } else {
            http.begin(plainClient, url);
        }
        http.setTimeout(HTTP_TIMEOUT);
        if (cfgDeviceToken.length() > 0) {
            http.addHeader("X-Device-Token", cfgDeviceToken);
        }

        int code = http.GET();
        Serial.printf("[FOCUS] alert-bmp HTTP code: %d\n", code);
        if (code == 204) {
            http.end();
            return false;
        }
        if (code != 200) {
            http.end();
            if (!recoverDeviceTokenIfUnauthorized(code)) return false;
            continue;
        }

        WiFiClient *stream = http.getStreamPtr();
        uint8_t fileHeader[14];
        if (!readExact(stream, fileHeader, 14)) {
            http.end();
            return false;
        }
        uint32_t pixelOffset = fileHeader[10]
                             | ((uint32_t)fileHeader[11] << 8)
                             | ((uint32_t)fileHeader[12] << 16)
                             | ((uint32_t)fileHeader[13] << 24);
        int toSkip = (int)pixelOffset - 14;
        while (toSkip > 0 && stream->connected()) {
            if (stream->available()) { stream->read(); toSkip--; }
        }

        uint8_t rowBuf[ROW_STRIDE];
        for (int bmpY = 0; bmpY < H; bmpY++) {
            if (!readExact(stream, rowBuf, ROW_STRIDE)) {
                http.end();
                return false;
            }
            int dispY = H - 1 - bmpY;
            memcpy(imgBuf + dispY * ROW_BYTES, rowBuf, ROW_BYTES);
        }
        http.end();
        return true;
    }
    return false;
}

// ── Fetch BMP from backend ──────────────────────────────────

bool fetchBMP(bool nextMode, bool *isFallback) {
    if (isFallback) *isFallback = false;
    if (!ensureDeviceToken()) return false;
    float v = readBatteryVoltage();
    String mac = WiFi.macAddress();
    int rssi = WiFi.RSSI();
#if DEBUG_MODE
    int effectiveRefreshMin = DEBUG_REFRESH_MIN;
#else
    int effectiveRefreshMin = cfgSleepMin;
#endif
    String url = cfgServer + "/api/render?v=" + String(v, 2)
               + "&mac=" + mac + "&rssi=" + String(rssi)
               + "&refresh_min=" + String(effectiveRefreshMin)
               + "&w=" + String(W) + "&h=" + String(H);
    if (nextMode) {
        url += "&next=1";
    }
    Serial.printf("GET %s (RSSI=%d)\n", url.c_str(), rssi);

    bool useSSL = cfgServer.startsWith("https://");
    for (int attempt = 0; attempt < 2; attempt++) {
        if (checkAbort()) return false;
        WiFiClient plainClient;
        WiFiClientSecure secClient;
        HTTPClient http;
        if (useSSL) {
            secClient.setCACert(ROOT_CA);
            http.begin(secClient, url);
        } else {
            http.begin(plainClient, url);
        }
        http.setTimeout(HTTP_TIMEOUT);
        http.setFollowRedirects(HTTPC_STRICT_FOLLOW_REDIRECTS);
        const char *headerKeys[] = {"X-Content-Fallback", "X-Refresh-Minutes"};
        http.collectHeaders(headerKeys, 2);

        http.addHeader("Accept-Encoding", "identity");
        if (cfgDeviceToken.length() > 0) {
            http.addHeader("X-Device-Token", cfgDeviceToken);
        }

        Serial.printf("Free heap: %d\n", ESP.getFreeHeap());
        int code = http.GET();
        Serial.printf("HTTP code: %d\n", code);
        if (isFallback) {
            String fallbackHeader = http.header("X-Content-Fallback");
            *isFallback = (fallbackHeader == "1" || fallbackHeader == "true");
            if (*isFallback) {
                Serial.println("[RENDER] Received fallback content");
            }
        }
        String refreshHeader = http.header("X-Refresh-Minutes");
        int serverRefreshMin = refreshHeader.toInt();
        if (serverRefreshMin >= 10 && serverRefreshMin <= 1440 && serverRefreshMin != cfgSleepMin) {
            saveSleepMin(serverRefreshMin);
            Serial.printf("[RENDER] Applied refresh interval: %d min\n", serverRefreshMin);
        }

        if (code != 200) {
            if (code < 0) {
                Serial.printf("HTTP error: %s\n", http.errorToString(code).c_str());
            } else {
                String body = http.getString();
                Serial.printf("Response: %s\n", body.substring(0, 500).c_str());
            }
            http.end();
            if (!recoverDeviceTokenIfUnauthorized(code)) {
                return false;
            }
            continue;
        }

        int contentLen = http.getSize();
        Serial.printf("Content-Length: %d\n", contentLen);

        WiFiClient *stream = http.getStreamPtr();

        uint8_t fileHeader[14];
        if (!readExact(stream, fileHeader, 14)) {
            Serial.println("Failed to read BMP header");
            http.end();
            return false;
        }

        uint32_t pixelOffset = fileHeader[10]
                             | ((uint32_t)fileHeader[11] << 8)
                             | ((uint32_t)fileHeader[12] << 16)
                             | ((uint32_t)fileHeader[13] << 24);
        Serial.printf("BMP pixel offset: %u\n", pixelOffset);

        int toSkip = pixelOffset - 14;
        while (toSkip > 0 && stream->connected()) {
            if (stream->available()) { stream->read(); toSkip--; }
        }

        uint8_t rowBuf[ROW_STRIDE];
        for (int bmpY = 0; bmpY < H; bmpY++) {
            if (!readExact(stream, rowBuf, ROW_STRIDE)) {
                Serial.printf("Failed to read row %d\n", bmpY);
                http.end();
                return false;
            }
            int dispY = H - 1 - bmpY;
            memcpy(imgBuf + dispY * ROW_BYTES, rowBuf, ROW_BYTES);
        }

        http.end();
        Serial.printf("BMP OK  %d bytes\n", IMG_BUF_LEN);
        lastHeartbeatAt = millis();
        return true;
    }
    return false;
}

bool hasPendingRemoteAction(bool *shouldExitLive) {
    if (WiFi.status() != WL_CONNECTED) return false;
    if (!ensureDeviceToken()) return false;

    String mac = WiFi.macAddress();
    String url = cfgServer + "/api/device/" + mac + "/state";

    bool useSSL = cfgServer.startsWith("https://");
    for (int attempt = 0; attempt < 2; attempt++) {
        if (checkAbort()) return false;
        WiFiClient plainClient;
        WiFiClientSecure secClient;
        HTTPClient http;
        if (useSSL) {
            secClient.setCACert(ROOT_CA);
            http.begin(secClient, url);
        } else {
            http.begin(plainClient, url);
        }
        http.setTimeout(HTTP_TIMEOUT);
        if (cfgDeviceToken.length() > 0) {
            http.addHeader("X-Device-Token", cfgDeviceToken);
        }

        int code = http.GET();
        if (code != 200) {
            http.end();
            if (!recoverDeviceTokenIfUnauthorized(code)) {
                return false;
            }
            continue;
        }

        String body = http.getString();
        http.end();

        if (shouldExitLive) {
            bool intervalRequested =
                body.indexOf("\"runtime_mode\":\"interval\"") >= 0 ||
                body.indexOf("\"runtime_mode\": \"interval\"") >= 0;
            *shouldExitLive = intervalRequested;
        }

        bool pendingRefresh =
            body.indexOf("\"pending_refresh\":1") >= 0 ||
            body.indexOf("\"pending_refresh\": 1") >= 0 ||
            body.indexOf("\"pending_refresh\":true") >= 0 ||
            body.indexOf("\"pending_refresh\": true") >= 0;

        bool pendingMode =
            (body.indexOf("\"pending_mode\":\"") >= 0 || body.indexOf("\"pending_mode\": \"") >= 0) &&
            body.indexOf("\"pending_mode\":\"\"") < 0 &&
            body.indexOf("\"pending_mode\": \"\"") < 0;

        return pendingRefresh || pendingMode;
    }
    return false;
}

// ── Post config to backend ──────────────────────────────────

void postConfigToBackend() {
    if (cfgConfigJson.length() == 0) return;
    if (!ensureDeviceToken()) return;

    // Inject MAC address into the config JSON
    String mac = WiFi.macAddress();
    String body = cfgConfigJson;
    if (body.startsWith("{")) {
        body = "{\"mac\":\"" + mac + "\"," + body.substring(1);
    }

    String url = cfgServer + "/api/config";
    bool useSSL = cfgServer.startsWith("https://");
    for (int attempt = 0; attempt < 2; attempt++) {
        if (checkAbort()) return;
        WiFiClient plainClient;
        WiFiClientSecure secClient;
        HTTPClient http;
        if (useSSL) {
            secClient.setCACert(ROOT_CA);
            http.begin(secClient, url);
        } else {
            http.begin(plainClient, url);
        }
        http.addHeader("Content-Type", "application/json");
        http.setTimeout(HTTP_TIMEOUT);
        if (cfgDeviceToken.length() > 0) {
            http.addHeader("X-Device-Token", cfgDeviceToken);
        }

        int code = http.POST(body);
        Serial.printf("POST /api/config -> %d\n", code);
        http.end();
        if (!recoverDeviceTokenIfUnauthorized(code)) {
            return;
        }
    }
}

// ── Post runtime mode to backend ────────────────────────────

bool postRuntimeMode(const char *mode) {
    if (!ensureDeviceToken()) return false;
    String mac = WiFi.macAddress();
    String url = cfgServer + "/api/device/" + mac + "/runtime";
    bool useSSL = cfgServer.startsWith("https://");
    String body = String("{\"mode\":\"") + mode + "\"}";
    for (int attempt = 0; attempt < 2; attempt++) {
        WiFiClient plainClient;
        WiFiClientSecure secClient;
        HTTPClient http;
        if (useSSL) {
            secClient.setCACert(ROOT_CA);
            http.begin(secClient, url);
        } else {
            http.begin(plainClient, url);
        }
        http.addHeader("Content-Type", "application/json");
        http.setTimeout(HTTP_TIMEOUT);
        if (cfgDeviceToken.length() > 0) {
            http.addHeader("X-Device-Token", cfgDeviceToken);
        }

        int code = http.POST(body);
        http.end();

        if (code == 404) {
            return true;
        }
        if (code >= 200 && code < 300) {
            return true;
        }
        if (!recoverDeviceTokenIfUnauthorized(code)) {
            return false;
        }
    }
    return false;
}

// ── NTP time sync ───────────────────────────────────────────

void syncNTP() {
    configTime(NTP_UTC_OFFSET, 0, "ntp.aliyun.com", "pool.ntp.org");
    struct tm timeinfo;
    if (getLocalTime(&timeinfo, 5000)) {
        curHour = timeinfo.tm_hour;
        curMin  = timeinfo.tm_min;
        curSec  = timeinfo.tm_sec;
        Serial.printf("NTP synced: %02d:%02d:%02d\n", curHour, curMin, curSec);
    } else {
        curHour = 0; curMin = 0; curSec = 0;
        Serial.println("NTP failed, using 00:00:00");
    }
}

// ── Software clock tick ─────────────────────────────────────

void tickTime() {
    curSec++;
    if (curSec >= 60) { curSec = 0; curMin++; }
    if (curMin >= 60) { curMin = 0; curHour++; }
    if (curHour >= 24) { curHour = 0; }
}
