// Smart e-ink desktop companion powered by LLM
// https://github.com/datascale-ai/inksight

#include <Arduino.h>
#include <freertos/FreeRTOS.h>
#include <freertos/queue.h>
#include <freertos/task.h>
#include <driver/gpio.h>
#include <esp_sleep.h>
#include <soc/soc_caps.h>
#if SOC_RTCIO_INPUT_OUTPUT_SUPPORTED
#include <driver/rtc_io.h>
#endif
#include <new>
#include <WiFi.h>

#include "config.h"
#if PIN_RGB_LED >= 0
#include <esp32-hal-rgb-led.h>
#endif
#if defined(BOARD_HAS_AUDIO)
#include "audio.h"
#include "audio_codec.h"
#include "audio_service.h"
#endif
#include "network.h"
#include "storage.h"
#include "portal.h"

#if !VOICE_ONLY_BUILD
#include "epd_driver.h"
#include "display.h"
#include "offline_cache.h"
#endif

// ── Shared framebuffers (referenced by other modules via extern) ──
uint8_t imgBuf[IMG_BUF_LEN];
#if EPD_BPP >= 2
uint8_t *colorBuf = nullptr;
bool useColorBuf = false;

bool ensureColorBuf() {
    if (colorBuf) return true;
    colorBuf = (uint8_t *)malloc(COLOR_BUF_LEN);
    if (!colorBuf) {
        Serial.println("[MEM] colorBuf alloc failed");
        return false;
    }
    Serial.printf("[MEM] colorBuf allocated %d bytes on heap\n", COLOR_BUF_LEN);
    return true;
}
#endif

// ── Voice constants ─────────────────────────────────────────
static const char *AI_CHAT_MODE_ID = "AI_CHAT";
static const char *VOCAB_REVIEW_MODE_ID = "VOCAB_REVIEW";
static const int VOICE_SILENCE_COMMIT_MS = 600;
static const float VOICE_STREAM_VAD_THRESHOLD = 150.0f;
static const unsigned long VOICE_MAX_CAPTURE_MS = 8000;
static const unsigned long VOICE_PLAYBACK_TAIL_CLEAR_MS = 300;
static const int VOICE_DEEP_CLEAR_INTERVAL = 5;  // deep-clear every N turns to remove ghosting

struct VoiceTurnPerf {
    int turnIndex = 0;
    unsigned long speechStartAt = 0;
    unsigned long firstChunkSentAt = 0;
    unsigned long commitAt = 0;
    unsigned long firstAsrPartialAt = 0;
    unsigned long asrFinalAt = 0;
    unsigned long firstLlmDeltaAt = 0;
    unsigned long firstTtsChunkAt = 0;
    unsigned long firstPlaybackAt = 0;
    unsigned long turnDoneAt = 0;
    size_t sentAudioChunks = 0;
    size_t sentAudioBytes = 0;
    size_t recvAudioChunks = 0;
    size_t recvAudioBytes = 0;
};

// ── Device state machine (shared) ─────────────────────────────
// This file is compiled for both VOICE_ONLY_BUILD and the display firmware,
// so the enum must exist before any DeviceContext uses it.
enum class DeviceState : uint8_t {
    BOOT,
    PORTAL,
    CONNECTING,
    FETCHING,
    DISPLAYING,
    REFRESHING,
    SLEEPING,
    ERROR,
};

enum class WakeupReason : uint8_t {
    POWER_ON,
    TIMER,
    BUTTON,
    UNKNOWN,
};

enum class PortalEntryReason : uint8_t {
    MANUAL,
    AUTO_WIFI_FAILURE,
};

struct DeviceContext {
    DeviceState state = DeviceState::BOOT;
    WakeupReason wakeupReason = WakeupReason::POWER_ON;

    // Button state
    unsigned long btnPressStart = 0;
    unsigned long aiBtnPressStart = 0;
    bool ignoreConfigButtonUntilRelease = false;
    bool ignoreAiButtonUntilRelease = false;
    bool liveMode = false;
    unsigned long temporaryOnlineUntil = 0;
    unsigned long lastLivePollAt = 0;
    unsigned long lastLiveWiFiRetryAt = 0;

    // Timing
    unsigned long setupDoneAt = 0;
    unsigned long lastClockTick = 0;
    unsigned long portalStartedAt = 0;
    unsigned long portalTimeoutMs = 0;

    // Pending actions (set by button handler, consumed by loop)
    bool wantRefresh = false;
    bool wantEnterAiChatMode = false;
    bool wantEnterVocabReview = false;
    bool wantVocabFlip = false;
    bool wantVocabNextRating = false;
    bool wantVocabSubmitRating = false;
    bool wantVocabExit = false;
    bool vocabReviewBackSide = false;
    String currentRenderedModeId;
    String switchToModeId;
};

static DeviceContext ctx;
static bool focusListening = false;
static bool alwaysActive = false;

static WakeupReason detectWakeupReason() {
    esp_sleep_wakeup_cause_t cause = esp_sleep_get_wakeup_cause();
    switch (cause) {
        case ESP_SLEEP_WAKEUP_TIMER:
            Serial.println("[WAKE] Wakeup from timer");
            return WakeupReason::TIMER;
        case ESP_SLEEP_WAKEUP_EXT0:
        case ESP_SLEEP_WAKEUP_EXT1:
        case ESP_SLEEP_WAKEUP_GPIO:
            Serial.println("[WAKE] Wakeup from button/GPIO");
            return WakeupReason::BUTTON;
        case ESP_SLEEP_WAKEUP_UNDEFINED:
            Serial.println("[WAKE] Power on or reset");
            return WakeupReason::POWER_ON;
        default:
            Serial.printf("[WAKE] Unknown wakeup cause: %d\n", (int)cause);
            return WakeupReason::UNKNOWN;
    }
}

static int effectiveSleepMinutes() {
#if DEBUG_MODE
    return DEBUG_REFRESH_MIN;
#else
    return cfgSleepMin;
#endif
}

static bool temporaryOnlineActive(unsigned long now = millis()) {
    return ctx.temporaryOnlineUntil != 0 &&
           (long)(now - ctx.temporaryOnlineUntil) < 0;
}

static bool temporaryOnlineExpired(unsigned long now = millis()) {
    return ctx.temporaryOnlineUntil != 0 &&
           (long)(now - ctx.temporaryOnlineUntil) >= 0;
}

static void clearTemporaryOnlineWindow() {
    ctx.temporaryOnlineUntil = 0;
}

static void extendTemporaryOnlineWindow(const char *reason) {
    ctx.temporaryOnlineUntil = millis() + TEMP_ONLINE_WINDOW_MS;
    ctx.liveMode = true;
    ctx.lastLivePollAt = 0;
    ctx.lastLiveWiFiRetryAt = 0;
    Serial.printf("[LIVE] Temporary online window: %lu min",
                  TEMP_ONLINE_WINDOW_MS / 60000UL);
    if (reason && reason[0]) {
        Serial.printf(" (%s)", reason);
    }
    Serial.println();
}

static bool refreshActivityFlags() {
    bool focusFlag = false;
    bool alwaysActiveFlag = false;
    if (!fetchFocusListeningFlag(&focusFlag, &alwaysActiveFlag)) {
        return false;
    }
    bool changed = (focusListening != focusFlag) || (alwaysActive != alwaysActiveFlag);
    focusListening = focusFlag;
    alwaysActive = alwaysActiveFlag;
    if (changed) {
        Serial.printf("[CONFIG] activity flags updated focus=%s always_active=%s\n",
                      focusListening ? "true" : "false",
                      alwaysActive ? "true" : "false");
    }
    return true;
}

// Content dedup — skip display refresh when content unchanged
static uint32_t lastContentChecksum = 0;
static int lastRenderedPeriod = -1;

static uint32_t computeChecksum(const uint8_t *buf, int len) {
    uint32_t sum = 0;
    for (int i = 0; i < len; i++) sum += buf[i];
    return sum;
}

// ── Forward declarations ────────────────────────────────────
#if VOCAB_REVIEW_BUILD
static uint8_t *vocabRatingParts = nullptr;
static size_t vocabRatingPartLen = 0;
static int vocabRegionYStart = 0;
static int vocabRegionYEnd = 0;
static int vocabRatingCursor = 0;

static int vocabReviewRegionYStart() {
    return (H <= 128) ? (H * 54 / 100) : (H * 52 / 100);
}

static int vocabReviewRegionYEnd() {
    return H - max(18, H / 12);
}

static size_t vocabReviewRegionLen() {
    int y0 = vocabReviewRegionYStart();
    int y1 = vocabReviewRegionYEnd();
    if (y1 <= y0) return 0;
    return (size_t)ROW_BYTES * (size_t)(y1 - y0);
}

static bool ensureVocabRatingCache() {
    size_t partLen = vocabReviewRegionLen();
    if (partLen == 0) return false;
    if (vocabRatingParts && vocabRatingPartLen == partLen) return true;
    if (vocabRatingParts) {
        free(vocabRatingParts);
        vocabRatingParts = nullptr;
    }
    vocabRatingParts = (uint8_t *)malloc(partLen * 3);
    if (!vocabRatingParts) {
        vocabRatingPartLen = 0;
        Serial.println("[VOCAB] rating cache alloc failed");
        return false;
    }
    vocabRatingPartLen = partLen;
    vocabRegionYStart = vocabReviewRegionYStart();
    vocabRegionYEnd = vocabReviewRegionYEnd();
    return true;
}

static void copyVocabRegionToImage(const uint8_t *part) {
    if (!part) return;
    int regionH = vocabRegionYEnd - vocabRegionYStart;
    for (int row = 0; row < regionH; row++) {
        memcpy(
            imgBuf + (vocabRegionYStart + row) * ROW_BYTES,
            part + row * ROW_BYTES,
            ROW_BYTES
        );
    }
}

