// Smart e-ink desktop companion powered by LLM
// https://github.com/datascale-ai/inksight

#include <Arduino.h>
#include <freertos/FreeRTOS.h>
#include <freertos/queue.h>
#include <freertos/task.h>
#include <new>
#include <WiFi.h>

#include "config.h"
#if defined(BOARD_PROFILE_ESP32_WROOM32E)
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
static const int VOICE_SILENCE_COMMIT_MS = 600;
static const float VOICE_STREAM_VAD_THRESHOLD = 150.0f;
static const unsigned long VOICE_MAX_CAPTURE_MS = 8000;
static const int VOICE_DEEP_CLEAR_INTERVAL = 5;  // deep-clear every N turns to remove ghosting

#if VOICE_ONLY_BUILD
static const float BARGE_IN_THRESHOLD = 2000.0f;
static const int BARGE_IN_CONFIRM_FRAMES = 3;
#endif

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

struct DeviceContext {
    DeviceState state = DeviceState::BOOT;

    // Button state
    unsigned long btnPressStart = 0;
    unsigned long aiBtnPressStart = 0;
    bool ignoreConfigButtonUntilRelease = false;
    bool liveMode = false;
    unsigned long lastLivePollAt = 0;
    unsigned long lastLiveWiFiRetryAt = 0;

    // Timing
    unsigned long setupDoneAt = 0;
    unsigned long lastClockTick = 0;

