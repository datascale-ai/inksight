// Smart e-ink desktop companion powered by LLM
// https://github.com/datascale-ai/inksight

#include <Arduino.h>
#include <WiFi.h>

#include "config.h"
#include "epd_driver.h"
#include "display.h"
#include "network.h"
#include "storage.h"
#include "portal.h"
#include "offline_cache.h"

// ── Shared framebuffer (referenced by other modules via extern) ──
uint8_t imgBuf[IMG_BUF_LEN];

// ── Device state machine ────────────────────────────────────
enum class DeviceState : uint8_t {
    BOOT,           // Initial state, loading config
    PORTAL,         // Captive portal active
    CONNECTING,     // Connecting to WiFi
    FETCHING,       // Downloading image from backend
    DISPLAYING,     // Showing content, clock ticking
    REFRESHING,     // Manual refresh triggered
    SLEEPING,       // Deep sleep
    ERROR,          // Error state, retry pending
};

struct DeviceContext {
    DeviceState state = DeviceState::BOOT;

    // Button state
    unsigned long btnPressStart = 0;
    bool liveMode = false;
    unsigned long lastLivePollAt = 0;
    unsigned long lastLiveWiFiRetryAt = 0;

    // Timing
    unsigned long setupDoneAt = 0;
    unsigned long lastClockTick = 0;

    // Pending actions (set by button handler, consumed by loop)
    bool wantRefresh = false;
    bool wantEnterLiveMode = false;
};

static DeviceContext ctx;
static bool focusListening = false;

// Content dedup — skip display refresh when content unchanged
static uint32_t lastContentChecksum = 0;
static int lastRenderedPeriod = -1;

static uint32_t computeChecksum(const uint8_t *buf, int len) {
    uint32_t sum = 0;
    for (int i = 0; i < len; i++) sum += buf[i];
    return sum;
}

// ── Forward declarations ────────────────────────────────────
static void checkConfigButton();
static void triggerImmediateRefresh(bool nextMode = false, bool keepWiFi = false);
static void handleLiveMode();
static bool waitForContentReady();
static void handleFailure(const char *reason);
static void enterDeepSleep(int minutes);

// ── LED feedback ────────────────────────────────────────────

static void ledInit() {
    pinMode(PIN_LED, OUTPUT);
    digitalWrite(PIN_LED, LOW);
}

static void ledFeedback(const char *pattern) {
    if (strcmp(pattern, "ack") == 0) {
        for (int i = 0; i < 2; i++) {
            digitalWrite(PIN_LED, HIGH); delay(80);
            digitalWrite(PIN_LED, LOW);  delay(80);
        }
    } else if (strcmp(pattern, "connecting") == 0) {
        digitalWrite(PIN_LED, HIGH); delay(200);
        digitalWrite(PIN_LED, LOW);  delay(200);
    } else if (strcmp(pattern, "downloading") == 0) {
        for (int i = 0; i < 3; i++) {
            digitalWrite(PIN_LED, HIGH); delay(150);
            digitalWrite(PIN_LED, LOW);  delay(150);
        }
    } else if (strcmp(pattern, "success") == 0) {
        digitalWrite(PIN_LED, HIGH); delay(1000);
        digitalWrite(PIN_LED, LOW);
    } else if (strcmp(pattern, "fail") == 0) {
        for (int i = 0; i < 5; i++) {
            digitalWrite(PIN_LED, HIGH); delay(60);
            digitalWrite(PIN_LED, LOW);  delay(60);
        }
    } else if (strcmp(pattern, "favorite") == 0) {
        digitalWrite(PIN_LED, HIGH); delay(2000);
        digitalWrite(PIN_LED, LOW);
    } else if (strcmp(pattern, "portal") == 0) {
        digitalWrite(PIN_LED, HIGH);
    } else if (strcmp(pattern, "off") == 0) {
        digitalWrite(PIN_LED, LOW);
    }
}

// ═════════════════════════════════════════════════════════════
// setup()
// ═════════════════════════════════════════════════════════════