static bool displayVocabDiffRegion(const uint8_t *newPart, const uint8_t *oldPart) {
    if (!newPart || !oldPart) return false;
    int regionH = vocabRegionYEnd - vocabRegionYStart;
    int minByte = ROW_BYTES;
    int maxByte = -1;
    int minRow = regionH;
    int maxRow = -1;

    for (int row = 0; row < regionH; row++) {
        const uint8_t *newRow = newPart + row * ROW_BYTES;
        const uint8_t *oldRow = oldPart + row * ROW_BYTES;
        for (int byteX = 0; byteX < ROW_BYTES; byteX++) {
            if (newRow[byteX] == oldRow[byteX]) continue;
            if (byteX < minByte) minByte = byteX;
            if (byteX > maxByte) maxByte = byteX;
            if (row < minRow) minRow = row;
            if (row > maxRow) maxRow = row;
        }
    }

    if (maxByte < minByte || maxRow < minRow) return true;

    int xByte0 = max(0, minByte - 1);
    int xByte1 = min(ROW_BYTES, maxByte + 2);
    int y0 = max(0, minRow - 2);
    int y1 = min(regionH, maxRow + 3);
    int widthBytes = xByte1 - xByte0;
    int height = y1 - y0;
    int refreshX0 = xByte0 * 8;
    int refreshY0 = vocabRegionYStart + y0;
    int refreshX1 = xByte1 * 8;
    int refreshY1 = vocabRegionYStart + y1;
    int refreshW = refreshX1 - refreshX0;
    int refreshH = refreshY1 - refreshY0;
    int areaPctX100 = (refreshW * refreshH * 10000) / max(1, W * H);
    Serial.printf(
        "[VOCAB] rating partial rect x=%d y=%d w=%d h=%d area=%d.%02d%% mode=with-old\n",
        refreshX0,
        refreshY0,
        refreshW,
        refreshH,
        areaPctX100 / 100,
        areaPctX100 % 100
    );
    size_t patchLen = (size_t)widthBytes * (size_t)height;
    uint8_t *newPatch = (uint8_t *)malloc(patchLen);
    uint8_t *oldPatch = (uint8_t *)malloc(patchLen);
    if (!newPatch || !oldPatch) {
        if (newPatch) free(newPatch);
        if (oldPatch) free(oldPatch);
        epdPartialDisplayWithOld((uint8_t *)newPart, oldPart, 0, vocabRegionYStart, W, vocabRegionYEnd);
        return true;
    }

    for (int row = 0; row < height; row++) {
        memcpy(newPatch + row * widthBytes, newPart + (y0 + row) * ROW_BYTES + xByte0, widthBytes);
        memcpy(oldPatch + row * widthBytes, oldPart + (y0 + row) * ROW_BYTES + xByte0, widthBytes);
    }

    epdPartialDisplayWithOld(
        newPatch,
        oldPatch,
        refreshX0,
        refreshY0,
        refreshX1,
        refreshY1
    );
    free(newPatch);
    free(oldPatch);
    return true;
}

static bool displayCachedVocabRating(int cursor) {
    if (!vocabRatingParts || vocabRatingPartLen == 0 || !epdSupportsPartialRefresh()) {
        return false;
    }
    cursor = ((cursor % 3) + 3) % 3;
    uint8_t *oldPart = (uint8_t *)malloc(vocabRatingPartLen);
    if (!oldPart) return false;

    int regionH = vocabRegionYEnd - vocabRegionYStart;
    for (int row = 0; row < regionH; row++) {
        memcpy(
            oldPart + row * ROW_BYTES,
            imgBuf + (vocabRegionYStart + row) * ROW_BYTES,
            ROW_BYTES
        );
    }

    uint8_t *newPart = vocabRatingParts + vocabRatingPartLen * cursor;
    copyVocabRegionToImage(newPart);
    displayVocabDiffRegion(newPart, oldPart);
    free(oldPart);
    return true;
}

static bool fetchAndDisplayVocabPack() {
    if (!ensureVocabRatingCache()) return false;
    if (!fetchVocabReviewPack(vocabRatingParts, vocabRatingPartLen, vocabRegionYStart, vocabRegionYEnd)) {
        return false;
    }
    vocabRatingCursor = 0;
    ctx.vocabReviewBackSide = false;
    ctx.currentRenderedModeId = VOCAB_REVIEW_MODE_ID;
    cacheSave(imgBuf, IMG_BUF_LEN);
    smartDisplay(imgBuf);
    lastContentChecksum = computeChecksum(imgBuf, IMG_BUF_LEN);
    lastRenderedPeriod = currentPeriodIndex();
    ctx.lastClockTick = millis();
    return true;
}
#endif

static void checkConfigButton();
static void triggerImmediateRefresh(bool nextMode = false, bool keepWiFi = false, bool partialVocabRating = false, const uint8_t *partialOldImage = nullptr, bool skipNtp = false);
static void handleLiveMode();
static bool temporaryOnlineActive(unsigned long now);
static bool temporaryOnlineExpired(unsigned long now);
static void clearTemporaryOnlineWindow();
static void extendTemporaryOnlineWindow(const char *reason);
static bool waitForContentReady();
static void handleFailure(const char *reason);
static void enterDeepSleep(int minutes, bool force = false);
static void enterPortalMode(PortalEntryReason reason = PortalEntryReason::MANUAL);
static void checkPortalTimeout();

// ── LED feedback ────────────────────────────────────────────

static void ledInit() {
#if PIN_LED >= 0
    pinMode(PIN_LED, OUTPUT);
    digitalWrite(PIN_LED, LOW);
#endif
#if PIN_RGB_LED >= 0
    neopixelWrite(PIN_RGB_LED, 0, 0, 0);
#endif
}

static void ledFeedback(const char *pattern) {
#if PIN_LED < 0
    (void)pattern;
#if PIN_RGB_LED >= 0
    neopixelWrite(PIN_RGB_LED, 0, 0, 0);
#endif
    return;
#else
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
#endif
}

static void enterPortalMode(PortalEntryReason reason) {
    g_userAborted = false;
    String mac = WiFi.macAddress();
    String apName = "InkSight-" + mac.substring(mac.length() - 5);
    apName.replace(":", "");

    ctx.liveMode = false;
    clearTemporaryOnlineWindow();
    ctx.wantRefresh = false;
    ctx.btnPressStart = 0;

    WiFi.disconnect(true);
    WiFi.mode(WIFI_OFF);

    ledFeedback("portal");
    #if !VOICE_ONLY_BUILD
    showSetupScreen(apName.c_str());
    #endif
    startCaptivePortal();
    ctx.state = DeviceState::PORTAL;
    ctx.portalStartedAt = millis();
    ctx.portalTimeoutMs = (reason == PortalEntryReason::AUTO_WIFI_FAILURE)
        ? PORTAL_AUTO_TIMEOUT_MS
        : PORTAL_MANUAL_TIMEOUT_MS;
    Serial.printf("[PORTAL] %s portal timeout: %lus\n",
                  reason == PortalEntryReason::AUTO_WIFI_FAILURE ? "Auto" : "Manual",
                  ctx.portalTimeoutMs / 1000UL);
    ctx.ignoreConfigButtonUntilRelease = (digitalRead(PIN_CFG_BTN) == LOW);
}
// ── Shared voice helpers ────────────────────────────────────

static unsigned long voicePerfSince(unsigned long startedAt) {
    return startedAt > 0 ? millis() - startedAt : 0;
}

static void resetVoiceTurnPerf(VoiceTurnPerf &perf) {
    perf = VoiceTurnPerf();
}

static bool checkAiChatShortPress() {
    static unsigned long pressStart = 0;
    bool isPressed = (digitalRead(PIN_CFG_BTN) == LOW);
    if (isPressed) {
        if (pressStart == 0) pressStart = millis();
        return false;
    }
    if (pressStart == 0) return false;
    unsigned long duration = millis() - pressStart;
    pressStart = 0;
    return duration >= (unsigned long)SHORT_PRESS_MIN_MS && duration < (unsigned long)CFG_BTN_HOLD_MS;
}

#if defined(BOARD_HAS_AUDIO)
static void drainSendQueue(AudioService &as) {
    AsAudioPacket* pkt = nullptr;
    while (as.PollSendPacket(pkt)) {
        voiceWsSendRawPacket(pkt->data, pkt->dataLen);
        as.ReleaseSendPacket(pkt);
    }
}

struct VocabAudioPlaybackCtx {
    AudioCodec *codec = nullptr;
    size_t bytesWritten = 0;
    size_t bytesDropped = 0;
    uint8_t pendingByte = 0;
    bool hasPendingByte = false;
};

static void vocabAudioChunkCallback(const uint8_t *data, size_t len, void *userData) {
    VocabAudioPlaybackCtx *ctx = static_cast<VocabAudioPlaybackCtx *>(userData);
    if (!ctx || !ctx->codec || !data || len == 0) return;

    const uint8_t *pcm = data;
    size_t pcmLen = len;
    int16_t firstSample = 0;
    if (ctx->hasPendingByte && pcmLen > 0) {
        firstSample = (int16_t)((uint16_t)ctx->pendingByte | ((uint16_t)pcm[0] << 8));
        int written = ctx->codec->Write(&firstSample, 1);
        if (written == 1) ctx->bytesWritten += 2;
        else ctx->bytesDropped += 2;
        pcm++;
        pcmLen--;
        ctx->hasPendingByte = false;
    }

    if (pcmLen >= 2) {
        size_t evenLen = pcmLen & ~((size_t)1);
        int samples = (int)(evenLen / sizeof(int16_t));
        int written = ctx->codec->Write((const int16_t *)pcm, samples);
        if (written > 0) ctx->bytesWritten += (size_t)written * sizeof(int16_t);
        if (written < samples) ctx->bytesDropped += (size_t)(samples - written) * sizeof(int16_t);
        pcm += evenLen;
        pcmLen -= evenLen;
    }

    if (pcmLen == 1) {
        ctx->pendingByte = pcm[0];
        ctx->hasPendingByte = true;
    }
}

static void playCurrentVocabWordAudio() {
#if VOCAB_REVIEW_BUILD
    Serial.println("[VOCAB] Playing current word audio...");
    static Inmp441Max98357Codec codec(false);
    if (!codec.Start()) {
        Serial.println("[VOCAB] codec start failed");
        return;
    }

    codec.EnableOutput(true);
    if (!codec.outputEnabled()) {
        Serial.println("[VOCAB] codec output enable failed");
        codec.Stop();
        return;
    }

    VocabAudioPlaybackCtx playbackCtx;
    playbackCtx.codec = &codec;
    bool ok = fetchVocabAudio(vocabAudioChunkCallback, &playbackCtx);
    if (!ok) {
        Serial.println("[VOCAB] audio fetch failed");
    }
    if (playbackCtx.hasPendingByte) {
        playbackCtx.bytesDropped += 1;
    }
    if (playbackCtx.bytesDropped > 0) {
        Serial.printf("[VOCAB] audio dropped %u bytes\n", (unsigned int)playbackCtx.bytesDropped);
    }

    unsigned long tailMs = playbackCtx.bytesWritten > 0 ? 250 : 80;
    delay(tailMs);
    codec.Stop();
#endif
}
#endif

// ═════════════════════════════════════════════════════════════
#if VOICE_ONLY_BUILD
// ═════════════════════════════════════════════════════════════
//
// Voice-only firmware: ESP32 + INMP441 + MAX98357A, no display.
// Full-duplex audio on two I2S peripherals.
// State machine inspired by xiaozhi-esp32.
//
// ═════════════════════════════════════════════════════════════

enum class VoiceState : uint8_t {
    IDLE,
    CONNECTING,
    LISTENING,
    THINKING,
    SPEAKING,
};

static const char *voiceStateName(VoiceState s) {
    switch (s) {
        case VoiceState::IDLE:       return "IDLE";
        case VoiceState::CONNECTING: return "CONNECTING";
        case VoiceState::LISTENING:  return "LISTENING";
        case VoiceState::THINKING:   return "THINKING";
        case VoiceState::SPEAKING:   return "SPEAKING";
        default:                     return "?";
    }
}

static bool gPortalMode = false;

