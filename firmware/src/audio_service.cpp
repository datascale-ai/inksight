#include "config.h"
#if defined(BOARD_PROFILE_ESP32_WROOM32E)

#include "audio_service.h"
#include "audio.h"
#include <new>

AudioService::AudioService() {}

AudioService::~AudioService() {
    Stop();
}

bool AudioService::Initialize(AudioCodec* codec) {
    if (codec == nullptr) return false;
    codec_ = codec;

    capture_queue_  = xQueueCreate(AS_CAPTURE_QUEUE_DEPTH,  sizeof(AsCaptureChunk*));
    encode_queue_   = xQueueCreate(AS_ENCODE_QUEUE_DEPTH,   sizeof(AsEncodeTask*));
    send_queue_     = xQueueCreate(AS_SEND_QUEUE_DEPTH,     sizeof(AsAudioPacket*));
    decode_queue_   = xQueueCreate(AS_DECODE_QUEUE_DEPTH,   sizeof(AsAudioPacket*));
    playback_queue_ = xQueueCreate(AS_PLAYBACK_QUEUE_DEPTH, sizeof(AsPlaybackChunk*));

    if (!capture_queue_ || !encode_queue_ || !send_queue_ || !decode_queue_ || !playback_queue_) {
        Serial.println("[AudioService] Queue creation failed");
        Stop();
        return false;
    }

#if ENABLE_OPUS
    if (!opusEncoderInit(CODEC_SAMPLE_RATE, 1)) {
        Serial.println("[AudioService] Opus encoder init failed");
    }
    if (!opusDecoderInit(CODEC_SAMPLE_RATE, 1)) {
        Serial.println("[AudioService] Opus decoder init failed");
    }
#endif

    Serial.println("[AudioService] Initialized");
    return true;
}

void AudioService::Start() {
    if (running_) return;
    running_ = true;
    last_output_at_ = millis();

    xTaskCreatePinnedToCore(inputTaskEntry,  "as_input",  AS_INPUT_TASK_STACK,  this, AS_INPUT_TASK_PRIO,  &input_task_,  1);
    xTaskCreatePinnedToCore(outputTaskEntry, "as_output", AS_OUTPUT_TASK_STACK, this, AS_OUTPUT_TASK_PRIO, &output_task_, 1);
    xTaskCreatePinnedToCore(codecTaskEntry,  "as_codec",  AS_CODEC_TASK_STACK,  this, AS_CODEC_TASK_PRIO,  &codec_task_,  0);

    Serial.println("[AudioService] Started (3 tasks)");
}

void AudioService::Stop() {
    running_ = false;
    vTaskDelay(pdMS_TO_TICKS(120));

    // The worker tasks self-delete in their entry wrappers. Clearing these
    // handles here avoids deleting stale task handles after they already exited.
    input_task_ = nullptr;
    output_task_ = nullptr;
    codec_task_ = nullptr;

#if ENABLE_OPUS
    opusEncoderDestroy();
    opusDecoderDestroy();
#endif

    if (capture_queue_)  { flushPtrQueue<AsCaptureChunk>(capture_queue_);  vQueueDelete(capture_queue_);  capture_queue_  = nullptr; }
    if (encode_queue_)   { flushPtrQueue<AsEncodeTask>(encode_queue_);     vQueueDelete(encode_queue_);   encode_queue_   = nullptr; }
    if (send_queue_)     { flushPacketQueue(send_queue_);                  vQueueDelete(send_queue_);     send_queue_     = nullptr; }
    if (decode_queue_)   { flushPacketQueue(decode_queue_);                vQueueDelete(decode_queue_);   decode_queue_   = nullptr; }
    if (playback_queue_) { flushPtrQueue<AsPlaybackChunk>(playback_queue_); vQueueDelete(playback_queue_); playback_queue_ = nullptr; }

    Serial.println("[AudioService] Stopped");
}

// ── Capture queue ────────────────────────────────────────────

bool AudioService::PollCaptureChunk(AsCaptureChunk*& chunk) {
    if (!capture_queue_) return false;
    return xQueueReceive(capture_queue_, &chunk, 0) == pdTRUE && chunk != nullptr;
}

void AudioService::ReleaseCaptureChunk(AsCaptureChunk* chunk) {
    delete chunk;
}

void AudioService::FlushCaptureQueue() {
    if (!capture_queue_) return;
    flushPtrQueue<AsCaptureChunk>(capture_queue_);
}

// ── Encode path ──────────────────────────────────────────────

void AudioService::PushForEncoding(const int16_t* pcm, size_t sampleCount) {
    if (!encode_queue_ || pcm == nullptr || sampleCount == 0) return;
    auto* task = new (std::nothrow) AsEncodeTask();
    if (!task) return;
    task->sampleCount = min(sampleCount, (size_t)(sizeof(task->samples) / sizeof(int16_t)));
    memcpy(task->samples, pcm, task->sampleCount * sizeof(int16_t));
    if (xQueueSend(encode_queue_, &task, pdMS_TO_TICKS(20)) != pdTRUE) {
        delete task;
    }
}

