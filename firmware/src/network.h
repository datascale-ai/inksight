#ifndef INKSIGHT_NETWORK_H
#define INKSIGHT_NETWORK_H

#include <Arduino.h>
#include <stddef.h>
#include <stdint.h>

enum class VoiceWsEventType : uint8_t {
    None = 0,
    SessionReady,
    AsrPartial,
    AsrFinal,
    LlmDelta,
    TtsTextChunk,
    TtsAudioChunk,
    TurnDone,
    TurnInterrupted,
    Error,
};

struct VoiceWsEvent {
    VoiceWsEventType type = VoiceWsEventType::None;
    String text;
    String transcript;
    String turnId;
    String switchToMode;
    int generationId = 0;
    int chunkId = 0;
    int sampleRate = 16000;
    bool exitConversation = false;
    bool needsDecode = false;
    uint8_t *data = nullptr;
    size_t dataLen = 0;
};

extern bool g_userAborted;
extern bool g_suppressAbortCheck;

// ── Time state (updated by syncNTP / tickTime) ──────────────
extern int curHour, curMin, curSec;

// ── WiFi ────────────────────────────────────────────────────

// Connect to WiFi using stored credentials. Returns true on success.
bool connectWiFi();

// ── HTTP ────────────────────────────────────────────────────

// Fetch BMP image from backend and store in imgBuf. Returns true on success.
// If nextMode is true, appends &next=1 to request the next mode in sequence.
bool fetchBMP(bool nextMode = false, bool *isFallback = nullptr, String *renderedModeIdOut = nullptr);

// Check whether backend has pending refresh/switch request for this device.
// If shouldExitLive is not null, it is set to true when backend runtime_mode is interval.
bool hasPendingRemoteAction(bool *shouldExitLive = nullptr);

// Peek pending_mode for this device without consuming it.
bool peekPendingMode(String &pendingModeOut);

// POST runtime mode (active/interval) to backend.
bool postRuntimeMode(const char *mode);

// POST device config JSON to backend /api/config endpoint.
void postConfigToBackend();

bool submitVoiceTurn(const char *pcmPath, int sampleRate, int screenW, int screenH, String &turnId, String &replyText, String &transcript, bool &exitConversation);
bool submitVoiceTurnBytes(const uint8_t *pcmBytes, size_t pcmSize, int sampleRate, int screenW, int screenH, String &turnId, String &replyText, String &transcript, bool &exitConversation);
bool fetchVoiceAudio(const String &turnId, const char *path);
bool fetchVoiceImage(const String &turnId);
bool fetchVoiceIntroImage(int screenW, int screenH);
bool voiceWsOpen(int sampleRate, int screenW, int screenH, bool includeImage);
bool voiceWsConnected();
void voiceWsLoop();
bool voiceWsSendAudioBin(const int16_t *samples, size_t sampleCount);
bool voiceWsSendAudioChunk(const int16_t *samples, size_t sampleCount);
bool voiceWsSendRawPacket(const uint8_t *data, size_t len);
bool voiceWsCommitTurn();
bool voiceWsInterrupt();
bool voiceWsPollEvent(VoiceWsEvent &eventOut);
void voiceWsReleaseEvent(VoiceWsEvent &event);
void voiceWsClose();
bool voiceWsBinaryAudio();
bool voiceWsServerVad();

bool ensureDeviceToken();
bool postHeartbeat(bool force = false);

// ── Focus listening helpers ─────────────────────────────────
bool fetchFocusListeningFlag(bool *outEnabled);
bool fetchFocusAlertBMP();

// ── Battery ─────────────────────────────────────────────────

// Read battery voltage via ADC (returns volts)
float readBatteryVoltage();

// ── NTP time ────────────────────────────────────────────────

// Sync time from NTP servers
void syncNTP();

// Advance software clock by one second
void tickTime();

#endif // INKSIGHT_NETWORK_H