static void voiceSetLed(VoiceState state) {
    switch (state) {
        case VoiceState::IDLE:       digitalWrite(PIN_LED, LOW); break;
        case VoiceState::CONNECTING: digitalWrite(PIN_LED, HIGH); break;
        case VoiceState::LISTENING:  digitalWrite(PIN_LED, HIGH); break;
        case VoiceState::THINKING:   digitalWrite(PIN_LED, LOW); break;
        case VoiceState::SPEAKING:   digitalWrite(PIN_LED, LOW); break;
    }
}

static void runVoiceLoop(AudioService &audioService) {
    audioService.Start();
    Serial.println("[VOICE] AudioService started");

    while (true) {
        VoiceState state = VoiceState::CONNECTING;
        voiceSetLed(state);
        Serial.println("[VOICE] Connecting WebSocket...");

        if (WiFi.status() != WL_CONNECTED) {
            Serial.println("[VOICE] WiFi disconnected, reconnecting...");
            ledFeedback("connecting");
            if (!connectWiFi()) {
                Serial.println("[VOICE] WiFi failed, retry in 5s");
                ledFeedback("fail");
                delay(5000);
                continue;
            }
        }

        if (!voiceWsOpen(SAMPLE_RATE, W, H, false)) {
            Serial.println("[VOICE] WebSocket open failed, retry in 3s");
            ledFeedback("fail");
            delay(3000);
            continue;
        }

        bool sessionReady = false;
        unsigned long readyStartAt = millis();
        while (!sessionReady && millis() - readyStartAt < 6000UL) {
            voiceWsLoop();
            VoiceWsEvent ev;
            while (voiceWsPollEvent(ev)) {
                if (ev.type == VoiceWsEventType::SessionReady) sessionReady = true;
                voiceWsReleaseEvent(ev);
            }
            delay(10);
        }
        if (!sessionReady) {
            Serial.println("[VOICE] Session ready timeout, retry in 3s");
            voiceWsClose();
            ledFeedback("fail");
            delay(3000);
            continue;
        }

        state = VoiceState::LISTENING;
        voiceSetLed(state);
        Serial.println("[VOICE] Session ready, LISTENING");

        bool speechDetected = false;
        unsigned long lastVoiceAt = 0;
        int turnCounter = 0;
        int bargeInFrames = 0;
        VoiceTurnPerf turnPerf;
        unsigned long lastRmsLogAt = 0;
        float peakRms = 0;

        audioService.FlushCaptureQueue();

        while (voiceWsConnected()) {
            voiceWsLoop();
            drainSendQueue(audioService);

            AsCaptureChunk *cap = nullptr;
            while (audioService.PollCaptureChunk(cap)) {
                if (state == VoiceState::LISTENING && cap->sampleCount > 0) {
                    audioNoiseGateApply(cap->samples, cap->sampleCount, 80.0f);
                    float rms = audioCalculateRMS(cap->samples, cap->sampleCount);
                    if (!speechDetected && rms < VOICE_STREAM_VAD_THRESHOLD) {
                        audioAdaptiveNoiseFloor(rms);
                    }
                    float noiseFloor = audioAdaptiveNoiseFloor(-1.0f);
                    float effectiveThreshold = max(VOICE_STREAM_VAD_THRESHOLD, noiseFloor * 3.0f);

                    if (rms > peakRms) peakRms = rms;
                    if (millis() - lastRmsLogAt >= 2000) {
                        Serial.printf("[VOICE] MIC peak RMS=%.0f (threshold=%.0f, noise=%.0f)\n", peakRms, effectiveThreshold, noiseFloor);
                        peakRms = 0;
                        lastRmsLogAt = millis();
                    }

                    if (rms >= effectiveThreshold) {
                        if (!speechDetected) {
                            turnCounter++;
                            resetVoiceTurnPerf(turnPerf);
                            turnPerf.turnIndex = turnCounter;
                            turnPerf.speechStartAt = millis();
                            Serial.printf("[VOICE] Turn %d: speech start (RMS=%.0f)\n", turnCounter, rms);
                        }
                        speechDetected = true;
                        lastVoiceAt = millis();
                    }

                    if (speechDetected) {
                        audioService.PushForEncoding(cap->samples, cap->sampleCount);
                        turnPerf.sentAudioChunks++;
                        turnPerf.sentAudioBytes += cap->sampleCount * sizeof(int16_t);
                        if (turnPerf.firstChunkSentAt == 0) turnPerf.firstChunkSentAt = millis();

                        bool silenceTimeout = !voiceWsServerVad() && (millis() - lastVoiceAt >= (unsigned long)VOICE_SILENCE_COMMIT_MS);
                        bool maxDuration = (millis() - turnPerf.speechStartAt >= VOICE_MAX_CAPTURE_MS);

                        if (silenceTimeout || maxDuration) {
                            speechDetected = false;
                            turnPerf.commitAt = millis();
                            Serial.printf("[VOICE] Turn %d: commit (%s, capture=%lums, chunks=%u)\n",
                                          turnPerf.turnIndex,
                                          maxDuration ? "max_duration" : "silence",
                                          voicePerfSince(turnPerf.speechStartAt),
                                          (unsigned int)turnPerf.sentAudioChunks);
                            drainSendQueue(audioService);
                            voiceWsCommitTurn();
                            state = VoiceState::THINKING;
                            voiceSetLed(state);
                        }
                    }

                } else if (state == VoiceState::SPEAKING && cap->sampleCount > 0) {
                    bargeInFrames = 0;
                } else {
                    bargeInFrames = 0;
                }

                audioService.ReleaseCaptureChunk(cap);
            }

            if (checkAiChatShortPress()) {
                if (state == VoiceState::THINKING || state == VoiceState::SPEAKING) {
                    Serial.println("[VOICE] Button interrupt");
                    voiceWsInterrupt();
                    audioService.ResetPlayback();
                    audioService.FlushCaptureQueue();
                    audioService.SetGenerationId(audioService.GetGenerationId() + 1);
                    speechDetected = false;
                    lastVoiceAt = 0;
                    bargeInFrames = 0;
                    resetVoiceTurnPerf(turnPerf);
                    state = VoiceState::LISTENING;
                    voiceSetLed(state);
                }
            }

            VoiceWsEvent event;
            while (voiceWsPollEvent(event)) {
                if (event.type == VoiceWsEventType::AsrPartial) {
                    if (turnPerf.firstAsrPartialAt == 0) {
                        turnPerf.firstAsrPartialAt = millis();
                        Serial.printf("[VOICE] Turn %d: ASR partial (+%lums) \"%s\"\n",
                                      turnPerf.turnIndex, voicePerfSince(turnPerf.commitAt), event.text.c_str());
                    }
                } else if (event.type == VoiceWsEventType::AsrFinal) {
                    if (state == VoiceState::LISTENING && voiceWsServerVad() && speechDetected) {
                        speechDetected = false;
                        turnPerf.commitAt = millis();
                        state = VoiceState::THINKING;
                        voiceSetLed(state);
                        Serial.printf("[VOICE] Turn %d: server_auto_commit \"%s\"\n",
                                      turnPerf.turnIndex, event.transcript.c_str());
                    }
                    turnPerf.asrFinalAt = millis();
                    Serial.printf("[VOICE] Turn %d: ASR final (+%lums) \"%s\"\n",
                                  turnPerf.turnIndex, voicePerfSince(turnPerf.commitAt), event.transcript.c_str());
                } else if (event.type == VoiceWsEventType::LlmDelta) {
                    if (turnPerf.firstLlmDeltaAt == 0) {
                        turnPerf.firstLlmDeltaAt = millis();
                        Serial.printf("[VOICE] Turn %d: first LLM delta (+%lums)\n",
                                      turnPerf.turnIndex, voicePerfSince(turnPerf.commitAt));
                    }
                } else if (event.type == VoiceWsEventType::TtsAudioChunk) {
                    turnPerf.recvAudioChunks++;
                    turnPerf.recvAudioBytes += event.dataLen;
                    if (turnPerf.firstTtsChunkAt == 0) {
                        turnPerf.firstTtsChunkAt = millis();
                        Serial.printf("[VOICE] Turn %d: first TTS chunk (+%lums, %u bytes)\n",
                                      turnPerf.turnIndex, voicePerfSince(turnPerf.commitAt), (unsigned int)event.dataLen);
                    }

                    audioService.SetGenerationId(event.generationId);
                    if (event.needsDecode) {
                        audioService.PushForDecoding(event.data, event.dataLen, event.generationId);
                    } else {
                        audioService.PushPcmForPlayback(event.data, event.dataLen, event.generationId);
                    }

                    if (state != VoiceState::SPEAKING) {
                        turnPerf.firstPlaybackAt = millis();
                        state = VoiceState::SPEAKING;
                        voiceSetLed(state);
                        bargeInFrames = 0;
                    }

                } else if (event.type == VoiceWsEventType::TurnInterrupted) {
                    Serial.printf("[VOICE] Turn %d: interrupted by server\n", turnPerf.turnIndex);
                    audioService.ResetPlayback();
                    audioService.FlushCaptureQueue();

                } else if (event.type == VoiceWsEventType::TurnDone) {
                    turnPerf.turnDoneAt = millis();
                    bool exitConversation = event.exitConversation;
                    Serial.printf("[VOICE] Turn %d: done (total=%lums, commit_to_done=%lums, tts_chunks=%u, exit=%s)\n",
                                  turnPerf.turnIndex,
                                  voicePerfSince(turnPerf.speechStartAt),
                                  voicePerfSince(turnPerf.commitAt),
                                  (unsigned int)turnPerf.recvAudioChunks,
                                  exitConversation ? "true" : "false");

                    unsigned long drainStart = millis();
                    while (!audioService.IsPlaybackEmpty() && millis() - drainStart < 10000UL) {
                        voiceWsLoop();
                        delay(20);
                    }
                    delay(VOICE_PLAYBACK_TAIL_CLEAR_MS);
                    audioService.ResetPlayback();

                    if (exitConversation) {
                        Serial.println("[VOICE] Conversation ended by user request");
                        voiceWsClose();
                        ledFeedback("success");
                        audioService.Stop();
                        return;
                    }

                    speechDetected = false;
                    lastVoiceAt = 0;
                    bargeInFrames = 0;
                    resetVoiceTurnPerf(turnPerf);
                    state = VoiceState::LISTENING;
                    voiceSetLed(state);
                    audioService.FlushCaptureQueue();

                } else if (event.type == VoiceWsEventType::Error) {
                    Serial.printf("[VOICE] Server error: %s\n", event.text.c_str());
                    audioService.ResetPlayback();
                    speechDetected = false;
                    lastVoiceAt = 0;
                    bargeInFrames = 0;
                    resetVoiceTurnPerf(turnPerf);
                    state = VoiceState::LISTENING;
                    voiceSetLed(state);
                }
                voiceWsReleaseEvent(event);
            }

            delay(5);
        }

        Serial.println("[VOICE] Disconnected, will reconnect in 2s");
        audioService.ResetPlayback();
        voiceWsClose();
        ledFeedback("fail");
        speechDetected = false;
        lastVoiceAt = 0;
        bargeInFrames = 0;
        delay(2000);
    }
}