    // Pending actions (set by button handler, consumed by loop)
    bool wantRefresh = false;
    bool wantEnterLiveMode = false;
    bool wantEnterAiChatMode = false;
    bool wantSingleVoiceTurn = false;
    String switchToModeId;
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
static void enterPortalMode();

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

static void enterPortalMode() {
    g_userAborted = false;
    String mac = WiFi.macAddress();
    String apName = "InkSight-" + mac.substring(mac.length() - 5);
    apName.replace(":", "");

    ctx.liveMode = false;
    ctx.wantEnterLiveMode = false;
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

#if defined(BOARD_PROFILE_ESP32_WROOM32E)
static void drainSendQueue(AudioService &as) {
    AsAudioPacket* pkt = nullptr;
    while (as.PollSendPacket(pkt)) {
        voiceWsSendRawPacket(pkt->data, pkt->dataLen);
        as.ReleaseSendPacket(pkt);
    }
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
                    float rms = audioCalculateRMS(cap->samples, cap->sampleCount);
                    if (rms >= BARGE_IN_THRESHOLD) {
                        bargeInFrames++;
                        if (bargeInFrames >= BARGE_IN_CONFIRM_FRAMES) {
                            Serial.printf("[VOICE] Barge-in detected (RMS=%.0f, frames=%d)\n", rms, bargeInFrames);
                            voiceWsInterrupt();
                            audioService.ResetPlayback();
                            audioService.SetGenerationId(audioService.GetGenerationId() + 1);
                            bargeInFrames = 0;

                            speechDetected = true;
                            turnCounter++;
                            resetVoiceTurnPerf(turnPerf);
                            turnPerf.turnIndex = turnCounter;
                            turnPerf.speechStartAt = millis();
                            lastVoiceAt = millis();

                            audioService.PushForEncoding(cap->samples, cap->sampleCount);
                            turnPerf.sentAudioChunks++;
                            turnPerf.sentAudioBytes += cap->sampleCount * sizeof(int16_t);
                            turnPerf.firstChunkSentAt = millis();

                            state = VoiceState::LISTENING;
                            voiceSetLed(state);
                        }
                    } else {
                        bargeInFrames = 0;
                    }
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
                    delay(300);
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
    Serial.begin(115200);
    delay(3000);
    Serial.println("\n=== InkSight Voice ===");

    ledInit();
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
        Serial.println("[VOICE] WiFi failed, restarting in 5s");
        ledFeedback("fail");
        delay(5000);
        ESP.restart();
    }
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
static void triggerImmediateRefresh(bool nextMode, bool keepWiFi);
static void handleLiveMode();
static bool waitForContentReady();
static void handleFailure(const char *reason);
static void enterDeepSleep(int minutes);
static bool runAiChatConversation();
static void runSingleVoiceTurn();
static bool decodeVoiceBmpToFrameBuffer(const uint8_t *bmpBytes, size_t bmpLen);

// ═════════════════════════════════════════════════════════════
// setup() — display build
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
#if PIN_AI_CHAT_SW >= 0
    pinMode(PIN_AI_CHAT_SW, INPUT_PULLUP);
#endif

    loadConfig();

    bool forcePortal = false;
    if (digitalRead(PIN_CFG_BTN) == LOW) {
        delay(400);
        forcePortal = (digitalRead(PIN_CFG_BTN) == LOW);
    }

    cacheInit();
    Serial.println("EPD ready");

    loadConfig();

    bool hasConfig = (cfgSSID.length() > 0);

    if (forcePortal || !hasConfig) {
        Serial.println(forcePortal ? "Config button held -> portal"
                                   : "No WiFi config -> portal");
        delay(5000);
        enterPortalMode();
        String mac = WiFi.macAddress();
        String apName = "InkSight-" + mac.substring(mac.length() - 5);
        apName.replace(":", "");
        ledFeedback("portal");
        showSetupScreen(apName.c_str());
        startCaptivePortal();
        ctx.state = DeviceState::PORTAL;
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
        handleFailure("WiFi failed");
        return;
    }

    bool focusFlag = false;
    if (fetchFocusListeningFlag(&focusFlag)) {
        focusListening = focusFlag;
    } else {
        focusListening = false;
    }
    if (g_userAborted) {
        Serial.println("User aborted during focus fetch -> portal");
        enterPortalMode();
        return;
    }

#if AUTO_BOOT_AI_CHAT && defined(BOARD_PROFILE_ESP32_WROOM32E)
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
// loop() — display build
// ═════════════════════════════════════════════════════════════

void loop() {
    if (ctx.state == DeviceState::PORTAL) {
        handlePortalClients();
        checkConfigButton();
        checkAiChatButton();
        delay(5);
        return;
    }

    checkConfigButton();
    checkAiChatButton();

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
    } else if (ctx.wantSingleVoiceTurn) {
        ctx.wantSingleVoiceTurn = false;
        ctx.switchToModeId = "";
        Serial.println("[VOICE] Short press -> single voice turn");
        if (WiFi.status() != WL_CONNECTED && !connectWiFi()) {
            Serial.println("[VOICE] WiFi reconnect failed, skip");
        } else {
            runSingleVoiceTurn();
            ctx.btnPressStart = 0;
            ctx.ignoreConfigButtonUntilRelease = (digitalRead(PIN_CFG_BTN) == LOW);
            if (ctx.switchToModeId.length() > 0) {
                Serial.printf("[VOICE] Mode switch to %s, refreshing immediately\n",
                              ctx.switchToModeId.c_str());
                g_suppressAbortCheck = true;
                triggerImmediateRefresh(false, true);
                g_suppressAbortCheck = false;
                WiFi.disconnect(true);
                WiFi.mode(WIFI_OFF);
                ctx.setupDoneAt = millis();
            }
        }
    } else if (ctx.wantEnterAiChatMode) {
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
                    triggerImmediateRefresh(false, true);
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

// ── Deep sleep ──────────────────────────────────────────────

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
        WiFi.disconnect(true);
        WiFi.mode(WIFI_OFF);
        ctx.state = DeviceState::DISPLAYING;
        ctx.setupDoneAt = millis();
        resetRetryCount();
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

// ── Live mode ───────────────────────────────────────────────

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

// ── Single voice turn (short-press, one Q&A) ────────────────

static void runSingleVoiceTurn() {
#if !defined(BOARD_PROFILE_ESP32_WROOM32E)
    return;
#else
    showVoiceIndicator(true);
    ledFeedback("ack");

    static Inmp441Max98357Codec codec(true);
    if (!codec.Start()) {
        Serial.println("[VOICE] Single turn: codec start failed");
        hideVoiceIndicator();
        return;
    }

    static AudioService audioService;
    if (!audioService.Initialize(&codec)) {
        Serial.println("[VOICE] Single turn: AudioService init failed");
        codec.Stop();
        hideVoiceIndicator();
        return;
    }

    if (!voiceWsOpen(SAMPLE_RATE, W, H, false)) {
        Serial.println("[VOICE] Single turn: WS open failed");
        audioService.Stop();
        codec.Stop();
        hideVoiceIndicator();
        return;
    }

    unsigned long readyStartAt = millis();
    bool sessionReady = false;
    while (millis() - readyStartAt < 6000) {
        voiceWsLoop();
        VoiceWsEvent event;
        while (voiceWsPollEvent(event)) {
            if (event.type == VoiceWsEventType::SessionReady) {
                sessionReady = true;
            }
            voiceWsReleaseEvent(event);
        }
        if (sessionReady) break;
        delay(10);
    }

    if (!sessionReady) {
        Serial.println("[VOICE] Single turn: session ready timeout");
        voiceWsClose();
        audioService.Stop();
        codec.Stop();
        hideVoiceIndicator();
        return;
    }

    audioService.Start();
    audioService.FlushCaptureQueue();
    Serial.println("[VOICE] Single turn: listening...");

    bool speechDetected = false;
    bool committed = false;
    unsigned long lastVoiceAt = 0;

    while (voiceWsConnected() && !committed) {
        voiceWsLoop();
        drainSendQueue(audioService);

        AsCaptureChunk *cap = nullptr;
        while (audioService.PollCaptureChunk(cap)) {
            if (cap->sampleCount > 0) {
                audioNoiseGateApply(cap->samples, cap->sampleCount, 80.0f);
                float rms = audioCalculateRMS(cap->samples, cap->sampleCount);
                if (!speechDetected && rms < VOICE_STREAM_VAD_THRESHOLD) {
                    audioAdaptiveNoiseFloor(rms);
                }
                float noiseFloor = audioAdaptiveNoiseFloor(-1.0f);
                float effectiveThreshold = max(VOICE_STREAM_VAD_THRESHOLD, noiseFloor * 3.0f);

                if (rms >= effectiveThreshold) {
                    speechDetected = true;
                    lastVoiceAt = millis();
                }
                if (speechDetected) {
                    audioService.PushForEncoding(cap->samples, cap->sampleCount);
                }
                bool silenceTimeout = speechDetected && lastVoiceAt > 0 &&
                    (millis() - lastVoiceAt >= (unsigned long)VOICE_SILENCE_COMMIT_MS);
                bool maxDuration = speechDetected &&
                    (millis() - lastVoiceAt >= VOICE_MAX_CAPTURE_MS + VOICE_SILENCE_COMMIT_MS);
                if (silenceTimeout || maxDuration) {
                    drainSendQueue(audioService);
                    voiceWsCommitTurn();
                    committed = true;
                }
            }
            audioService.ReleaseCaptureChunk(cap);
        }
        delay(5);
    }

    if (!committed) {
        Serial.println("[VOICE] Single turn: no speech or WS dropped");
        audioService.Stop();
        voiceWsClose();
        codec.Stop();
        hideVoiceIndicator();
        return;
    }

    Serial.println("[VOICE] Single turn: waiting for response...");
    unsigned long waitStart = millis();
    bool gotDone = false;
    while (voiceWsConnected() && millis() - waitStart < 15000) {
        voiceWsLoop();
        drainSendQueue(audioService);

        VoiceWsEvent event;
        while (voiceWsPollEvent(event)) {
            if (event.type == VoiceWsEventType::TtsAudioChunk) {
                if (event.needsDecode) {
                    audioService.PushForDecoding(event.data, event.dataLen, event.generationId);
                } else {
                    audioService.PushPcmForPlayback(event.data, event.dataLen, event.generationId);
                }
            } else if (event.type == VoiceWsEventType::TurnDone) {
                gotDone = true;
                if (event.switchToMode.length() > 0) {
                    ctx.switchToModeId = event.switchToMode;
                    Serial.printf("[VOICE] Single turn: mode switch -> %s\n", event.switchToMode.c_str());
                }
                voiceWsReleaseEvent(event);
                break;
            }
            voiceWsReleaseEvent(event);
        }
        if (gotDone) break;
        delay(10);
    }

    unsigned long drainStart = millis();
    while (!audioService.IsPlaybackEmpty() && millis() - drainStart < 8000) {
        voiceWsLoop();
        delay(20);
    }
    delay(100);

    audioService.Stop();
    audioService.ResetPlayback();
    voiceWsClose();
    codec.Stop();
    hideVoiceIndicator();
    Serial.println("[VOICE] Single turn: done");
#endif
}

// ── AI Chat conversation (display build, full-duplex) ───────

static bool runAiChatConversation() {
#if !defined(BOARD_PROFILE_ESP32_WROOM32E)
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

    showVoiceChatScreen();

    if (!voiceWsOpen(SAMPLE_RATE, W, H, false)) {
        showAiChatStatus("WS FAIL", "");
        codec.Stop();
        return false;
    }
    Serial.printf("[VOICE_PERF][DEVICE] ws_open_ms=%lu\n", millis() - wsOpenStartedAt);

    unsigned long readyStartAt = millis();
    while (!sessionReady && millis() - readyStartAt < 6000UL) {
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
            } else if (event.type == VoiceWsEventType::TurnDone) {
                waitingForTurnDone = false;
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
                delay(120);
                audioService.ResetPlayback();
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
        String renderedModeId;
        bool fetched = fetchBMP(nextMode, nullptr, &renderedModeId);
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

            if (aiChatRequested) {
                ledFeedback("ack");
                g_userAborted = false;
                bool exited = runAiChatConversation();
                if (g_userAborted) {
                    Serial.println("User aborted AI chat -> portal");
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
            Serial.println("Fetch failed, retrying after reconnect...");
            WiFi.disconnect(true);
            delay(300);
            if (connectWiFi()) {
                fetched = fetchBMP(nextMode, nullptr, &renderedModeId);
                if (fetched) {
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
                }
            } else {
                ledFeedback("fail");
                Serial.println("WiFi reconnect failed, keeping old content");
            }
        }
        if (!keepWiFiEffective) {
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
                Serial.printf("Config button held for %dms, restarting...\n", CFG_BTN_HOLD_MS);
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

static void checkAiChatButton() {
#if PIN_AI_CHAT_SW < 0
    return;
#else
    bool isPressed = (digitalRead(PIN_AI_CHAT_SW) == LOW);
    if (isPressed) {
        if (ctx.aiBtnPressStart == 0) {
            ctx.aiBtnPressStart = millis();
        } else if (!ctx.wantEnterAiChatMode &&
                   (millis() - ctx.aiBtnPressStart >= (unsigned long)AI_CHAT_BTN_HOLD_MS)) {
            Serial.printf("[AI CHAT] Switch held for %dms, queue enter ai chat\n", AI_CHAT_BTN_HOLD_MS);
            ctx.wantEnterAiChatMode = true;
            ctx.aiBtnPressStart = millis();
        }
    } else {
        if (ctx.aiBtnPressStart > 0 && !ctx.wantEnterAiChatMode) {
            unsigned long duration = millis() - ctx.aiBtnPressStart;
            if (duration >= (unsigned long)SHORT_PRESS_MIN_MS &&
                duration < (unsigned long)AI_CHAT_BTN_HOLD_MS) {
                Serial.printf("[VOICE] Short press %lums, queue single voice turn\n", duration);
                ctx.wantSingleVoiceTurn = true;
            }
        }
        ctx.aiBtnPressStart = 0;
    }
#endif
}

#endif // VOICE_ONLY_BUILD
