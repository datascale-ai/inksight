// ── InkSight Firmware ────────────────────────────────────────
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

// ── Shared framebuffer (referenced by other modules via extern) ──
uint8_t imgBuf[IMG_BUF_LEN];

// ── Runtime state ───────────────────────────────────────────
static unsigned long cfgBtnPressStart   = 0;
static unsigned long setupDoneMillis    = 0;
static unsigned long lastShortPressTime = 0;
static unsigned long lastClockTickMillis = 0;
static int           clickCount         = 0;
static bool          pendingRefresh     = false;
static bool          pendingNextMode    = false;
static bool          pendingFavorite    = false;

// ── Forward declarations ────────────────────────────────────
static void checkConfigButton();
static void triggerImmediateRefresh(bool nextMode = false);
static void triggerFavorite();
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
    Serial.println("EPD ready");

    loadConfig();

    // Check if config button is held or no WiFi config exists
    bool forcePortal = (digitalRead(PIN_CFG_BTN) == LOW);
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

    Serial.println("Fetching image...");
    ledFeedback("downloading");
    if (!fetchBMP()) {
        ledFeedback("fail");
        handleFailure("Server error");
        return;
    }

    // Success - reset retry counter
    resetRetryCount();

    Serial.println("Displaying image...");
    smartDisplay(imgBuf);
    ledFeedback("success");
    Serial.println("Display done");

    syncNTP();
    updateTimeDisplay();
    lastClockTickMillis = millis();

    WiFi.disconnect(true);
    WiFi.mode(WIFI_OFF);

    setupDoneMillis = millis();
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
    if (portalActive) {
        handlePortalClients();
        checkConfigButton();
        delay(5);
        return;
    }

    checkConfigButton();

    // Handle button-triggered actions
    if (pendingFavorite) {
        triggerFavorite();
        pendingFavorite = false;
        pendingNextMode = false;
        pendingRefresh = false;
        setupDoneMillis = millis();
    } else if (pendingRefresh || pendingNextMode) {
        triggerImmediateRefresh(pendingNextMode);
        pendingRefresh = false;
        pendingNextMode = false;
        setupDoneMillis = millis();
    }

    unsigned long now = millis();
    bool timeChanged = false;
    while (now - lastClockTickMillis >= 1000UL) {
        tickTime();
        lastClockTickMillis += 1000UL;
        timeChanged = true;
    }
    if (timeChanged) {
        updateTimeDisplay();
    }

    unsigned long refreshInterval = 0;
#if DEBUG_MODE
    refreshInterval = (unsigned long)DEBUG_REFRESH_MIN * 60000UL;
#else
    refreshInterval = (unsigned long)cfgSleepMin * 60000UL;
#endif
    if (millis() - setupDoneMillis >= refreshInterval) {
#if DEBUG_MODE
        Serial.printf("[DEBUG] %d min elapsed, refreshing content...\n", DEBUG_REFRESH_MIN);
#else
        Serial.printf("%d min elapsed, refreshing content...\n", cfgSleepMin);
#endif
        triggerImmediateRefresh();
        setupDoneMillis = millis();
    }

    delay(50);
}

// ── Deep sleep helper ───────────────────────────────────────

static void enterDeepSleep(int minutes) {
    epdSleep();
    Serial.printf("Deep sleep for %d min (~%duA)\n", minutes, 5);
    Serial.flush();
    esp_sleep_enable_timer_wakeup((uint64_t)minutes * 60ULL * 1000000ULL);
    esp_deep_sleep_start();
}

// ── Failure handler with retry logic ────────────────────────

static void handleFailure(const char *reason) {
    showError(reason);
    epdSleep();

    int retryCount = getRetryCount();
    if (retryCount < MAX_RETRY_COUNT) {
        setRetryCount(retryCount + 1);
        Serial.printf("%s, retry %d/%d in %ds...\n",
                      reason, retryCount + 1, MAX_RETRY_COUNT, RETRY_DELAY_SEC);
        delay(RETRY_DELAY_SEC * 1000);
        ESP.restart();
    } else {
        Serial.println("Max retries reached, entering deep sleep");
        resetRetryCount();
        esp_sleep_enable_timer_wakeup((uint64_t)cfgSleepMin * 60ULL * 1000000ULL);
        esp_deep_sleep_start();
    }
}