// ── setup (voice-only) ──────────────────────────────────────

void setup() {
    ledInit();
    Serial.begin(115200);
    delay(3000);
#if defined(BOARD_PROFILE_ESP32_C3_WROOM02) || defined(BOARD_PROFILE_SMT_WROOM32E) || defined(BOARD_PROFILE_YD_ESP32_S3_N16R8)
    analogReadResolution(12);
    analogSetAttenuation(ADC_11db);
#endif
    Serial.println("\n=== InkSight Voice ===");

    loadConfig();

    bool forcePortal = false;
    if (digitalRead(PIN_CFG_BTN) == LOW) {
        delay(400);
        forcePortal = (digitalRead(PIN_CFG_BTN) == LOW);
    }
    bool hasConfig = (cfgSSID.length() > 0);

    if (forcePortal || !hasConfig || cfgServer.length() == 0) {
        Serial.println(forcePortal ? "[PORTAL] Button held -> portal" : "[PORTAL] No config -> portal");
        String mac = WiFi.macAddress();
        String apName = "InkSight-" + mac.substring(mac.length() - 5);
        apName.replace(":", "");
        Serial.printf("[PORTAL] AP: %s\n", apName.c_str());
        ledFeedback("portal");
        startCaptivePortal();
        gPortalMode = true;
        return;
    }

    ledFeedback("connecting");
    if (!connectWiFi()) {
        // Quick in-place retry sweeps, then fall back to the captive portal.
        for (int i = 0; i < WIFI_PORTAL_RETRY_SWEEPS; i++) {
            Serial.printf("[VOICE] WiFi unreachable, quick retry sweep %d/%d in %lus\n",
                          i + 1, WIFI_PORTAL_RETRY_SWEEPS, WIFI_PORTAL_RETRY_DELAY_MS / 1000);
            ledFeedback("fail");
            delay(WIFI_PORTAL_RETRY_DELAY_MS);
            if (connectWiFi()) break;
        }
        if (WiFi.status() != WL_CONNECTED) {
            Serial.println("[VOICE] WiFi still unreachable -> captive portal");
            resetRetryCount();
            ledFeedback("portal");
            startCaptivePortal();
            gPortalMode = true;
            return;
        }
    }
    resetRetryCount();
    Serial.println("[VOICE] WiFi connected");

    static Inmp441Max98357Codec codec(true);
    if (!codec.Start()) {
        Serial.println("[VOICE] Codec start failed, restarting in 5s");
        ledFeedback("fail");
        delay(5000);
        ESP.restart();
    }

    static AudioService audioService;
    if (!audioService.Initialize(&codec)) {
        Serial.println("[VOICE] AudioService init failed, restarting in 5s");
        ledFeedback("fail");
        delay(5000);
        ESP.restart();
    }

    ledFeedback("success");
    runVoiceLoop(audioService);
}

// ── loop (voice-only) ───────────────────────────────────────

void loop() {
    if (gPortalMode) {
        handlePortalClients();
        if (digitalRead(PIN_CFG_BTN) == LOW) {
            delay(400);
            if (digitalRead(PIN_CFG_BTN) == LOW) {
                unsigned long held = millis();
                while (digitalRead(PIN_CFG_BTN) == LOW && millis() - held < (unsigned long)CFG_BTN_HOLD_MS) {
                    delay(10);
                }
                if (millis() - held >= (unsigned long)CFG_BTN_HOLD_MS) {
                    Serial.println("[PORTAL] Long press -> restart");
                    ledFeedback("ack");
                    delay(500);
                    ESP.restart();
                }
            }
        }
        delay(5);
        return;
    }
    delay(100);
}

// ═════════════════════════════════════════════════════════════
#else  // !VOICE_ONLY_BUILD — original display firmware
// ═════════════════════════════════════════════════════════════

static const char *VOICE_INPUT_FILE = "/voice_input.pcm";
static const char *VOICE_REPLY_FILE = "/voice_reply.pcm";
static const int VOICE_RECORD_SECONDS = 10;
static const int AUTO_BOOT_VOICE_RECORD_SECONDS = 3;

// ── Forward declarations ────────────────────────────────────
static void checkConfigButton();
static void checkAiChatButton();
static void triggerImmediateRefresh(bool nextMode, bool keepWiFi, bool partialVocabRating, const uint8_t *partialOldImage, bool skipNtp);
static void handleLiveMode();
static bool waitForContentReady();
static void handleFailure(const char *reason);
static void handleWiFiFailure();
static void enterDeepSleep(int minutes, bool force);
static bool runAiChatConversation();
static bool decodeVoiceBmpToFrameBuffer(const uint8_t *bmpBytes, size_t bmpLen);

// ═════════════════════════════════════════════════════════════
// setup() — display build
// ═════════════════════════════════════════════════════════════