void setup() {
    Serial.begin(115200);
    delay(3000);
    Serial.println("\n=== InkSight ===");

    gpioInit();
    ledInit();
    epdInit();
    cacheInit();
    Serial.println("EPD ready");

    loadConfig();

    // Only force portal if BOOT is held for a moment (avoids RST bounce triggering portal)
    bool forcePortal = false;
    if (digitalRead(PIN_CFG_BTN) == LOW) {
        delay(400);
        forcePortal = (digitalRead(PIN_CFG_BTN) == LOW);
    }
    bool hasConfig   = (cfgSSID.length() > 0);

    if (forcePortal || !hasConfig) {
        Serial.println(forcePortal ? "Config button held -> portal"
                                   : "No WiFi config -> portal");

        String mac = WiFi.macAddress();
        String apName = "InkSight-" + mac.substring(mac.length() - 5);
        apName.replace(":", "");

        ledFeedback("portal");
        showSetupScreen(apName.c_str());
        startCaptivePortal();
        ctx.state = DeviceState::PORTAL;
        return;
    }

    // Check server URL is configured
    if (cfgServer.length() == 0) {
        Serial.println("No server URL configured -> portal");
        String mac = WiFi.macAddress();
        String apName = "InkSight-" + mac.substring(mac.length() - 5);
        apName.replace(":", "");
        ledFeedback("portal");
        showSetupScreen(apName.c_str());
        startCaptivePortal();
        ctx.state = DeviceState::PORTAL;
        return;
    }

    // Normal boot: connect WiFi and fetch image
    int retryCount = getRetryCount();
    Serial.printf("Retry count: %d/%d\n", retryCount, MAX_RETRY_COUNT);

    ledFeedback("connecting");
    if (!connectWiFi()) {
        ledFeedback("fail");
        handleFailure("WiFi failed");
        return;
    }

    // Best-effort fetch focus flag from backend
    bool focusFlag = false;
    if (fetchFocusListeningFlag(&focusFlag)) {
        focusListening = focusFlag;
    } else {
        focusListening = false;
    }

    Serial.println("Fetching image...");
    ledFeedback("downloading");
    bool gotFallback = false;
    bool ok = fetchBMP(false, &gotFallback);
    if (!ok || gotFallback) {
        if (!waitForContentReady()) {
            ledFeedback("fail");
            handleFailure("Server error");
            return;
        }
    }

    // Success - reset retry counter
    resetRetryCount();

    cacheSave(imgBuf, IMG_BUF_LEN);
    lastContentChecksum = computeChecksum(imgBuf, IMG_BUF_LEN);
    syncNTP();
    Serial.println("Displaying image...");
    smartDisplay(imgBuf);
    ledFeedback("success");
    Serial.println("Display done");
    lastRenderedPeriod = currentPeriodIndex();
    ctx.lastClockTick = millis();

    bool firstInstallLivePending = isFirstInstallLiveModePending();
    if (firstInstallLivePending) {
        ctx.liveMode = true;
        ctx.lastLivePollAt = 0;
        ctx.lastLiveWiFiRetryAt = 0;
        markFirstInstallLiveModeDone();
        postRuntimeMode("active");
        Serial.println("[LIVE] First install: default to active mode");
    } else {
        postRuntimeMode("interval");
        if (focusListening) {
            Serial.println("[FOCUS] Focus listening enabled, keeping WiFi connected in interval mode");
        } else {
            WiFi.disconnect(true);
            WiFi.mode(WIFI_OFF);
        }
    }

    ctx.state = DeviceState::DISPLAYING;
    ctx.setupDoneAt = millis();
#if DEBUG_MODE
    Serial.printf("[DEBUG] Staying awake, refresh every %d min (user config: %d min)\n",
                  DEBUG_REFRESH_MIN, cfgSleepMin);
#else
    Serial.printf("Staying awake, refresh every %d min\n", cfgSleepMin);
#endif
}

// ═════════════════════════════════════════════════════════════
// loop()
// ═════════════════════════════════════════════════════════════

