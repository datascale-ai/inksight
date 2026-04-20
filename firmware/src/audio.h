#ifndef INKSIGHT_AUDIO_H
#define INKSIGHT_AUDIO_H

#include <Arduino.h>

// ── Pin assignments ──────────────────────────────────────────

#define I2S_MIC_SCK  18
#define I2S_MIC_WS   19
#define I2S_MIC_SD   33

#if defined(BOARD_PROFILE_ESP32_WROOM32E)
#define I2S_SPK_SCK  17
#define I2S_SPK_WS   16
#define I2S_SPK_DOUT 22
#else
#define I2S_SPK_SCK  I2S_MIC_SCK
#define I2S_SPK_WS   I2S_MIC_WS
#define I2S_SPK_DOUT 22
#endif

#define I2S_WS       I2S_MIC_WS
#define I2S_SCK      I2S_MIC_SCK
#define I2S_SD       I2S_MIC_SD
#define I2S_DOUT     I2S_SPK_DOUT

// ── Audio constants ──────────────────────────────────────────

#define SAMPLE_RATE  16000
#define SAMPLE_BITS  32
#define BUFFER_SIZE  1024
#define STREAM_CHUNK_MS 40
#define STREAM_CHUNK_SAMPLES ((SAMPLE_RATE * STREAM_CHUNK_MS) / 1000)

// ── Analysis ─────────────────────────────────────────────────

float audioCalculateRMS(const int16_t *samples, size_t count);
bool audioDetectVoice(const int16_t *samples, size_t count, float threshold = 500.0);
void audioNoiseGateApply(int16_t *samples, size_t count, float gateThresholdRms = 80.0f);
float audioAdaptiveNoiseFloor(float currentRms, float alpha = 0.02f);

// ── Opus codec (conditional) ────────────────────────────────

#if ENABLE_OPUS

#define OPUS_FRAME_DURATION_MS 60
#define OPUS_FRAME_SAMPLES     (SAMPLE_RATE * OPUS_FRAME_DURATION_MS / 1000)
#define OPUS_MAX_PACKET_BYTES  512

bool opusEncoderInit(int sampleRate = SAMPLE_RATE, int channels = 1);
int  opusEncode(const int16_t *pcm, int frameSize, uint8_t *output, int maxBytes);
void opusEncoderDestroy();

bool opusDecoderInit(int sampleRate = SAMPLE_RATE, int channels = 1);
int  opusDecode(const uint8_t *data, int len, int16_t *pcm, int maxSamples);
void opusDecoderDestroy();

#endif // ENABLE_OPUS

#endif