void setup() {
    ledInit();
    Serial.begin(115200);
    delay(3000);
#if defined(BOARD_PROFILE_ESP32_C3_WROOM02) || defined(BOARD_PROFILE_SMT_WROOM32E) || defined(BOARD_PROFILE_YD_ESP32_S3_N16R8)
    analogReadResolution(12);
    analogSetAttenuation(ADC_11db);
#endif
    Serial.println("\n=== InkSight ===");

    gpioInit();
    ctx.wakeupReason = detectWakeupReason();

    epdInit();
    cacheInit();
    Serial.println("EPD ready");
#if PIN_AI_CHAT_SW >= 0
    pinMode(PIN_AI_CHAT_SW, INPUT_PULLUP);
#endif

    loadConfig();

    bool forcePortal = false;
    if (digitalRead(PIN_CFG_BTN) == LOW) {
        delay(400);
        forcePortal = (digitalRead(PIN_CFG_BTN) == LOW);
    }

    bool hasConfig = (cfgSSID.length() > 0);

    if (forcePortal || !hasConfig) {
        Serial.println(forcePortal ? "Config button held -> portal"
                                   : "No WiFi config -> portal");
        delay(5000);
        enterPortalMode();
        return;
    }

    if (cfgServer.length() == 0) {
        Serial.println("No server URL configured -> portal");
        enterPortalMode();
        return;
    }

    int retryCount = getRetryCount();
    Serial.printf("Retry count: %d/%d\n", retryCount, MAX_RETRY_COUNT);

    ledFeedback("connecting");
    if (!connectWiFi()) {
        if (g_userAborted) {
            Serial.println("User aborted during WiFi connect -> portal");
            enterPortalMode();
            return;
        }
        ledFeedback("fail");
        handleWiFiFailure();
        return;
    }

    if (!refreshActivityFlags()) {
        focusListening = false;
        alwaysActive = false;
    }
    if (g_userAborted) {
        Serial.println("User aborted during focus fetch -> portal");
        enterPortalMode();
        return;
    }

#if AUTO_BOOT_AI_CHAT && defined(BOARD_HAS_AUDIO)
    Serial.println("[AI CHAT] Auto boot enabled, entering conversation mode");
    ledFeedback("ack");
    g_userAborted = false;
    bool autoExited = runAiChatConversation();
    Serial.printf("[AI CHAT] Auto boot conversation finished, exited=%s\n", autoExited ? "true" : "false");
    if (g_userAborted) {
        Serial.println("User aborted AI chat -> portal");
        enterPortalMode();
        return;
    }
#endif

    Serial.println("Fetching image...");
    ledFeedback("downloading");
    bool gotFallback = false;
    String renderedModeId;
    bool ok = fetchBMP(false, &gotFallback, &renderedModeId);
    if (g_userAborted) {
        Serial.println("User aborted during fetch -> portal");
        enterPortalMode();
        return;
    }
    if (!ok || gotFallback) {
        if (!waitForContentReady()) {
            ledFeedback("fail");
            handleFailure("Server error");
            return;
        }
    }

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

    bool aiChatRequested = renderedModeId.equalsIgnoreCase(AI_CHAT_MODE_ID);
    if (renderedModeId.length() > 0) {
        ctx.currentRenderedModeId = renderedModeId;
        if (!ctx.currentRenderedModeId.equalsIgnoreCase(VOCAB_REVIEW_MODE_ID)) {
            ctx.vocabReviewBackSide = false;
        }
    }
    if (aiChatRequested) {
        g_userAborted = false;
        bool exited = runAiChatConversation();
        if (g_userAborted) {
            Serial.println("User aborted AI chat -> portal");
            enterPortalMode();
            return;
        }
        if (exited) {
            ledFeedback("downloading");
            if (fetchBMP(true, nullptr, nullptr)) {
                cacheSave(imgBuf, IMG_BUF_LEN);
                lastContentChecksum = computeChecksum(imgBuf, IMG_BUF_LEN);
                syncNTP();
                smartDisplay(imgBuf);
                ledFeedback("success");
                lastRenderedPeriod = currentPeriodIndex();
                ctx.lastClockTick = millis();
            }
        }
    }

    bool firstInstallLivePending = isFirstInstallLiveModePending();
    bool buttonTemporaryOnline = (ctx.wakeupReason == WakeupReason::BUTTON);
    if (alwaysActive) {
        ctx.liveMode = true;
        clearTemporaryOnlineWindow();
        ctx.lastLivePollAt = 0;
        ctx.lastLiveWiFiRetryAt = 0;
        if (firstInstallLivePending) {
            markFirstInstallLiveModeDone();
        }
        postRuntimeMode("active");
        Serial.println("[LIVE] Always active config enabled");
    } else if (firstInstallLivePending) {
        markFirstInstallLiveModeDone();
        extendTemporaryOnlineWindow("first install");
        postRuntimeMode("active");
    } else if (buttonTemporaryOnline) {
        extendTemporaryOnlineWindow("button wakeup");
        postRuntimeMode("active");
    } else {
        clearTemporaryOnlineWindow();
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
    if (!ctx.liveMode) {
#if DEBUG_MODE
        Serial.printf("[DEBUG] Boot complete, entering deep sleep for %d min\n", DEBUG_REFRESH_MIN);
#else
        Serial.printf("Boot complete, entering deep sleep for %d min\n", cfgSleepMin);
#endif
        enterDeepSleep(effectiveSleepMinutes());
    }
#if DEBUG_MODE
    Serial.printf("[DEBUG] Staying awake, refresh every %d min (user config: %d min)\n",
                  DEBUG_REFRESH_MIN, cfgSleepMin);
#else
    if (temporaryOnlineActive()) {
        Serial.printf("Staying awake for temporary online window (%lu min)\n",
                      TEMP_ONLINE_WINDOW_MS / 60000UL);
    } else {
        Serial.printf("Staying awake, refresh every %d min\n", cfgSleepMin);
    }
#endif
}

// ═════════════════════════════════════════════════════════════
// loop() — display build
// ═════════════════════════════════════════════════════════════

void loop() {
    if (ctx.state == DeviceState::PORTAL) {
        handlePortalClients();
        checkPortalTimeout();
        checkConfigButton();
        checkAiChatButton();
        delay(5);
        return;
    }

    checkConfigButton();
    checkAiChatButton();

#if VOCAB_REVIEW_BUILD
    if (ctx.wantEnterVocabReview || ctx.wantVocabFlip || ctx.wantVocabNextRating || ctx.wantVocabSubmitRating || ctx.wantVocabExit) {
        bool doEnter = ctx.wantEnterVocabReview;
        bool doFlip = ctx.wantVocabFlip;
        bool doNextRating = ctx.wantVocabNextRating;
        bool doSubmit = ctx.wantVocabSubmitRating;
        bool doExit = ctx.wantVocabExit;
        ctx.wantEnterVocabReview = false;
        ctx.wantVocabFlip = false;
        ctx.wantVocabNextRating = false;
        ctx.wantVocabSubmitRating = false;
        ctx.wantVocabExit = false;
        ledFeedback("ack");

        if (doExit) {
            Serial.println("[VOCAB] Exit vocab review, showing next mode");
            ctx.vocabReviewBackSide = false;
            ctx.currentRenderedModeId = "";
            lastContentChecksum = 0;
            bool previousSuppressAbortCheck = g_suppressAbortCheck;
            g_suppressAbortCheck = true;
            triggerImmediateRefresh(true, true);
            g_suppressAbortCheck = previousSuppressAbortCheck;
            ctx.btnPressStart = 0;
            ctx.aiBtnPressStart = 0;
            ctx.ignoreConfigButtonUntilRelease = (digitalRead(PIN_CFG_BTN) == LOW);
#if PIN_AI_CHAT_SW >= 0
            ctx.ignoreAiButtonUntilRelease = (digitalRead(PIN_AI_CHAT_SW) == LOW);
#endif
            ctx.setupDoneAt = millis();
        } else if (doFlip) {
            vocabRatingCursor = 0;
            if (displayCachedVocabRating(vocabRatingCursor)) {
                ctx.vocabReviewBackSide = true;
                Serial.println("[VOCAB] Flip from cached review-pack");
            } else {
                Serial.println("[VOCAB] Cached flip unavailable, falling back to render");
                if (WiFi.status() == WL_CONNECTED || connectWiFi()) {
                    if (postVocabEvent("flip")) {
                        ctx.vocabReviewBackSide = true;
                        lastContentChecksum = 0;
                        triggerImmediateRefresh(false, true, epdSupportsPartialRefresh(), nullptr, true);
                    } else {
                        ledFeedback("fail");
                    }
                } else {
                    ledFeedback("fail");
                }
            }
            ctx.setupDoneAt = millis();
        } else if (doNextRating) {
            vocabRatingCursor = (vocabRatingCursor + 1) % 3;
            if (displayCachedVocabRating(vocabRatingCursor)) {
                ctx.vocabReviewBackSide = true;
                Serial.printf("[VOCAB] Local rating cursor -> %d\n", vocabRatingCursor);
            } else {
                Serial.println("[VOCAB] Cached rating unavailable, falling back to render");
                if (WiFi.status() == WL_CONNECTED || connectWiFi()) {
                    if (postVocabEvent("next_rating")) {
                        lastContentChecksum = 0;
                        triggerImmediateRefresh(false, true, epdSupportsPartialRefresh(), nullptr, true);
                    } else {
                        ledFeedback("fail");
                    }
                } else {
                    ledFeedback("fail");
                }
            }
            ctx.setupDoneAt = millis();
        } else {
            const char *action = doEnter ? "enter" : "submit_rating";
            const char *ratings[] = {"forgot", "fuzzy", "remember"};
            const char *rating = doSubmit ? ratings[vocabRatingCursor % 3] : nullptr;
            if (WiFi.status() != WL_CONNECTED && !connectWiFi()) {
                Serial.println("[VOCAB] WiFi reconnect failed, skip");
            } else if (postVocabEvent(action, rating)) {
                bool previousSuppressAbortCheck = g_suppressAbortCheck;
                g_suppressAbortCheck = true;
                if (!fetchAndDisplayVocabPack()) {
                    Serial.println("[VOCAB] review-pack unavailable, falling back to render");
                    lastContentChecksum = 0;
                    triggerImmediateRefresh(false, true);
                }
                g_suppressAbortCheck = previousSuppressAbortCheck;
#if defined(BOARD_HAS_AUDIO)
                playCurrentVocabWordAudio();
#endif
                ctx.btnPressStart = 0;
                ctx.ignoreConfigButtonUntilRelease = (digitalRead(PIN_CFG_BTN) == LOW);
                Serial.println("[VOCAB] Keeping WiFi connected for review actions");
                ctx.setupDoneAt = millis();
            } else {
                ledFeedback("fail");
            }
        }
    } else
#endif
    if (ctx.wantEnterAiChatMode) {
        ctx.wantEnterAiChatMode = false;
        ctx.switchToModeId = "";
        Serial.println("[AI CHAT] Dedicated switch long press -> enter conversation mode");
        ledFeedback("ack");
        if (WiFi.status() != WL_CONNECTED && !connectWiFi()) {
            Serial.println("[AI CHAT] WiFi reconnect failed, skip this request");
        } else {
            g_userAborted = false;
            bool exited = runAiChatConversation();
            ctx.btnPressStart = 0;
            ctx.ignoreConfigButtonUntilRelease = (digitalRead(PIN_CFG_BTN) == LOW);
            Serial.printf("[AI CHAT] Manual conversation finished, exited=%s\n", exited ? "true" : "false");
            if (g_userAborted) {
                Serial.println("User aborted AI chat -> portal");
                enterPortalMode();
                return;
            }
            if (exited) {
                if (ctx.switchToModeId.length() > 0) {
                    Serial.printf("[AI CHAT] Mode switch to %s, refreshing immediately\n",
                                  ctx.switchToModeId.c_str());
                }
                // WiFi is often unstable after a long WS session; force a clean reconnect.
                // Suppress GPIO0 abort check — it may be floating LOW on this board.
                g_suppressAbortCheck = true;
                WiFi.disconnect(true);
                WiFi.mode(WIFI_OFF);
                delay(1000);
                bool reconnected = false;
                for (int i = 0; i < 3 && !reconnected; i++) {
                    Serial.printf("[AI CHAT] WiFi reconnect attempt %d/3\n", i + 1);
                    reconnected = connectWiFi();
                    if (!reconnected) {
                        WiFi.disconnect(true);
                        WiFi.mode(WIFI_OFF);
                        delay(1000);
                    }
                }
                if (reconnected) {
                    lastContentChecksum = 0;  // force display refresh after AI chat UI
                    triggerImmediateRefresh(false, true);
                    if (!focusListening && !alwaysActive) {
                        ctx.liveMode = false;
                        postRuntimeMode("interval");
                        Serial.println("[AI CHAT] Refresh complete, entering interval deep sleep");
                        enterDeepSleep(effectiveSleepMinutes());
                    }
                } else {
                    Serial.println("[AI CHAT] WiFi reconnect failed after conversation, will retry next cycle");
                }
                g_suppressAbortCheck = false;
                WiFi.disconnect(true);
                WiFi.mode(WIFI_OFF);
                ctx.setupDoneAt = millis();
            }
        }
    } else if (ctx.wantRefresh) {
        triggerImmediateRefresh();
        ctx.wantRefresh = false;
        ctx.setupDoneAt = millis();
        if (!focusListening && !alwaysActive) {
            if (ctx.liveMode) {
                ctx.liveMode = false;
                postRuntimeMode("interval");
                Serial.println("[LIVE] Manual refresh complete, entering interval deep sleep");
            }
            enterDeepSleep(effectiveSleepMinutes());
        }
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
            enterDeepSleep(effectiveSleepMinutes());
        }
    }

    if (WiFi.status() == WL_CONNECTED) {
        postHeartbeat();
    }

    static unsigned long lastAlertPollAt = 0;
    static bool alertVisible = false;
    static unsigned long alertShownAt = 0;
#if INKSIGHT_IMG_BUF_BYTES_MACRO > 20000
    // Second full-frame static buffer overflows classic ESP32 DRAM for 5.83"/7.5" panels.
    static uint8_t *alertBackupBuf = nullptr;
    if (!alertBackupBuf) {
        alertBackupBuf = (uint8_t *)malloc(IMG_BUF_LEN);
        if (!alertBackupBuf) {
            Serial.println("[MEM] alertBackupBuf malloc failed; focus alerts disabled");
        }
    }
#else
    static uint8_t alertBackupBufStatic[IMG_BUF_LEN];
    uint8_t *const alertBackupBuf = alertBackupBufStatic;
#endif
    static bool hasAlertBackup = false;

    if (focusListening && alertBackupBuf) {
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

// ── Deep sleep ──────────────────────────────────────────────

static void enterDeepSleep(int minutes, bool force) {
    if (!force && (focusListening || alwaysActive)) {
        Serial.println(focusListening
                       ? "[FOCUS] Focus listening enabled, skipping deep sleep"
                       : "[LIVE] Always active enabled, skipping deep sleep");
        return;
    }
    ctx.state = DeviceState::SLEEPING;
    WiFi.disconnect(true);
    WiFi.mode(WIFI_OFF);
    epdSleep();
    ledFeedback("off");
    Serial.printf("Deep sleep for %d min (~%duA)\n", minutes, 5);
    Serial.flush();
    esp_sleep_enable_timer_wakeup((uint64_t)minutes * 60ULL * 1000000ULL);
#if PIN_CFG_BTN >= 0
    pinMode(PIN_CFG_BTN, INPUT_PULLUP);
    unsigned long releaseStartedAt = millis();
    while (digitalRead(PIN_CFG_BTN) == LOW && millis() - releaseStartedAt < 3000UL) {
        delay(10);
    }
    delay(50);
    bool wakeButtonReady = (digitalRead(PIN_CFG_BTN) == HIGH);
    if (!wakeButtonReady) {
        Serial.printf("[WAKE] GPIO%d is still LOW; timer-only wake for this sleep cycle\n", PIN_CFG_BTN);
    } else {
        const uint64_t wakeMask = 1ULL << PIN_CFG_BTN;
#if SOC_RTCIO_INPUT_OUTPUT_SUPPORTED
        rtc_gpio_pullup_en((gpio_num_t)PIN_CFG_BTN);
        rtc_gpio_pulldown_dis((gpio_num_t)PIN_CFG_BTN);
        esp_sleep_pd_config(ESP_PD_DOMAIN_RTC_PERIPH, ESP_PD_OPTION_ON);
#else
        gpio_pullup_en((gpio_num_t)PIN_CFG_BTN);
        gpio_pulldown_dis((gpio_num_t)PIN_CFG_BTN);
#endif
#if SOC_GPIO_SUPPORT_DEEPSLEEP_WAKEUP
        esp_deep_sleep_enable_gpio_wakeup(wakeMask, ESP_GPIO_WAKEUP_GPIO_LOW);
#elif CONFIG_IDF_TARGET_ESP32
        esp_sleep_enable_ext1_wakeup(wakeMask, ESP_EXT1_WAKEUP_ALL_LOW);
#else
        esp_sleep_enable_ext1_wakeup(wakeMask, ESP_EXT1_WAKEUP_ANY_LOW);
#endif
        Serial.printf("[WAKE] Timer + GPIO%d button wake enabled\n", PIN_CFG_BTN);
    }
#endif
    esp_deep_sleep_start();
}

static void checkPortalTimeout() {
    if (ctx.state != DeviceState::PORTAL || ctx.portalStartedAt == 0 || ctx.portalTimeoutMs == 0) {
        return;
    }
    unsigned long now = millis();
    if (now - ctx.portalStartedAt < ctx.portalTimeoutMs) {
        return;
    }
    Serial.printf("[PORTAL] Timeout %lus, entering deep sleep\n", ctx.portalTimeoutMs / 1000UL);
    ctx.portalStartedAt = 0;
    ctx.portalTimeoutMs = 0;
    enterDeepSleep(effectiveSleepMinutes(), true);
}

// ── Failure handler ─────────────────────────────────────────

static void showFailureDiagnostic(const char *reason) {
    char l2[64], l3[64];
    snprintf(l2, sizeof(l2), "SSID: %.40s", cfgSSID.c_str());
    snprintf(l3, sizeof(l3), "URL: %.44s", cfgServer.c_str());
    showDiagnostic(reason, l2, l3, "Hold BOOT to reconfigure");
}

static void handleFailure(const char *reason) {
    Serial.printf("[DIAG] %s | SSID=%s | Server=%s\n",
                  reason, cfgSSID.c_str(), cfgServer.c_str());
    showFailureDiagnostic(reason);
    delay(5000);

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
        ctx.state = DeviceState::DISPLAYING;
        ctx.setupDoneAt = millis();
        resetRetryCount();
        enterDeepSleep(effectiveSleepMinutes());
        return;
    }

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
        enterDeepSleep(effectiveSleepMinutes());
    }
}

