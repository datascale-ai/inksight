#include "ota.h"
#include "network.h"
#include "display.h"
#include "config.h"
#include "storage.h"
#include "certs.h"
#include <WiFi.h>
#include <WiFiClient.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <esp_ota_ops.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>

// ── Global parameters set by network.cpp ───────────────────
String g_pending_ota_url = "";
String g_pending_ota_version = "";

// ── Independent OTA task handle (prevents re-entrancy) ───────
static TaskHandle_t s_otaTaskHandle = NULL;

// ── Report OTA progress to backend ─────────────────────────

static bool reportOTAProgress(int progress, const char* result) {
    if (!ensureDeviceToken()) return false;

    String mac = WiFi.macAddress();
    String url = cfgServer + "/api/device/" + mac + "/ota/progress";
    String body = "{\"progress\":" + String(progress);
    if (result && strlen(result) > 0) {
        body += ",\"result\":\"" + String(result) + "\"";
    }
    body += "}";

    WiFiClient plainClient;
    WiFiClientSecure secClient;
    HTTPClient http;
    if (!beginHttpForUrl(http, plainClient, secClient, url)) return false;
    http.addHeader("Content-Type", "application/json");
    http.setTimeout(HTTP_TIMEOUT);
    if (cfgDeviceToken.length() > 0) {
        http.addHeader("X-Device-Token", cfgDeviceToken);
    }
    int code = http.POST(body);
    http.end();
    return code >= 200 && code < 300;
}

// ── Perform firmware update ─────────────────────────────────

