#include "config.h"
#if defined(BOARD_PROFILE_ESP32_WROOM32E)

#include "audio_codec.h"
#include "audio.h"
#include <driver/i2s.h>

#define I2S_HALF_DUPLEX_PORT I2S_NUM_0
#define I2S_MIC_PORT         I2S_NUM_1
#define I2S_SPK_PORT         I2S_NUM_0

// ── Inmp441Max98357Codec ─────────────────────────────────────

Inmp441Max98357Codec::Inmp441Max98357Codec(bool duplex) {
    duplex_ = duplex;
}

Inmp441Max98357Codec::~Inmp441Max98357Codec() {
    Stop();
}

// ── Half-duplex I2S drivers ──────────────────────────────────

static bool installHalfDuplexInputDriver() {
    i2s_config_t cfg = {
        .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
        .sample_rate = CODEC_SAMPLE_RATE,
        .bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT,
        .channel_format = I2S_CHANNEL_FMT_ONLY_RIGHT,
        .communication_format = I2S_COMM_FORMAT_STAND_I2S,
        .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
        .dma_buf_count = 4,
        .dma_buf_len = CODEC_BUFFER_SIZE,
        .use_apll = false,
        .tx_desc_auto_clear = false,
        .fixed_mclk = 0,
    };
    i2s_pin_config_t pins = {
        .bck_io_num = I2S_MIC_SCK,
        .ws_io_num = I2S_MIC_WS,
        .data_out_num = I2S_PIN_NO_CHANGE,
        .data_in_num = I2S_MIC_SD,
    };
    esp_err_t err = i2s_driver_install(I2S_HALF_DUPLEX_PORT, &cfg, 0, NULL);
    if (err != ESP_OK) {
        Serial.printf("[CODEC] Input driver install failed: %d\n", err);
        return false;
    }
    err = i2s_set_pin(I2S_HALF_DUPLEX_PORT, &pins);
    if (err != ESP_OK) {
        Serial.printf("[CODEC] Input pin config failed: %d\n", err);
        i2s_driver_uninstall(I2S_HALF_DUPLEX_PORT);
        return false;
    }
    i2s_zero_dma_buffer(I2S_HALF_DUPLEX_PORT);
    return true;
}

static bool installHalfDuplexOutputDriver() {
    i2s_config_t cfg = {
        .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX),
        .sample_rate = CODEC_SAMPLE_RATE,
        .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
        .channel_format = I2S_CHANNEL_FMT_RIGHT_LEFT,
        .communication_format = I2S_COMM_FORMAT_STAND_I2S,
        .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
        .dma_buf_count = 8,
        .dma_buf_len = CODEC_BUFFER_SIZE,
        .use_apll = false,
        .tx_desc_auto_clear = true,
        .fixed_mclk = 0,
    };
    i2s_pin_config_t pins = {
        .bck_io_num = I2S_SPK_SCK,
        .ws_io_num = I2S_SPK_WS,
        .data_out_num = I2S_SPK_DOUT,
        .data_in_num = I2S_PIN_NO_CHANGE,
    };
    esp_err_t err = i2s_driver_install(I2S_HALF_DUPLEX_PORT, &cfg, 0, NULL);
    if (err != ESP_OK) {
        Serial.printf("[CODEC] Output driver install failed: %d\n", err);
        return false;
    }
    err = i2s_set_pin(I2S_HALF_DUPLEX_PORT, &pins);
    if (err != ESP_OK) {
        i2s_driver_uninstall(I2S_HALF_DUPLEX_PORT);
        return false;
    }
    err = i2s_set_clk(I2S_HALF_DUPLEX_PORT, CODEC_SAMPLE_RATE, I2S_BITS_PER_SAMPLE_16BIT, I2S_CHANNEL_STEREO);
    if (err != ESP_OK) {
        i2s_driver_uninstall(I2S_HALF_DUPLEX_PORT);
        return false;
    }
    i2s_zero_dma_buffer(I2S_HALF_DUPLEX_PORT);
    return true;
}

// ── Full-duplex I2S drivers ──────────────────────────────────

static bool installDuplexMicDriver() {
    i2s_config_t cfg = {
        .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
        .sample_rate = CODEC_SAMPLE_RATE,
        .bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT,
        .channel_format = I2S_CHANNEL_FMT_ONLY_RIGHT,
        .communication_format = I2S_COMM_FORMAT_STAND_I2S,
        .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
        .dma_buf_count = 6,
        .dma_buf_len = 240,
        .use_apll = false,
        .tx_desc_auto_clear = false,
        .fixed_mclk = 0,
    };
    i2s_pin_config_t pins = {
        .bck_io_num = I2S_MIC_SCK,
        .ws_io_num = I2S_MIC_WS,
        .data_out_num = I2S_PIN_NO_CHANGE,
        .data_in_num = I2S_MIC_SD,
    };
    esp_err_t err = i2s_driver_install(I2S_MIC_PORT, &cfg, 0, NULL);
    if (err != ESP_OK) {
        Serial.printf("[CODEC] Duplex mic driver failed: %d\n", err);
        return false;
    }
    err = i2s_set_pin(I2S_MIC_PORT, &pins);
    if (err != ESP_OK) {
        i2s_driver_uninstall(I2S_MIC_PORT);
        return false;
    }
    i2s_zero_dma_buffer(I2S_MIC_PORT);
    return true;
}

