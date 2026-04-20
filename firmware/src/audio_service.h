#ifndef INKSIGHT_AUDIO_SERVICE_H
#define INKSIGHT_AUDIO_SERVICE_H

#include <Arduino.h>
#include <freertos/FreeRTOS.h>
#include <freertos/queue.h>
#include <freertos/task.h>
#include "audio_codec.h"

#define AS_STREAM_CHUNK_MS      40
#define AS_STREAM_CHUNK_SAMPLES (CODEC_SAMPLE_RATE * AS_STREAM_CHUNK_MS / 1000)

#define AS_CAPTURE_QUEUE_DEPTH   8
#define AS_ENCODE_QUEUE_DEPTH    4
#define AS_SEND_QUEUE_DEPTH      12
#define AS_DECODE_QUEUE_DEPTH    16
#define AS_PLAYBACK_QUEUE_DEPTH  8

#define AS_INPUT_TASK_STACK   4096
#define AS_OUTPUT_TASK_STACK  6144
#define AS_CODEC_TASK_STACK   8192

#if VOICE_ONLY_BUILD
#define AS_INPUT_TASK_PRIO    8
#define AS_OUTPUT_TASK_PRIO   4
#define AS_CODEC_TASK_PRIO    5
#else
#define AS_INPUT_TASK_PRIO    5
#define AS_OUTPUT_TASK_PRIO   4
#define AS_CODEC_TASK_PRIO    3
#endif

#define AS_POWER_TIMEOUT_MS   15000

struct AsCaptureChunk {
    size_t sampleCount = 0;
    int16_t samples[AS_STREAM_CHUNK_SAMPLES];
};

struct AsEncodeTask {
    size_t sampleCount = 0;
    int16_t samples[960]; // OPUS_FRAME_SAMPLES at 16kHz/60ms
};

struct AsAudioPacket {
    uint8_t* data = nullptr;
    size_t dataLen = 0;
    int generationId = 0;
};

struct AsPlaybackChunk {
    int generationId = 0;
    size_t byteCount = 0;
    uint8_t bytes[4096];
};

class AudioService {
public:
    AudioService();
    ~AudioService();

    bool Initialize(AudioCodec* codec);
    void Start();
    void Stop();

    bool PollCaptureChunk(AsCaptureChunk*& chunk);
    void ReleaseCaptureChunk(AsCaptureChunk* chunk);
    void FlushCaptureQueue();

    void PushForEncoding(const int16_t* pcm, size_t sampleCount);

    bool PollSendPacket(AsAudioPacket*& packet);
    void ReleaseSendPacket(AsAudioPacket* packet);

    void PushForDecoding(const uint8_t* data, size_t len, int generationId = 0);
    void PushPcmForPlayback(const uint8_t* pcm, size_t len, int generationId = 0);

    void ResetPlayback();

    void SetGenerationId(int id) { active_generation_id_ = id; }
    int GetGenerationId() const { return active_generation_id_; }

    bool IsPlaybackEmpty() const;
    bool IsRunning() const { return running_; }

private:
    static void inputTaskEntry(void* arg);
    static void outputTaskEntry(void* arg);
    static void codecTaskEntry(void* arg);

    void inputTaskLoop();
    void outputTaskLoop();
    void codecTaskLoop();

    template<typename T>
    void flushPtrQueue(QueueHandle_t q);
    void flushPacketQueue(QueueHandle_t q);

    AudioCodec* codec_ = nullptr;
    volatile bool running_ = false;
    volatile int active_generation_id_ = 0;

    QueueHandle_t capture_queue_ = nullptr;
    QueueHandle_t encode_queue_ = nullptr;
    QueueHandle_t send_queue_ = nullptr;
    QueueHandle_t decode_queue_ = nullptr;
    QueueHandle_t playback_queue_ = nullptr;

    TaskHandle_t input_task_ = nullptr;
    TaskHandle_t output_task_ = nullptr;
    TaskHandle_t codec_task_ = nullptr;

    unsigned long last_output_at_ = 0;
};

#endif