static bool performOTAUpdate(const char* ota_url, const char* ota_version) {
    // ── Pre-flight: NTP sync + WiFi check ──────────────────
    Serial.println("[OTA] === Starting OTA update ===");
    Serial.printf("[OTA] Target version : %s\n", ota_version);
    Serial.printf("[OTA] Download URL  : %s\n", ota_url);
    Serial.printf("[OTA] WiFi RSSI      : %d dBm\n", WiFi.RSSI());
    Serial.printf("[OTA] WiFi strength  : %s\n",
        WiFi.RSSI() > -50 ? "excellent" :
        WiFi.RSSI() > -60 ? "good" :
        WiFi.RSSI() > -70 ? "fair" : "poor");

    syncNTP();

    // ── Partition check ──────────────────────────────────────
    const esp_partition_t* running = esp_ota_get_running_partition();
    const esp_partition_t* update_partition = esp_ota_get_next_update_partition(NULL);
    if (!update_partition) {
        Serial.println("[OTA] ERROR: No OTA partition found!");
        reportOTAProgress(0, "failed:no_ota_partition");
        return false;
    }
    Serial.printf("[OTA] Running part   : addr=0x%x size=%lu bytes\n",
                  running->address, (unsigned long)running->size);
    Serial.printf("[OTA] Update part     : addr=0x%x size=%lu bytes\n",
                  update_partition->address, (unsigned long)update_partition->size);

    // ── HTTP client setup ────────────────────────────────────
    HTTPClient http;
    bool useHTTPS = cfgServer.startsWith("https://") ||
                    String(ota_url).startsWith("https://");

    if (useHTTPS) {
        WiFiClientSecure* secClient = new WiFiClientSecure();
        secClient->setCACert(ROOT_CA);
        secClient->setTimeout(30);  // socket-level timeout 30s
        http.begin(*secClient, ota_url);
        Serial.println("[OTA] Transport       : HTTPS (TLS)");
    } else {
        WiFiClient* plainClient = new WiFiClient();
        http.begin(*plainClient, ota_url);
        Serial.println("[OTA] Transport       : HTTP (plain)");
    }

    http.setTimeout(static_cast<uint32_t>(HTTP_TIMEOUT) * 3);  // 90s total
    Serial.printf("[OTA] HTTP timeout    : %lu ms\n", (unsigned long)HTTP_TIMEOUT * 3);

    // ── Connect & GET ─────────────────────────────────────────
    Serial.println("[OTA] Connecting to OTA server...");
    int httpCode = http.GET();

    if (httpCode < 0) {
        // Negative code = esp_http_client error (connect timeout, TLS error, etc.)
        String errStr = http.errorToString(httpCode);
        Serial.printf("[OTA] ERROR: HTTP connect failed (code=%d): %s\n", httpCode, errStr.c_str());
        // Common negative codes:
        //  -1  HTTPC_ERROR_CONNECTION_FAILED    "Connection refused" or timeout
        //  -2  HTTPC_ERROR_NO_RESPONSE           Server didn't respond
        //  -4  HTTPC_ERROR_TLS_INIT_FAILED       TLS handshake failed
        //  -5  HTTPC_ERROR_CONNECTION_TIMEOUT    Timeout during TLS/TCP handshake
        //  -7  HTTPC_ERROR_WRITE_FAILED          Request send failed
        //  -8  HTTPC_ERROR_READ_TIMEOUT         Response timeout
        if (httpCode == -1 || httpCode == -5) {
            Serial.println("[OTA] Likely cause: TLS handshake timeout (server unreachable or NTP not synced)");
        } else if (httpCode == -4) {
            Serial.println("[OTA] Likely cause: TLS cert validation failed (wrong time or unknown CA)");
        }
        reportOTAProgress(0, "failed:connect_error");
        http.end();
        return false;
    }

    Serial.printf("[OTA] HTTP response   : %d\n", httpCode);

    if (httpCode != 200) {
        Serial.printf("[OTA] ERROR: Unexpected HTTP status %d (expected 200)\n", httpCode);
        Serial.printf("[OTA]  Possible causes: 404=wrong URL, 403=rate limit/auth, 5xx=server error\n");
        reportOTAProgress(0, "failed:http_error");
        http.end();
        return false;
    }

    // ── Content-Length check ─────────────────────────────────
    int contentLen = http.getSize();
    Serial.printf("[OTA] Content-Length  : %d bytes\n", contentLen);
    if (contentLen <= 0) {
        Serial.println("[OTA] WARNING: Server did not send Content-Length, streaming in unknown-size mode");
    }
    if (contentLen > (int)update_partition->size) {
        Serial.printf("[OTA] ERROR: Firmware too large! (%d > %lu bytes available)\n",
                      contentLen, (unsigned long)update_partition->size);
        reportOTAProgress(0, "failed:firmware_too_large");
        http.end();
        return false;
    }

    // ── OTA begin ─────────────────────────────────────────────
    reportOTAProgress(0, "downloading");
    ledFeedback("downloading");

    Serial.println("[OTA] Starting OTA write...");
    esp_ota_handle_t ota_handle;
    esp_err_t err = esp_ota_begin(
        update_partition,
        contentLen > 0 ? contentLen : OTA_SIZE_UNKNOWN,
        &ota_handle
    );
    if (err != ESP_OK) {
        Serial.printf("[OTA] ERROR: esp_ota_begin failed: %s (0x%x)\n", esp_err_to_name(err), err);
        reportOTAProgress(0, "failed:ota_begin");
        http.end();
        return false;
    }
    Serial.println("[OTA] esp_ota_begin OK, starting download loop...");

    // ── Download loop with per-chunk progress ─────────────────
    WiFiClient* stream = http.getStreamPtr();
    uint8_t buf[4096];
    int totalWritten = 0;
    int lastReportPct = 0;
    unsigned long downloadStart = millis();

    while (http.connected() && (contentLen > 0 || contentLen <= 0)) {
        size_t avail = stream->available();
        if (avail > 0) {
            int readLen = stream->readBytes(buf, min((size_t)avail, sizeof(buf)));
            if (readLen <= 0) {
                Serial.println("[OTA] WARNING: stream.readBytes returned 0, retrying...");
                delay(10);
                continue;
            }
            err = esp_ota_write(ota_handle, buf, readLen);
            if (err != ESP_OK) {
                Serial.printf("[OTA] ERROR: esp_ota_write failed: %s (0x%x)\n",
                              esp_err_to_name(err), err);
                reportOTAProgress(0, "failed:write_error");
                esp_ota_abort(ota_handle);
                http.end();
                return false;
            }
            totalWritten += readLen;

            // Progress logging every ~5% or every 30s
            if (contentLen > 0) {
                int pct = min(49, (totalWritten * 50) / contentLen);
                if (pct >= lastReportPct + 5) {
                    unsigned long elapsed = millis() - downloadStart;
                    int speedKBs = elapsed > 0 ? (totalWritten / 1024) * 1000 / elapsed : 0;
                    Serial.printf("[OTA] Progress: %d%% (%d / %d bytes, %lu ms elapsed, %d KB/s)\n",
                                  pct, totalWritten, contentLen, elapsed, speedKBs);
                    reportOTAProgress(pct, "downloading");
                    lastReportPct = pct;
                }
            }
        }
        if (contentLen > 0 && totalWritten >= contentLen) break;
        delay(1);
    }

    unsigned long downloadTime = millis() - downloadStart;
    Serial.printf("[OTA] Download complete: %d bytes in %lu ms (avg %d KB/s)\n",
                  totalWritten, downloadTime,
                  downloadTime > 0 ? (totalWritten / 1024) * 1000 / downloadTime : 0);

    http.end();
    reportOTAProgress(50, "flashing");
    Serial.println("[OTA] === Download done, flashing ===");

    // ── OTA end ───────────────────────────────────────────────
    err = esp_ota_end(ota_handle);
    if (err != ESP_OK) {
        Serial.printf("[OTA] ERROR: esp_ota_end failed: %s (0x%x)\n", esp_err_to_name(err), err);
        reportOTAProgress(50, "failed:ota_end");
        return false;
    }
    Serial.println("[OTA] esp_ota_end OK");

    // ── Set boot partition ────────────────────────────────────
    err = esp_ota_set_boot_partition(update_partition);
    if (err != ESP_OK) {
        Serial.printf("[OTA] ERROR: esp_ota_set_boot_partition failed: %s (0x%x)\n",
                      esp_err_to_name(err), err);
        reportOTAProgress(50, "failed:set_boot");
        return false;
    }
    Serial.println("[OTA] Boot partition set");

    // ── Success ───────────────────────────────────────────────
    reportOTAProgress(100, "success");
    Serial.println("[OTA] === Firmware update SUCCESS, rebooting in 2s ===");
    ledFeedback("success");
    delay(2000);
    ESP.restart();

    return true;  // Never reached
}