// ── Send queue ───────────────────────────────────────────────

bool AudioService::PollSendPacket(AsAudioPacket*& packet) {
    if (!send_queue_) return false;
    return xQueueReceive(send_queue_, &packet, 0) == pdTRUE && packet != nullptr;
}

void AudioService::ReleaseSendPacket(AsAudioPacket* packet) {
    if (packet) {
        free(packet->data);
        delete packet;
    }
}

// ── Decode path ──────────────────────────────────────────────

void AudioService::PushForDecoding(const uint8_t* data, size_t len, int generationId) {
    if (!decode_queue_ || data == nullptr || len == 0) return;
    auto* pkt = new (std::nothrow) AsAudioPacket();
    if (!pkt) return;
    pkt->data = (uint8_t*)malloc(len);
    if (!pkt->data) { delete pkt; return; }
    memcpy(pkt->data, data, len);
    pkt->dataLen = len;
    pkt->generationId = generationId;
    if (xQueueSend(decode_queue_, &pkt, pdMS_TO_TICKS(20)) != pdTRUE) {
        free(pkt->data);
        delete pkt;
    }
}

void AudioService::PushPcmForPlayback(const uint8_t* pcm, size_t len, int generationId) {
    if (!playback_queue_ || pcm == nullptr || len == 0) return;
    auto* pc = new (std::nothrow) AsPlaybackChunk();
    if (!pc) return;
    pc->generationId = generationId;
    pc->byteCount = min(len, sizeof(pc->bytes));
    memcpy(pc->bytes, pcm, pc->byteCount);
    if (xQueueSend(playback_queue_, &pc, pdMS_TO_TICKS(50)) != pdTRUE) {
        delete pc;
    }
}

// ── Playback control ─────────────────────────────────────────

void AudioService::ResetPlayback() {
    if (decode_queue_)   flushPacketQueue(decode_queue_);
    if (playback_queue_) flushPtrQueue<AsPlaybackChunk>(playback_queue_);
    if (codec_) codec_->FlushOutput();
}

bool AudioService::IsPlaybackEmpty() const {
    if (!playback_queue_ || !decode_queue_) return true;
    return uxQueueMessagesWaiting(playback_queue_) == 0 &&
           uxQueueMessagesWaiting(decode_queue_) == 0;
}

// ── Task entry points ────────────────────────────────────────

void AudioService::inputTaskEntry(void* arg) {
    AudioService* self = static_cast<AudioService*>(arg);
    self->inputTaskLoop();
    self->input_task_ = nullptr;
    vTaskDelete(nullptr);
}

void AudioService::outputTaskEntry(void* arg) {
    AudioService* self = static_cast<AudioService*>(arg);
    self->outputTaskLoop();
    self->output_task_ = nullptr;
    vTaskDelete(nullptr);
}

void AudioService::codecTaskEntry(void* arg) {
    AudioService* self = static_cast<AudioService*>(arg);
    self->codecTaskLoop();
    self->codec_task_ = nullptr;
    vTaskDelete(nullptr);
}

// ── InputTask: codec → capture_queue ─────────────────────────

void AudioService::inputTaskLoop() {
    Serial.println("[AudioService] InputTask started");
    while (running_) {
        if (!codec_ || !codec_->inputEnabled()) {
            vTaskDelay(pdMS_TO_TICKS(50));
            continue;
        }

        auto* chunk = new (std::nothrow) AsCaptureChunk();
        if (!chunk) {
            vTaskDelay(pdMS_TO_TICKS(10));
            continue;
        }

        int n = codec_->Read(chunk->samples, AS_STREAM_CHUNK_SAMPLES);
        if (n <= 0) {
            delete chunk;
            vTaskDelay(pdMS_TO_TICKS(5));
            continue;
        }
        chunk->sampleCount = (size_t)n;

        if (xQueueSend(capture_queue_, &chunk, pdMS_TO_TICKS(20)) != pdTRUE) {
            delete chunk;
        }
    }
    Serial.println("[AudioService] InputTask exiting");
}

// ── OutputTask: playback_queue → codec ───────────────────────