void loop() {
    // Portal mode: only handle web requests
    if (ctx.state == DeviceState::PORTAL) {
        handlePortalClients();
        checkConfigButton();
        delay(5);
        return;
    }

    checkConfigButton();

    if (ctx.wantEnterLiveMode) {
        ctx.wantEnterLiveMode = false;
        if (ctx.liveMode) {
            ctx.liveMode = false;
            Serial.println("[LIVE] Live mode disabled, back to interval mode");
            ledFeedback("ack");
            postRuntimeMode("interval");
            WiFi.disconnect(true);
            WiFi.mode(WIFI_OFF);
        } else {
            ctx.liveMode = true;
            ctx.lastLivePollAt = 0;
            ctx.lastLiveWiFiRetryAt = 0;
            Serial.println("[LIVE] Live mode enabled");
            ledFeedback("ack");
            if (connectWiFi()) {
                Serial.println("[LIVE] WiFi connected");
                postRuntimeMode("active");
            }
        }
    } else if (ctx.wantRefresh) {
        triggerImmediateRefresh();
        ctx.wantRefresh = false;
        ctx.setupDoneAt = millis();
    }

    handleLiveMode();

    unsigned long now = millis();
    bool timeChanged = false;
    while (now - ctx.lastClockTick >= 1000UL) {
        tickTime();
        ctx.lastClockTick += 1000UL;
        timeChanged = true;
    }
    if (timeChanged && cfgSleepMin > 180 && !focusListening) {
        int currentPeriod = currentPeriodIndex();
        if (currentPeriod != lastRenderedPeriod) {
            updateTimeDisplay();
            lastRenderedPeriod = currentPeriod;
        }
    }

    if (!ctx.liveMode) {
        unsigned long refreshInterval = 0;
#if DEBUG_MODE
        refreshInterval = (unsigned long)DEBUG_REFRESH_MIN * 60000UL;
#else
        refreshInterval = (unsigned long)cfgSleepMin * 60000UL;
#endif
        if (millis() - ctx.setupDoneAt >= refreshInterval) {
#if DEBUG_MODE
            Serial.printf("[DEBUG] %d min elapsed, refreshing content...\n", DEBUG_REFRESH_MIN);
#else
            Serial.printf("%d min elapsed, refreshing content...\n", cfgSleepMin);
#endif
            triggerImmediateRefresh();
            ctx.setupDoneAt = millis();
        }
    }

    if (WiFi.status() == WL_CONNECTED) {
        postHeartbeat();
    }

    // Focus Mode: 10s poll alert-bmp and show full-screen alert for 30s
    static unsigned long lastAlertPollAt = 0;
    static bool alertVisible = false;
    static unsigned long alertShownAt = 0;
    static uint8_t alertBackupBuf[IMG_BUF_LEN];
    static bool hasAlertBackup = false;

    if (focusListening) {
        unsigned long nowMs = millis();
        if (!alertVisible) {
            const unsigned long ALERT_INTERVAL_MS = 10000UL;
            if (lastAlertPollAt == 0 || nowMs - lastAlertPollAt >= ALERT_INTERVAL_MS) {
                lastAlertPollAt = nowMs;
                memcpy(alertBackupBuf, imgBuf, IMG_BUF_LEN);
                hasAlertBackup = true;
                if (fetchFocusAlertBMP()) {
                    epdDisplayFast(imgBuf);
                    alertVisible = true;
                    alertShownAt = nowMs;
                } else {
                    if (hasAlertBackup) memcpy(imgBuf, alertBackupBuf, IMG_BUF_LEN);
                    hasAlertBackup = false;
                }
            }
        } else {
            const unsigned long ALERT_DISPLAY_MS = 30000UL;
            if (nowMs - alertShownAt >= ALERT_DISPLAY_MS) {
                if (hasAlertBackup) {
                    memcpy(imgBuf, alertBackupBuf, IMG_BUF_LEN);
                    epdDisplayFast(imgBuf);
                }
                hasAlertBackup = false;
                alertVisible = false;
            }
        }
    }

    delay(50);
}

// ── Deep sleep helper ───────────────────────────────────────

static void enterDeepSleep(int minutes) {
    if (focusListening) {
        Serial.println("[FOCUS] Focus listening enabled, skipping deep sleep");
        return;
    }
    epdSleep();
    Serial.printf("Deep sleep for %d min (~%duA)\n", minutes, 5);
    Serial.flush();
    esp_sleep_enable_timer_wakeup((uint64_t)minutes * 60ULL * 1000000ULL);
    esp_deep_sleep_start();
}