static bool installDuplexSpkDriver() {
    i2s_config_t cfg = {
        .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX),
        .sample_rate = CODEC_SAMPLE_RATE,
        .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
        .channel_format = I2S_CHANNEL_FMT_RIGHT_LEFT,
        .communication_format = I2S_COMM_FORMAT_STAND_I2S,
        .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
        .dma_buf_count = 8,
        .dma_buf_len = 240,
        .use_apll = false,
        .tx_desc_auto_clear = true,
        .fixed_mclk = 0,
    };
    i2s_pin_config_t pins = {
        .bck_io_num = I2S_SPK_SCK,
        .ws_io_num = I2S_SPK_WS,
        .data_out_num = I2S_SPK_DOUT,
        .data_in_num = I2S_PIN_NO_CHANGE,
    };
    esp_err_t err = i2s_driver_install(I2S_SPK_PORT, &cfg, 0, NULL);
    if (err != ESP_OK) {
        Serial.printf("[CODEC] Duplex spk driver failed: %d\n", err);
        return false;
    }
    err = i2s_set_pin(I2S_SPK_PORT, &pins);
    if (err != ESP_OK) {
        i2s_driver_uninstall(I2S_SPK_PORT);
        return false;
    }
    err = i2s_set_clk(I2S_SPK_PORT, CODEC_SAMPLE_RATE, I2S_BITS_PER_SAMPLE_16BIT, I2S_CHANNEL_STEREO);
    if (err != ESP_OK) {
        i2s_driver_uninstall(I2S_SPK_PORT);
        return false;
    }
    i2s_zero_dma_buffer(I2S_SPK_PORT);
    return true;
}

// ── Codec lifecycle ──────────────────────────────────────────

bool Inmp441Max98357Codec::Start() {
    if (started_) return true;
    if (duplex_) {
        if (!installDuplexSpkDriver()) return false;
        if (!installDuplexMicDriver()) {
            i2s_driver_uninstall(I2S_SPK_PORT);
            return false;
        }
        Serial.printf("[CODEC] Full-duplex ready (MIC=I2S%d, SPK=I2S%d, SR=%d)\n",
                      I2S_MIC_PORT, I2S_SPK_PORT, CODEC_SAMPLE_RATE);
    } else {
        if (!installHalfDuplexInputDriver()) return false;
        Serial.printf("[CODEC] Half-duplex input ready (SR=%d)\n", CODEC_SAMPLE_RATE);
    }
    started_ = true;
    input_enabled_ = true;
    output_enabled_ = duplex_;
    return true;
}

void Inmp441Max98357Codec::Stop() {
    if (!started_) return;
    if (duplex_) {
        i2s_driver_uninstall(I2S_MIC_PORT);
        i2s_driver_uninstall(I2S_SPK_PORT);
    } else {
        i2s_driver_uninstall(I2S_HALF_DUPLEX_PORT);
    }
    started_ = false;
    input_enabled_ = false;
    output_enabled_ = false;
    Serial.println("[CODEC] Stopped");
}

void Inmp441Max98357Codec::EnableInput(bool enable) {
    if (!started_) return;
    input_enabled_ = enable;
}

void Inmp441Max98357Codec::EnableOutput(bool enable) {
    if (!started_) return;
    if (duplex_) {
        output_enabled_ = enable;
        if (enable) i2s_zero_dma_buffer(I2S_SPK_PORT);
    } else {
        if (enable && !output_enabled_) {
            i2s_driver_uninstall(I2S_HALF_DUPLEX_PORT);
            if (installHalfDuplexOutputDriver()) {
                output_enabled_ = true;
                input_enabled_ = false;
            }
        } else if (!enable && output_enabled_) {
            output_enabled_ = false;
        }
    }
}

// ── I/O ──────────────────────────────────────────────────────

int Inmp441Max98357Codec::Read(int16_t* dest, int maxSamples) {
    if (!input_enabled_ || dest == nullptr || maxSamples <= 0) return 0;
    i2s_port_t port = duplex_ ? I2S_MIC_PORT : I2S_HALF_DUPLEX_PORT;

    size_t bytesRead = 0;
    int toRead = (maxSamples > CODEC_BUFFER_SIZE) ? CODEC_BUFFER_SIZE : maxSamples;
    esp_err_t err = i2s_read(port, read_buf_, toRead * sizeof(int32_t), &bytesRead, portMAX_DELAY);
    if (err != ESP_OK || bytesRead == 0) return 0;

    int samplesRead = bytesRead / sizeof(int32_t);
    if (samplesRead > maxSamples) samplesRead = maxSamples;
    for (int i = 0; i < samplesRead; i++) {
        dest[i] = (int16_t)(read_buf_[i] >> 16);
    }
    return samplesRead;
}

int Inmp441Max98357Codec::Write(const int16_t* data, int samples) {
    if (!output_enabled_ || data == nullptr || samples <= 0) return 0;
    i2s_port_t port = duplex_ ? I2S_SPK_PORT : I2S_HALF_DUPLEX_PORT;

    int offset = 0;
    while (offset < samples) {
        int chunk = samples - offset;
        if (chunk > CODEC_BUFFER_SIZE) chunk = CODEC_BUFFER_SIZE;
        for (int i = 0; i < chunk; i++) {
            stereo_buf_[i * 2]     = data[offset + i];
            stereo_buf_[i * 2 + 1] = data[offset + i];
        }
        size_t written = 0;
        esp_err_t err = i2s_write(port, stereo_buf_, chunk * sizeof(int16_t) * 2, &written, portMAX_DELAY);
        if (err != ESP_OK) return offset;
        offset += chunk;
    }
    return offset;
}

void Inmp441Max98357Codec::FlushOutput() {
    if (!started_) return;
    i2s_port_t port = duplex_ ? I2S_SPK_PORT : I2S_HALF_DUPLEX_PORT;
    i2s_zero_dma_buffer(port);
}

#endif // BOARD_PROFILE_ESP32_WROOM32E