// ── Check and launch OTA in independent task ────────────────

bool isOtaTaskRunning() {
    return s_otaTaskHandle != NULL;
}

// Internal task entry — runs in its own 12KB stack
static void otaTaskFunction(void* param) {
    (void)param;
    Serial.println("[OTA] OTA task started on independent stack");

    bool ok = performOTAUpdate(
        g_pending_ota_url.c_str(),
        g_pending_ota_version.c_str()
    );

    // Clear pending globals
    g_pending_ota_url = "";
    g_pending_ota_version = "";

    if (!ok) {
        ledFeedback("fail");
        Serial.println("[OTA] Firmware update FAILED — see logs above");
    }

    // Clean up and delete this task
    s_otaTaskHandle = NULL;
    vTaskDelete(NULL);
}

bool checkAndPerformOTA() {
    if (g_pending_ota_url.length() == 0) {
        return false;
    }

    // Prevent re-entrancy: if a task is already running, skip
    if (s_otaTaskHandle != NULL) {
        Serial.println("[OTA] OTA task already running, skipping");
        return true;
    }

    Serial.println("[OTA] === Pending firmware update detected ===");

    BaseType_t ret = xTaskCreatePinnedToCore(
        otaTaskFunction,
        "OTA",
        12 * 1024,                       // 12KB stack — plenty for HTTPS+TLS
        NULL,
        configMAX_PRIORITIES - 2,        // slightly below loopTask priority
        &s_otaTaskHandle,
        0                                 // ESP32-C3 has only one core, pin to 0
    );

    if (ret != pdPASS) {
        Serial.println("[OTA] Failed to create OTA task");
        s_otaTaskHandle = NULL;
        g_pending_ota_url = "";
        g_pending_ota_version = "";
        ledFeedback("fail");
        return false;
    }

    Serial.println("[OTA] OTA task launched (independent stack, 12KB)");
    // Caller should return immediately. On success the task reboots;
    // on failure it clears globals and deletes itself.
    return true;
}
