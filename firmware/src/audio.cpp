#include "config.h"
#if defined(BOARD_PROFILE_ESP32_WROOM32E)

#include "audio.h"
#include <math.h>

// ── Analysis ────────────────────────────────────────────────

float audioCalculateRMS(const int16_t *samples, size_t count) {
    if (samples == NULL || count == 0) return 0.0;
    int64_t sumSquares = 0;
    for (size_t i = 0; i < count; i++) {
        sumSquares += (int64_t)samples[i] * samples[i];
    }
    return sqrt((float)sumSquares / count);
}

bool audioDetectVoice(const int16_t *samples, size_t count, float threshold) {
    return audioCalculateRMS(samples, count) > threshold;
}

static float gNoiseFloor = 0.0f;

void audioNoiseGateApply(int16_t *samples, size_t count, float gateThresholdRms) {
    if (samples == nullptr || count == 0) return;
    float rms = audioCalculateRMS(samples, count);
    if (rms < gateThresholdRms) {
        memset(samples, 0, count * sizeof(int16_t));
    }
}

float audioAdaptiveNoiseFloor(float currentRms, float alpha) {
    if (currentRms < 0.0f) return gNoiseFloor;
    if (gNoiseFloor <= 0.0f) {
        gNoiseFloor = currentRms;
    } else {
        gNoiseFloor = gNoiseFloor * (1.0f - alpha) + currentRms * alpha;
    }
    return gNoiseFloor;
}

// ── Opus codec (conditional) ────────────────────────────────

#if ENABLE_OPUS
#include <opus.h>

static OpusEncoder *gOpusEncoder = nullptr;
static OpusDecoder *gOpusDecoder = nullptr;

bool opusEncoderInit(int sampleRate, int channels) {
    opusEncoderDestroy();
    int error = 0;
    gOpusEncoder = opus_encoder_create(sampleRate, channels, OPUS_APPLICATION_VOIP, &error);
    if (error != OPUS_OK || gOpusEncoder == nullptr) {
        Serial.printf("[OPUS] Encoder init failed: %d\n", error);
        gOpusEncoder = nullptr;
        return false;
    }
    opus_encoder_ctl(gOpusEncoder, OPUS_SET_COMPLEXITY(0));
    opus_encoder_ctl(gOpusEncoder, OPUS_SET_DTX(1));
    opus_encoder_ctl(gOpusEncoder, OPUS_SET_SIGNAL(OPUS_SIGNAL_VOICE));
    Serial.printf("[OPUS] Encoder ready (sr=%d, ch=%d)\n", sampleRate, channels);
    return true;
}

int opusEncode(const int16_t *pcm, int frameSize, uint8_t *output, int maxBytes) {
    if (gOpusEncoder == nullptr || pcm == nullptr) return -1;
    return opus_encode(gOpusEncoder, pcm, frameSize, output, maxBytes);
}

void opusEncoderDestroy() {
    if (gOpusEncoder != nullptr) {
        opus_encoder_destroy(gOpusEncoder);
        gOpusEncoder = nullptr;
    }
}

bool opusDecoderInit(int sampleRate, int channels) {
    opusDecoderDestroy();
    int error = 0;
    gOpusDecoder = opus_decoder_create(sampleRate, channels, &error);
    if (error != OPUS_OK || gOpusDecoder == nullptr) {
        Serial.printf("[OPUS] Decoder init failed: %d\n", error);
        gOpusDecoder = nullptr;
        return false;
    }
    Serial.printf("[OPUS] Decoder ready (sr=%d, ch=%d)\n", sampleRate, channels);
    return true;
}

int opusDecode(const uint8_t *data, int len, int16_t *pcm, int maxSamples) {
    if (gOpusDecoder == nullptr || data == nullptr) return -1;
    return opus_decode(gOpusDecoder, data, len, pcm, maxSamples, 0);
}

void opusDecoderDestroy() {
    if (gOpusDecoder != nullptr) {
        opus_decoder_destroy(gOpusDecoder);
        gOpusDecoder = nullptr;
    }
}

#endif // ENABLE_OPUS

#endif // BOARD_PROFILE_ESP32_WROOM32E
