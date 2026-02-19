#include "network.h"
#include "config.h"
#include "storage.h"

#include <WiFi.h>
#include <HTTPClient.h>
#include <time.h>

// ── Time state ──────────────────────────────────────────────
int curHour, curMin, curSec;

// ── WiFi connection ─────────────────────────────────────────

bool connectWiFi() {
    Serial.printf("WiFi: %s ", cfgSSID.c_str());
    WiFi.mode(WIFI_STA);
    WiFi.begin(cfgSSID.c_str(), cfgPass.c_str());

    unsigned long t0 = millis();
    while (WiFi.status() != WL_CONNECTED) {
        if (millis() - t0 > (unsigned long)WIFI_TIMEOUT) {
            Serial.println("TIMEOUT");
            return false;
        }
        delay(300);
        Serial.print(".");
    }
    Serial.printf(" OK  IP=%s\n", WiFi.localIP().toString().c_str());
    return true;
}

// ── Battery voltage ─────────────────────────────────────────

float readBatteryVoltage() {
    int raw = analogRead(PIN_BAT_ADC);
    return raw * (3.3f / 4095.0f) * 2.0f;
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

// ── Fetch BMP from backend ──────────────────────────────────

bool fetchBMP() {
    float v = readBatteryVoltage();
    String mac = WiFi.macAddress();
    int rssi = WiFi.RSSI();
    String url = cfgServer + "/api/render?v=" + String(v, 2)
               + "&mac=" + mac + "&rssi=" + String(rssi)
               + "&w=" + String(W) + "&h=" + String(H);
    Serial.printf("GET %s (RSSI=%d)\n", url.c_str(), rssi);

    WiFiClient client;
    HTTPClient http;
    http.begin(client, url);
    http.setTimeout(HTTP_TIMEOUT);
    http.setFollowRedirects(HTTPC_STRICT_FOLLOW_REDIRECTS);

    Serial.printf("Free heap: %d\n", ESP.getFreeHeap());
    int code = http.GET();
    Serial.printf("HTTP code: %d\n", code);

    if (code != 200) {
        if (code < 0) {
            Serial.printf("HTTP error: %s\n", http.errorToString(code).c_str());
        } else {
            String body = http.getString();
            Serial.printf("Response: %s\n", body.substring(0, 500).c_str());
        }
        http.end();
        return false;
    }

    int contentLen = http.getSize();
    Serial.printf("Content-Length: %d\n", contentLen);

    WiFiClient *stream = http.getStreamPtr();

    // Read BMP file header (14 bytes)
    uint8_t fileHeader[14];
    if (!readExact(stream, fileHeader, 14)) {
        Serial.println("Failed to read BMP header");
        http.end();
        return false;
    }

    // Extract pixel data offset from header
    uint32_t pixelOffset = fileHeader[10]
                         | ((uint32_t)fileHeader[11] << 8)
                         | ((uint32_t)fileHeader[12] << 16)
                         | ((uint32_t)fileHeader[13] << 24);
    Serial.printf("BMP pixel offset: %u\n", pixelOffset);

    // Skip remaining header bytes
    int toSkip = pixelOffset - 14;
    while (toSkip > 0 && stream->connected()) {
        if (stream->available()) { stream->read(); toSkip--; }
    }

    // Read pixel data row by row (BMP is bottom-up)
    uint8_t rowBuf[ROW_STRIDE];
    for (int bmpY = 0; bmpY < H; bmpY++) {
        if (!readExact(stream, rowBuf, ROW_STRIDE)) {
            Serial.printf("Failed to read row %d\n", bmpY);
            http.end();
            return false;
        }
        int dispY = H - 1 - bmpY;  // Flip vertical (BMP is bottom-up)
        memcpy(imgBuf + dispY * ROW_BYTES, rowBuf, ROW_BYTES);
    }

    http.end();
    Serial.printf("BMP OK  %d bytes\n", IMG_BUF_LEN);

#if DEBUG_MODE
    // Checksum for verifying image data changed
    uint32_t checksum = 0;
    for (int i = 0; i < IMG_BUF_LEN; i++) checksum += imgBuf[i];
    Serial.printf("imgBuf checksum: %u\n", checksum);
#endif

    return true;
}

// ── Post config to backend ──────────────────────────────────

void postConfigToBackend() {
    if (cfgConfigJson.length() == 0) return;

    // Inject MAC address into the config JSON
    String mac = WiFi.macAddress();
    String body = cfgConfigJson;
    if (body.startsWith("{")) {
        body = "{\"mac\":\"" + mac + "\"," + body.substring(1);
    }

    HTTPClient http;
    WiFiClient client;
    String url = cfgServer + "/api/config";
    http.begin(client, url);
    http.addHeader("Content-Type", "application/json");
    http.setTimeout(HTTP_TIMEOUT);

    int code = http.POST(body);
    Serial.printf("POST /api/config -> %d\n", code);
    http.end();
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