// ── Failure handler with retry logic ────────────────────────

static void showFailureDiagnostic(const char *reason) {
    char l2[64], l3[64];
    snprintf(l2, sizeof(l2), "SSID: %.40s", cfgSSID.c_str());
    snprintf(l3, sizeof(l3), "URL: %.44s", cfgServer.c_str());
    showDiagnostic(reason, l2, l3, "Hold BOOT to reconfigure");
}

static void handleFailure(const char *reason) {
    // Show diagnostic screen so user can see what's wrong
    Serial.printf("[DIAG] %s | SSID=%s | Server=%s\n",
                  reason, cfgSSID.c_str(), cfgServer.c_str());
    showFailureDiagnostic(reason);

    // Wait 5 seconds so user can read the diagnostic
    delay(5000);

    // Try offline cache
    if (cacheLoad(imgBuf, IMG_BUF_LEN)) {
        Serial.println("Showing cached content (offline mode)");
        const int offlineScale = 2;
        const int offlineLen = 7;
        const int offlineWidth = offlineLen * (5 * offlineScale + offlineScale) - offlineScale;
        const int offlineX = W - offlineWidth - 4;
        const int offlineY = (H * 12 / 100) + 2;
        drawText("OFFLINE", offlineX, offlineY, offlineScale);
        syncNTP();
        smartDisplay(imgBuf);
        ledFeedback("success");
        updateTimeDisplay();
        lastRenderedPeriod = currentPeriodIndex();
        ctx.lastClockTick = millis();
        WiFi.disconnect(true);
        WiFi.mode(WIFI_OFF);
        ctx.state = DeviceState::DISPLAYING;
        ctx.setupDoneAt = millis();
        resetRetryCount();
        return;
    }

    // No cache — retry logic
    int retryCount = getRetryCount();

    if (retryCount < MAX_RETRY_COUNT) {
        int delaySec = RETRY_DELAYS[retryCount];
        setRetryCount(retryCount + 1);

        Serial.printf("%s, retry %d/%d in %ds...\n",
                      reason, retryCount + 1, MAX_RETRY_COUNT, delaySec);
        delay((unsigned long)delaySec * 1000);
        ESP.restart();
    } else {
        Serial.println("Max retries reached, entering deep sleep");
        resetRetryCount();
        if (focusListening) {
            Serial.println("[FOCUS] Focus listening enabled, not entering deep sleep");
            ctx.state = DeviceState::DISPLAYING;
            ctx.setupDoneAt = millis();
            return;
        }
        esp_sleep_enable_timer_wakeup((uint64_t)cfgSleepMin * 60ULL * 1000000ULL);
        esp_deep_sleep_start();
    }
}

// ── Immediate refresh (reused by button press and timer) ────

static void handleLiveMode() {
    if (!ctx.liveMode) return;

    unsigned long now = millis();
#if DEBUG_MODE
    unsigned long refreshInterval = (unsigned long)DEBUG_REFRESH_MIN * 60000UL;
#else
    unsigned long refreshInterval = (unsigned long)cfgSleepMin * 60000UL;
#endif
    if (WiFi.status() != WL_CONNECTED) {
        if (now - ctx.lastLiveWiFiRetryAt >= (unsigned long)LIVE_WIFI_RETRY_MS) {
            ctx.lastLiveWiFiRetryAt = now;
            ledFeedback("connecting");
            if (connectWiFi()) {
                Serial.println("[LIVE] WiFi connected");
            } else {
                Serial.println("[LIVE] WiFi reconnect failed");
            }
        }
        return;
    }

    if (ctx.lastLivePollAt != 0 &&
        now - ctx.lastLivePollAt < (unsigned long)LIVE_POLL_MS) {
        return;
    }
    ctx.lastLivePollAt = now;

    bool shouldExitLive = false;
    if (hasPendingRemoteAction(&shouldExitLive)) {
        Serial.println("[LIVE] Pending action detected, refreshing now");
        triggerImmediateRefresh(false, true);
        ctx.setupDoneAt = millis();
        return;
    }
    if (shouldExitLive) {
        ctx.liveMode = false;
        postRuntimeMode("interval");
        WiFi.disconnect(true);
        WiFi.mode(WIFI_OFF);
        Serial.println("[LIVE] Backend requested interval mode");
        return;
    }

    if (millis() - ctx.setupDoneAt >= refreshInterval) {
#if DEBUG_MODE
        Serial.printf("[LIVE][DEBUG] Fallback %d min elapsed, refreshing content...\n", DEBUG_REFRESH_MIN);
#else
        Serial.printf("[LIVE] Fallback %d min elapsed, refreshing content...\n", cfgSleepMin);
#endif
        triggerImmediateRefresh(false, true);
        ctx.setupDoneAt = millis();
    }
}

