#include "network.h"
#include "config.h"
#include "storage.h"
#include "certs.h"
#include "audio.h"

#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <WebSocketsClient.h>
#include <LittleFS.h>
#include <mbedtls/base64.h>
#include <time.h>

// ── Time state ──────────────────────────────────────────────
int curHour, curMin, curSec;
static unsigned long lastHeartbeatAt = 0;
bool g_userAborted = false;
bool g_suppressAbortCheck = false;

static bool checkAbort() {
    if (g_suppressAbortCheck) return false;
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
static String extractJsonBoolField(const String &body, const char *key);
static int extractJsonIntField(const String &body, const char *key, int defaultValue = 0);
static bool parseWsServerUrl(const String &baseUrl, bool &useSSL, String &hostOut, uint16_t &portOut, String &pathOut);
static bool decodeBase64ToHeap(const String &encoded, uint8_t **dataOut, size_t *dataLenOut);
static String encodeBase64(const uint8_t *data, size_t len);
static void handleVoiceWsEvent(VoiceWsEvent &event);
static void voiceWsSocketEvent(WStype_t type, uint8_t *payload, size_t length);

static WebSocketsClient gVoiceWsClient;
static bool gVoiceWsConnected = false;
static bool gVoiceWsConfigured = false;
static bool gVoiceWsBinaryAudioEnabled = false;
static bool gVoiceWsOpusEnabled = false;
static bool gVoiceWsServerVadEnabled = false;
static QueueHandle_t gVoiceWsEventQueue = nullptr;

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
    String needle = String("\"") + key + "\"";
    int start = body.indexOf(needle);
    if (start < 0) return "";
    start += needle.length();
    while (start < body.length() && (body[start] == ' ' || body[start] == '\t' || body[start] == '\r' || body[start] == '\n')) {
        start++;
    }
    if (start >= body.length() || body[start] != ':') return "";
    start++;
    while (start < body.length() && (body[start] == ' ' || body[start] == '\t' || body[start] == '\r' || body[start] == '\n')) {
        start++;
    }
    if (start >= body.length() || body[start] != '"') return "";
    start++;
    int end = body.indexOf('"', start);
    if (end < 0) return "";
    return body.substring(start, end);
}

static String extractJsonBoolField(const String &body, const char *key) {
    String needle = String("\"") + key + "\":";
    int start = body.indexOf(needle);
    if (start < 0) return "";
    start += needle.length();
    while (start < body.length() && body[start] == ' ') {
        start++;
    }
    if (body.startsWith("true", start)) return "true";
    if (body.startsWith("false", start)) return "false";
    if (body.startsWith("1", start)) return "1";
    if (body.startsWith("0", start)) return "0";
    return "";
}

static int extractJsonIntField(const String &body, const char *key, int defaultValue) {
    String needle = String("\"") + key + "\":";
    int start = body.indexOf(needle);
    if (start < 0) return defaultValue;
    start += needle.length();
    while (start < body.length() && body[start] == ' ') {
        start++;
    }
    int end = start;
    while (end < body.length() && (body[end] == '-' || (body[end] >= '0' && body[end] <= '9'))) {
        end++;
    }
    if (end <= start) return defaultValue;
    return body.substring(start, end).toInt();
}

static bool parseWsServerUrl(const String &baseUrl, bool &useSSL, String &hostOut, uint16_t &portOut, String &pathOut) {
    String url = baseUrl;
    useSSL = false;
    if (url.startsWith("https://")) {
        useSSL = true;
        url = url.substring(8);
        portOut = 443;
    } else if (url.startsWith("http://")) {
        url = url.substring(7);
        portOut = 80;
    } else {
        return false;
    }

    int slash = url.indexOf('/');
    String hostPort = slash >= 0 ? url.substring(0, slash) : url;
    pathOut = slash >= 0 ? url.substring(slash) : "";
    if (pathOut.length() == 0) {
        pathOut = "";
    }

    int colon = hostPort.indexOf(':');
    if (colon >= 0) {
        hostOut = hostPort.substring(0, colon);
        portOut = (uint16_t)hostPort.substring(colon + 1).toInt();
    } else {
        hostOut = hostPort;
    }
    if (hostOut.length() == 0) {
        return false;
    }
    return true;
}