// ── WiFi failure handler ────────────────────────────────────
// All saved WiFi networks failed to associate (connectWiFi already swept the
// full list once). Do a few quick in-place retry sweeps to ride out a brief
// blip (e.g. router rebooting), then fall back to the captive portal so the
// user can fix or add credentials. Auto-opened AP is time-limited so a
// battery-powered device does not stay in high-power portal mode indefinitely.
static void handleWiFiFailure() {
    for (int i = 0; i < WIFI_PORTAL_RETRY_SWEEPS; i++) {
        Serial.printf("[DIAG] WiFi unreachable, quick retry sweep %d/%d in %lus\n",
                      i + 1, WIFI_PORTAL_RETRY_SWEEPS, WIFI_PORTAL_RETRY_DELAY_MS / 1000);
        delay(WIFI_PORTAL_RETRY_DELAY_MS);
        if (connectWiFi()) {
            Serial.println("[DIAG] WiFi recovered -> reboot to resume normal flow");
            resetRetryCount();
            ESP.restart();
        }
        if (g_userAborted) break;
    }
    Serial.println("[DIAG] WiFi still unreachable -> captive portal");
    resetRetryCount();
    enterPortalMode(PortalEntryReason::AUTO_WIFI_FAILURE);
}

// ── Live mode ───────────────────────────────────────────────

static void handleLiveMode() {
    if (!ctx.liveMode) return;

    unsigned long now = millis();
    if (ctx.temporaryOnlineUntil != 0 && alwaysActive) {
        clearTemporaryOnlineWindow();
    }
    if (temporaryOnlineExpired(now) && !focusListening && !alwaysActive) {
        ctx.liveMode = false;
        clearTemporaryOnlineWindow();
        if (WiFi.status() == WL_CONNECTED) {
            postRuntimeMode("interval");
        }
        Serial.println("[LIVE] Temporary online window expired, entering deep sleep");
        enterDeepSleep(effectiveSleepMinutes());
        return;
    }
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
        bool wasAlwaysActive = alwaysActive;
        bool wasTemporaryOnline = (ctx.temporaryOnlineUntil != 0);
        refreshActivityFlags();
        triggerImmediateRefresh(false, true);
        ctx.setupDoneAt = millis();
        if (wasTemporaryOnline && !focusListening && !alwaysActive) {
            extendTemporaryOnlineWindow("remote action");
            return;
        }
        if (!focusListening && !alwaysActive) {
            ctx.liveMode = false;
            postRuntimeMode("interval");
            if (shouldExitLive) {
                Serial.println("[LIVE] Backend requested interval mode after refresh");
            } else if (wasAlwaysActive) {
                Serial.println("[LIVE] Always active disabled, entering interval deep sleep");
            } else {
                Serial.println("[LIVE] Temporary active refresh complete, entering interval deep sleep");
            }
            enterDeepSleep(effectiveSleepMinutes());
        }
        return;
    }
    if (shouldExitLive && ctx.temporaryOnlineUntil == 0) {
        ctx.liveMode = false;
        postRuntimeMode("interval");
        WiFi.disconnect(true);
        WiFi.mode(WIFI_OFF);
        Serial.println("[LIVE] Backend requested interval mode");
        enterDeepSleep(effectiveSleepMinutes());
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
        if (ctx.temporaryOnlineUntil != 0 && !focusListening && !alwaysActive) {
            Serial.println("[LIVE] Fallback refresh complete, temporary window remains active");
            return;
        }
        if (!focusListening && !alwaysActive) {
            ctx.liveMode = false;
            postRuntimeMode("interval");
            Serial.println("[LIVE] Fallback refresh complete, entering interval deep sleep");
            enterDeepSleep(effectiveSleepMinutes());
        }
    }
}

// ── BMP decode helper ───────────────────────────────────────

static bool decodeVoiceBmpToFrameBuffer(const uint8_t *bmpBytes, size_t bmpLen) {
    if (bmpBytes == nullptr || bmpLen < 14) return false;
    uint32_t pixelOffset = bmpBytes[10]
                         | ((uint32_t)bmpBytes[11] << 8)
                         | ((uint32_t)bmpBytes[12] << 16)
                         | ((uint32_t)bmpBytes[13] << 24);
    if (pixelOffset >= bmpLen) return false;
    const uint8_t *pixelData = bmpBytes + pixelOffset;
    size_t requiredBytes = (size_t)ROW_STRIDE * H;
    if ((size_t)(bmpLen - pixelOffset) < requiredBytes) return false;
    for (int bmpY = 0; bmpY < H; bmpY++) {
        int dispY = H - 1 - bmpY;
        memcpy(imgBuf + dispY * ROW_BYTES, pixelData + (size_t)bmpY * ROW_STRIDE, ROW_BYTES);
    }
    return true;
}

// ── AI Chat conversation (display build, full-duplex) ───────