void AudioService::outputTaskLoop() {
    Serial.println("[AudioService] OutputTask started");
    while (running_) {
        AsPlaybackChunk* pc = nullptr;
        if (xQueueReceive(playback_queue_, &pc, pdMS_TO_TICKS(50)) != pdTRUE || pc == nullptr) {
            if (last_output_at_ != 0 && millis() - last_output_at_ > AS_POWER_TIMEOUT_MS) {
                if (codec_ && codec_->outputEnabled() && codec_->isDuplex()) {
                    Serial.println("[AudioService] Output idle, power down speaker");
                    codec_->EnableOutput(false);
                    last_output_at_ = 0;
                }
            }
            continue;
        }

        int genId = pc->generationId;
        if (genId != 0 && genId != active_generation_id_) {
            delete pc;
            continue;
        }

        if (codec_ && !codec_->outputEnabled()) {
            codec_->EnableOutput(true);
        }

        if (pc->byteCount > 0 && codec_) {
            size_t sampleCount = pc->byteCount / sizeof(int16_t);
            codec_->Write((const int16_t*)pc->bytes, (int)sampleCount);
        }

        last_output_at_ = millis();
        delete pc;
    }
    Serial.println("[AudioService] OutputTask exiting");
}

// ── OpusCodecTask: encode/decode ─────────────────────────────

void AudioService::codecTaskLoop() {
    Serial.println("[AudioService] CodecTask started");
    while (running_) {
        bool didWork = false;

        // --- Encode: encode_queue → send_queue ---
        AsEncodeTask* eTask = nullptr;
        if (xQueueReceive(encode_queue_, &eTask, 0) == pdTRUE && eTask != nullptr) {
            auto* pkt = new (std::nothrow) AsAudioPacket();
            if (pkt) {
#if ENABLE_OPUS
                uint8_t opusBuf[OPUS_MAX_PACKET_BYTES];
                int encoded = opusEncode(eTask->samples, (int)eTask->sampleCount, opusBuf, sizeof(opusBuf));
                if (encoded > 0) {
                    pkt->data = (uint8_t*)malloc(encoded);
                    if (pkt->data) {
                        memcpy(pkt->data, opusBuf, encoded);
                        pkt->dataLen = encoded;
                    }
                }
#else
                size_t pcmBytes = eTask->sampleCount * sizeof(int16_t);
                pkt->data = (uint8_t*)malloc(pcmBytes);
                if (pkt->data) {
                    memcpy(pkt->data, eTask->samples, pcmBytes);
                    pkt->dataLen = pcmBytes;
                }
#endif
                if (pkt->dataLen > 0) {
                    if (xQueueSend(send_queue_, &pkt, pdMS_TO_TICKS(50)) != pdTRUE) {
                        free(pkt->data);
                        delete pkt;
                    }
                } else {
                    free(pkt->data);
                    delete pkt;
                }
            }
            delete eTask;
            didWork = true;
        }

        // --- Decode: decode_queue → playback_queue ---
        AsAudioPacket* dPkt = nullptr;
        if (xQueueReceive(decode_queue_, &dPkt, 0) == pdTRUE && dPkt != nullptr) {
            int genId = dPkt->generationId;
            if (genId != 0 && genId != active_generation_id_) {
                free(dPkt->data);
                delete dPkt;
            } else {
                auto* pc = new (std::nothrow) AsPlaybackChunk();
                if (pc) {
                    pc->generationId = genId;
#if ENABLE_OPUS
                    int16_t pcmBuf[960]; // OPUS_FRAME_SAMPLES
                    int decoded = opusDecode(dPkt->data, (int)dPkt->dataLen, pcmBuf, 960);
                    if (decoded > 0) {
                        pc->byteCount = min((size_t)(decoded * sizeof(int16_t)), sizeof(pc->bytes));
                        memcpy(pc->bytes, pcmBuf, pc->byteCount);
                    }
#else
                    pc->byteCount = min(dPkt->dataLen, sizeof(pc->bytes));
                    memcpy(pc->bytes, dPkt->data, pc->byteCount);
#endif
                    if (pc->byteCount > 0) {
                        if (xQueueSend(playback_queue_, &pc, pdMS_TO_TICKS(50)) != pdTRUE) {
                            delete pc;
                        }
                    } else {
                        delete pc;
                    }
                }
                free(dPkt->data);
                delete dPkt;
            }
            didWork = true;
        }

        if (!didWork) {
            vTaskDelay(pdMS_TO_TICKS(5));
        }
    }
    Serial.println("[AudioService] CodecTask exiting");
}

// ── Queue flush helpers ──────────────────────────────────────

template<typename T>
void AudioService::flushPtrQueue(QueueHandle_t q) {
    T* item = nullptr;
    while (xQueueReceive(q, &item, 0) == pdTRUE) {
        delete item;
    }
}

void AudioService::flushPacketQueue(QueueHandle_t q) {
    AsAudioPacket* pkt = nullptr;
    while (xQueueReceive(q, &pkt, 0) == pdTRUE) {
        if (pkt) {
            free(pkt->data);
            delete pkt;
        }
    }
}

#endif // BOARD_PROFILE_ESP32_WROOM32E