static bool decodeBase64ToHeap(const String &encoded, uint8_t **dataOut, size_t *dataLenOut) {
    if (dataOut == nullptr || dataLenOut == nullptr) return false;
    *dataOut = nullptr;
    *dataLenOut = 0;
    if (encoded.length() == 0) {
        return true;
    }
    size_t maxLen = ((encoded.length() + 3) / 4) * 3 + 4;
    uint8_t *buffer = (uint8_t *)malloc(maxLen);
    if (buffer == nullptr) {
        return false;
    }
    size_t outputLen = 0;
    int rc = mbedtls_base64_decode(buffer, maxLen, &outputLen, (const unsigned char *)encoded.c_str(), encoded.length());
    if (rc != 0) {
        free(buffer);
        return false;
    }
    *dataOut = buffer;
    *dataLenOut = outputLen;
    return true;
}

static String encodeBase64(const uint8_t *data, size_t len) {
    if (data == nullptr || len == 0) return "";
    size_t outputLen = 0;
    size_t capacity = ((len + 2) / 3) * 4 + 4;
    unsigned char *buffer = (unsigned char *)malloc(capacity);
    if (buffer == nullptr) {
        return "";
    }
    int rc = mbedtls_base64_encode(buffer, capacity, &outputLen, data, len);
    if (rc != 0) {
        free(buffer);
        return "";
    }
    buffer[outputLen] = '\0';
    String encoded = String((const char *)buffer);
    free(buffer);
    return encoded;
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

bool fetchBMP(bool nextMode, bool *isFallback, String *renderedModeIdOut) {
    if (isFallback) *isFallback = false;
    if (renderedModeIdOut) *renderedModeIdOut = "";
    if (!ensureDeviceToken()) return false;
    float v = readBatteryVoltage();
    String mac = WiFi.macAddress();
    int rssi = WiFi.RSSI();
#if DEBUG_MODE
    int effectiveRefreshMin = DEBUG_REFRESH_MIN;
#else
    int effectiveRefreshMin = cfgSleepMin;
#endif
#if EPD_BPP >= 2
    const int colorCapability = 4;
#else
    const int colorCapability = 2;
#endif
    String url = cfgServer + "/api/render?v=" + String(v, 2)
               + "&mac=" + mac + "&rssi=" + String(rssi)
               + "&refresh_min=" + String(effectiveRefreshMin)
               + "&w=" + String(W) + "&h=" + String(H)
               + "&bpp=" + String(EPD_BPP)
               + "&colors=" + String(colorCapability);
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
        const char *headerKeys[] = {"X-Content-Fallback", "X-Refresh-Minutes", "X-Mode-Id"};
        http.collectHeaders(headerKeys, 3);

        http.addHeader("Accept-Encoding", "identity");
        if (cfgDeviceToken.length() > 0) {
            http.addHeader("X-Device-Token", cfgDeviceToken);
        }

        Serial.printf("Free heap: %d\n", ESP.getFreeHeap());
        int code = http.GET();
        Serial.printf("HTTP code: %d\n", code);
        if (renderedModeIdOut && code >= 200 && code < 300) {
            *renderedModeIdOut = http.header("X-Mode-Id");
        }
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

#if EPD_BPP >= 2
        if (contentLen == COLOR_BUF_LEN) {
            if (!ensureColorBuf()) {
                Serial.println("colorBuf alloc failed, skip 2bpp");
                http.end();
                return false;
            }
            if (!readExact(stream, colorBuf, COLOR_BUF_LEN)) {
                Serial.println("Failed to read 2bpp data");
                http.end();
                return false;
            }
            useColorBuf = true;
            http.end();
            Serial.printf("2BPP OK  %d bytes\n", COLOR_BUF_LEN);
            lastHeartbeatAt = millis();
            return true;
        }
        Serial.printf("Not raw 2bpp (%d bytes), fallback to BMP\n", contentLen);
        useColorBuf = false;
#endif

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
        memset(imgBuf, 0xFF, IMG_BUF_LEN);
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

bool peekPendingMode(String &pendingModeOut) {
    pendingModeOut = "";
    if (WiFi.status() != WL_CONNECTED) return false;
    if (!ensureDeviceToken()) return false;

    String mac = WiFi.macAddress();
    String url = cfgServer + "/api/device/" + mac + "/state";
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
        pendingModeOut = extractJsonStringField(body, "pending_mode");
        return pendingModeOut.length() > 0;
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

static bool parseVoiceTurnResponse(const String &body, String &turnId, String &replyText, String &transcript, bool &exitConversation) {
    turnId = extractJsonStringField(body, "turn_id");
    replyText = extractJsonStringField(body, "reply_text");
    transcript = extractJsonStringField(body, "transcript");
    String exitStr = extractJsonStringField(body, "exit_conversation");
    exitConversation = false;
    if (exitStr == "true" || exitStr == "1") {
        exitConversation = true;
    } else if (body.indexOf("\"exit_conversation\":true") >= 0) {
        exitConversation = true;
    }
    return turnId.length() > 0;
}

bool submitVoiceTurn(const char *pcmPath, int sampleRate, int screenW, int screenH, String &turnId, String &replyText, String &transcript, bool &exitConversation) {
    turnId = "";
    replyText = "";
    transcript = "";
    exitConversation = false;
    if (!ensureDeviceToken()) return false;

    File file = LittleFS.open(pcmPath, "r");
    if (!file) {
        Serial.println("[VOICE] failed to open PCM file");
        return false;
    }

    String mac = WiFi.macAddress();
    String url = cfgServer + "/api/device/" + mac + "/voice/turn"
               + "?sample_rate=" + String(sampleRate)
               + "&w=" + String(screenW)
               + "&h=" + String(screenH);
    bool useSSL = cfgServer.startsWith("https://");

    for (int attempt = 0; attempt < 2; attempt++) {
        file.seek(0);
        WiFiClient plainClient;
        WiFiClientSecure secClient;
        HTTPClient http;
        if (useSSL) {
            secClient.setCACert(ROOT_CA);
            http.begin(secClient, url);
        } else {
            http.begin(plainClient, url);
        }
        http.addHeader("Content-Type", "application/octet-stream");
        http.setTimeout(60000);
        if (cfgDeviceToken.length() > 0) {
            http.addHeader("X-Device-Token", cfgDeviceToken);
        }

        int code = http.sendRequest("POST", &file, file.size());
        if (code >= 200 && code < 300) {
            String body = http.getString();
            http.end();
            file.close();
            return parseVoiceTurnResponse(body, turnId, replyText, transcript, exitConversation);
        }
        if (code < 0) {
            Serial.printf("[VOICE] submit error: %s\n", http.errorToString(code).c_str());
        } else {
            String body = http.getString();
            Serial.printf("[VOICE] submit -> %d %s\n", code, body.substring(0, 300).c_str());
        }
        http.end();
        if (!recoverDeviceTokenIfUnauthorized(code)) {
            file.close();
            return false;
        }
    }

    file.close();
    return false;
}

bool submitVoiceTurnBytes(const uint8_t *pcmBytes, size_t pcmSize, int sampleRate, int screenW, int screenH, String &turnId, String &replyText, String &transcript, bool &exitConversation) {
    turnId = "";
    replyText = "";
    transcript = "";
    exitConversation = false;
    if (!ensureDeviceToken()) return false;
    if (pcmBytes == NULL || pcmSize == 0) {
        Serial.println("[VOICE] empty PCM payload");
        return false;
    }

    String mac = WiFi.macAddress();
    String url = cfgServer + "/api/device/" + mac + "/voice/turn"
               + "?sample_rate=" + String(sampleRate)
               + "&w=" + String(screenW)
               + "&h=" + String(screenH);
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
        http.addHeader("Content-Type", "application/octet-stream");
        http.setTimeout(60000);
        if (cfgDeviceToken.length() > 0) {
            http.addHeader("X-Device-Token", cfgDeviceToken);
        }

        int code = http.sendRequest("POST", (uint8_t *)pcmBytes, pcmSize);
        if (code >= 200 && code < 300) {
            String body = http.getString();
            http.end();
            return parseVoiceTurnResponse(body, turnId, replyText, transcript, exitConversation);
        }
        if (code < 0) {
            Serial.printf("[VOICE] submit-bytes error: %s\n", http.errorToString(code).c_str());
        } else {
            String body = http.getString();
            Serial.printf("[VOICE] submit-bytes -> %d %s\n", code, body.substring(0, 300).c_str());
        }
        http.end();
        if (!recoverDeviceTokenIfUnauthorized(code)) {
            return false;
        }
    }

    return false;
}

bool fetchVoiceAudio(const String &turnId, const char *path) {
    if (!ensureDeviceToken()) return false;
    String mac = WiFi.macAddress();
    String url = cfgServer + "/api/device/" + mac + "/voice/" + turnId + "/audio";
    bool useSSL = cfgServer.startsWith("https://");
    for (int attempt = 0; attempt < 2; attempt++) {
        File file = LittleFS.open(path, "w");
        if (!file) {
            Serial.println("[VOICE] failed to open audio output file");
            return false;
        }
        WiFiClient plainClient;
        WiFiClientSecure secClient;
        HTTPClient http;
        if (useSSL) {
            secClient.setCACert(ROOT_CA);
            http.begin(secClient, url);
        } else {
            http.begin(plainClient, url);
        }
        http.setTimeout(60000);
        if (cfgDeviceToken.length() > 0) {
            http.addHeader("X-Device-Token", cfgDeviceToken);
        }

        int code = http.GET();
        if (code == 200) {
            WiFiClient *stream = http.getStreamPtr();
            uint8_t buffer[1024];
            while (http.connected() || stream->available()) {
                int available = stream->available();
                if (available <= 0) {
                    delay(1);
                    continue;
                }
                int readLen = stream->readBytes(buffer, min(available, (int)sizeof(buffer)));
                if (readLen > 0) {
                    file.write(buffer, readLen);
                }
            }
            http.end();
            file.close();
            return true;
        }
        if (code < 0) {
            Serial.printf("[VOICE] audio error: %s\n", http.errorToString(code).c_str());
        } else {
            String body = http.getString();
            Serial.printf("[VOICE] audio -> %d %s\n", code, body.substring(0, 200).c_str());
        }
        http.end();
        if (!recoverDeviceTokenIfUnauthorized(code)) {
            file.close();
            return false;
        }
        file.close();
    }
    return false;
}

bool fetchVoiceImage(const String &turnId) {
    if (!ensureDeviceToken()) return false;

    String mac = WiFi.macAddress();
    String url = cfgServer + "/api/device/" + mac + "/voice/" + turnId + "/image";
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
            if (code < 0) {
                Serial.printf("[VOICE] image error: %s\n", http.errorToString(code).c_str());
            } else {
                String body = http.getString();
                Serial.printf("[VOICE] image -> %d %s\n", code, body.substring(0, 200).c_str());
            }
            http.end();
            if (!recoverDeviceTokenIfUnauthorized(code)) {
                return false;
            }
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
            if (stream->available()) {
                stream->read();
                toSkip--;
            }
        }

        uint8_t rowBuf[ROW_STRIDE];
        memset(imgBuf, 0xFF, IMG_BUF_LEN);
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

bool fetchVoiceIntroImage(int screenW, int screenH) {
    if (!ensureDeviceToken()) return false;

    String mac = WiFi.macAddress();
    String url = cfgServer + "/api/device/" + mac + "/voice/intro/image?w=" + String(screenW) + "&h=" + String(screenH);
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
            if (code < 0) {
                Serial.printf("[VOICE] intro image error: %s\n", http.errorToString(code).c_str());
            } else {
                String body = http.getString();
                Serial.printf("[VOICE] intro image -> %d %s\n", code, body.substring(0, 200).c_str());
            }
            http.end();
            if (!recoverDeviceTokenIfUnauthorized(code)) {
                return false;
            }
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
            if (stream->available()) {
                stream->read();
                toSkip--;
            }
        }

        uint8_t rowBuf[ROW_STRIDE];
        memset(imgBuf, 0xFF, IMG_BUF_LEN);
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

static void handleVoiceWsEvent(VoiceWsEvent &event) {
    if (gVoiceWsEventQueue == nullptr) {
        voiceWsReleaseEvent(event);
        return;
    }
    VoiceWsEvent *heapEvent = new VoiceWsEvent(event);
    if (heapEvent == nullptr) {
        voiceWsReleaseEvent(event);
        return;
    }
    if (xQueueSend(gVoiceWsEventQueue, &heapEvent, 0) != pdTRUE) {
        delete heapEvent;
        voiceWsReleaseEvent(event);
    }
}

static void voiceWsSocketEvent(WStype_t type, uint8_t *payload, size_t length) {
    switch (type) {
        case WStype_CONNECTED:
            gVoiceWsConnected = true;
            Serial.println("[VOICE_WS] connected");
            return;
        case WStype_DISCONNECTED:
            gVoiceWsConnected = false;
            Serial.println("[VOICE_WS] disconnected");
            return;
        case WStype_BIN: {
            if (payload == nullptr || length == 0) return;
            VoiceWsEvent event;
            event.type = VoiceWsEventType::TtsAudioChunk;
            event.sampleRate = 16000;
            event.needsDecode = gVoiceWsOpusEnabled;
            event.data = (uint8_t *)malloc(length);
            if (event.data == nullptr) return;
            memcpy(event.data, payload, length);
            event.dataLen = length;
            handleVoiceWsEvent(event);
            return;
        }
        case WStype_TEXT:
            break;
        case WStype_ERROR:
            Serial.println("[VOICE_WS] socket error");
            return;
        default:
            return;
    }

    String body;
    body.reserve(length + 1);
    for (size_t i = 0; i < length; i++) {
        body += (char)payload[i];
    }
    String eventName = extractJsonStringField(body, "event");
    if (eventName.length() == 0) {
        return;
    }

    VoiceWsEvent event;
    if (eventName == "session.ready") {
        event.type = VoiceWsEventType::SessionReady;
        String binaryAudio = extractJsonBoolField(body, "binary_audio");
        gVoiceWsBinaryAudioEnabled = (binaryAudio == "true" || binaryAudio == "1");
        String codec = extractJsonStringField(body, "audio_codec");
        gVoiceWsOpusEnabled = (codec == "opus");
        String serverVad = extractJsonBoolField(body, "server_vad");
        gVoiceWsServerVadEnabled = (serverVad == "true" || serverVad == "1");
    } else if (eventName == "asr.partial") {
        event.type = VoiceWsEventType::AsrPartial;
        event.text = extractJsonStringField(body, "text");
    } else if (eventName == "asr.final") {
        event.type = VoiceWsEventType::AsrFinal;
        event.transcript = extractJsonStringField(body, "transcript");
    } else if (eventName == "llm.delta") {
        event.type = VoiceWsEventType::LlmDelta;
        event.text = extractJsonStringField(body, "delta");
        event.generationId = extractJsonIntField(body, "generation_id", 0);
    } else if (eventName == "tts.text_chunk") {
        event.type = VoiceWsEventType::TtsTextChunk;
        event.text = extractJsonStringField(body, "text");
        event.generationId = extractJsonIntField(body, "generation_id", 0);
        event.chunkId = extractJsonIntField(body, "chunk_id", 0);
    } else if (eventName == "tts.audio_chunk") {
        event.type = VoiceWsEventType::TtsAudioChunk;
        event.generationId = extractJsonIntField(body, "generation_id", 0);
        event.chunkId = extractJsonIntField(body, "chunk_id", 0);
        event.sampleRate = extractJsonIntField(body, "sample_rate", 16000);
        if (!decodeBase64ToHeap(extractJsonStringField(body, "audio"), &event.data, &event.dataLen)) {
            Serial.println("[VOICE_WS] failed to decode audio chunk");
            return;
        }
    } else if (eventName == "turn.done") {
        event.type = VoiceWsEventType::TurnDone;
        event.turnId = extractJsonStringField(body, "turn_id");
        event.transcript = extractJsonStringField(body, "transcript");
        event.text = extractJsonStringField(body, "reply_text");
        event.generationId = extractJsonIntField(body, "generation_id", 0);
        String exitFlag = extractJsonBoolField(body, "exit_conversation");
        event.exitConversation = (exitFlag == "true" || exitFlag == "1");
        event.switchToMode = extractJsonStringField(body, "switch_to_mode");
        if (!decodeBase64ToHeap(extractJsonStringField(body, "image"), &event.data, &event.dataLen)) {
            Serial.println("[VOICE_WS] failed to decode image payload");
            return;
        }
    } else if (eventName == "turn.interrupted") {
        event.type = VoiceWsEventType::TurnInterrupted;
        event.generationId = extractJsonIntField(body, "generation_id", 0);
    } else if (eventName == "error") {
        event.type = VoiceWsEventType::Error;
        event.text = extractJsonStringField(body, "message");
    } else {
        return;
    }
    handleVoiceWsEvent(event);
}

bool voiceWsOpen(int sampleRate, int screenW, int screenH, bool includeImage) {
    if (WiFi.status() != WL_CONNECTED) return false;
    if (!ensureDeviceToken()) return false;

    if (gVoiceWsEventQueue == nullptr) {
        gVoiceWsEventQueue = xQueueCreate(12, sizeof(VoiceWsEvent *));
        if (gVoiceWsEventQueue == nullptr) {
            return false;
        }
    }

    voiceWsClose();

    bool useSSL = false;
    String host;
    uint16_t port = 0;
    String basePath;
    if (!parseWsServerUrl(cfgServer, useSSL, host, port, basePath)) {
        Serial.println("[VOICE_WS] invalid server url");
        return false;
    }

    String mac = WiFi.macAddress();
    String path = basePath + "/api/device/" + mac + "/voice/ws";

    gVoiceWsClient.onEvent(voiceWsSocketEvent);
    gVoiceWsClient.setReconnectInterval(0);
    String extraHeaders = String("X-Device-Token: ") + cfgDeviceToken + "\r\n";
    gVoiceWsClient.setExtraHeaders(extraHeaders.c_str());
    if (useSSL) {
        gVoiceWsClient.beginSslWithCA(host.c_str(), port, path.c_str(), ROOT_CA);
    } else {
        gVoiceWsClient.begin(host.c_str(), port, path.c_str());
    }
    gVoiceWsClient.enableHeartbeat(15000, 3000, 2);
    gVoiceWsConfigured = true;

    unsigned long startAt = millis();
    while (!gVoiceWsConnected && millis() - startAt < 6000UL) {
        gVoiceWsClient.loop();
        delay(10);
    }
    if (!gVoiceWsConnected) {
        Serial.println("[VOICE_WS] connect timeout");
        voiceWsClose();
        return false;
    }

    gVoiceWsBinaryAudioEnabled = false;
    gVoiceWsOpusEnabled = false;
    gVoiceWsServerVadEnabled = false;
    String startMsg = String("{\"type\":\"session.start\",\"sample_rate\":") + sampleRate
                    + ",\"w\":" + screenW
                    + ",\"h\":" + screenH
                    + ",\"include_image\":" + (includeImage ? "true" : "false")
                    + ",\"protocol\":2"
#if ENABLE_OPUS
                    + ",\"audio_codec\":\"opus\""
#else
                    + ",\"audio_codec\":\"pcm\""
#endif
                    + "}";
    if (!gVoiceWsClient.sendTXT(startMsg)) {
        Serial.println("[VOICE_WS] failed to send session.start");
        voiceWsClose();
        return false;
    }
    return true;
}

bool voiceWsConnected() {
    return gVoiceWsConnected;
}

void voiceWsLoop() {
    if (gVoiceWsConfigured) {
        gVoiceWsClient.loop();
    }
}

bool voiceWsSendAudioBin(const int16_t *samples, size_t sampleCount) {
    if (!gVoiceWsConnected || samples == nullptr || sampleCount == 0) return false;
#if ENABLE_OPUS
    if (gVoiceWsOpusEnabled) {
        uint8_t opusBuf[OPUS_MAX_PACKET_BYTES];
        int encoded = opusEncode(samples, sampleCount, opusBuf, sizeof(opusBuf));
        if (encoded > 0) {
            return gVoiceWsClient.sendBIN(opusBuf, encoded);
        }
        return false;
    }
#endif
    return gVoiceWsClient.sendBIN((const uint8_t *)samples, sampleCount * sizeof(int16_t));
}

bool voiceWsSendAudioChunk(const int16_t *samples, size_t sampleCount) {
    if (!gVoiceWsConnected || samples == nullptr || sampleCount == 0) return false;
    if (gVoiceWsBinaryAudioEnabled) {
        return voiceWsSendAudioBin(samples, sampleCount);
    }
    String audio = encodeBase64((const uint8_t *)samples, sampleCount * sizeof(int16_t));
    if (audio.length() == 0) {
        return false;
    }
    String msg = String("{\"type\":\"audio.append\",\"audio\":\"") + audio + "\"}";
    return gVoiceWsClient.sendTXT(msg);
}

bool voiceWsSendRawPacket(const uint8_t *data, size_t len) {
    if (!gVoiceWsConnected || data == nullptr || len == 0) return false;
    if (gVoiceWsBinaryAudioEnabled) {
        return gVoiceWsClient.sendBIN(data, len);
    }
    String audio = encodeBase64(data, len);
    if (audio.length() == 0) return false;
    String msg = String("{\"type\":\"audio.append\",\"audio\":\"") + audio + "\"}";
    return gVoiceWsClient.sendTXT(msg);
}

bool voiceWsBinaryAudio() {
    return gVoiceWsBinaryAudioEnabled;
}

bool voiceWsServerVad() {
    return gVoiceWsServerVadEnabled;
}

bool voiceWsCommitTurn() {
    if (!gVoiceWsConnected) return false;
    return gVoiceWsClient.sendTXT("{\"type\":\"audio.commit\"}");
}

bool voiceWsInterrupt() {
    if (!gVoiceWsConnected) return false;
    return gVoiceWsClient.sendTXT("{\"type\":\"interrupt\"}");
}

bool voiceWsPollEvent(VoiceWsEvent &eventOut) {
    if (gVoiceWsEventQueue == nullptr) return false;
    VoiceWsEvent *heapEvent = nullptr;
    if (xQueueReceive(gVoiceWsEventQueue, &heapEvent, 0) != pdTRUE || heapEvent == nullptr) {
        return false;
    }
    eventOut = *heapEvent;
    delete heapEvent;
    return true;
}

void voiceWsReleaseEvent(VoiceWsEvent &event) {
    if (event.data != nullptr) {
        free(event.data);
        event.data = nullptr;
    }
    event.dataLen = 0;
    event.text = "";
    event.transcript = "";
    event.turnId = "";
    event.type = VoiceWsEventType::None;
}

void voiceWsClose() {
    if (gVoiceWsConfigured) {
        if (gVoiceWsConnected) {
            gVoiceWsClient.sendTXT("{\"type\":\"close\"}");
        }
        gVoiceWsClient.disconnect();
    }
    gVoiceWsConfigured = false;
    gVoiceWsConnected = false;
    gVoiceWsBinaryAudioEnabled = false;
    gVoiceWsOpusEnabled = false;
    gVoiceWsServerVadEnabled = false;
    if (gVoiceWsEventQueue != nullptr) {
        VoiceWsEvent *heapEvent = nullptr;
        while (xQueueReceive(gVoiceWsEventQueue, &heapEvent, 0) == pdTRUE) {
            if (heapEvent != nullptr) {
                voiceWsReleaseEvent(*heapEvent);
                delete heapEvent;
            }
        }
    }
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