static bool runAiChatConversation() {
#if !defined(BOARD_HAS_AUDIO)
    showAiChatStatus("AI CHAT", "unsupported on this board");
    return false;
#else
    // Keep large audio objects off the function stack. The voice-only build
    // already uses static lifetime here and is stable on WROOM32E.
    static Inmp441Max98357Codec codec(true);
    if (!codec.Start()) {
        showAiChatStatus("AUDIO FAIL", "");
        return false;
    }

    static AudioService audioService;
    Serial.println("[AI CHAT] Audio codec started, initializing AudioService");
    if (!audioService.Initialize(&codec)) {
        showAiChatStatus("QUEUE FAIL", "");
        codec.Stop();
        return false;
    }

    bool sessionReady = false;
    bool waitingForTurnDone = false;
    bool speechDetected = false;
    bool exitConversation = false;
    unsigned long lastVoiceAt = 0;
    unsigned long wsOpenStartedAt = millis();
    int turnCounter = 0;
    VoiceTurnPerf turnPerf;
    unsigned long lastRmsLogAt = 0;
    float peakRms = 0;
#if PIN_AI_CHAT_SW >= 0
    bool exitButtonIgnoreUntilRelease = (digitalRead(PIN_AI_CHAT_SW) == LOW);
    unsigned long exitButtonPressStart = 0;
#endif

    showVoiceChatScreen();

    if (!voiceWsOpen(SAMPLE_RATE, W, H, false)) {
        showAiChatStatus("WS FAIL", "");
        codec.Stop();
        return false;
    }
    Serial.printf("[VOICE_PERF][DEVICE] ws_open_ms=%lu\n", millis() - wsOpenStartedAt);

    unsigned long readyStartAt = millis();
    while (!sessionReady && millis() - readyStartAt < 15000UL) {
        voiceWsLoop();
        VoiceWsEvent readyEvent;
        while (voiceWsPollEvent(readyEvent)) {
            if (readyEvent.type == VoiceWsEventType::SessionReady) {
                sessionReady = true;
            } else if (readyEvent.type == VoiceWsEventType::Error) {
                showAiChatStatus("WS ERROR", readyEvent.text.c_str());
            }
            voiceWsReleaseEvent(readyEvent);
        }
        delay(10);
    }
    if (!sessionReady) {
        voiceWsClose();
        codec.Stop();
        Serial.println("[AI CHAT] session ready timeout");
        return false;
    }
    Serial.printf("[VOICE_PERF][DEVICE] session_ready_wait_ms=%lu total_ready_ms=%lu\n", millis() - readyStartAt, millis() - wsOpenStartedAt);

    Serial.println("[AI CHAT] Session ready, listening...");
    audioService.Start();
    audioService.FlushCaptureQueue();

    while (voiceWsConnected()) {
        voiceWsLoop();
        drainSendQueue(audioService);

#if PIN_AI_CHAT_SW >= 0
        bool exitButtonPressed = (digitalRead(PIN_AI_CHAT_SW) == LOW);
        if (exitButtonIgnoreUntilRelease) {
            if (!exitButtonPressed) {
                exitButtonIgnoreUntilRelease = false;
            }
            exitButtonPressStart = 0;
        } else if (exitButtonPressed) {
            if (exitButtonPressStart == 0) {
                exitButtonPressStart = millis();
            } else if (millis() - exitButtonPressStart >= (unsigned long)AI_CHAT_BTN_HOLD_MS) {
                Serial.printf("[AI CHAT] Switch held for %dms, exit conversation\n", AI_CHAT_BTN_HOLD_MS);
                audioService.ResetPlayback();
                voiceWsInterrupt();
                audioService.Stop();
                voiceWsClose();
                codec.Stop();
                ctx.aiBtnPressStart = 0;
                ctx.ignoreAiButtonUntilRelease = true;
                return true;
            }
        } else {
            exitButtonPressStart = 0;
        }
#endif

        AsCaptureChunk *captureChunk = nullptr;
        while (audioService.PollCaptureChunk(captureChunk)) {
            if (!waitingForTurnDone && captureChunk->sampleCount > 0) {
                audioNoiseGateApply(captureChunk->samples, captureChunk->sampleCount, 80.0f);
                float rms = audioCalculateRMS(captureChunk->samples, captureChunk->sampleCount);
                if (!speechDetected && rms < VOICE_STREAM_VAD_THRESHOLD) {
                    audioAdaptiveNoiseFloor(rms);
                }
                float noiseFloor = audioAdaptiveNoiseFloor(-1.0f);
                float effectiveThreshold = max(VOICE_STREAM_VAD_THRESHOLD, noiseFloor * 3.0f);

                if (rms > peakRms) peakRms = rms;
                if (millis() - lastRmsLogAt >= 2000) {
                    Serial.printf("[VOICE_PERF][DEVICE] MIC peak RMS=%.0f threshold=%.0f noise=%.0f\n",
                                  peakRms, effectiveThreshold, noiseFloor);
                    peakRms = 0;
                    lastRmsLogAt = millis();
                }

                if (rms >= effectiveThreshold) {
                    if (!speechDetected) {
                        turnCounter++;
                        resetVoiceTurnPerf(turnPerf);
                        turnPerf.turnIndex = turnCounter;
                        turnPerf.speechStartAt = millis();
                        Serial.printf("[VOICE_PERF][DEVICE] turn=%d speech_start rms=%.0f threshold=%.0f\n",
                                      turnPerf.turnIndex, rms, effectiveThreshold);
                    }
                    speechDetected = true;
                    lastVoiceAt = millis();
                }
                if (speechDetected) {
                    audioService.PushForEncoding(captureChunk->samples, captureChunk->sampleCount);
                    turnPerf.sentAudioChunks++;
                    turnPerf.sentAudioBytes += captureChunk->sampleCount * sizeof(int16_t);
                    if (turnPerf.firstChunkSentAt == 0) {
                        turnPerf.firstChunkSentAt = millis();
                        Serial.printf(
                            "[VOICE_PERF][DEVICE] turn=%d first_audio_chunk_sent_ms=%lu bytes=%u\n",
                            turnPerf.turnIndex,
                            voicePerfSince(turnPerf.speechStartAt),
                            (unsigned int)(captureChunk->sampleCount * sizeof(int16_t))
                        );
                    }
                }

                bool silenceTimeout = !voiceWsServerVad() && speechDetected && (millis() - lastVoiceAt >= (unsigned long)VOICE_SILENCE_COMMIT_MS);
                bool maxDurationReached = speechDetected && (millis() - turnPerf.speechStartAt >= VOICE_MAX_CAPTURE_MS);

                if (silenceTimeout || maxDurationReached) {
                    waitingForTurnDone = true;
                    speechDetected = false;
                    turnPerf.commitAt = millis();
                    Serial.printf(
                        "[VOICE_PERF][DEVICE] turn=%d commit_sent capture_ms=%lu sent_chunks=%u sent_bytes=%u reason=%s\n",
                        turnPerf.turnIndex,
                        voicePerfSince(turnPerf.speechStartAt),
                        (unsigned int)turnPerf.sentAudioChunks,
                        (unsigned int)turnPerf.sentAudioBytes,
                        maxDurationReached ? "max_duration" : "silence"
                    );
                    drainSendQueue(audioService);
                    if (!voiceWsCommitTurn()) {
                        audioService.Stop();
                        voiceWsClose();
                        codec.Stop();
                        Serial.println("[AI CHAT] commit failed");
                        return false;
                    }
                }
            }
            audioService.ReleaseCaptureChunk(captureChunk);
        }

        if (waitingForTurnDone && checkAiChatShortPress()) {
            voiceWsInterrupt();
            waitingForTurnDone = false;
            speechDetected = false;
            lastVoiceAt = 0;
            if (turnPerf.turnIndex > 0) {
                Serial.printf("[VOICE_PERF][DEVICE] turn=%d interrupted_after_commit_ms=%lu\n", turnPerf.turnIndex, voicePerfSince(turnPerf.commitAt));
            }
            audioService.ResetPlayback();
            audioService.FlushCaptureQueue();
            audioService.SetGenerationId(audioService.GetGenerationId() + 1);
            resetVoiceTurnPerf(turnPerf);
        }

        VoiceWsEvent event;
        while (voiceWsPollEvent(event)) {
            if (event.type == VoiceWsEventType::AsrPartial) {
                if (turnPerf.firstAsrPartialAt == 0) {
                    turnPerf.firstAsrPartialAt = millis();
                    Serial.printf(
                        "[VOICE_PERF][DEVICE] turn=%d first_asr_partial_after_commit_ms=%lu text=%s\n",
                        turnPerf.turnIndex, voicePerfSince(turnPerf.commitAt), event.text.c_str()
                    );
                }
            } else if (event.type == VoiceWsEventType::AsrFinal) {
                if (!waitingForTurnDone && voiceWsServerVad()) {
                    waitingForTurnDone = true;
                    speechDetected = false;
                    if (turnPerf.commitAt == 0) turnPerf.commitAt = millis();
                    Serial.printf(
                        "[VOICE_PERF][DEVICE] turn=%d server_auto_commit transcript=%s\n",
                        turnPerf.turnIndex, event.transcript.c_str()
                    );
                }
                if (turnPerf.asrFinalAt == 0) {
                    turnPerf.asrFinalAt = millis();
                    Serial.printf(
                        "[VOICE_PERF][DEVICE] turn=%d asr_final_after_commit_ms=%lu transcript=%s\n",
                        turnPerf.turnIndex, voicePerfSince(turnPerf.commitAt), event.transcript.c_str()
                    );
                }
            } else if (event.type == VoiceWsEventType::LlmDelta) {
                if (turnPerf.firstLlmDeltaAt == 0) {
                    turnPerf.firstLlmDeltaAt = millis();
                    Serial.printf(
                        "[VOICE_PERF][DEVICE] turn=%d first_llm_delta_after_commit_ms=%lu text=%s\n",
                        turnPerf.turnIndex, voicePerfSince(turnPerf.commitAt), event.text.c_str()
                    );
                }
            } else if (event.type == VoiceWsEventType::TtsAudioChunk) {
                waitingForTurnDone = true;
                speechDetected = false;
                lastVoiceAt = 0;
                turnPerf.recvAudioChunks++;
                turnPerf.recvAudioBytes += event.dataLen;
                if (turnPerf.firstTtsChunkAt == 0) {
                    turnPerf.firstTtsChunkAt = millis();
                    Serial.printf(
                        "[VOICE_PERF][DEVICE] turn=%d first_tts_chunk_after_commit_ms=%lu bytes=%u\n",
                        turnPerf.turnIndex, voicePerfSince(turnPerf.commitAt), (unsigned int)event.dataLen
                    );
                }
                audioService.SetGenerationId(event.generationId);
                if (event.needsDecode) {
                    audioService.PushForDecoding(event.data, event.dataLen, event.generationId);
                } else {
                    audioService.PushPcmForPlayback(event.data, event.dataLen, event.generationId);
                }
                if (turnPerf.firstPlaybackAt == 0) {
                    turnPerf.firstPlaybackAt = millis();
                    Serial.printf(
                        "[VOICE_PERF][DEVICE] turn=%d playback_started_after_commit_ms=%lu\n",
                        turnPerf.turnIndex, voicePerfSince(turnPerf.commitAt)
                    );
                }
            } else if (event.type == VoiceWsEventType::TurnInterrupted) {
                if (turnPerf.turnIndex > 0) {
                    Serial.printf("[VOICE_PERF][DEVICE] turn=%d turn_interrupted_after_commit_ms=%lu\n", turnPerf.turnIndex, voicePerfSince(turnPerf.commitAt));
                }
                audioService.ResetPlayback();
                audioService.FlushCaptureQueue();
            } else if (event.type == VoiceWsEventType::TurnDone) {
                speechDetected = false;
                lastVoiceAt = 0;
                exitConversation = event.exitConversation;
                turnPerf.turnDoneAt = millis();
                if (event.switchToMode.length() > 0) {
                    ctx.switchToModeId = event.switchToMode;
                    Serial.printf("[AI CHAT] mode switch -> %s\n", event.switchToMode.c_str());
                    exitConversation = true;
                }
                unsigned long drainStartedAt = millis();
                while (!audioService.IsPlaybackEmpty() && millis() - drainStartedAt < 10000UL) {
                    voiceWsLoop();
                    delay(20);
                }
                delay(VOICE_PLAYBACK_TAIL_CLEAR_MS);
                audioService.ResetPlayback();
                audioService.FlushCaptureQueue();
                waitingForTurnDone = false;
                Serial.printf(
                    "[VOICE_PERF][DEVICE] turn=%d done total_ms=%lu commit_to_done_ms=%lu recv_audio_chunks=%u recv_audio_bytes=%u exit=%s\n",
                    turnPerf.turnIndex,
                    voicePerfSince(turnPerf.speechStartAt),
                    voicePerfSince(turnPerf.commitAt),
                    (unsigned int)turnPerf.recvAudioChunks,
                    (unsigned int)turnPerf.recvAudioBytes,
                    exitConversation ? "true" : "false"
                );
                if (exitConversation) {
                    audioService.Stop();
                    voiceWsClose();
                    codec.Stop();
                    return true;
                }
                resetVoiceTurnPerf(turnPerf);
            } else if (event.type == VoiceWsEventType::Error) {
                if (turnPerf.turnIndex > 0) {
                    Serial.printf("[VOICE_PERF][DEVICE] turn=%d error_after_commit_ms=%lu message=%s\n", turnPerf.turnIndex, voicePerfSince(turnPerf.commitAt), event.text.c_str());
                }
                Serial.printf("[AI CHAT] WS error: %s\n", event.text.c_str());
                waitingForTurnDone = false;
                speechDetected = false;
                lastVoiceAt = 0;
                audioService.ResetPlayback();
                audioService.FlushCaptureQueue();
                resetVoiceTurnPerf(turnPerf);
            }
            voiceWsReleaseEvent(event);
        }

        delay(10);
    }

    audioService.Stop();
    voiceWsClose();
    codec.Stop();
    return false;
#endif
}

// ── Immediate refresh ───────────────────────────────────────