static void triggerImmediateRefresh(bool nextMode, bool keepWiFi) {
    Serial.println("[REFRESH] Triggering immediate refresh...");
    ledFeedback("ack");
    if (nextMode) {
        showModePreview("NEXT");
    }
    bool connected = (WiFi.status() == WL_CONNECTED);
    if (!connected) {
        ledFeedback("connecting");
        connected = connectWiFi();
    }
    if (connected) {
        ledFeedback("downloading");
        if (fetchBMP(nextMode)) {
            cacheSave(imgBuf, IMG_BUF_LEN);

            uint32_t newChecksum = computeChecksum(imgBuf, IMG_BUF_LEN);
            syncNTP();
            if (newChecksum == lastContentChecksum && !nextMode) {
                Serial.println("Content unchanged, skipping display refresh");
                ledFeedback("success");
            } else {
                Serial.println("Displaying new content...");
                smartDisplay(imgBuf);
                lastContentChecksum = newChecksum;
                ledFeedback("success");
                Serial.println("Display done");
            }

            lastRenderedPeriod = currentPeriodIndex();
            ctx.lastClockTick = millis();
        } else {
            ledFeedback("fail");
            Serial.println("Fetch failed, keeping old content");
        }
        if (!keepWiFi) {
            WiFi.disconnect(true);
            WiFi.mode(WIFI_OFF);
        }
    } else {
        ledFeedback("fail");
        Serial.println("WiFi reconnect failed");
    }
}

static bool waitForContentReady() {
    const int maxRetries = 4;
    const int waitMs = 15000;
    for (int i = 0; i < maxRetries; i++) {
        Serial.printf("[BOOT] Content not ready, retry %d/%d\n", i + 1, maxRetries);
        showError("Generating...");
        delay(waitMs);
        if (WiFi.status() != WL_CONNECTED) {
            if (!connectWiFi()) {
                continue;
            }
        }
        ledFeedback("downloading");
        bool gotFallback = false;
        if (fetchBMP(false, &gotFallback) && !gotFallback) {
            Serial.println("[BOOT] Content is ready");
            return true;
        }
    }
    return false;
}

// ── Config button handler ───────────────────────────────────
// Single click:       toggle live mode / interval mode
// Long press (>=2s):  restart into config portal

static void checkConfigButton() {
    bool isPressed = (digitalRead(PIN_CFG_BTN) == LOW);

    if (isPressed) {
        if (ctx.btnPressStart == 0) {
            ctx.btnPressStart = millis();
        } else {
            unsigned long holdTime = millis() - ctx.btnPressStart;
            if (holdTime >= (unsigned long)CFG_BTN_HOLD_MS) {
                Serial.printf("Config button held for %dms, restarting...\n", CFG_BTN_HOLD_MS);
                ledFeedback("ack");
                showError("Restarting");
                delay(1000);
                ESP.restart();
            }
        }
    } else {
        if (ctx.btnPressStart != 0) {
            unsigned long pressDuration = millis() - ctx.btnPressStart;
            ctx.btnPressStart = 0;

            if (pressDuration >= (unsigned long)SHORT_PRESS_MIN_MS &&
                pressDuration < (unsigned long)CFG_BTN_HOLD_MS) {
                Serial.println("[BTN] Single click -> toggle live mode");
                ctx.wantEnterLiveMode = true;
            }
        }
    }
}