// ── Immediate refresh (reused by button press and timer) ────

static void triggerImmediateRefresh(bool nextMode) {
    Serial.println("[REFRESH] Triggering immediate refresh...");
    ledFeedback("ack");
    if (nextMode) {
        showModePreview("NEXT");
    }
    ledFeedback("connecting");
    if (connectWiFi()) {
        ledFeedback("downloading");
        if (fetchBMP(nextMode)) {
            Serial.println("Displaying new content...");
            smartDisplay(imgBuf);
            ledFeedback("success");
            Serial.println("Display done");
            syncNTP();
            updateTimeDisplay();
            lastClockTickMillis = millis();
        } else {
            ledFeedback("fail");
            Serial.println("Fetch failed, keeping old content");
        }
        WiFi.disconnect(true);
        WiFi.mode(WIFI_OFF);
    } else {
        ledFeedback("fail");
        Serial.println("WiFi reconnect failed");
    }
}

// ── Favorite handler (triple-click) ─────────────────────────

static void triggerFavorite() {
    Serial.println("[FAVORITE] Posting favorite...");
    ledFeedback("ack");
    if (connectWiFi()) {
        if (postFavorite()) {
            ledFeedback("favorite");
            Serial.println("Favorite posted successfully");
        } else {
            ledFeedback("fail");
            Serial.println("Favorite post failed");
        }
        WiFi.disconnect(true);
        WiFi.mode(WIFI_OFF);
    } else {
        ledFeedback("fail");
        Serial.println("WiFi reconnect failed for favorite");
    }
}

// ── Config button handler ───────────────────────────────────
// Single click:       trigger immediate refresh
// Double-click:       switch to next mode (adds &next=1 to URL)
// Triple-click:       favorite/bookmark current content
// Long press (>=2s):  restart into config portal

static void checkConfigButton() {
    bool isPressed = (digitalRead(PIN_CFG_BTN) == LOW);

    if (isPressed) {
        if (cfgBtnPressStart == 0) {
            cfgBtnPressStart = millis();
        } else {
            unsigned long holdTime = millis() - cfgBtnPressStart;
            if (holdTime >= (unsigned long)CFG_BTN_HOLD_MS) {
                Serial.printf("Config button held for %dms, restarting...\n", CFG_BTN_HOLD_MS);
                ledFeedback("ack");
                showError("Restarting");
                delay(1000);
                ESP.restart();
            }
        }
    } else {
        if (cfgBtnPressStart != 0) {
            unsigned long pressDuration = millis() - cfgBtnPressStart;
            cfgBtnPressStart = 0;

            if (pressDuration >= (unsigned long)SHORT_PRESS_MIN_MS &&
                pressDuration < (unsigned long)CFG_BTN_HOLD_MS) {
                unsigned long now = millis();
                if (now - lastShortPressTime < (unsigned long)TRIPLE_CLICK_MS) {
                    clickCount++;
                    if (clickCount >= 3) {
                        Serial.println("[BTN] Triple-click -> favorite");
                        pendingFavorite = true;
                        clickCount = 0;
                        lastShortPressTime = 0;
                    } else if (clickCount == 2) {
                        Serial.println("[BTN] Double-click -> next mode");
                        pendingNextMode = true;
                        // Don't reset yet — wait to see if triple-click
                        lastShortPressTime = now;
                    }
                } else {
                    clickCount = 1;
                    lastShortPressTime = now;
                    Serial.printf("[BTN] Click #1 (%lums), waiting...\n", pressDuration);
                }
            }
        } else {
            if (lastShortPressTime != 0 &&
                (millis() - lastShortPressTime >= (unsigned long)TRIPLE_CLICK_MS)) {
                if (clickCount == 1) {
                    Serial.println("[BTN] Single click -> immediate refresh");
                    pendingRefresh = true;
                } else if (clickCount == 2 && !pendingFavorite) {
                    // Double-click confirmed (no third click came)
                    // pendingNextMode already set above
                }
                clickCount = 0;
                lastShortPressTime = 0;
            }
        }
    }
}