static void triggerImmediateRefresh(bool nextMode, bool keepWiFi, bool partialVocabRating, const uint8_t *partialOldImage, bool skipNtp) {
    Serial.println("[REFRESH] Triggering immediate refresh...");
    ledFeedback("ack");
    uint8_t *previousImage = nullptr;
    if (nextMode) {
        previousImage = (uint8_t *)malloc(IMG_BUF_LEN);
        if (previousImage) {
            memcpy(previousImage, imgBuf, IMG_BUF_LEN);
        }
        showModePreview("NEXT");
    }
    auto restorePreviousImage = [&]() {
        if (nextMode && previousImage) {
            memcpy(imgBuf, previousImage, IMG_BUF_LEN);
            Serial.println("[REFRESH] Restoring previous image after failed next-mode refresh");
            smartDisplay(imgBuf);
        }
    };
    bool connected = (WiFi.status() == WL_CONNECTED);
    if (!connected) {
        ledFeedback("connecting");
        connected = connectWiFi();
    }
    if (connected) {
        ledFeedback("downloading");
        String renderedModeId;
        bool fetched = fetchBMP(nextMode, nullptr, &renderedModeId);
        if (fetched && renderedModeId.length() > 0) {
            ctx.currentRenderedModeId = renderedModeId;
            if (!ctx.currentRenderedModeId.equalsIgnoreCase(VOCAB_REVIEW_MODE_ID)) {
                ctx.vocabReviewBackSide = false;
            }
        }
        bool aiChatRequested = renderedModeId.equalsIgnoreCase(AI_CHAT_MODE_ID);
        String pendingMode;
        if (!aiChatRequested) {
            aiChatRequested = peekPendingMode(pendingMode) && pendingMode.equalsIgnoreCase(AI_CHAT_MODE_ID);
        }
        bool keepWiFiEffective = keepWiFi || aiChatRequested;
        if (fetched) {
            bool hasRaw2bpp = false;
#if EPD_BPP >= 2
            hasRaw2bpp = useColorBuf;
#endif
            if (!hasRaw2bpp) {
                cacheSave(imgBuf, IMG_BUF_LEN);
            }

            uint32_t newChecksum = 0;
#if EPD_BPP >= 2
            newChecksum = (hasRaw2bpp && colorBuf)
                ? computeChecksum(colorBuf, COLOR_BUF_LEN)
                : computeChecksum(imgBuf, IMG_BUF_LEN);
#else
            newChecksum = computeChecksum(imgBuf, IMG_BUF_LEN);
#endif
            if (!skipNtp) {
                syncNTP();
            }
            if (newChecksum == lastContentChecksum && !nextMode) {
                Serial.println("Content unchanged, skipping display refresh");
                ledFeedback("success");
            } else {
                if (partialVocabRating && ctx.currentRenderedModeId.equalsIgnoreCase(VOCAB_REVIEW_MODE_ID)) {
                    Serial.println("[VOCAB] Displaying reveal/control region with partial refresh...");
                    updateVocabRatingRegion(partialOldImage);
                } else {
                    Serial.println("Displaying new content...");
                    smartDisplay(imgBuf);
                }
                lastContentChecksum = newChecksum;
                ledFeedback("success");
                Serial.println("Display done");
            }

            if (aiChatRequested) {
                ledFeedback("ack");
                g_userAborted = false;
                bool exited = runAiChatConversation();
                if (g_userAborted) {
                    Serial.println("User aborted AI chat -> portal");
                    if (previousImage) free(previousImage);
                    enterPortalMode();
                    return;
                }
                if (exited) {
                    Serial.println("AI chat exited, showing next mode...");
                    ledFeedback("downloading");
                    if (fetchBMP(true, nullptr, nullptr)) {
                        cacheSave(imgBuf, IMG_BUF_LEN);
                        uint32_t newChecksum2 = computeChecksum(imgBuf, IMG_BUF_LEN);
                        syncNTP();
                        smartDisplay(imgBuf);
                        lastContentChecksum = newChecksum2;
                        ledFeedback("success");
                    }
                }
            }

            lastRenderedPeriod = currentPeriodIndex();
            ctx.lastClockTick = millis();
        } else {
            bool retryReady = false;
            if (keepWiFiEffective && WiFi.status() == WL_CONNECTED) {
                Serial.println("Fetch failed, retrying on existing WiFi...");
                retryReady = true;
            } else {
                Serial.println("Fetch failed, retrying after reconnect...");
                WiFi.disconnect(true);
                delay(300);
                retryReady = connectWiFi();
            }
            if (retryReady) {
                fetched = fetchBMP(nextMode, nullptr, &renderedModeId);
                if (fetched) {
                    if (renderedModeId.length() > 0) {
                        ctx.currentRenderedModeId = renderedModeId;
                        if (!ctx.currentRenderedModeId.equalsIgnoreCase(VOCAB_REVIEW_MODE_ID)) {
                            ctx.vocabReviewBackSide = false;
                        }
                    }
                    cacheSave(imgBuf, IMG_BUF_LEN);
                    uint32_t retryChecksum = computeChecksum(imgBuf, IMG_BUF_LEN);
                    syncNTP();
                    smartDisplay(imgBuf);
                    lastContentChecksum = retryChecksum;
                    lastRenderedPeriod = currentPeriodIndex();
                    ctx.lastClockTick = millis();
                    ledFeedback("success");
                    Serial.println("Retry succeeded");
                } else {
                    ledFeedback("fail");
                    Serial.println("Retry also failed, keeping old content");
                    restorePreviousImage();
                }
            } else {
                ledFeedback("fail");
                Serial.println("WiFi reconnect failed, keeping old content");
                restorePreviousImage();
            }
        }
        if (!keepWiFiEffective) {
            WiFi.disconnect(true);
            WiFi.mode(WIFI_OFF);
        }
    } else {
        ledFeedback("fail");
        Serial.println("WiFi reconnect failed");
        restorePreviousImage();
    }
    if (previousImage) free(previousImage);
}

static bool waitForContentReady() {
    const int maxRetries = 4;
    const int waitMs = 15000;
    for (int i = 0; i < maxRetries; i++) {
        Serial.printf("[BOOT] Content not ready, retry %d/%d\n", i + 1, maxRetries);
        showError("Generating...");
        unsigned long t0 = millis();
        while (millis() - t0 < (unsigned long)waitMs) {
            if (digitalRead(PIN_CFG_BTN) == LOW) {
                delay(400);
                if (digitalRead(PIN_CFG_BTN) == LOW) {
                    Serial.println("[BOOT] Config button held during wait -> portal");
                    enterPortalMode();
                    return false;
                }
            }
            delay(50);
        }
        if (WiFi.status() != WL_CONNECTED) {
            if (!connectWiFi()) {
                if (g_userAborted) {
                    enterPortalMode();
                    return false;
                }
                continue;
            }
        }
        ledFeedback("downloading");
        bool gotFallback = false;
        if (fetchBMP(false, &gotFallback) && !gotFallback) {
            Serial.println("[BOOT] Content is ready");
            return true;
        }
        if (g_userAborted) {
            enterPortalMode();
            return false;
        }
    }
    return false;
}

// ── Config button handler ───────────────────────────────────

static void checkConfigButton() {
    bool isPressed = (digitalRead(PIN_CFG_BTN) == LOW);

    if (ctx.ignoreConfigButtonUntilRelease) {
        if (!isPressed) {
            ctx.ignoreConfigButtonUntilRelease = false;
        }
        ctx.btnPressStart = 0;
        return;
    }

    if (isPressed) {
        if (ctx.btnPressStart == 0) {
            ctx.btnPressStart = millis();
        } else {
            unsigned long holdTime = millis() - ctx.btnPressStart;
            if (holdTime >= (unsigned long)CFG_BTN_HOLD_MS) {
                Serial.printf("Config button held for %dms, entering portal...\n", CFG_BTN_HOLD_MS);
                ctx.btnPressStart = 0;
                enterPortalMode();
            }
        }
    } else {
        if (ctx.btnPressStart != 0) {
            unsigned long pressDuration = millis() - ctx.btnPressStart;
            ctx.btnPressStart = 0;

            if (pressDuration >= (unsigned long)SHORT_PRESS_MIN_MS &&
                pressDuration < (unsigned long)CFG_BTN_HOLD_MS) {
                Serial.println("[BTN] Short press while awake; no action");
            }
        }
    }
}

static void checkAiChatButton() {
#if PIN_AI_CHAT_SW < 0
    return;
#else
    bool isPressed = (digitalRead(PIN_AI_CHAT_SW) == LOW);
    if (ctx.ignoreAiButtonUntilRelease) {
        if (!isPressed) {
            ctx.ignoreAiButtonUntilRelease = false;
        }
        ctx.aiBtnPressStart = 0;
        return;
    }

    if (isPressed) {
        if (ctx.aiBtnPressStart == 0) {
            ctx.aiBtnPressStart = millis();
        } else if (!ctx.wantEnterAiChatMode) {
            unsigned long holdTime = millis() - ctx.aiBtnPressStart;
#if VOCAB_REVIEW_BUILD
            bool inVocabMode = ctx.currentRenderedModeId.equalsIgnoreCase(VOCAB_REVIEW_MODE_ID);
            unsigned long holdThreshold = inVocabMode
                ? (unsigned long)VOCAB_EXIT_HOLD_MS
                : (unsigned long)VOCAB_ENTER_HOLD_MS;
#else
            unsigned long holdThreshold = (unsigned long)AI_CHAT_BTN_HOLD_MS;
#endif
            if (holdTime >= holdThreshold) {
#if VOCAB_REVIEW_BUILD
                if (inVocabMode) {
                    Serial.printf("[VOCAB] Switch held for %dms, exit vocab review\n", VOCAB_EXIT_HOLD_MS);
                    ctx.wantVocabExit = true;
                } else {
                    Serial.printf("[VOCAB] Switch held for %dms, enter vocab review\n", VOCAB_ENTER_HOLD_MS);
                    ctx.wantEnterVocabReview = true;
                }
                ctx.aiBtnPressStart = 0;
                ctx.ignoreAiButtonUntilRelease = true;
#else
                Serial.printf("[AI CHAT] Switch held for %dms, queue enter ai chat\n", AI_CHAT_BTN_HOLD_MS);
                ctx.wantEnterAiChatMode = true;
                ctx.aiBtnPressStart = 0;
                ctx.ignoreAiButtonUntilRelease = true;
#endif
            }
        }
    } else {
        if (ctx.aiBtnPressStart > 0 && !ctx.wantEnterAiChatMode) {
            unsigned long duration = millis() - ctx.aiBtnPressStart;
            if (duration >= (unsigned long)SHORT_PRESS_MIN_MS &&
#if VOCAB_REVIEW_BUILD
                duration < (unsigned long)(
                    ctx.currentRenderedModeId.equalsIgnoreCase(VOCAB_REVIEW_MODE_ID)
                        ? VOCAB_EXIT_HOLD_MS
                        : VOCAB_ENTER_HOLD_MS
                )) {
#else
                duration < (unsigned long)AI_CHAT_BTN_HOLD_MS) {
#endif
#if VOCAB_REVIEW_BUILD
                if (ctx.currentRenderedModeId.equalsIgnoreCase(VOCAB_REVIEW_MODE_ID)) {
                    if (ctx.vocabReviewBackSide && duration >= (unsigned long)VOCAB_BTN_HOLD_MS) {
                        Serial.printf("[VOCAB] Switch released after %lums, submit rating\n", duration);
                        ctx.wantVocabSubmitRating = true;
                    } else if (ctx.vocabReviewBackSide) {
                        Serial.printf("[VOCAB] Short press %lums, next rating\n", duration);
                        ctx.wantVocabNextRating = true;
                    } else {
                        Serial.printf("[VOCAB] Short press %lums, flip card\n", duration);
                        ctx.wantVocabFlip = true;
                    }
                }
#else
                // Short press is intentionally unused; long press enters AI chat.
#endif
            }
        }
        ctx.aiBtnPressStart = 0;
    }
#endif
}

#endif // VOICE_ONLY_BUILD
